# -*- coding: utf-8 -*-
"""컴퍼니가이드 데이터 수집 모듈"""
import asyncio
from playwright.async_api import async_playwright


class CompanyGuideCollector:
    """컴퍼니가이드에서 재무 심층 분석 데이터 수집"""

    BASE_URL = "https://comp.fnguide.com"

    def __init__(self):
        self._browser = None
        self._context = None

    async def _ensure_browser(self):
        from collectors.browser import ensure_browser
        await ensure_browser(self)

    async def close(self):
        from collectors.browser import close_browser
        await close_browser(self)

    async def get_financial_summary(self, stock_code: str, stock_name: str) -> dict:
        """재무 요약 데이터 수집 (PER, PBR, 부채비율 등)"""
        from collectors.browser import open_page
        page = await open_page(self)
        try:
            url = f"{self.BASE_URL}/sise498.naver?giession={stock_code}"
            await page.goto(url, wait_until="domcontentloaded", timeout=getattr(self, "limits", {}).get("navigation", 15) * 1000)
            await page.wait_for_timeout(1500)

            # 재무 비율 데이터 추출 시도
            financial_data = {
                "per": await self._extract_value(page, "PER"),
                "pbr": await self._extract_value(page, "PBR"),
                "roe": await self._extract_value(page, "ROE"),
                "debt_ratio": await self._extract_value(page, "부채비율"),
                "dividend_yield": await self._extract_value(page, "배당수익률"),
            }

            return financial_data
        except Exception as e:
            print(f"컴퍼니가이드 수집 오류 ({stock_name}): {e}")
            raise
        finally:
            await page.close()

    async def _extract_value(self, page, label: str) -> str:
        """페이지에서 특정 라벨의 값 추출"""
        try:
            # 다양한 선택자로 값 추출 시도
            selectors = [
                f"text={label}",
                f"th:has-text('{label}') + td",
                f"td:has-text('{label}')",
            ]
            for selector in selectors:
                elements = await page.locator(selector).all()
                for el in elements:
                    text = (await el.inner_text()).strip()
                    if text and any(c.isdigit() for c in text):
                        return text
            return "N/A"
        except Exception:
            return "N/A"
