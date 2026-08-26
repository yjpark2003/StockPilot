# -*- coding: utf-8 -*-
"""해외 주식 데이터 수집 모듈 (yfinance)"""
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional


class YfinanceCollector:
    """yfinance를 사용한 해외 주식 데이터 수집"""

    def __init__(self):
        pass

    async def close(self):
        """리소스 정리 (yfinance는 별도 리소스 없음)"""
        pass

    async def get_weekly_price(self, ticker: str, currency: str = "USD") -> dict:
        """최근 1주간 주가 변동 데이터 수집"""
        try:
            stock = yf.Ticker(ticker)

            # 최근 5일 데이터
            hist = stock.history(period="5d", interval="1d")
            if hist.empty:
                return self._get_empty_price(ticker)

            weekly_data = []
            for date, row in hist.iterrows():
                weekly_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })

            # 날짜 순서대로 정렬 (오래된 날짜가 왼쪽)
            weekly_data.sort(key=lambda x: x["date"])

            # 주간 변동률 계산
            if len(weekly_data) >= 2:
                start_price = weekly_data[0]["close"]
                end_price = weekly_data[-1]["close"]
                change_rate = ((end_price - start_price) / start_price) * 100
            elif len(weekly_data) == 1:
                start_price = end_price = weekly_data[0]["close"]
                change_rate = 0.0
            else:
                start_price = end_price = 0
                change_rate = 0.0

            # 현재가 (info에서 가져오기)
            try:
                info = stock.info
                current_price = info.get("currentPrice") or info.get("regularMarketPrice") or end_price
            except Exception:
                current_price = end_price

            return {
                "current_price": round(float(current_price), 2),
                "weekly_data": weekly_data,  # 날짜 순서대로 (오래된 날짜가 왼쪽)
                "change_rate": round(change_rate, 2),
                "start_price": start_price,
                "end_price": end_price,
                "currency": currency,
            }
        except Exception as e:
            print(f"yfinance 가격 수집 오류 ({ticker}): {e}")
            return self._get_empty_price(ticker)

    async def get_news(self, ticker: str, count: int = 3) -> list:
        """종목 관련 뉴스 수집"""
        try:
            stock = yf.Ticker(ticker)
            news = stock.news

            news_items = []
            if news:
                for item in news[:count]:
                    # yfinance 뉴스 구조: {id, content: {title, provider, canonicalUrl, ...}}
                    content = item.get("content", {})
                    
                    title = content.get("title", "")
                    provider = content.get("provider", {})
                    publisher = provider.get("displayName", "") if provider else ""
                    
                    canonical_url = content.get("canonicalUrl", {})
                    link = canonical_url.get("url", "") if canonical_url else ""
                    
                    # 발행 시간
                    pub_time = content.get("pubDate", "")
                    if pub_time:
                        # ISO 형식 파싱 시도
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
                            publish_time = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            publish_time = pub_time[:16]
                    else:
                        publish_time = ""

                    if title:
                        news_items.append({
                            "title": title,
                            "link": link,
                            "source": publisher,
                            "time": f"{publisher} | {publish_time}" if publisher else publish_time,
                        })
            return news_items
        except Exception as e:
            print(f"yfinance 뉴스 수집 오류 ({ticker}): {e}")
            return []

    async def get_financial_summary(self, ticker: str) -> dict:
        """재무 요약 데이터 수집 (PER, PBR, 시가총액 등)"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            return {
                "per": self._format_number(info.get("trailingPE")),
                "forward_pe": self._format_number(info.get("forwardPE")),
                "pbr": self._format_number(info.get("priceToBook")),
                "market_cap": self._format_market_cap(info.get("marketCap")),
                "dividend_yield": self._format_percent(info.get("dividendYield")),
                "52_week_high": self._format_number(info.get("fiftyTwoWeekHigh")),
                "52_week_low": self._format_number(info.get("fiftyTwoWeekLow")),
                "beta": self._format_number(info.get("beta")),
                "eps": self._format_number(info.get("trailingEps")),
            }
        except Exception as e:
            print(f"yfinance 재무 데이터 수집 오류 ({ticker}): {e}")
            return {
                "per": "N/A", "forward_pe": "N/A", "pbr": "N/A",
                "market_cap": "N/A", "dividend_yield": "N/A",
                "52_week_high": "N/A", "52_week_low": "N/A",
                "beta": "N/A", "eps": "N/A",
            }

    async def get_short_interest(self, ticker: str) -> dict:
        """공매도/숏 포지션 데이터 수집"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # 공매도 관련 데이터
            short_ratio = info.get("shortRatio")
            short_percent = info.get("shortPercentOfFloat")
            shares_short = info.get("sharesShort")
            shares_outstanding = info.get("sharesOutstanding")
            float_shares = info.get("floatShares")
            
            # 거래량 데이터
            avg_volume = info.get("averageVolume")
            avg_volume_10d = info.get("averageVolume10days")
            current_volume = info.get("volume")

            # 숏 커버링 일수 계산
            short_covering_days = None
            if short_ratio and short_ratio > 0:
                short_covering_days = round(float(short_ratio), 2)

            return {
                "short_ratio": self._format_number(short_ratio),
                "short_percent": self._format_percent(short_percent),
                "shares_short": self._format_large_number(shares_short),
                "shares_outstanding": self._format_large_number(shares_outstanding),
                "float_shares": self._format_large_number(float_shares),
                "short_covering_days": f"{short_covering_days}일" if short_covering_days else "N/A",
                "avg_volume": self._format_large_number(avg_volume),
                "avg_volume_10d": self._format_large_number(avg_volume_10d),
                "current_volume": self._format_large_number(current_volume),
                "sentiment": self._calculate_sentiment(short_percent, short_ratio),
            }
        except Exception as e:
            print(f"yfinance 공매도 데이터 수집 오류 ({ticker}): {e}")
            return {
                "short_ratio": "N/A", "short_percent": "N/A",
                "shares_short": "N/A", "shares_outstanding": "N/A",
                "float_shares": "N/A", "short_covering_days": "N/A",
                "avg_volume": "N/A", "avg_volume_10d": "N/A",
                "current_volume": "N/A", "sentiment": "중립",
            }

    def _calculate_sentiment(self, short_percent, short_ratio) -> str:
        """숏 포지션 기반 센티먼트 계산"""
        try:
            if short_percent is None or short_ratio is None:
                return "중립"
            
            short_pct = float(short_percent) * 100
            ratio = float(short_ratio)
            
            if short_pct > 20 or ratio > 10:
                return "매우 높은 숏 (주의)"
            elif short_pct > 10 or ratio > 5:
                return "높은 숏"
            elif short_pct > 5 or ratio > 2:
                return "보통"
            elif short_pct > 2:
                return "낮은 숏 (긍정적)"
            else:
                return "매우 낮은 숏 (매우 긍정적)"
        except:
            return "중립"

    def _format_large_number(self, value) -> str:
        """큰 숫자 포맷팅"""
        if value is None:
            return "N/A"
        try:
            value = float(value)
            if value >= 1e12:
                return f"{value/1e12:,.2f}T"
            elif value >= 1e9:
                return f"{value/1e9:,.2f}B"
            elif value >= 1e6:
                return f"{value/1e6:,.2f}M"
            elif value >= 1e3:
                return f"{value/1e3:,.1f}K"
            else:
                return f"{value:,.0f}"
        except (ValueError, TypeError):
            return "N/A"

    def _format_number(self, value) -> str:
        """숫자 포맷팅"""
        if value is None:
            return "N/A"
        try:
            return f"{float(value):,.2f}"
        except (ValueError, TypeError):
            return "N/A"

    def _format_market_cap(self, value) -> str:
        """시가총액 포맷팅 (조 단위)"""
        if value is None:
            return "N/A"
        try:
            value = float(value)
            if value >= 1e12:
                return f"${value/1e12:,.2f}T"
            elif value >= 1e9:
                return f"${value/1e9:,.2f}B"
            elif value >= 1e6:
                return f"${value/1e6:,.2f}M"
            else:
                return f"${value:,.0f}"
        except (ValueError, TypeError):
            return "N/A"

    def _format_percent(self, value) -> str:
        """백분율 포맷팅"""
        if value is None:
            return "N/A"
        try:
            return f"{float(value)*100:.2f}%"
        except (ValueError, TypeError):
            return "N/A"

    def _get_empty_price(self, ticker: str) -> dict:
        return {
            "current_price": 0, "weekly_data": [], "change_rate": 0.0,
            "start_price": 0, "end_price": 0, "currency": "USD",
        }
