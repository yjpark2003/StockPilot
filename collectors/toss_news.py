# -*- coding: utf-8 -*-
"""토스증권 뉴스 수집 모듈"""
import asyncio
import json
import re
import urllib.parse
from playwright.async_api import async_playwright


class TossNewsCollector:
    """토스증권에서 종목별 뉴스 수집"""

    BASE_URL = "https://tossinvest.com"

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

    def _convert_stock_code(self, stock_code: str, market: str = "KRX") -> str:
        """종목 코드를 토스증권 형식으로 변환"""
        if market == "NASDAQ" or market == "NYSE":
            # 해외 종목: US{코드} 형식
            return f"US{stock_code}"
        else:
            # 국내 종목: A{코드} 형식
            return f"A{stock_code}"

    async def get_news(self, stock_code: str, count: int = 3, market: str = "KRX") -> list:
        """종목별 뉴스 수집"""
        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            toss_code = self._convert_stock_code(stock_code, market)
            url = f"{self.BASE_URL}/stocks/{toss_code}/news"
            
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1500)
            
            # 페이지 스크롤하여 콘텐츠 로드
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(1000)
            
            # 뉴스 링크에서 정보 추출
            news_links = await page.locator('a[href*="contentType=news"]').all()
            
            news_items = []
            seen_titles = set()
            
            for link in news_links:
                try:
                    href = await link.get_attribute("href")
                    if not href or "contentType=news" not in href:
                        continue
                    
                    # 링크에서 제목 추출 시도
                    title = await link.inner_text()
                    title = title.strip()
                    
                    # 제목이 너무 짧거나 중복이면 건너뛰기
                    if len(title) < 10 or title in seen_titles:
                        continue
                    
                    # 가격 정보 제외
                    if re.match(r'^[\d,]+원', title) or title.startswith('+') or title.startswith('-'):
                        continue
                    
                    seen_titles.add(title)
                    
                    # 전체 URL 생성
                    full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    
                    # 콘텐츠 ID에서 출처 추출
                    source = "토스증권"
                    content_id = ""
                    
                    # URL 디코딩 후 contentParams 추출
                    decoded_href = urllib.parse.unquote(href)
                    
                    if "contentParams" in decoded_href:
                        match = re.search(r'"id":"([^"]+)"', decoded_href)
                        if match:
                            content_id = match.group(1)
                            # 출처 매핑
                            source_map = {
                                "edaily": "이데일리",
                                "hankyung": "한국경제",
                                "etoday": "이투데이",
                                "mk": "매일경제",
                                "yna": "연합뉴스",
                                "fn": "파이낸셜뉴스",
                                "financial": "파이낸셜뉴스",
                                "news1": "뉴스1",
                                "ytn": "YTN",
                                "sbs": "SBS",
                                "mbn": "MBN",
                                "channel_a": "채널A",
                                "jtbc": "JTBC",
                                "kbs": "KBS",
                                "mbc": "MBC",
                                "sbs_cnb": "SBS CNBC",
                                "한국경제": "한국경제",
                                "매일경제": "매일경제",
                            }
                            for key, value in source_map.items():
                                if key in content_id:
                                    source = value
                                    break
                    else:
                        # 제목에서 출처 추출 시도
                        source_patterns = {
                            "[이데일리": "이데일리",
                            "[한국경제": "한국경제",
                            "[매일경제": "매일경제",
                            "[파이낸셜뉴스": "파이낸셜뉴스",
                            "[연합뉴스": "연합뉴스",
                            "[뉴스1": "뉴스1",
                            "[YTN": "YTN",
                            "[SBS": "SBS",
                            "[MBN": "MBN",
                            "[채널A": "채널A",
                            "[JTBC": "JTBC",
                            "[KBS": "KBS",
                            "[MBC": "MBC",
                        }
                        for pattern, src in source_patterns.items():
                            if pattern in title:
                                source = src
                                # 제목에서 출처 부분 제거
                                title = re.sub(r'\[.*?\]\s*', '', title).strip()
                                break
                    
                    news_items.append({
                        "title": title,
                        "link": full_url,
                        "source": source,
                        "time": "",
                        "content_id": content_id,
                    })
                    
                    if len(news_items) >= count:
                        break
                        
                except Exception as e:
                    continue
            
            # 뉴스가 부족하면 페이지 텍스트에서 추출
            if len(news_items) < count:
                content = await page.inner_text("body")
                lines = content.split("\n")
                
                # 출처 패턴 매핑
                source_patterns = {
                    "[이데일리": "이데일리",
                    "[한국경제": "한국경제",
                    "[매일경제": "매일경제",
                    "[파이낸셜뉴스": "파이낸셜뉴스",
                    "[연합뉴스": "연합뉴스",
                    "[뉴스핌": "뉴스핌",
                    "[뉴스1": "뉴스1",
                    "[YTN": "YTN",
                    "[SBS": "SBS",
                    "[MBN": "MBN",
                    "[채널A": "채널A",
                    "[JTBC": "JTBC",
                    "[KBS": "KBS",
                    "[MBC": "MBC",
                    "[조선비즈": "조선비즈",
                    "[아시아경제": "아시아경제",
                    "[서울신문": "서울신문",
                    "[한겨레": "한겨레",
                    "[중앙일보": "중앙일보",
                    "[동아일보": "동아일보",
                    "[세계일보": "세계일보",
                    "[스포츠서울": "스포츠서울",
                    "[ 증시": "토스증권",
                    "[마켓뷰": "토스증권",
                    "[오늘의": "토스증권",
                    "[모닝": "토스증권",
                    "[리포트": "토스증권",
                    "[핫이슈": "토스증권",
                    "[종목": "토스증권",
                }
                
                for line in lines:
                    line = line.strip()
                    if (len(line) > 20 and 
                        line not in seen_titles and
                        not line.startswith("http") and
                        "로그인" not in line and
                        "원)" not in line and
                        "investing" not in line.lower()):
                        
                        # 출처 추출
                        source = "토스증권"
                        title = line
                        
                        for pattern, src in source_patterns.items():
                            if pattern in line:
                                source = src
                                # 제목에서 출처 부분 제거
                                title = re.sub(r'\[.*?\]\s*', '', line).strip()
                                break
                        
                        # 뉴스 제목으로 보이는 라인 (주요 키워드 포함)
                        news_keywords = ["삼성전자", "SK하이닉스", "NAVER", "카카오", "반도체", "증시", "투자", 
                                       "코스피", "코스닥", "금리", "실적", "배당", "전망", "분석"]
                        
                        if any(keyword in line for keyword in news_keywords):
                            seen_titles.add(line)
                            news_items.append({
                                "title": title[:100],
                                "link": url,
                                "source": source,
                                "time": "",
                            })
                            
                            if len(news_items) >= count:
                                break
            
            return news_items[:count]
            
        except Exception as e:
            print(f"토스증권 뉴스 수집 오류 ({stock_code}): {e}")
            return []
        finally:
            await page.close()

    async def get_news_with_content(self, stock_code: str, market: str = "KRX") -> dict:
        """뉴스 상세 내용 포함 수집"""
        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            toss_code = self._convert_stock_code(stock_code, market)
            url = f"{self.BASE_URL}/stocks/{toss_code}/news"
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # 페이지 전체 텍스트 추출
            content = await page.inner_text("body")
            
            # 뉴스 제목들 추출
            lines = content.split("\n")
            headlines = []
            
            for line in lines:
                line = line.strip()
                if (len(line) > 20 and 
                    not line.startswith("http") and
                    "로그인" not in line and
                    "원)" not in line):
                    headlines.append(line)
                    if len(headlines) >= 5:
                        break
            
            return {
                "url": url,
                "headlines": headlines,
                "content_preview": content[:500],
            }
            
        except Exception as e:
            print(f"토스증권 뉴스 상세 수집 오류 ({stock_code}): {e}")
            return {"url": "", "headlines": [], "content_preview": ""}
        finally:
            await page.close()
