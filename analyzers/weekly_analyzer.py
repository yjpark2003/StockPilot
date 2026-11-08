# -*- coding: utf-8 -*-
"""주간 주식 분석 엔진"""
import asyncio
from datetime import date, datetime
from typing import Optional

from analyzers.period import WeeklyPeriod, resolve_period
from analyzers.market_calendar import MARKET_KR, MARKET_US
from collectors.execution import StageRunner
from collectors.limits import load_limits
import time
from collectors.investor_trend import (
    SOURCE_AVAILABLE as INVESTOR_TREND_AVAILABLE,
    SOURCE_UNAVAILABLE_REASON as INVESTOR_TREND_REASON,
)

# 섹션별 데이터 기준 (basis)
#   period      -> 지정 구간에 정확히 대응
#   snapshot    -> 구간과 무관하게 '기준일(수집일) 현재값'만 제공
#   unavailable -> 소스 부재로 수집 불가
#   incomplete  -> 구간은 맞았지만 소스 데이터가 일부 미제공 (예: 최근 거래일 지연)
BASIS_PERIOD = "period"
BASIS_SNAPSHOT = "snapshot"
BASIS_UNAVAILABLE = "unavailable"
BASIS_INCOMPLETE = "incomplete"

BASIS_LABELS = {
    BASIS_PERIOD: "구간 일치",
    BASIS_SNAPSHOT: "기준일 스냅샷",
    BASIS_UNAVAILABLE: "미지원",
    BASIS_INCOMPLETE: "구간 일부 미수집",
}

BASIS_NOTES = {
    BASIS_SNAPSHOT: "해당 수치는 구간 종료일이 아닌 수집 시점 기준입니다.",
    BASIS_UNAVAILABLE: INVESTOR_TREND_REASON,
}

# 시장별 섹션 기준. 주가/뉴스만 구간 지정이 실제로 반영된다.
SECTION_BASIS = {
    "domestic": {
        "price": BASIS_PERIOD,
        "news": BASIS_PERIOD,
        "financial": BASIS_SNAPSHOT,
        "investor_trend": BASIS_UNAVAILABLE,
        "volume_data": BASIS_UNAVAILABLE,
    },
    "foreign": {
        "price": BASIS_PERIOD,
        "news": BASIS_PERIOD,
        "financial": BASIS_SNAPSHOT,
        "short_interest": BASIS_SNAPSHOT,
    },
}


def price_alignment(price_data: dict, period: WeeklyPeriod,
                    market: str = MARKET_KR) -> dict:
    """주가 섹션의 구간 충족도를 계산한다.

    소스(yfinance 등)가 구간의 모든 거래일을 제공하지 않는 경우가 실제로 있다
    (국내 피드는 최근 거래일이 1~2일 늦게 반영된다). 이때 '구간 일치' 배지를
    그대로 쓰면 없는 데이터를 있는 것처럼 보이게 하므로, 누락이 있으면
    '구간 일부 미수집' 으로 낮춰 표시한다.

    기대일은 휴장일 달력(`trading_days_for`)으로 정한다. 휴장일을 기대일에
    넣으면 실제로는 정상인데도 누락으로 보고하는 오탐이 생긴다. 예) 추석
    연휴(2026-09-24·25)에는 국내 장이 닫혔으므로 기대 거래일은 3일이다.
    """
    weekly = price_data.get("weekly_data") or []
    got = [str(d.get("date", ""))[:10] for d in weekly if isinstance(d, dict)]
    got = [d for d in got if d]
    expected = [d.isoformat() for d in period.trading_days_for(market)]
    missing = [d for d in expected if d not in set(got)]

    out = {"count": len(got), "expected_count": len(expected)}
    if not got:
        out["basis"] = BASIS_INCOMPLETE
        out["missing_days"] = list(expected)
        out["note"] = "구간 내 주가 데이터를 하나도 가져오지 못했습니다 (티커/코드 또는 수집 실패 확인 필요)."
    elif expected and missing:
        out["missing_days"] = missing
        out["basis"] = BASIS_INCOMPLETE
        out["note"] = (
            f"거래일 {len(expected)}일 중 {len(missing)}일분 데이터가 소스에 없습니다 "
            f"({', '.join(missing)}). 소스 반영 지연일 수 있습니다."
        )
    return out


