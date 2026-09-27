# -*- coding: utf-8 -*-
"""국내 주식 투자자별 매매동향 수집 모듈

주의 (2026-09-27 확인)
  이 모듈이 파싱하던 네이버금융 레거시 화면이 모두 폐기되었다.
    * /item/frgn.naver  -> 302 (stock.naver.com SPA로 이동)
    * /item/sise_day.naver -> 410 Gone ("이 페이지는 더 이상 제공되지 않습니다")
  따라서 수집 결과는 항상 비어 있고, 리포트에도 투자자별 섹션이
  렌더링되지 않는다. 구간 지정 분석에서도 되돌릴 수 없는 데이터다.
  (유일한 정본은 KRX data.krx.co.kr 투자자별 거래실적이며, 현재
   이 환경에서는 `LOGOUT` responses로 차단되어 있다.)

  아래 `SOURCE_AVAILABLE = False` 는 이 사실을 코드에 명시해 매번
  브라우저를 띄우며 실패하는 것을 막고, 리포트에 "미지원"으로
  표시할 수 있게 한다. 소스가 되살아나면 True 로 바꾸면 된다.
"""
import asyncio
import re
from playwright.async_api import async_playwright

SOURCE_AVAILABLE = False
SOURCE_UNAVAILABLE_REASON = (
    "네이버금융 투자자별 매매동향 화면이 302/410 으로 폐기됨 (KRX 대체 필요)"
)


