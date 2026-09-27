# -*- coding: utf-8 -*-
"""토스증권 뉴스 수집 모듈

구간 지정 분석에 대응하기 위해 뉴스마다 발행일을 함께 수집한다.

발행일 추출 우선순위
  1. URL 의 contentParams.id 끝 14자리 숫자 -> 'edaily_2026092718100300253'
     (월~일, 시각까지 정확) - 6건 중 5건이 이 형식
  2. 목록 행의 '출처 ・ 3시간 전' 상대 표기를 수집 시점으로 환산
  3. 목록 행의 '2026.09.01.' 절대 표기
  4. 전부 실패 -> undated=True (구간 필터가 걸려 있으면 제외)

주의: 토스 종목별 뉴스 목록은 최근 6건만 노출되고 페이지네이션/무한 스크롤이
없다. 그래서 과거 주차(예: 3주 전)를 지정하면 결과가 비게 된다. 비어 있는
것이 틀린 정보보다 정직하므로 그대로 두고, 리포트에 '해당 구간 뉴스 없음'으로
표시한다.
"""
import asyncio
import json
import re
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Optional
from playwright.async_api import async_playwright


class TossNewsCollector:
    """토스증권에서 종목별 뉴스 수집"""

    BASE_URL = "https://tossinvest.com"

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

    def _convert_stock_code(self, stock_code: str, market: str = "KRX") -> str:
        """종목 코드를 토스증권 형식으로 변환"""
        if market == "NASDAQ" or market == "NYSE":
            # 해외 종목: US{코드} 형식
            return f"US{stock_code}"
        else:
            # 국내 종목: A{코드} 형식
            return f"A{stock_code}"

    # --- 발행일 추출 ------------------------------------------------------
    _ID_TS = re.compile(r"_(\d{14})\d*$")
    _ABS_DATE = re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")
    _REL = re.compile(r"(\d+)\s*(분|시간|일|주|개월)")

    _SOURCE_BY_ID = {
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
        "seokyung": "서울경제",
        "moneytoday": "머니투데이",
    }

    @classmethod
    def _content_id(cls, href: str) -> str:
        """href 의 contentParams 에서 id 를 뽑는다"""
        decoded = urllib.parse.unquote(href or "")
        if "contentParams" not in decoded:
            return ""
        match = re.search(r'"id":"([^"]+)"', decoded)
        return match.group(1) if match else ""

    @classmethod
    def _published_at(cls, href: str, meta_text: str, today: date) -> Optional[date]:
        """발행일 산출. 알 수 없으면 None"""
        content_id = cls._content_id(href)
        stamp = cls._ID_TS.search(content_id or "")
        if stamp:
            try:
                return datetime.strptime(stamp.group(1), "%Y%m%d%H%M%S").date()
            except ValueError:
                pass

        text = meta_text or ""
        absolute = cls._ABS_DATE.search(text)
        if absolute:
            try:
                return date(*(int(g) for g in absolute.groups()))
            except ValueError:
                pass

        if "어제" in text:
            return today - timedelta(days=1)
        if "오늘" in text:
            return today

        relative = cls._REL.search(text)
        if relative:
            amount = int(relative.group(1))
            unit = relative.group(2)
            days = {
                "분": 0, "시간": 0, "일": amount,
                "주": amount * 7, "개월": amount * 30,
            }.get(unit)
            if days is not None:
                return today - timedelta(days=days)
        return None

    @classmethod
    def _source_of(cls, content_id: str, meta_text: str) -> str:
        """목록 행 표기(출처 ・ 시각)를 우선, 없으면 contentId 로 추정"""
        if meta_text:
            head = re.split(r"[・|]", meta_text)[0].strip()
            if head and len(head) <= 20 and not head.isdigit():
                return head
        for key, name in cls._SOURCE_BY_ID.items():
            if key in (content_id or ""):
                return name
        return "토스증권"

    _EXTRACT_JS = """() => {
      const out = [];
      const seen = new Set();
      const metaRe = /[・|]/;
      document.querySelectorAll('a[href*="contentType=news"]').forEach(a => {
        const href = a.getAttribute('href') || '';
        if (href.indexOf('contentType=news') === -1) return;
        const title = (a.getAttribute('aria-label') || a.innerText || '').trim();
        if (!title || seen.has(title)) return;
        seen.add(title);
        let meta = '';
        let el = a;
        for (let i = 0; i < 5 && el && !meta; i++) {
          const spans = el.querySelectorAll('span');
          for (let j = 0; j < spans.length; j++) {
            const t = (spans[j].innerText || '').trim();
            if (t && t.length < 60 && metaRe.test(t) &&
                (/(전|어제|오늘)/.test(t) || /20\\d{2}[.\\-/]\\d{1,2}[.\\-/]\\d{1,2}/.test(t))) {
              meta = t;
              break;
            }
          }
          el = el.parentElement;
        }
        out.push({href: href, title: title, meta: meta});
      });
      return out;
    }"""

    async def get_news(
        self,
        stock_code: str,
        count: int = 3,
        market: str = "KRX",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> list:
        """종목별 뉴스 수집

        `start`/`end`(YYYY-MM-DD)를 주면 그 구간에 발행된 기사만 남긴다.
        발행일을 모르는 항목(undated)은 구간 필터가 걸려 있으면 제외한다.
        """
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

            today = date.today()
            lo = self._parse_bound(start)
            hi = self._parse_bound(end)
            filtering = lo is not None or hi is not None

            news_items = []
            seen_titles = set()

            try:
                raw_items = await page.evaluate(self._EXTRACT_JS)
            except Exception:
                raw_items = []

            for raw in raw_items:
                try:
                    href = raw.get("href") or ""
                    title = (raw.get("title") or "").strip()
                    meta_text = (raw.get("meta") or "").strip()

                    if len(title) < 10 or title in seen_titles:
                        continue
                    if re.match(r'^[\d,]+원', title) or title.startswith('+') or title.startswith('-'):
                        continue

                    published = self._published_at(href, meta_text, today)
                    if filtering and (published is None or not self._in_range(published, lo, hi)):
                        continue

                    seen_titles.add(title)
                    full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    news_items.append({
                        "title": title,
                        "link": full_url,
                        "source": self._source_of(self._content_id(href), meta_text),
                        "time": published.strftime("%Y-%m-%d") if published else "",
                        "pub_date": published.isoformat() if published else "",
                        "undated": published is None,
                        "content_id": self._content_id(href),
                    })

                    if len(news_items) >= count:
                        break
                except Exception:
                    continue

            # 뉴스가 부족하면 페이지 텍스트에서 추출 (발행일 미상)
            if len(news_items) < count and not filtering:
                news_items.extend(
                    self._scrape_fallback(page, url, seen_titles, count - len(news_items))
                )

            return news_items[:count]

        except Exception as e:
            print(f"토스증권 뉴스 수집 오류 ({stock_code}): {e}")
            return []
        finally:
            await page.close()

    @staticmethod
    def _parse_bound(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _in_range(day: date, lo: Optional[date], hi: Optional[date]) -> bool:
        if lo and day < lo:
            return False
        if hi and day > hi:
            return False
        return True

    _FALLBACK_SOURCES = {
        "[이데일리": "이데일리", "[한국경제": "한국경제", "[매일경제": "매일경제",
        "[파이낸셜뉴스": "파이낸셜뉴스", "[연합뉴스": "연합뉴스", "[뉴스핌": "뉴스핌",
        "[뉴스1": "뉴스1", "[YTN": "YTN", "[SBS": "SBS", "[MBN": "MBN",
        "[채널A": "채널A", "[JTBC": "JTBC", "[KBS": "KBS", "[MBC": "MBC",
        "[조선비즈": "조선비즈", "[아시아경제": "아시아경제", "[서울신문": "서울신문",
        "[한겨레": "한겨레", "[중앙일보": "중앙일보", "[동아일보": "동아일보",
        "[세계일보": "세계일보", "[스포츠서울": "스포츠서울", "[ 증시": "토스증권",
        "[마켓뷰": "토스증권", "[오늘의": "토스증권", "[모닝": "토스증권",
        "[리포트": "토스증권", "[핫이슈": "토스증권", "[종목": "토스증권",
    }

    _FALLBACK_KEYWORDS = [
        "삼성전자", "SK하이닉스", "NAVER", "카카오", "반도체", "증시", "투자",
        "코스피", "코스닥", "금리", "실적", "배당", "전망", "분석",
    ]

    async def _scrape_fallback(self, page, url: str, seen_titles: set, limit: int) -> list:
        """목록 파싱 실패 시 본문 라인에서 대체 수집 (발행일 미상)"""
        if limit <= 0:
            return []
        try:
            content = await page.inner_text("body")
        except Exception:
            return []

        out = []
        for line in content.split("\n"):
            line = line.strip()
            if not (len(line) > 20 and line not in seen_titles and not line.startswith("http")
                    and "로그인" not in line and "원)" not in line
                    and "investing" not in line.lower()):
                continue
            if not any(keyword in line for keyword in self._FALLBACK_KEYWORDS):
                continue

            source = "토스증권"
            title = line
            for pattern, name in self._FALLBACK_SOURCES.items():
                if pattern in line:
                    source = name
                    title = re.sub(r'\[.*?\]\s*', '', line).strip()
                    break

            seen_titles.add(line)
            out.append({
                "title": title[:100],
                "link": url,
                "source": source,
                "time": "",
                "pub_date": "",
                "undated": True,
            })
            if len(out) >= limit:
                break
        return out

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
