# -*- coding: utf-8 -*-
"""FastAPI 웹 서버"""
import os
import yaml
import asyncio
from datetime import date
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="주간 주식 분석 리포트")

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", "weekly")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class CacheStaticFiles(StaticFiles):
    """정적 자산에 짧은 캐시 + 재검증 헤더 부여 (테마/차트 라이브러리 재방문 로드 절감)"""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=86400, must-revalidate"
        return response


app.mount("/static", CacheStaticFiles(directory=STATIC_DIR), name="static")


def get_config_path(filename: str) -> str:
    """설정 파일 경로 반환 (로컬 > 기본 순서)"""
    local_path = os.path.join(CONFIG_DIR, "local", filename)
    if os.path.exists(local_path):
        return local_path
    return os.path.join(CONFIG_DIR, filename)


def html_escape(value) -> str:
    """HTML 특수문자 이스케이프 (XSS 방지)"""
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

# 해외 주요 종목 한글명 별칭 (한글 검색 지원)
FOREIGN_ALIASES = {
    "애플": "AAPL", "아이폰": "AAPL",
    "마이크로소프트": "MSFT", "ms": "MSFT",
    "알파벳": "GOOGL", "구글": "GOOGL", "google": "GOOGL",
    "아마존": "AMZN", "앤드로이드": "AMZN",
    "테슬라": "TSLA", "엔비디아": "NVDA", "인텔": "INTC", "amd": "AMD",
    "브로드컴": "AVGO", "tsmc": "TSM", "타이완반도체": "TSM",
    "메타": "META", "페이스북": "META", "넷플릭스": "NFLX",
    "보잉": "BA", "디즈니": "DIS", "월트디즈니": "DIS",
    "코카콜라": "KO", "존스앤존슨": "JNJ", "시모스": "SCHD",
}