class InvestorTrendCollector:
    """투자자별 매매동향 수집 (외국인/기관/개인)"""

    BASE_URL = "https://finance.naver.com"

    def __init__(self):
        self._browser = None
        self._context = None

    async def _ensure_browser(self):
        if self._browser is None:
            if getattr(self, "_pw", None) is None:
                self._pw = await async_playwright().start()
            try:
                self._browser = await self._pw.chromium.launch(headless=True)
                self._context = await self._browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
            except Exception:
                pw = self._pw
                self._browser = None
                self._context = None
                self._pw = None
                try:
                    await pw.stop()
                except Exception:
                    pass
                raise

    async def close(self):
        browser = self._browser
        pw = getattr(self, "_pw", None)
        self._browser = None
        self._context = None
        self._pw = None
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass

    async def get_investor_trend(self, stock_code: str, days: int = 5) -> dict:
        """투자자별 매매동향 수집 (외국인/기관/개인)

        현재는 소스 폐기 때문에 항상 빈 결과를 돌려준다. 아래 구현은
        소스 복구 시 되살리기 위한 원본 로직이다.
        """
        if not SOURCE_AVAILABLE:
            return {"daily_trend": [], "foreign_ratio": "N/A", "summary": {},
                    "unavailable_reason": SOURCE_UNAVAILABLE_REASON}

        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            url = f"{self.BASE_URL}/item/frgn.naver?code={stock_code}&page=1"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1000)

            # 투자자별 매매동향 테이블 찾기
            tables = await page.locator("table").all()
            
            for table in tables:
                text = await table.inner_text()
                if "외국인" in text and "기관" in text and "순매매" in text:
                    rows = await table.locator("tr").all()
                    trend_data = []
                    
                    for row in rows[1:days+1]:
                        try:
                            cells = await row.locator("td").all()
                            if len(cells) >= 9:  # 외국인 보유율까지 포함
                                date_text = (await cells[0].inner_text()).strip()
                                close_text = (await cells[1].inner_text()).strip().replace(",", "")
                                volume_text = (await cells[4].inner_text()).strip().replace(",", "")
                                inst_net = (await cells[5].inner_text()).strip().replace("+", "").replace(",", "")
                                foreign_net = (await cells[6].inner_text()).strip().replace("+", "").replace(",", "")
                                foreign_ratio_text = (await cells[8].inner_text()).strip().replace("%", "")
                                
                                if date_text and close_text:
                                    volume = int(volume_text) if volume_text.replace("-", "").isdigit() else 0
                                    inst = int(inst_net) if inst_net.replace("-", "").isdigit() else 0
                                    foreign = int(foreign_net) if foreign_net.replace("-", "").isdigit() else 0
                                    individual = volume - inst - foreign
                                    foreign_ratio = float(foreign_ratio_text) if foreign_ratio_text.replace(".", "").isdigit() else 0
                                    
                                    trend_data.append({
                                        "date": date_text,
                                        "close": int(float(close_text)) if close_text.replace(".", "").isdigit() else 0,
                                        "volume": volume,
                                        "inst_net": inst,
                                        "foreign_net": foreign,
                                        "individual_net": individual,
                                        "foreign_ratio": foreign_ratio,
                                    })
                        except Exception:
                            continue
                    
                    if trend_data:
                        foreign_ratio = "N/A"
                        foreign_ratio_change = 0.0
                        foreign_shares = 0
                        
                        # 페이지 텍스트에서 외국인 보유율 정보 찾기
                        content = await page.inner_text("body")
                        lines = content.split("\n")
                        
                        for i, line in enumerate(lines):
                            # 외국인보유주식수 찾기
                            if "외국인보유주식수" in line:
                                match = re.search(r"외국인보유주식수.*?(\d[\d,]+)", line)
                                if match:
                                    foreign_shares = int(match.group(1).replace(",", ""))
                            
                            # 외국인소진율 찾기 (다음 라인에 값이 있음)
                            if "외국인소진율" in line and i + 1 < len(lines):
                                next_line = lines[i + 1]
                                match = re.search(r"(\d+\.?\d*)%", next_line)
                                if match:
                                    foreign_ratio = match.group(1) + "%"
                        
                        # 외국인 보유율 변화량 계산 (최근 5일 기준)
                        if len(trend_data) >= 2:
                            # trend_data에서 보유율 변화 계산
                            first_foreign_ratio = trend_data[0].get("foreign_ratio", 0)
                            last_foreign_ratio = trend_data[-1].get("foreign_ratio", 0)
                            if first_foreign_ratio and last_foreign_ratio:
                                foreign_ratio_change = last_foreign_ratio - first_foreign_ratio

                        return {
                            "daily_trend": trend_data,
                            "foreign_ratio": foreign_ratio,
                            "foreign_ratio_change": round(foreign_ratio_change, 2),
                            "foreign_shares": foreign_shares,
                            "summary": self._calculate_summary(trend_data),
                        }
            
            return {"daily_trend": [], "foreign_ratio": "N/A", "summary": {}}
        except Exception as e:
            print(f"투자자 매매동향 수집 오류 ({stock_code}): {e}")
            return {"daily_trend": [], "foreign_ratio": "N/A", "summary": {}}
        finally:
            await page.close()

    def _calculate_summary(self, trend_data: list) -> dict:
        """매매동향 요약 계산"""
        if not trend_data:
            return {}
        
        total_inst = sum(d["inst_net"] for d in trend_data)
        total_foreign = sum(d["foreign_net"] for d in trend_data)
        total_individual = sum(d["individual_net"] for d in trend_data)
        
        return {
            "inst_total": total_inst,
            "inst_trend": "순매수" if total_inst > 0 else "순매도" if total_inst < 0 else "중립",
            "foreign_total": total_foreign,
            "foreign_trend": "순매수" if total_foreign > 0 else "순매도" if total_foreign < 0 else "중립",
            "individual_total": total_individual,
            "individual_trend": "순매수" if total_individual > 0 else "순매도" if total_individual < 0 else "중립",
            "inst_avg": total_inst // len(trend_data),
            "foreign_avg": total_foreign // len(trend_data),
            "individual_avg": total_individual // len(trend_data),
        }

    async def get_trading_volume(self, stock_code: str) -> dict:
        """거래량 데이터 수집 (소스 폐기로 항상 빈 결과)"""
        if not SOURCE_AVAILABLE:
            return {"volume_data": [], "unavailable_reason": SOURCE_UNAVAILABLE_REASON}

        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            url = f"{self.BASE_URL}/item/sise_day.naver?code={stock_code}"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(800)

            rows = await page.locator("table.type2 tr").all()
            volume_data = []
            
            for row in rows[1:6]:
                try:
                    cells = await row.locator("td").all()
                    if len(cells) >= 6:
                        date_text = (await cells[0].inner_text()).strip()
                        volume_text = (await cells[4].inner_text()).strip().replace(",", "")
                        
                        if date_text and volume_text and volume_text.isdigit():
                            volume_data.append({
                                "date": date_text,
                                "volume": int(volume_text),
                            })
                except Exception:
                    continue
            
            return {"volume_data": volume_data}
        except Exception as e:
            print(f"거래량 수집 오류 ({stock_code}): {e}")
            return {"volume_data": []}
        finally:
            await page.close()
