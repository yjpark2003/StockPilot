# -*- coding: utf-8 -*-
"""국내 종목 한글명 검색 모듈"""
import os
import re
from typing import Optional

import yaml

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "korean_stocks.yaml"
)

_stocks: Optional[dict] = None
_by_code: Optional[dict] = None


def _load() -> dict:
    """한글명 매핑 테이블 로드 (프로세스 내 1회 캐시)"""
    global _stocks
    if _stocks is None:
        data = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            data = config.get("stocks", {}) or {}
        _stocks = data
    return _stocks


def _code_index() -> dict:
    """종목코드 -> 한글명/시장 인덱스 (프로세스 내 1회 캐시)"""
    global _by_code
    if _by_code is None:
        index = {}
        for name, info in _load().items():
            code = str(info.get("code", ""))
            if code and code not in index:
                index[code] = {
                    "name": name,
                    "code": code,
                    "market": info.get("market", "KOSPI"),
                }
        _by_code = index
    return _by_code


def normalize(text: str) -> str:
    """검색어 정규화 (공백·특수문자 제거, 소문자화)"""
    return re.sub(r"[^0-9a-z가-힣]", "", (text or "").lower())


def search_stocks(query: str, limit: int = 10) -> list:
    """한글명/종목코드로 국내 종목 검색 (부분 일치)

    검색어와 정확히 일치 > 이름으로 시작 > 이름 포함 > 코드 포함 순으로 정렬
    """
    normalized = normalize(query)
    if not normalized:
        return []

    exact, prefix, contains, by_code = [], [], [], []

    for name, info in _load().items():
        code = str(info.get("code", ""))
        item = {
            "name": name,
            "code": code,
            "market": info.get("market", "KOSPI"),
        }
        name_normalized = normalize(name)

        if name_normalized == normalized or code == normalized:
            exact.append(item)
        elif name_normalized.startswith(normalized):
            prefix.append(item)
        elif normalized in name_normalized:
            contains.append(item)
        elif normalized in code:
            by_code.append(item)

    results = exact + prefix + contains + by_code
    return results[:limit]


def find_by_code(code: str) -> Optional[dict]:
    """종목코드로 한글명/시장 조회"""
    target = str(code).strip()
    if not target:
        return None
    return _code_index().get(target)


def get_name(code: str) -> str:
    """종목코드에 대응하는 한글명 (없으면 빈 문자열)"""
    found = find_by_code(code)
    return found["name"] if found else ""
