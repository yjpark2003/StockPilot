# -*- coding: utf-8 -*-
"""주간 주식 분석 엔진"""
import asyncio
from datetime import datetime
from typing import Optional

from collectors import (
    NaverFinanceCollector,
    DartCollector,
    KrxCollector,
    CompanyGuideCollector,
    YfinanceCollector,
    InvestorTrendCollector,
    TossNewsCollector,
)


class WeeklyAnalyzer:
    """종목별 주간 분석 수행"""

    def __init__(self, news_count: int = 3, dart_api_key: str = "", with_dart: bool = False, progress_callback=None):
        self.news_count = news_count
        self.with_dart = with_dart
        self.progress_callback = progress_callback
        self.naver = NaverFinanceCollector()
        self.dart = DartCollector(api_key=dart_api_key) if with_dart else None
        self.krx = KrxCollector()
        self.company_guide = CompanyGuideCollector()
        self.yfinance = YfinanceCollector()
        self.investor_trend = InvestorTrendCollector()
        self.toss_news = TossNewsCollector()

    async def analyze_stock(self, stock: dict, market: str = "domestic") -> dict:
        """단일 종목 분석"""
        if market == "foreign":
            return await self._analyze_foreign_stock(stock)
        else:
            return await self._analyze_domestic_stock(stock)

    async def _analyze_domestic_stock(self, stock: dict) -> dict:
        """국내 종목 분석"""
        import time
        code = stock["code"]
        name = stock["name"]
        print(f"  [{name}] 데이터 수집 중...")
        
        timings = {}
        total_start = time.time()

        # 데이터 수집 (병렬 실행) - yfinance 우선 사용
        # 국내 종목은 .KS 접미사 추가
        ticker_ks = f"{code}.KS"
        price_task = self.yfinance.get_weekly_price(ticker_ks, "KRW")
        news_task = self.toss_news.get_news(code, self.news_count, "KRX")
        financial_task = self.company_guide.get_financial_summary(code, name)
        investor_task = self.investor_trend.get_investor_trend(code)
        volume_task = self.investor_trend.get_trading_volume(code)

        # 태스크 목록 구성 (yfinance 사용으로 krx 제거)
        tasks = [price_task, news_task, financial_task, investor_task, volume_task]
        task_names = ["yfinance", "toss_news", "company_guide", "investor_trend", "volume"]

        # 개별 태스크 시간 측정
        completed_tasks = {}
        for i, (task, name_key) in enumerate(zip(tasks, task_names)):
            task_start = time.time()
            try:
                result = await task
                completed_tasks[name_key] = result
                timings[name_key] = time.time() - task_start
            except Exception as e:
                completed_tasks[name_key] = e
                timings[name_key] = time.time() - task_start

        timings["total"] = time.time() - total_start
        
        # 타이밍 출력
        print(f"  [{name}] 소요시간: {timings['total']:.2f}초")
        for key, t in sorted(timings.items(), key=lambda x: -x[1]):
            if key != "total":
                print(f"    - {key}: {t:.2f}초")

        price_data = completed_tasks.get("yfinance", {})
        if isinstance(price_data, Exception) or not price_data or not price_data.get("weekly_data"):
            price_data = {
                "current_price": 0, "weekly_data": [], "change_rate": 0.0,
                "start_price": 0, "end_price": 0, "currency": "KRW",
            }
        
        news_data = completed_tasks.get("toss_news", [])
        if isinstance(news_data, Exception):
            news_data = []
            
        financial_data = completed_tasks.get("company_guide", {})
        if isinstance(financial_data, Exception) or not financial_data:
            financial_data = {
                "per": "N/A", "pbr": "N/A", "roe": "N/A",
                "debt_ratio": "N/A", "dividend_yield": "N/A",
            }
            
        investor_data = completed_tasks.get("investor_trend", {})
        if isinstance(investor_data, Exception) or not investor_data:
            investor_data = {
                "daily_trend": [], "foreign_ratio": "N/A", "summary": {},
            }
            
        volume_data = completed_tasks.get("volume", {})
        if isinstance(volume_data, Exception) or not volume_data:
            volume_data = {"volume_data": []}

        # 주목 포인트 분석
        key_points = self._generate_key_points(
            name, price_data, news_data, [], financial_data, "KRW", investor_data
        )

        return {
            "code": code,
            "name": name,
            "market": stock.get("market", ""),
            "market_type": "domestic",
            "stock_type": stock.get("type", ""),
            "currency": "KRW",
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "price": price_data,
            "news": news_data,
            "disclosures": [],
            "market_data": {},
            "financial": financial_data,
            "investor_trend": investor_data,
            "volume_data": volume_data.get("volume_data", []),
            "key_points": key_points,
        }

    async def _analyze_foreign_stock(self, stock: dict) -> dict:
        """해외 종목 분석"""
        ticker = stock["ticker"]
        name = stock["name"]
        currency = stock.get("currency", "USD")
        print(f"  [{name}] 데이터 수집 중...")

        # 데이터 수집 (병렬 실행)
        price_task = self.yfinance.get_weekly_price(ticker, currency)
        news_task = self.yfinance.get_news(ticker, self.news_count)
        financial_task = self.yfinance.get_financial_summary(ticker)
        short_task = self.yfinance.get_short_interest(ticker)

        results = await asyncio.gather(
            price_task, news_task, financial_task, short_task,
            return_exceptions=True,
        )

        price_data = results[0] if not isinstance(results[0], Exception) else {
            "current_price": 0, "weekly_data": [], "change_rate": 0.0,
            "start_price": 0, "end_price": 0, "currency": currency,
        }
        news_data = results[1] if not isinstance(results[1], Exception) else []
        financial_data = results[2] if not isinstance(results[2], Exception) else {
            "per": "N/A", "pbr": "N/A", "market_cap": "N/A",
            "dividend_yield": "N/A", "eps": "N/A",
        }
        short_data = results[3] if not isinstance(results[3], Exception) else {
            "short_ratio": "N/A", "short_percent": "N/A",
            "shares_short": "N/A", "shares_outstanding": "N/A",
            "float_shares": "N/A", "short_covering_days": "N/A",
            "avg_volume": "N/A", "avg_volume_10d": "N/A",
            "current_volume": "N/A", "sentiment": "중립",
        }

        # 주목 포인트 분석
        key_points = self._generate_key_points(
            name, price_data, news_data, [], financial_data, currency, None, short_data
        )

        return {
            "code": ticker,
            "name": name,
            "market": stock.get("market", ""),
            "market_type": "foreign",
            "currency": currency,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "price": price_data,
            "news": news_data,
            "disclosures": [],
            "market_data": {},
            "financial": financial_data,
            "short_interest": short_data,
            "key_points": key_points,
        }

    async def analyze_all(self, stocks: list, market: str = "domestic", start_idx: int = 0, total: int = 0) -> list:
        """전체 종목 분석"""
        local_total = len(stocks)
        print(f"\n{'='*50}")
        print(f"총 {local_total}개 종목 분석 시작 ({market})")
        print(f"{'='*50}")
        
        results = []
        for idx, stock in enumerate(stocks, 1):
            name = stock.get('name', stock.get('ticker', ''))
            global_idx = start_idx + idx
            
            # 진행률 콜백 호출
            if self.progress_callback:
                await self.progress_callback(global_idx, total, name, f"[{global_idx}/{total}] {name} 분석 중...")
            
            print(f"\n[{idx}/{local_total}] {name} 분석 중...")
            try:
                result = await self.analyze_stock(stock, market)
                results.append(result)
                # 성공 시 간략 결과 출력
                change = result.get('price', {}).get('change_rate', 0)
                icon = "+" if change > 0 else ""
                print(f"  ✓ 완료 ({icon}{change:.1f}%)")
            except Exception as e:
                print(f"  ✗ 오류: {e}")
                results.append({
                    "code": stock.get("code", stock.get("ticker", "")),
                    "name": stock.get("name", ""),
                    "error": str(e),
                })
        
        print(f"\n{'='*50}")
        print(f"분석 완료: {len(results)}/{local_total}개 종목")
        print(f"{'='*50}\n")
        
        return results

    def _generate_key_points(
        self,
        name: str,
        price_data: dict,
        news_data: list,
        disclosure_data: list,
        financial_data: dict,
        currency: str = "KRW",
        investor_data: dict = None,
        short_data: dict = None,
    ) -> list:
        """주목 포인트 생성"""
        points = []
        currency_symbol = "₩" if currency == "KRW" else "$"

        # 주가 변동 분석
        if price_data and "change_rate" in price_data:
            rate = price_data["change_rate"]
            if rate > 5:
                points.append(f"지난 1주간 {rate:.1f}% 상승으로 강세 지속")
            elif rate > 0:
                points.append(f"지난 1주간 {rate:.1f}% 소폭 상승")
            elif rate < -5:
                points.append(f"지난 1주간 {abs(rate):.1f}% 하락으로 약세 지속")
            elif rate < 0:
                points.append(f"지난 1주간 {abs(rate):.1f}% 소폭 하락")
            else:
                points.append("지난 1주간 보합세 유지")

        # 뉴스 분석
        if news_data:
            points.append(f"최근 주요 뉴스 {len(news_data)}건 확인")

        # 공시 분석 (국내만)
        if disclosure_data and disclosure_data[0].get("title", "").find("목업") == -1:
            points.append(f"최근 공시 {len(disclosure_data)}건 등록")

        # 재무 분석
        if financial_data and financial_data.get("per") != "N/A":
            points.append(f"현재 PER: {financial_data.get('per', 'N/A')}")

        # 투자자 매매동향 분석 (국내)
        if investor_data and investor_data.get("summary"):
            summary = investor_data["summary"]
            if summary.get("foreign_trend"):
                points.append(f"외국인: {summary['foreign_trend']}")
            if summary.get("inst_trend"):
                points.append(f"기관: {summary['inst_trend']}")

        # 공매도 분석 (해외)
        if short_data and short_data.get("sentiment") != "중립":
            points.append(f"숏 포지션: {short_data.get('sentiment', 'N/A')}")

        if not points:
            points.append("분석 데이터 부족 - 추가 확인 필요")

        return points

    async def close(self):
        """리소스 정리"""
        await self.naver.close()
        await self.company_guide.close()
        await self.investor_trend.close()
        await self.toss_news.close()
