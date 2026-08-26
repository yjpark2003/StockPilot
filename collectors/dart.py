# -*- coding: utf-8 -*-
"""DART 전자공시 데이터 수집 모듈"""
import requests
from datetime import datetime, timedelta
from typing import Optional


class DartCollector:
    """DART에서 공시 데이터 수집"""

    BASE_URL = "https://opendart.fss.or.kr/api"
    API_KEY = ""  # DART API 키 (무료 발급: https://opendart.fss.or.kr)

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or self.API_KEY
        self.session = requests.Session()

    def get_disclosures(self, stock_code: str, count: int = 5) -> list:
        """최근 공시 데이터 수집"""
        if not self.api_key:
            return self._get_mock_disclosures(stock_code, count)

        try:
            url = f"{self.BASE_URL}/list.json"
            params = {
                "crtfc_key": self.api_key,
                "stock_code": stock_code,
                "page_count": count,
            }
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()

            disclosures = []
            for item in data.get("list", [])[:count]:
                disclosures.append({
                    "title": item.get("report_nm", ""),
                    "date": item.get("rcept_dt", ""),
                    "type": item.get("flr_nm", ""),
                    "link": f"https://dart.fss.or.kr/dsaf001/main.do?rcp_no={item.get('rcept_no', '')}",
                })
            return disclosures
        except Exception as e:
            print(f"DART API 오류: {e}")
            return self._get_mock_disclosures(stock_code, count)

    def _get_mock_disclosures(self, stock_code: str, count: int) -> list:
        """API 키가 없을 때 목업 데이터 반환"""
        return [
            {
                "title": f"[{stock_code}] 사업보고서 (목업 데이터 - API 키 설정 필요)",
                "date": datetime.now().strftime("%Y%m%d"),
                "type": "사업보고서",
                "link": "https://dart.fss.or.kr",
            }
        ]

    def get_financial_statements(self, stock_code: str) -> dict:
        """재무제표 데이터 수집"""
        if not self.api_key:
            return {"error": "API 키가 설정되지 않았습니다."}

        try:
            url = f"{self.BASE_URL}/fnSingl.json"
            params = {
                "crtfc_key": self.api_key,
                "stock_code": stock_code,
                "reprt_code": "11011",  # 사업보고서
                "fs_div": "OFS",  # 연결재무제표
            }
            resp = self.session.get(url, params=params, timeout=10)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
