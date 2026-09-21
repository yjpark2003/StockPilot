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

    async def get_financial_summary(self, stock_code: str, stock_name: str) -> dict:
        """재무 요약 데이터 수집 (PER, PBR, 부채비율 등)"""
        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            url = f"{self.BASE_URL}/sise498.naver?giession={stock_code}"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
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
            return {
                "per": "N/A",
                "pbr": "N/A",
                "roe": "N/A",
                "debt_ratio": "N/A",
                "dividend_yield": "N/A",
            }
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
