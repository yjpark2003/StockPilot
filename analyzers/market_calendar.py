"""거래 시장 휴장일 달력.

`analyzers/period.py` 는 한동안 "평일이면 거래일"로 가정했으나 실제로는
휴장일이 있다. 예를 들어 2026-09-24(목)·25(금) 는 추석 연휴로 국내 증시가
닫혔는데도 거래일로 세면 (1) 거래일 개수가 과대 계산되고 (2) 실제로는
정상인데도 '구간 일부 미수집' 오탐 경고가 뜬다.

국내(KRX) 휴장일은 `^KS11` 지수의 실제 거래일과 대조해 검증한 표를 쓴다.
음력 공휴일(설·추석·부처님오신날)과 대체공휴일, 명절이 아닌 임시공휴일
까지 표에 포함되므로 규칙 계산만으로는 재현되지 않는다. 표에 없는 연도는
고정공휴일만 계산하므로 정확도가 떨어진다(`kr_calendar_is_exact` 참조).

해외(미국)는 고정공휴일이 모두 규칙으로 계산되므로 연도 제한이 없다.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Set

MARKET_KR = "kr"
MARKET_US = "us"

MARKET_LABELS = {
    MARKET_KR: "국내",
    MARKET_US: "해외",
}

# 실제 휴장일로 검증된 KRX 휴장일 (연도 -> [(월, 일), ...])
# 2023~2026년 9/28 이전은 `^KS11` 거래일과 대조해 확인했다.
# 2026년 10/12월은 아직 발생하지 않아 KRX 공휴일 예정일 기준이다.
_KR_HOLIDAYS: Dict[int, tuple] = {
    2023: ((1, 23), (1, 24), (3, 1), (5, 1), (5, 5), (5, 29), (6, 6),
           (8, 15), (9, 28), (9, 29), (10, 2), (10, 3), (10, 9),
           (12, 25), (12, 29)),
    2024: ((1, 1), (2, 9), (2, 12), (3, 1), (4, 10), (5, 1), (5, 6),
           (5, 15), (6, 6), (8, 15), (9, 16), (9, 17), (9, 18),
           (10, 1), (10, 3), (10, 9), (12, 25), (12, 31)),
    2025: ((1, 1), (1, 27), (1, 28), (1, 29), (1, 30), (3, 3), (5, 1),
           (5, 5), (5, 6), (6, 3), (6, 6), (8, 15), (10, 3), (10, 6),
           (10, 7), (10, 8), (10, 9), (12, 25), (12, 31)),
    2026: ((1, 1), (2, 16), (2, 17), (2, 18), (3, 2), (5, 1), (5, 5),
           (5, 25), (6, 3), (7, 17), (8, 17), (9, 24), (9, 25),
           (10, 5), (10, 9), (12, 25), (12, 31)),
}

# 표가 없는 연도에서 쓸 고정공휴일 (음력 공휴일 제외)
_KR_FIXED_RULE = ((1, 1), (3, 1), (5, 1), (5, 5), (6, 6), (8, 15),
                  (10, 3), (10, 9), (12, 25))


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """연도/month의 n번째 weekday(0=월) 날짜"""
    first = dt.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + dt.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    """연도/month의 마지막 weekday 날짜"""
    if month == 12:
        last = dt.date(year, 12, 31)
    else:
        last = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def _easter_sunday(year: int) -> dt.date:
    """그레고리력 부활절 (익명 알고리즘)"""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    day = ((h + m - 7 * n + 114) % 31) + 1
    return dt.date(year, month, day)


def _observed(day: dt.date) -> dt.date:
    """NYSE 관행: 토요일 공휴일은 금요일, 일요일 공휴일은 월요일로 observance"""
    if day.weekday() == 5:
        return day - dt.timedelta(days=1)
    if day.weekday() == 6:
        return day + dt.timedelta(days=1)
    return day


def kr_holidays(year: int) -> Set[dt.date]:
    """국내(KRX) 휴장일"""
    table = _KR_HOLIDAYS.get(year)
    if table is not None:
        return {dt.date(year, m, d) for m, d in table}
    days = {dt.date(year, m, d) for m, d in _KR_FIXED_RULE}
    for m, d in _KR_FIXED_RULE:
        day = dt.date(year, m, d)
        if day.weekday() == 6:  # 일요일과 겹치면 다음 날 대체공휴일
            days.add(day + dt.timedelta(days=1))
    return days


def kr_calendar_is_exact(year: int) -> bool:
    """해당 연도의 국내 달력이 실제 휴장일로 검증되었는지"""
    return year in _KR_HOLIDAYS


def us_holidays(year: int) -> Set[dt.date]:
    """미국(NYSE/Nasdaq) 휴장일. 전부 규칙으로 계산된다."""
    easter = _easter_sunday(year)
    days = {
        _observed(dt.date(year, 1, 1)),                      # 신정
        _nth_weekday(year, 1, 0, 3),                        # 마틴 루서 킹 데이
        _nth_weekday(year, 2, 0, 3),                        # 링컨 데이
        easter - dt.timedelta(days=2),                      # 굵은 금요일
        _last_weekday(year, 5, 0),                          # 메모리얼 데이
        _observed(dt.date(year, 6, 19)),                    # 준틴스스
        _observed(dt.date(year, 7, 4)),                     # 독립기념일
        _nth_weekday(year, 9, 0, 1),                        # 노동절
        _nth_weekday(year, 11, 3, 4),                       # 추수감사절
        _observed(dt.date(year, 12, 25)),                   # 성탄절
    }
    # 규칙으로 예측할 수 없는 개별 휴장. 2025-01-09 는 제프 카터 제9대 대통령
    # 국장 조기로 NYSE 가 임시 휴장했다 (^GSPC 거래일 대조로 확인).
    days.add(dt.date(2025, 1, 9))
    return {d for d in days if d.year == year}


_HOLIDAYS = {MARKET_KR: kr_holidays, MARKET_US: us_holidays}


def holidays(year: int, market: str = MARKET_KR) -> Set[dt.date]:
    """시장별 휴장일"""
    fn = _HOLIDAYS.get(market, kr_holidays)
    return fn(year)


def is_trading_day(day: dt.date, market: str = MARKET_KR) -> bool:
    """휴장일을 제외한 실제 거래일 여부"""
    if day.weekday() >= 5:
        return False
    return day not in holidays(day.year, market)


def trading_days(start: dt.date, end: dt.date, market: str = MARKET_KR) -> List[dt.date]:
    """[start, end] 구간의 거래일 (오래된 순). 휴장일/주말 제외."""
    out: List[dt.date] = []
    cursor = start
    while cursor <= end:
        if is_trading_day(cursor, market):
            out.append(cursor)
        cursor += dt.timedelta(days=1)
    return out


def last_trading_days(end: dt.date, count: int = 5,
                      market: str = MARKET_KR) -> List[dt.date]:
    """end(含)까지 거슬러 올라가며 최근 count개 거래일 (오래된 순)"""
    out: List[dt.date] = []
    cursor = end
    guard = 0
    while len(out) < count and guard < count * 7 + 30:
        if is_trading_day(cursor, market):
            out.append(cursor)
        cursor -= dt.timedelta(days=1)
        guard += 1
    return list(reversed(out))


# 한국 시간. KST 는 UTC+9 로 고정이라 시각 계산이 단순하다.
KST = dt.timezone(dt.timedelta(hours=9))
KR_CLOSE = dt.time(15, 30)      # KRX 정규장 마감 (KST)
US_CLOSE_KST = dt.time(6, 0)    # 미국 정규장 마감 = KST 다음날 06:00 근사


def last_closed_trading_day(market: str = MARKET_KR,
                            now: Optional[dt.datetime] = None) -> dt.date:
    """이미 마감된 마지막 거래일.

    아직 장이 끝나지 않은 날을 구간에 넣으면 아직 공개되지 않은 데이터를
    수집하려고 시도해 '구간 일부 미수집' 오탐이 나고,国内外 구간의 날짜가
    어긋난다. 그래서 시장별 마감 시각을 고려해 구간을 자른다.
    """
    now = now or dt.datetime.now(KST)
    today = now.date()
    if market == MARKET_KR:
        cand = today if now.timetz().replace(tzinfo=None) >= KR_CLOSE \
            else today - dt.timedelta(days=1)
    else:
        # 미국 정규장은 KST 저녁에 개장하므로 '어제'까지가 마감 대상이다.
        # 새벽 6시 이전이면 그 전날 장도 아직 끝나지 않았다.
        cand = today - dt.timedelta(days=1)
        if now.timetz().replace(tzinfo=None) < US_CLOSE_KST:
            cand -= dt.timedelta(days=1)
    return last_trading_days(cand, 1, market)[0]
