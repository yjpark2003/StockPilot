# -*- coding: utf-8 -*-
"""FastAPI 웹 서버"""
import os
import yaml
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="주간 주식 분석 리포트")

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", "weekly")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")

# 진행률 추적
analysis_progress = {
    "is_running": False,
    "current": 0,
    "total": 0,
    "current_stock": "",
    "status": "idle",
    "message": "",
}

# 종목 추가/삭제 요청 모델
class DomesticStockRequest(BaseModel):
    code: str
    name: str
    market: str = "KOSPI"
    type: Optional[str] = None

class ForeignStockRequest(BaseModel):
    ticker: str
    name: str
    market: str = "NASDAQ"
    currency: str = "USD"
    type: Optional[str] = None


def load_stock_config():
    """종목 설정 로드"""
    stocks = {"domestic": [], "foreign": []}
    
    # 국내 종목
    domestic_path = os.path.join(CONFIG_DIR, "stocks.yaml")
    if os.path.exists(domestic_path):
        with open(domestic_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            stocks["domestic"] = config.get("stocks", [])
    
    # 해외 종목
    foreign_path = os.path.join(CONFIG_DIR, "foreign_stocks.yaml")
    if os.path.exists(foreign_path):
        with open(foreign_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            stocks["foreign"] = config.get("foreign_stocks", [])
    
    return stocks


@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 페이지 - 리포트 목록"""
    try:
        dirs = sorted(
            [d for d in os.listdir(REPORTS_DIR) if os.path.isdir(os.path.join(REPORTS_DIR, d))],
            reverse=True,
        )
    except FileNotFoundError:
        dirs = []

    # 종목 설정 로드
    stock_config = load_stock_config()
    
    # 종목 태그 생성
    domestic_tags = " ".join([f'<span class="tag">{s["name"]}</span>' for s in stock_config["domestic"]])
    foreign_tags = " ".join([f'<span class="tag">{s["name"]}</span>' for s in stock_config["foreign"]])

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>주간 주식 분석 리포트</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', -apple-system, sans-serif; background: #f5f7fa; color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        
        header {{ background: linear-gradient(135deg, #1a237e, #0d47a1); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; text-align: center; }}
        header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        header p {{ opacity: 0.8; }}

        .floating-action {{ position: fixed; top: 20px; right: 20px; z-index: 1000; display: flex; gap: 8px; }}
        .btn {{ padding: 10px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; text-decoration: none; border: none; font-weight: 600; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
        .btn-all {{ background: #43a047; color: white; }}
        .btn-all:hover {{ background: #388e3c; }}
        .btn-domestic {{ background: white; color: #1565c0; }}
        .btn-domestic:hover {{ background: #e3f2fd; }}
        .btn-foreign {{ background: white; color: #7b1fa2; }}
        .btn-foreign:hover {{ background: #f3e5f5; }}

        .info-bar {{ background: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
        .stock-section {{ margin-bottom: 15px; }}
        .stock-section:last-of-type {{ margin-bottom: 0; }}
        .stock-section h3 {{ font-size: 14px; margin-bottom: 10px; color: #1a237e; }}
        .stock-tags {{ display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }}
        .tag {{ background: #f5f7fa; padding: 4px 10px; border-radius: 15px; font-size: 12px; border: 1px solid #e0e0e0; }}

        .report-list {{ list-style: none; }}
        .report-item {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: transform 0.2s; }}
        .report-item:hover {{ transform: translateX(4px); }}
        .report-item a {{ text-decoration: none; color: #1a237e; font-size: 18px; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }}
        .report-item a:hover {{ color: #0d47a1; }}
        .report-info {{ display: flex; flex-direction: column; gap: 4px; }}
        .report-date {{ font-size: 16px; color: #1a237e; }}
        .report-label {{ font-size: 14px; color: #666; font-weight: 400; }}
        .report-item .arrow {{ font-size: 20px; color: #ccc; }}
        .no-reports {{ text-align: center; padding: 60px; color: #999; }}
    </style>
</head>
<body>
    <div class="floating-action">
        <a href="/run-analysis?market=all" class="btn btn-all">전체 분석</a>
        <a href="/run-analysis?market=domestic" class="btn btn-domestic">국내</a>
        <a href="/run-analysis?market=foreign" class="btn btn-foreign">해외</a>
        <a href="/dashboard" class="btn btn-domestic">종목 관리</a>
    </div>

    <div class="container">
        <header>
            <h1>주간 주식 분석 리포트</h1>
        </header>

        <div class="info-bar">
            <div class="stock-section">
                <h3>🇰🇷 국내 ({len(stock_config['domestic'])}종목)</h3>
                <div class="stock-tags">{domestic_tags}</div>
            </div>
            
            <div class="stock-section">
                <h3>🌍 해외 ({len(stock_config['foreign'])}종목)</h3>
                <div class="stock-tags">{foreign_tags}</div>
            </div>
        </div>

        <ul class="report-list">
    """
    if dirs:
        for d in dirs:
            # Calculate week range from date (1주일 전 ~ 리포트일)
            try:
                report_date = datetime.strptime(d, "%Y-%m-%d")
                # 7일 전 (실제 주식 데이터 기준)
                start_date = report_date - timedelta(days=7)
                period = f"{start_date.strftime('%m/%d')} - {report_date.strftime('%m/%d')}"
                year = report_date.strftime('%Y')
            except:
                period = ""
                year = ""
            
            html += f"""
            <li class="report-item">
                <a href="/reports/{d}/index.html">
                    <div class="report-info">
                        <span class="report-date">📊 {year} {period}</span>
                        <span class="report-label">주간 리포트</span>
                    </div>
                    <span class="arrow">→</span>
                </a>
            </li>"""
    else:
        html += '<div class="no-reports"><p>아직 생성된 리포트가 없습니다.</p><p>위 버튼을 눌러 분석을 실행하세요.</p></div>'

    html += f"""
        </ul>
    </div>
</body>
</html>"""
    return html


@app.get("/reports/{date}/{filename}")
async def serve_report(date: str, filename: str):
    """리포트 파일 서빙"""
    file_path = os.path.join(REPORTS_DIR, date, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")
    return HTMLResponse("<h1>404 - 리포트를 찾을 수 없습니다</h1>", status_code=404)


@app.get("/api/progress")
async def get_progress():
    """분석 진행률 API"""
    return analysis_progress


@app.get("/api/progress/stream")
async def stream_progress():
    """SSE를 통한 실시간 진행률 스트림"""
    import json
    
    async def event_generator():
        last_status = None
        while True:
            # 현재 진행률 전송
            data = json.dumps(analysis_progress, ensure_ascii=False)
            yield f"data: {data}\n\n"
            
            # 완료 또는 오류 시 종료
            if analysis_progress["status"] in ("completed", "error"):
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/run-analysis")
async def run_analysis_endpoint(
    market: str = Query("all", regex="^(all|domestic|foreign)$"),
    with_dart: bool = Query(False)
):
    """수동 분석 실행 (진행률 표시 페이지)"""
    from scripts.run_analysis import run_analysis, load_config
    
    # 진행률 초기화
    analysis_progress["is_running"] = True
    analysis_progress["status"] = "running"
    analysis_progress["current"] = 0
    analysis_progress["message"] = "분석 준비 중..."
    
    # 종목 수 계산
    total_stocks = 0
    if market in ("all", "domestic"):
        config = load_config("domestic")
        total_stocks += len(config.get("stocks", []))
    if market in ("all", "foreign"):
        config = load_config("foreign")
        total_stocks += len(config.get("foreign_stocks", []))
    
    analysis_progress["total"] = total_stocks
    
    # 백그라운드 분석 함수
    async def run_background():
        try:
            async def progress_callback(current, total, stock_name, status):
                analysis_progress["current"] = current
                analysis_progress["total"] = total
                analysis_progress["current_stock"] = stock_name
                analysis_progress["message"] = status
            
            # 분석 실행 (진행률 콜백 전달)
            await run_analysis(market, with_dart, progress_callback)
            analysis_progress["status"] = "completed"
            analysis_progress["message"] = "분석 완료!"
            analysis_progress["current"] = analysis_progress["total"]
            analysis_progress["current_stock"] = ""
        except Exception as e:
            analysis_progress["status"] = "error"
            analysis_progress["message"] = f"오류: {str(e)}"
        finally:
            analysis_progress["is_running"] = False
    
    # 백그라운드에서 분석 실행
    asyncio.create_task(run_background())
    
    market_label = {"all": "전체", "domestic": "국내", "foreign": "해외"}[market]
    dart_text = " (DART 포함)" if with_dart else ""
    
    # 진행률 표시 페이지 반환
    progress_page = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>분석 진행 중...</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f5f7fa; padding: 50px; text-align: center; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
        h1 { color: #1a237e; margin-bottom: 20px; }
        .progress-bar { width: 100%; height: 30px; background: #e0e0e0; border-radius: 15px; overflow: hidden; margin: 20px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #1a237e, #0d47a1); transition: width 0.3s; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; }
        .status { margin: 20px 0; color: #666; }
        .stock-name { font-size: 24px; color: #1a237e; font-weight: 600; margin: 10px 0; }
        .complete { display: none; }
        .btn { display: inline-block; padding: 12px 24px; background: #1a237e; color: white; text-decoration: none; border-radius: 8px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MARKET_LABEL 종목 분석DART_TEXT</h1>
        <div class="stock-name" id="stock-name">준비 중...</div>
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill" style="width: 0%">0%</div>
        </div>
        <div class="status" id="status">분석을 시작합니다...</div>
        
        <div class="complete" id="complete">
            <p style="font-size: 18px; color: #43a047;">분석 완료!</p>
            <a href="/" class="btn">메인으로 돌아가기</a>
        </div>
    </div>
    
    <script>
        let completed = false;
        let eventSource;
        
        function updateProgress(data) {
            if (completed) return;
            
            const percent = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
            document.getElementById('progress-fill').style.width = percent + '%';
            document.getElementById('progress-fill').textContent = percent + '%';
            
            if (data.current_stock) {
                document.getElementById('stock-name').textContent = data.current_stock;
            }
            
            document.getElementById('status').textContent = data.message || '분석 중...';
            
            if (data.status === 'completed' || data.status === 'error') {
                completed = true;
                if (eventSource) eventSource.close();
                if (data.status === 'completed') {
                    document.getElementById('complete').style.display = 'block';
                    document.getElementById('stock-name').textContent = '분석 완료!';
                    document.getElementById('progress-fill').style.width = '100%';
                    document.getElementById('progress-fill').textContent = '100%';
                } else {
                    document.getElementById('status').textContent = '오류: ' + data.message;
                    document.getElementById('status').style.color = '#e53935';
                }
            }
        }
        
        // SSE 연결 시도
        function connectSSE() {
            eventSource = new EventSource('/api/progress/stream');
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    updateProgress(data);
                } catch (e) {
                    console.log('SSE 파싱 오류:', e);
                }
            };
            
            eventSource.onerror = function() {
                console.log('SSE 연결 오류, 폴링으로 전환...');
                eventSource.close();
                if (!completed) {
                    startPolling();
                }
            };
        }
        
        // 폴링 폴백
        function startPolling() {
            const pollInterval = setInterval(async () => {
                if (completed) {
                    clearInterval(pollInterval);
                    return;
                }
                try {
                    const response = await fetch('/api/progress');
                    const data = await response.json();
                    updateProgress(data);
                } catch (e) {
                    console.log('폴링 오류:', e);
                }
            }, 1000);
        }
        
        // SSE 시작
        connectSSE();
        
        // 초기 데이터 즉시 로드
        fetch('/api/progress')
            .then(res => res.json())
            .then(data => updateProgress(data))
            .catch(e => console.log('초기 로드 오류:', e));
        
        // 3초 후 SSE가 아직 연결 안 되면 폴링 시작
        setTimeout(() => {
            if (!completed && (!eventSource || eventSource.readyState !== EventSource.OPEN)) {
                console.log('SSE 연결 실패, 폴링 시작');
                if (eventSource) eventSource.close();
                startPolling();
            }
        }, 3000);
    </script>
</body>
</html>"""
    
    progress_page = progress_page.replace("MARKET_LABEL", market_label).replace("DART_TEXT", dart_text)
    
    return HTMLResponse(progress_page)


@app.get("/api/run")
async def api_run_analysis(with_dart: bool = Query(False)):
    """API: 전체 분석 실행"""
    from scripts.run_analysis import run_analysis
    try:
        await run_analysis("all", with_dart)
        return {"status": "success", "message": "분석 완료"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========== 종목 관리 API ==========

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """종목 관리 대시보드"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from dashboard import DASHBOARD_HTML
    return DASHBOARD_HTML


@app.get("/api/stocks")
async def get_stocks():
    """전체 종목 목록 조회"""
    return load_stock_config()


@app.get("/api/stocks/domestic")
async def get_domestic_stocks():
    """국내 종목 목록 조회"""
    config = load_stock_config()
    return {"stocks": config["domestic"]}


@app.post("/api/stocks/domestic")
async def add_domestic_stock(stock: DomesticStockRequest):
    """국내 종목 추가"""
    domestic_path = os.path.join(CONFIG_DIR, "stocks.yaml")
    if os.path.exists(domestic_path):
        with open(domestic_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
    
    stocks = config.get("stocks", [])
    for s in stocks:
        if s.get("code") == stock.code:
            raise HTTPException(status_code=400, detail="이미 존재하는 종목입니다.")
    
    new_stock = {"code": stock.code, "name": stock.name, "market": stock.market}
    if stock.type:
        new_stock["type"] = stock.type
    stocks.append(new_stock)
    config["stocks"] = stocks
    
    with open(domestic_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    return {"status": "success", "message": f"{stock.name} 종목이 추가되었습니다.", "stocks": stocks}


@app.delete("/api/stocks/domestic/{code}")
async def delete_domestic_stock(code: str):
    """국내 종목 삭제"""
    domestic_path = os.path.join(CONFIG_DIR, "stocks.yaml")
    if not os.path.exists(domestic_path):
        raise HTTPException(status_code=404, detail="설정 파일을 찾을 수 없습니다.")
    
    with open(domestic_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    
    stocks = config.get("stocks", [])
    new_stocks = [s for s in stocks if s.get("code") != code]
    
    if len(new_stocks) == len(stocks):
        raise HTTPException(status_code=404, detail="해당 종목을 찾을 수 없습니다.")
    
    config["stocks"] = new_stocks
    with open(domestic_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    return {"status": "success", "message": "종목이 삭제되었습니다.", "stocks": new_stocks}


@app.get("/api/stocks/foreign")
async def get_foreign_stocks():
    """해외 종목 목록 조회"""
    config = load_stock_config()
    return {"stocks": config["foreign"]}


@app.post("/api/stocks/foreign")
async def add_foreign_stock(stock: ForeignStockRequest):
    """해외 종목 추가"""
    foreign_path = os.path.join(CONFIG_DIR, "foreign_stocks.yaml")
    if os.path.exists(foreign_path):
        with open(foreign_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
    
    stocks = config.get("foreign_stocks", [])
    for s in stocks:
        if s.get("ticker") == stock.ticker:
            raise HTTPException(status_code=400, detail="이미 존재하는 종목입니다.")
    
    new_stock = {"ticker": stock.ticker, "name": stock.name, "market": stock.market, "currency": stock.currency}
    if stock.type:
        new_stock["type"] = stock.type
    stocks.append(new_stock)
    config["foreign_stocks"] = stocks
    
    with open(foreign_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    return {"status": "success", "message": f"{stock.name} 종목이 추가되었습니다.", "stocks": stocks}


@app.delete("/api/stocks/foreign/{ticker}")
async def delete_foreign_stock(ticker: str):
    """해외 종목 삭제"""
    foreign_path = os.path.join(CONFIG_DIR, "foreign_stocks.yaml")
    if not os.path.exists(foreign_path):
        raise HTTPException(status_code=404, detail="설정 파일을 찾을 수 없습니다.")
    
    with open(foreign_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    
    stocks = config.get("foreign_stocks", [])
    new_stocks = [s for s in stocks if s.get("ticker") != ticker]
    
    if len(new_stocks) == len(stocks):
        raise HTTPException(status_code=404, detail="해당 종목을 찾을 수 없습니다.")
    
    config["foreign_stocks"] = new_stocks
    with open(foreign_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    return {"status": "success", "message": "종목이 삭제되었습니다.", "stocks": new_stocks}


@app.get("/api/stocks/search")
async def search_stocks(q: str = Query(..., min_length=1), market: str = Query("all")):
    """종목 검색 (yfinance 사용 + 한글명 검색)"""
    results = []
    q_upper = q.upper()
    q_lower = q.lower()
    
    # 현재 등록된 종목에서 한글명/종목코드 검색
    if market in ("all", "domestic"):
        domestic_path = os.path.join(CONFIG_DIR, "stocks.yaml")
        if os.path.exists(domestic_path):
            with open(domestic_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            for s in config.get("stocks", []):
                name = s.get("name", "")
                code = s.get("code", "")
                if q in name or q_upper == code or q_lower == code.lower():
                    results.append({
                        "type": "domestic",
                        "code": code,
                        "name": name,
                        "market": s.get("market", "KOSPI"),
                        "currency": "KRW"
                    })
    
    if market in ("all", "foreign"):
        foreign_path = os.path.join(CONFIG_DIR, "foreign_stocks.yaml")
        if os.path.exists(foreign_path):
            with open(foreign_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            for s in config.get("foreign_stocks", []):
                name = s.get("name", "")
                ticker = s.get("ticker", "")
                if q in name or q_upper == ticker.upper():
                    results.append({
                        "type": "foreign",
                        "ticker": ticker,
                        "name": name,
                        "market": s.get("market", "NASDAQ"),
                        "currency": s.get("currency", "USD")
                    })
    
    # 등록된 종목에 없으면 한글 종목명 매핑에서 검색
    if not results:
        KOREAN_STOCK_MAP = {
            "sk텔레콤": "017670", "sk하이닉스": "000660", "sk": "000660",
            "네이버": "035420", "카카오": "035720", "쿠팡": "CPNG",
            "현대차": "005380", "기아": "000270", "포스코": "005490",
            "lg화학": "051910", "lg에너지솔루션": "373220", "lg전자": "066570",
            "삼성바이오로직스": "207940", "삼성sdi": "006400", "삼성물산": "028260",
            "셀트리온": "068270", "신한지주": "055550", "kb금융": "105560",
            "하나금융지주": "086790", "우리금융지주": "316140", "메리츠금융지주": "138930",
            "한국전력": "015760", "gs": "078930", "현대건설": "000720",
            "대우건설": "047040", "삼성생명": "032830", "한화솔루션": "009830",
            "두산에너빌리티": "034020", "hd현대": "011200", "한미반도체": "420770",
            "래미안": "078000", "카카오뱅크": "323410", "토스코리아": "444530",
            "카카오페이": "373000", "배달의민족": "WOORA", "무신사": "MUSINSA",
        }
        q_lower = q.lower()
        if market in ("all", "domestic") and q_lower in KOREAN_STOCK_MAP:
            code = KOREAN_STOCK_MAP[q_lower]
            if code.isdigit():
                ticker = f"{code}.KS"
            else:
                ticker = code
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                info = stock.info
                if info and info.get("shortName"):
                    results.append({
                        "type": "domestic",
                        "code": code,
                        "name": info.get("shortName", ""),
                        "market": "KOSPI",
                        "currency": "KRW"
                    })
            except Exception:
                pass

    # 이미 결과가 있으면 반환
    if results:
        return {"results": results[:10]}

    # 등록된 종목에 없으면 yfinance로 검색
    try:
        import yfinance as yf
        if market in ("all", "domestic") and q.isdigit():
            ticker = f"{q}.KS"
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                if info and info.get("shortName"):
                    results.append({"type": "domestic", "code": q, "name": info.get("shortName", ""), "market": "KOSPI", "currency": "KRW"})
            except Exception:
                pass
        
        if market in ("all", "foreign") and not q.isdigit():
            ticker = q.upper()
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                if info and info.get("shortName"):
                    exchange = info.get("exchange", "")
                    market_type = "NASDAQ" if "NMS" in exchange or "NSD" in exchange else "NYSE" if "NYQ" in exchange else exchange
                    results.append({"type": "foreign", "ticker": ticker, "name": info.get("shortName", ""), "market": market_type, "currency": "USD"})
            except Exception:
                pass
            
            if len(results) == 0:
                company_map = {"apple": "AAPL", "amazon": "AMZN", "nvidia": "NVDA", "google": "GOOGL", "alphabet": "GOOGL", "microsoft": "MSFT", "meta": "META", "tesla": "TSLA", "netflix": "NFLX"}
                lower_q = q.lower()
                if lower_q in company_map:
                    ticker = company_map[lower_q]
                    try:
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        if info and info.get("shortName"):
                            results.append({"type": "foreign", "ticker": ticker, "name": info.get("shortName", ""), "market": "NASDAQ", "currency": "USD"})
                    except Exception:
                        pass
        
        return {"results": results[:10]}
    except ImportError:
        return {"results": results}
    except Exception as e:
        return {"results": results}


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """서버 시작"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
