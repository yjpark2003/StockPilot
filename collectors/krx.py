# -*- coding: utf-8 -*-
"""한국거래소(KRX) 데이터 수집 모듈"""
import requests
from datetime import datetime, timedelta
from typing import Optional


class KrxCollector:
    """한국거래소에서 시장 데이터 수집"""

    DATA_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://data.krx.co.kr/",
        })

    def get_market_data(self, stock_code: str) -> dict:
        """시장 데이터 수집 (거래량, 시가총액 등)"""
        try:
            # KRX REST API 호출
            date_str = datetime.now().strftime("%Y%m%d")
            params = {
                "bld": "dbms/MDC/STAT/developer/MDCAnal01001M01",
                "locale": "ko_KR",
                "mktId": "STK",
                "sectId": "",
                "quotes": stock_code,
                "requestTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            resp = self.session.get(self.DATA_URL, params=params, timeout=10)

            # JSON 응답 확인
            content_type = resp.headers.get("Content-Type", "")
            if "json" not in content_type and not resp.text.strip().startswith("{"):
                print(f"KRX: JSON 응답 아님 ({content_type})")
                return self._get_empty_data(stock_code)

            data = resp.json()

            if "OutBlock_1" in data and data["OutBlock_1"]:
                item = data["OutBlock_1"][0]
                return {
                    "stock_code": stock_code,
                    "current_price": int(item.get("TDD_CLSPRC", 0)),
                    "change_rate": float(item.get("TDD_OPNPRC", 0)),
                    "volume": int(item.get("ACC_TRDVOL", 0)),
                    "trade_value": int(item.get("ACC_TRDVAL", 0)),
                    "market_cap": int(item.get("MKTCAP", 0)),
                }
            return self._get_empty_data(stock_code)
        except Exception as e:
            print(f"KRX 데이터 수집 오류: {e}")
            return self._get_empty_data(stock_code)

    def get_weekly_volume(self, stock_code: str, days: int = 5) -> list:
        """최근 N거래일 거래량 데이터"""
        try:
            date_str = datetime.now().strftime("%Y%m%d")
            params = {
                "bld": "dbms/MDC/STAT/developer/MDCAnal01001M01",
                "locale": "ko_KR",
                "mktId": "STK",
                "sectId": "",
                "quotes": stock_code,
            }
            resp = self.session.get(self.DATA_URL, params=params, timeout=10)
            data = resp.json()

            weekly_volume = []
            if "OutBlock_1" in data:
                for item in data["OutBlock_1"][:days]:
                    weekly_volume.append({
                        "date": item.get("TRD_DD", ""),
                        "volume": int(item.get("ACC_TRDVOL", 0)),
                        "trade_value": int(item.get("ACC_TRDVAL", 0)),
                    })
            return weekly_volume
        except Exception as e:
            print(f"KRX 주간 거래량 수집 오류: {e}")
            return []

    def _get_empty_data(self, stock_code: str) -> dict:
        return {
            "stock_code": stock_code,
            "current_price": 0,
            "change_rate": 0.0,
            "volume": 0,
            "trade_value": 0,
            "market_cap": 0,
        }
