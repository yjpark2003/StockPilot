# -*- coding: utf-8 -*-
"""네이버 금융 데이터 수집 모듈"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import async_playwright


class NaverFinanceCollector:
    """네이버 금융에서 주가, 뉴스 데이터 수집"""

    BASE_URL = "https://finance.naver.com"

    def __init__(self):
        self._browser = None
        self._context = None

    async def _ensure_browser(self):
        if self._browser is None:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

    async def close(self):
        if self._browser:
            await self._browser.close()
            await self._pw.stop()

    async def get_weekly_price(self, stock_code: str) -> dict:
        """최근 1주간 주가 변동 데이터 수집"""
        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            url = f"{self.BASE_URL}/item/main.naver?code={stock_code}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # 현재가
            current_price = await page.locator("p.no_today .blind").first.inner_text()
            current_price = int(current_price.replace(",", ""))

            # 최근 5거래일 데이터
            chart_url = f"{self.BASE_URL}/item/sise_day.naver?code={stock_code}&page=1"
            await page.goto(chart_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1000)

            rows = await page.locator("table.type2 tr").all()
            weekly_data = []
            for row in rows[:7]:
                try:
                    cells = await row.locator("td").all()
                    if len(cells) >= 6:
                        date_text = (await cells[0].inner_text()).strip()
                        close_text = (await cells[1].inner_text()).strip().replace(",", "")
                        if date_text and close_text and close_text.replace(".", "").isdigit():
                            weekly_data.append({
                                "date": date_text,
                                "close": int(float(close_text)),
                            })
                except Exception:
                    continue

            # 날짜 순서대로 정렬 (오래된 날짜가 왼쪽)
            weekly_data.reverse()

            # 주간 변동률 계산
            if len(weekly_data) >= 2:
                start_price = weekly_data[0]["close"]
                end_price = weekly_data[-1]["close"]
                change_rate = ((end_price - start_price) / start_price) * 100
            else:
                change_rate = 0.0

            return {
                "current_price": current_price,
                "weekly_data": weekly_data[:5],
                "change_rate": round(change_rate, 2),
                "start_price": weekly_data[0]["close"] if weekly_data else 0,
                "end_price": weekly_data[-1]["close"] if weekly_data else current_price,
            }
        finally:
            await page.close()

    async def get_news(self, stock_code: str, stock_name: str, count: int = 3) -> list:
        """종목 관련 뉴스 수집"""
        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            url = f"{self.BASE_URL}/item/news.naver?code={stock_code}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            news_items = []
            rows = await page.locator("table.newsList tr").all()
            for row in rows[:count + 2]:
                try:
                    title_el = row.locator("a.title")
                    if await title_el.count() > 0:
                        title = (await title_el.inner_text()).strip()
                        link = await title_el.get_attribute("href")
                        time_el = row.locator("td.time")
                        time_text = ""
                        if await time_el.count() > 0:
                            time_text = (await time_el.inner_text()).strip()
                        if title and len(news_items) < count:
                            news_items.append({
                                "title": title,
                                "link": link or "",
                                "time": time_text,
                            })
                except Exception:
                    continue

            return news_items
        finally:
            await page.close()