def build_alignment(market_type: str, sections: Optional[dict] = None) -> dict:
    """종목별 섹션 데이터 기준 정보를 만든다 (리포트 배지용)"""
    table = SECTION_BASIS.get(market_type, {})
    out = {}
    for name, basis in table.items():
        entry = {
            "basis": basis,
            "label": BASIS_LABELS[basis],
            "note": BASIS_NOTES.get(basis, ""),
        }
        extra = (sections or {}).get(name)
        if isinstance(extra, dict):
            # 섹션이 basis 를 직접 낮춘다 (예: 거래일 누락 -> incomplete)
            if extra.get("basis") in BASIS_LABELS:
                entry["basis"] = extra["basis"]
                entry["label"] = BASIS_LABELS[extra["basis"]]
                entry["note"] = BASIS_NOTES.get(extra["basis"], "")
            for key in ("count", "expected_count", "missing_days", "unavailable_reason", "note"):
                if extra.get(key) not in (None, "", 0):
                    entry[key] = extra[key]
        elif extra not in (None, [], {}):
            entry["count"] = len(extra) if isinstance(extra, (list, tuple)) else extra
        out[name] = entry
    return out


class WeeklyAnalyzer:
    """종목별 주간 분석 수행"""

    def __init__(self, news_count=3, dart_api_key="", with_dart=False,
                 progress_callback=None, period=None, stage_callback=None, limits=None):
        self.news_count = news_count
        self.with_dart = with_dart
        self.progress_callback = progress_callback
        self.stage_callback = stage_callback
        self.period = period or resolve_period()
        self.limits = limits or load_limits()
        self.runner = StageRunner(self.limits['consecutive_timeouts'])

    async def _collect(self, stage, source, method, args, kwargs, deadline=None):
        limit = self.limits[stage]
        if deadline is not None:
            limit = max(0, min(limit, deadline - time.monotonic()))
        payload = dict(source=source, method=method, args=args, kwargs=kwargs, limits=self.limits,
                       full_budget=limit == self.limits[stage])
        result = await self.runner.run(stage, source, payload, limit, self.stage_callback)
        if self.stage_callback:
            await self.stage_callback({**result, 'finished': True})
        return result

    async def collect_benchmark(self, ticker):
        result = await self._collect('benchmark', 'yfinance', 'get_weekly_price', [ticker],
                                     dict(start=self.period.start.isoformat(), end=self.period.end.isoformat(),
                                          include_live_quote=False))
        return {**(result.pop('data', None) or {}), 'collection_status': result}

    async def analyze_stock(self, stock, market='domestic'):
        deadline = time.monotonic() + self.limits['stock']
        foreign = market == 'foreign'
        code = stock['ticker'] if foreign else stock['code']
        currency = stock.get('currency', 'USD') if foreign else 'KRW'
        ticker = code if foreign else code + ('.KQ' if stock.get('market', '').upper() == 'KOSDAQ' else '.KS')
        bounds = dict(start=self.period.start.isoformat(), end=self.period.end.isoformat())
        stages = {}
        # Sequential stages share one deadline. Workers own all network/browser resources.
        stages['price'] = await self._collect('price', 'yfinance', 'get_weekly_price',
                                              [ticker, currency], {**bounds, 'include_live_quote': False}, deadline)
        stages['news'] = await self._collect('news', 'yfinance' if foreign else 'toss', 'get_news',
                                             [ticker if foreign else code, self.news_count], bounds, deadline)
        stages['financial'] = await self._collect('financial', 'yfinance' if foreign else 'company_guide',
                                                  'get_financial_summary', [ticker] if foreign else [code, stock['name']], {}, deadline)
        if foreign:
            stages['short_interest'] = await self._collect('short_interest', 'yfinance', 'get_short_interest', [ticker], {}, deadline)
        else:
            for section in ('investor_trend', 'volume_data'):
                stages[section] = dict(status='unsupported', error=INVESTOR_TREND_REASON, elapsed_seconds=0)
        price = stages['price'].get('data') or dict(current_price=0, weekly_data=[], change_rate=0,
                                                  start_price=0, end_price=0, currency=currency)
        news = stages['news'].get('data') or []
        financial = stages['financial'].get('data') or {key: 'N/A' for key in
            ('per', 'pbr', 'roe', 'debt_ratio', 'dividend_yield', 'market_cap', 'eps', 'forward_pe', '52_week_high', '52_week_low', 'beta')}
        short = stages.get('short_interest', {}).get('data') or {}
        alignment = build_alignment(market, {
            'price': price_alignment(price, self.period, MARKET_US if foreign else MARKET_KR),
            'news': self._news_alignment(news),
        })
        for section, result in stages.items():
            if section in alignment and result['status'] in ('timeout', 'error', 'skipped'):
                alignment[section].update(basis='incomplete', label='수집 실패',
                                          note=result.get('error', '수집 실패'), collection_status=result['status'])
            elif section in alignment and section != 'news' and result['status'] == 'empty':
                alignment[section].update(basis='unavailable', label='데이터 없음', note='소스에 해당 지표가 없습니다.')
        collection = {key: {k: v for k, v in result.items() if k != 'data'} for key, result in stages.items()}
        failed = not price.get('weekly_data')
        partial = any(result['status'] in ('timeout', 'error', 'skipped')
                      or (section != 'news' and result['status'] == 'empty')
                      for section, result in stages.items())
        result = dict(code=code, name=stock['name'], market=stock.get('market', ''), market_type=market,
                      stock_type=stock.get('type') or ('ETF' if stock.get('market') == 'ETF' else financial.get('stock_type', '')),
                      currency=currency, analysis_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                      price=price, news=news, financial=financial, short_interest=short,
                      disclosures=[], market_data={}, investor_trend={}, volume_data=[],
                      key_points=self._generate_key_points(stock['name'], price if not failed else {}, news, [], financial, currency, None, short),
                      data_alignment=alignment, collection_status=collection,
                      analysis_status='failed' if failed else 'partial' if partial else 'complete')
        if failed:
            result['error'] = stages['price'].get('error') or '구간 주가 데이터 없음'
        return result

    def _news_alignment(self, news):
        dated = [item for item in news if item.get('pub_date')]
        undated = [item for item in news if item.get('undated')]
        if not news:
            note = '해당 구간에 발행된 뉴스를 찾지 못했습니다.'
        elif dated:
            note = f'{len(dated)}건이 구간 발행일로 확인됩니다.'
            if undated:
                note += f' {len(undated)}건은 발행일 미상으로 구간 검증에서 제외했습니다.'
        else:
            note = '발행일을 확인하지 못해 구간 정합성을 검증할 수 없습니다.'
        return dict(count=len(news), note=note)

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
                if result.get('error'):
                    print(f"  ✗ 실패: {result['error']}", flush=True)
                    continue
                # 성공 시 간략 결과 출력
                change = result.get('price', {}).get('change_rate', 0)
                icon = "+" if change > 0 else ""
                label = '부분 수집' if result.get('analysis_status') == 'partial' else '완료'
                print(f"  ✓ {label} ({icon}{change:.1f}%)", flush=True)
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
            span = "해당 구간" if self.period.is_custom else "지난 1주간"
            if rate > 5:
                points.append(f"{span} {rate:.1f}% 상승")
            elif rate > 0:
                points.append(f"{span} {rate:.1f}% 소폭 상승")
            elif rate < -5:
                points.append(f"{span} {abs(rate):.1f}% 하락")
            elif rate < 0:
                points.append(f"{span} {abs(rate):.1f}% 소폭 하락")
            else:
                points.append(f"{span} 보합세 유지")

        # 뉴스 분석
        if news_data:
            scope = "해당 구간" if self.period.is_custom else "최근"
            points.append(f"{scope} 주요 뉴스 {len(news_data)}건 확인")

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
        """Each stage reaps its isolated process before returning."""
        pass