# 진행률 추적
analysis_progress = {
    "is_running": False,
    "current": 0,
    "total": 0,
    "current_stock": "",
    "status": "idle",
    "message": "",
    "period": None,
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
    """종목 설정 로드 (로컬 > 기본 순서로 적용)"""
    stocks = {"domestic": [], "foreign": []}
    
    # 국내 종목
    domestic_path = get_config_path("stocks.yaml")
    if os.path.exists(domestic_path):
        with open(domestic_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            stocks["domestic"] = config.get("stocks", [])
    
    # 해외 종목
    foreign_path = get_config_path("foreign_stocks.yaml")
    if os.path.exists(foreign_path):
        with open(foreign_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            stocks["foreign"] = config.get("foreign_stocks", [])
    
    return stocks


def run_panel_options(today: date) -> dict:
    """분석 구간 지정 패널의 연/월/주차 옵션과 기본 선택값

    기본 선택은 '오늘이 포함되는 주차'다. 2026-09-01처럼 月초면 9월 1주차가
    선택되고(ISO 36주차 = 08/31~09/06), 8월 31일처럼 월 경계에 걸친 날짜는
    그 날짜를 실제로 포함하는 9월 1주차로 넘어간다.
    """
    from analyzers.period import MAX_MONTH_WEEK, month_week_for_day

    cur_year, cur_month, cur_week = month_week_for_day(today)

    years = sorted({cur_year - 2, cur_year - 1, cur_year, cur_year + 1}, reverse=True)
    year_options = "".join(
        f'<option value="{y}"{" selected" if y == cur_year else ""}>{y}년</option>' for y in years
    )
    month_options = "".join(
        f'<option value="{m}"{" selected" if m == cur_month else ""}>{m}월</option>'
        for m in range(1, 13)
    )
    week_options = "".join(
        f'<option value="{w}"{" selected" if w == cur_week else ""}>{w}주차</option>'
        for w in range(1, MAX_MONTH_WEEK + 1)
    )
    return {
        "year_options": year_options,
        "month_options": month_options,
        "week_options": week_options,
    }


@app.get("/", response_class=HTMLResponse)
async def root(y: Optional[str] = None, m: Optional[str] = None):
    """메인 페이지 - 연도/주차 캘린더 형태의 주간 리포트 목록"""
    from server.report_calendar import (
        CALENDAR_CSS,
        render_calendar,
        render_week_list,
        render_year_options,
        resolve_view,
        scan_reports,
    )
    from server.theme import THEME_INIT_SCRIPT, THEME_TOGGLE_BTN, THEME_TOGGLE_SCRIPT

    today = date.today()
    entries = scan_reports(REPORTS_DIR)
    view_year, view_month = resolve_view(entries, y, m, today)

    # 종목 설정 로드
    stock_config = load_stock_config()
    
    # 종목 태그 생성
    domestic_tags = " ".join([f'<span class="tag">{html_escape(s.get("name", ""))}</span>' for s in stock_config["domestic"]])
    foreign_tags = " ".join([f'<span class="tag">{html_escape(s.get("name", ""))}</span>' for s in stock_config["foreign"]])

    calendar_html = render_calendar(entries, view_year, view_month, today)
    year_options = render_year_options(entries, view_year, today)
    week_list_html = render_week_list(entries)
    total_reports = len(entries)
    panel = run_panel_options(today)
    empty_hint = (
        ""
        if entries
        else '<div class="no-reports"><p>아직 생성된 리포트가 없습니다.</p>'
             "<p>위 버튼을 눌러 분석을 실행하세요.</p></div>"
    )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>주간 주식 분석 리포트</title>
    <link rel="stylesheet" href="/static/theme.css">
    {THEME_INIT_SCRIPT}
    <style>
        .container {{ max-width: 960px; }}
        .stock-section {{ margin-bottom: 15px; }}
        .stock-section:last-of-type {{ margin-bottom: 0; }}
        .stock-section h3 {{ font-size: 14px; margin-bottom: 10px; color: var(--primary); }}
        .stock-tags {{ display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }}
        .tag {{ background: var(--surface-subtle); padding: 4px 10px; border-radius: 15px; font-size: 12px; border: 1px solid var(--border); color: var(--text); }}
        .cal-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 24px 0 12px; }}
        .cal-head h2 {{ font-size: 18px; color: var(--text); margin: 0; }}
        .cal-head .cal-meta {{ font-size: 13px; color: var(--text-secondary); }}
        .no-reports {{ text-align: center; padding: 60px; color: var(--text-faint); }}

        /* 분석 구간 지정 패널 */
        .run-panel {{ margin: 0 0 22px; padding: 16px 18px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; }}
        .run-panel h2 {{ font-size: 16px; margin: 0 0 4px; color: var(--text); }}
        .run-panel .hint {{ font-size: 12.5px; color: var(--text-secondary); margin: 0 0 12px; }}
        .run-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)); gap: 10px; align-items: end; }}
        .run-field {{ display: flex; flex-direction: column; gap: 4px; }}
        .run-field label {{ font-size: 12px; color: var(--text-secondary); font-weight: 600; }}
        .run-field select, .run-field input {{ font: inherit; font-size: 14px; padding: 7px 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-subtle); color: var(--text); min-width: 0; }}
        .run-field select:focus, .run-field input:focus {{ outline: 2px solid var(--primary); outline-offset: 1px; }}
        .run-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }}
        .run-actions .btn {{ padding: 8px 14px; font-size: 14px; }}
        .run-preview {{ flex: 1 1 240px; min-width: 0; font-size: 13px; color: var(--text-secondary); }}
        .run-preview strong {{ color: var(--text); }}
        .run-preview.is-custom {{ color: var(--text); }}
        .run-preview .pv-badge {{ display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 7px; margin-right: 6px; border-radius: 999px; background: rgba(158, 158, 158, .18); color: #5f6368; vertical-align: middle; }}
        .run-preview.is-custom .pv-badge {{ background: rgba(25, 118, 210, .14); color: #1565c0; }}
        [data-theme="dark"] .run-preview .pv-badge {{ background: rgba(174, 174, 174, .18); color: #bdbdbd; }}
        [data-theme="dark"] .run-preview.is-custom .pv-badge {{ background: rgba(66, 165, 245, .18); color: #90caf9; }}
        .run-panel details {{ margin-top: 12px; }}
        .run-panel summary {{ font-size: 13px; color: var(--text-secondary); cursor: pointer; }}
        {CALENDAR_CSS}
    </style>
</head>
<body>
    <div class="floating-action">
        <a href="/run-analysis?market=all" class="btn btn-green">전체 분석</a>
        <a href="/run-analysis?market=domestic" class="btn btn-blue">국내</a>
        <a href="/run-analysis?market=foreign" class="btn btn-purple">해외</a>
        <a href="/dashboard" class="btn btn-blue">종목 관리</a>
    </div>
    {THEME_TOGGLE_BTN}

    <div class="container">
        <header class="brand">
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

        <div class="run-panel">
            <h2>🎯 분석 구간 지정</h2>
            <p class="hint">
                주가는 지정한 구간으로 정확히 조회합니다. 뉴스는 발행일이 구간 안인 기사만 담고,
                재무·공매도는 구간과 무관한 <strong>수집 시점 현재값</strong>입니다.
            </p>
            <div class="run-grid">
                <div class="run-field">
                    <label for="run-year">연도</label>
                    <select id="run-year">{panel['year_options']}</select>
                </div>
                <div class="run-field">
                    <label for="run-month">월</label>
                    <select id="run-month">{panel['month_options']}</select>
                </div>
                <div class="run-field">
                    <label for="run-week">주차</label>
                    <select id="run-week">{panel['week_options']}</select>
                </div>
                <div class="run-field">
                    <label for="run-market">시장</label>
                    <select id="run-market">
                        <option value="all">전체</option>
                        <option value="domestic">국내만</option>
                        <option value="foreign">해외만</option>
                    </select>
                </div>
            </div>
            <details id="run-custom">
                <summary>직접 날짜로 지정 (시작일 ~ 종료일)</summary>
                <div class="run-grid" style="margin-top:10px;">
                    <div class="run-field">
                        <label for="run-start">시작일</label>
                        <input type="date" id="run-start">
                    </div>
                    <div class="run-field">
                        <label for="run-end">종료일</label>
                        <input type="date" id="run-end">
                    </div>
                </div>
            </details>
            <div class="run-actions">
                <button type="button" class="btn btn-green" id="run-go">이 구간 분석 실행</button>
                <a href="/run-analysis?market=all" class="btn btn-secondary" id="run-default">기본 구간으로 실행</a>
                <span class="run-preview" id="run-preview" aria-live="polite">구간을 선택하세요.</span>
            </div>
        </div>

        <div class="cal-head">
            <h2>📅 주간 리포트 캘린더</h2>
            <div class="cal-meta">
                <select class="year-picker" onchange="location.href='/?y={{this.value}}&m={view_month}'" aria-label="연도 선택">
                    {year_options}
                </select>
                <span>총 {total_reports}건</span>
            </div>
        </div>

        <div class="cal-wrap">
            {calendar_html}
            <p class="cal-legend">
                <span class="swatch"></span>해당 주차 분석 리포트 있음 (좌측은 ISO 주차, 오른쪽 배지는 해당 주차 번호)
            </p>
        </div>

        {empty_hint}
        {week_list_html}
    </div>
    {THEME_TOGGLE_SCRIPT}
    <script>
    (function () {{
        var elYear = document.getElementById('run-year');
        var elMonth = document.getElementById('run-month');
        var elWeek = document.getElementById('run-week');
        var elStart = document.getElementById('run-start');
        var elEnd = document.getElementById('run-end');
        var elMarket = document.getElementById('run-market');
        var elGo = document.getElementById('run-go');
        var elDefault = document.getElementById('run-default');
        var elPreview = document.getElementById('run-preview');
        if (!elYear || !elGo) return;

        // 날짜 입력이 비어 있으면 연/월/주차, 채워져 있으면 날짜 범위를 쓴다
        function params() {{
            var q = ['market=' + encodeURIComponent(elMarket.value)];
            if (elStart.value || elEnd.value) {{
                if (elStart.value) q.push('start=' + elStart.value);
                if (elEnd.value) q.push('end=' + elEnd.value);
            }} else {{
                q.push('year=' + elYear.value);
                q.push('month=' + elMonth.value);
                q.push('week=' + elWeek.value);
            }}
            return q.join('&');
        }}

        function render(data) {{
            if (!data) return;
            elPreview.className = 'run-preview' + (data.is_custom ? ' is-custom' : '');
            // 휴장일이 시장마다 달라 거래일 개수가 다를 수 있다(추석 등).
            // 선택한 시장의 거래일을 보여주되, 두 시장이 다르면 둘 다 알린다.
            var label;
            if (data.markets_differ && elMarket.value === 'all') {{
                label = '국내 ' + data.trading_label_domestic +
                        ' · 해외 ' + data.trading_label_foreign;
            }} else if (elMarket.value === 'domestic') {{
                label = data.trading_label_domestic;
            }} else if (elMarket.value === 'foreign') {{
                label = data.trading_label_foreign;
            }} else {{
                label = data.trading_label;
            }}
            elPreview.innerHTML = '<span class="pv-badge">' +
                (data.is_custom ? '지정 구간' : '기본 구간') + '</span><strong>' +
                data.year_week_label + '</strong> · ' + data.range_label + ' · ' + label;
        }}

        function fail(text) {{
            elPreview.className = 'run-preview';
            elPreview.textContent = text;
        }}

        function refresh() {{
            fail('구간 확인 중...');
            fetch('/api/period/preview?' + params())
                .then(function (r) {{ return r.ok ? r.json() : r.json().then(function (e) {{ throw e; }}); }})
                .then(render)
                .catch(function (e) {{
                    fail((e && e.detail) ? e.detail : '구간을 읽을 수 없습니다.');
                }});
        }}

        [elYear, elMonth, elWeek, elStart, elEnd].forEach(function (el) {{
            el.addEventListener('change', refresh);
        }});
        elMarket.addEventListener('change', function () {{
            elDefault.href = '/run-analysis?market=' + encodeURIComponent(elMarket.value);
            refresh();
        }});

        elGo.addEventListener('click', function () {{
            location.href = '/run-analysis?' + params();
        }});
        elDefault.addEventListener('click', function (e) {{
            e.preventDefault();
            location.href = '/run-analysis?market=' + encodeURIComponent(elMarket.value);
        }});

        refresh();
    }})();
    </script>
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


def resolve_request_period(
    start: Optional[str] = None,
    end: Optional[str] = None,
    iso_year: Optional[str] = None,
    iso_week: Optional[str] = None,
    year: Optional[str] = None,
    month: Optional[str] = None,
    week: Optional[str] = None,
    market: str = "all",
):
    """HTTP 쿼리 파라미터 -> WeeklyPeriod (없으면 None)

    잘못된 지정이면 사용자에게 400 과 함께 한국어 오류 메시지를 돌려준다.
    `market` 는 구간의 기준 시장이며, 두 시장을 함께 보면 마감 시각이 늦은
    해외 장을 기준으로 구간을 자른다.
    """
    from analyzers.period import PeriodError, period_from_values
    from analyzers.market_calendar import MARKET_KR, MARKET_US

    period_market = MARKET_KR if market == "domestic" else MARKET_US
    try:
        return period_from_values(
            start=start, end=end, iso_year=iso_year, iso_week=iso_week,
            year=year, month=month, week=week, market=period_market,
        )
    except PeriodError as e:
        raise HTTPException(status_code=400, detail=f"분석 구간을 읽을 수 없습니다: {e}")


@app.get("/run-analysis")
async def run_analysis_endpoint(
    market: str = Query("all", regex="^(all|domestic|foreign)$"),
    with_dart: bool = Query(False),
    start: Optional[str] = None,
    end: Optional[str] = None,
    iso_year: Optional[str] = None,
    iso_week: Optional[str] = None,
    year: Optional[str] = None,
    month: Optional[str] = None,
    week: Optional[str] = None,
):
    """수동 분석 실행 (진행률 표시 페이지)"""
    from scripts.run_analysis import run_analysis, load_config

    period = resolve_request_period(
        start=start, end=end, iso_year=iso_year, iso_week=iso_week,
        year=year, month=month, week=week, market=market,
    )

    # 이미 실행 중이면 새로 시작하지 않고 진행 상황 페이지 재사용.
    # 이때 period=None 을 넘기면 페이지가 '기본 구간'을 계산해 사용자가
    # 지정한 구간과 다른 날짜를 보여준다(예: 39주차 링크 -> 09/17~09/23).
    # 요청한 구간을 그대로 넘겨 링크와 화면이 일치하게 한다.
    if analysis_progress["is_running"]:
        return HTMLResponse(_progress_page(market, False, period))

    # 진행률 초기화
    analysis_progress["is_running"] = True
    analysis_progress["status"] = "running"
    analysis_progress["current"] = 0
    analysis_progress["current_stock"] = ""
    analysis_progress["message"] = "분석 준비 중..."
    analysis_progress["period"] = period.to_dict() if period else None

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

            # 분석 실행 (진행률 콜백 + 구간 전달)
            await run_analysis(market, with_dart, progress_callback, period=period)
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

    # 진행률 표시 페이지 반환
    return HTMLResponse(_progress_page(market, with_dart, period))


def _split_trading_html(period) -> str:
    """거래일 표기. 휴장일 차이로 국내/해외가 다르면 둘 다 보여준다."""
    if period.markets_differ:
        from analyzers.market_calendar import MARKET_KR, MARKET_US
        return (f'국내 {html_escape(period.trading_label_for(MARKET_KR))} · '
                f'해외 {html_escape(period.trading_label_for(MARKET_US))}')
    return html_escape(period.trading_label)


def _progress_page(market: str, with_dart: bool, period=None) -> str:
    """분석 진행률 표시 페이지 생성"""
    market_label = {"all": "전체", "domestic": "국내", "foreign": "해외"}[market]
    dart_text = " (DART 포함)" if with_dart else ""
    if period is not None:
        period_html = (
            '<div class="run-period">'
            f'<span class="run-period-badge">지정 구간</span>'
            f'<strong>{html_escape(period.year_week_label)}</strong> · '
            f'{html_escape(period.range_label)} · ' + _split_trading_html(period)
            + "</div>"
        )
    else:
        from analyzers.period import resolve_period as _rp
        from analyzers.market_calendar import MARKET_KR, MARKET_US
        _default = _rp(market=MARKET_KR if market == "domestic" else MARKET_US)
        period_html = (
            '<div class="run-period">'
            '<span class="run-period-badge run-period-default">기본 구간</span>'
            f'<strong>{html_escape(_default.year_week_label)}</strong> · '
            f'{html_escape(_default.range_label)} · '
            + _split_trading_html(_default)
            + "</div>"
        )
    progress_page = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>분석 진행 중...</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/static/theme.css">
    <script>
    (function () {
        var stored = null;
        try { stored = localStorage.getItem('stockpilot-theme'); } catch (e) {}
        var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', stored === 'dark' || stored === 'light' ? stored : (prefersDark ? 'dark' : 'light'));
    })();
    </script>
    <style>
        body { padding: 50px; text-align: center; }
        .container { max-width: 600px; margin: 0 auto; background: var(--surface); padding: 40px; border-radius: 12px; box-shadow: var(--shadow-md); }
        h1 { color: var(--primary); margin-bottom: 20px; }
        .stock-name { font-size: 24px; color: var(--primary); font-weight: 600; margin: 10px 0; }
        .run-period { margin: 0 auto 18px; padding: 10px 14px; max-width: 460px; font-size: 14px; color: var(--text-secondary); background: var(--surface-subtle); border: 1px solid var(--border); border-radius: 8px; }
        .run-period strong { color: var(--text); }
        .run-period-badge { display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 8px; margin-right: 8px; border-radius: 999px; background: rgba(25, 118, 210, .14); color: #1565c0; vertical-align: middle; }
        .run-period-default { background: rgba(158, 158, 158, .18); color: #5f6368; }
        [data-theme="dark"] .run-period-badge { background: rgba(66, 165, 245, .18); color: #90caf9; }
        [data-theme="dark"] .run-period-default { background: rgba(174, 174, 174, .18); color: #bdbdbd; }
        .progress-bar { width: 100%; height: 30px; background: #e0e0e0; border-radius: 15px; overflow: hidden; margin: 20px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #1a237e, #0d47a1); transition: width 0.5s cubic-bezier(0.16, 1, 0.3, 1); display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 600; min-width: 0; }
        .status { margin: 20px 0; color: var(--text-secondary); display: flex; align-items: center; justify-content: center; gap: 8px; }
        .status-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--primary); animation: sp-pulse 1.6s ease-in-out infinite; }
        .complete { display: none; }
    </style>
</head>
<body>
    <button type="button" class="theme-toggle" id="theme-toggle" aria-label="테마 전환">🌓</button>
    <div class="container">
        <h1>MARKET_LABEL 종목 분석DART_TEXT</h1>
        PERIOD_HTML
        <div class="stock-name" id="stock-name">준비 중...</div>
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill" style="width: 0%">0%</div>
        </div>
        <div class="status" id="status-row" role="status" aria-live="polite">
            <span class="status-dot" aria-hidden="true"></span>
            <span id="status">분석을 시작합니다...</span>
        </div>
        
        <div class="complete" id="complete">
            <p style="font-size: 18px; color: var(--success);">분석 완료!</p>
            <a href="/" class="btn btn-primary">메인으로 돌아가기</a>
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
                var dot = document.querySelector('#status-row .status-dot');
                if (dot) dot.style.display = 'none';
                if (data.status === 'completed') {
                    document.getElementById('complete').style.display = 'block';
                    document.getElementById('stock-name').textContent = '분석 완료!';
                    document.getElementById('progress-fill').style.width = '100%';
                    document.getElementById('progress-fill').textContent = '100%';
                } else {
                    document.getElementById('status').textContent = '오류: ' + data.message;
                    document.getElementById('status').style.color = 'var(--danger)';
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
    <script>
    (function () {
        var btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', function () {
                var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                try { localStorage.setItem('stockpilot-theme', next); } catch (e) {}
            });
        }
    })();
    </script>
</body>
</html>"""

    return (progress_page
            .replace("MARKET_LABEL", market_label)
            .replace("DART_TEXT", dart_text)
            .replace("PERIOD_HTML", period_html))


@app.get("/api/run")
async def api_run_analysis(
    with_dart: bool = Query(False),
    start: Optional[str] = None,
    end: Optional[str] = None,
    iso_year: Optional[str] = None,
    iso_week: Optional[str] = None,
    year: Optional[str] = None,
    month: Optional[str] = None,
    week: Optional[str] = None,
):
    """API: 전체 분석 실행"""
    from scripts.run_analysis import run_analysis
    try:
        period = resolve_request_period(
            start=start, end=end, iso_year=iso_year, iso_week=iso_week,
            year=year, month=month, week=week, market="all",
        )
        await run_analysis("all", with_dart, period=period)
        return {"status": "success", "message": "분석 완료"}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/period/preview")
async def preview_period(
    start: Optional[str] = None,
    end: Optional[str] = None,
    iso_year: Optional[str] = None,
    iso_week: Optional[str] = None,
    year: Optional[str] = None,
    month: Optional[str] = None,
    week: Optional[str] = None,
    market: str = Query("all", regex="^(all|domestic|foreign)$"),
):
    """구간 선택 미리보기 - UI가 실행 전에 실제 구간/거래일을 보여준다"""
    from analyzers.period import resolve_period
    from analyzers.market_calendar import MARKET_KR, MARKET_US

    period_market = MARKET_KR if market == "domestic" else MARKET_US
    period = resolve_request_period(
        start=start, end=end, iso_year=iso_year, iso_week=iso_week,
        year=year, month=month, week=week, market=market,
    )
    if period is None:
        period = resolve_period(market=period_market)
        return {"is_custom": False, **period.to_dict()}
    return {"is_custom": True, **period.to_dict()}


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
    domestic_path = get_config_path("stocks.yaml")
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
    domestic_path = get_config_path("stocks.yaml")
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
    foreign_path = get_config_path("foreign_stocks.yaml")
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
    foreign_path = get_config_path("foreign_stocks.yaml")
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
    """종목 검색 (한글명/종목코드 부분 일치 + yfinance 해외 검색)"""
    from collectors import search_korean_stocks, find_by_code

    results = []
    q_upper = q.upper()
    stock_config = load_stock_config()

    # 1) 등록된 종목 (한글명/종목코드 부분 일치)
    if market in ("all", "domestic"):
        for s in stock_config["domestic"]:
            name = s.get("name", "")
            code = str(s.get("code", ""))
            if q in name or q_upper in code.upper():
                results.append({
                    "type": "domestic",
                    "code": code,
                    "name": name,
                    "market": s.get("market", "KOSPI"),
                    "currency": "KRW",
                })

    if market in ("all", "foreign"):
        for s in stock_config["foreign"]:
            name = s.get("name", "")
            ticker = s.get("ticker", "")
            if q.lower() in name.lower() or q_upper in ticker.upper():
                results.append({
                    "type": "foreign",
                    "ticker": ticker,
                    "name": name,
                    "market": s.get("market", "NASDAQ"),
                    "currency": s.get("currency", "USD"),
                })

    # 2) 한글명 매핑 테이블 (부분 일치) - 등록 종목이 없을 때
    if not results and market in ("all", "domestic"):
        for item in search_korean_stocks(q, limit=10):
            results.append({
                "type": "domestic",
                "code": item["code"],
                "name": item["name"],
                "market": item["market"],
                "currency": "KRW",
            })

    if results:
        return {"results": results[:10]}

    # 3) 6자리 종목코드 직접 입력 (매핑에 없는 코드)
    code_match = None
    if market in ("all", "domestic") and q.isdigit() and len(q) == 6:
        code_match = q
        found = find_by_code(q)
        if found:
            return {"results": [{
                "type": "domestic",
                "code": found["code"],
                "name": found["name"],
                "market": found["market"],
                "currency": "KRW",
            }]}

    # 4) yfinance 폴백 (해외 티커 / 국내 코드 검증)
    try:
        import yfinance as yf

        if code_match:
            for suffix in (".KS", ".KQ"):
                try:
                    info = yf.Ticker(code_match + suffix).info
                    if info and info.get("shortName"):
                        return {"results": [{
                            "type": "domestic",
                            "code": code_match,
                            "name": info["shortName"],
                            "market": "KOSDAQ" if suffix == ".KQ" else "KOSPI",
                            "currency": "KRW",
                        }]}
                except Exception:
                    continue
            return {"results": []}

        if market in ("all", "foreign"):
            ticker = q_upper
            for alias, alias_ticker in FOREIGN_ALIASES.items():
                if q.lower() == alias:
                    ticker = alias_ticker
                    break
            try:
                info = yf.Ticker(ticker).info
                if info and info.get("shortName"):
                    exchange = info.get("exchange", "")
                    if "NMS" in exchange or "NSD" in exchange:
                        market_type = "NASDAQ"
                    elif "NYQ" in exchange:
                        market_type = "NYSE"
                    else:
                        market_type = exchange
                    return {"results": [{
                        "type": "foreign",
                        "ticker": ticker,
                        "name": info["shortName"],
                        "market": market_type,
                        "currency": "USD",
                    }]}
            except Exception:
                pass

        return {"results": []}
    except ImportError:
        return {"results": []}
    except Exception:
        return {"results": []}


def start_server(host: str = "0.0.0.0", port: int = 8001):
    """서버 시작"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
