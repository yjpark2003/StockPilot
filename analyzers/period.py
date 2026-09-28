# -*- coding: utf-8 -*-
"""주간 분석 구간(period) 정의 - 라벨·데이터 수집·저장의 단일 소스

구간 규칙
  * 지정 구간(custom): 사용자가 연/월/주차 또는 시작일·종료일로 직접 고른다.
    예) 2026년 9월 1주차 -> 08/31(월) ~ 09/06(일)
  * 토/일(weekend)에 분석을 요청하면 "이번 주 월~일" 전체를 분석한다.
    예) 2026-09-27(일) 요청 -> 09/21(월) ~ 09/27(일), 거래일 09/21~09/23
    (09/24·25 는 추석 연휴 휴장일)
  * 평일(weekday)에 분석을 요청하면 "최근 5거래일"을 분석한다.
    구간은 요청일이 아니라 *마감된* 마지막 거래일까지 거슬러 계산한다
    (국내 15:30 KST 전이면 당일은 제외).
    예) 2026-09-28(월) 10시 요청 -> 09/17(목) ~ 09/23(수),
        거래일 09/17,18,21,22,23 (09/24·25 는 추석 연휴)

거래일은 `market_calendar` 의 휴장일 달력을 따른다. 주말/휴장일을 거래일로 세면
거래일 개수가 과대 계산되고 '구간 일부 미수집' 오탐 경고가 뜬다.
아직 마감되지 않은 세션(국내 15:30 KST, 미국 KST 다음날 06:00 기준)도
구간에서 제외하므로, 아직 공개되지 않은 데이터를 요구하지 않는다.
"""
import calendar
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Iterable, List, Optional, Sequence

from analyzers.market_calendar import (
    MARKET_KR,
    MARKET_LABELS,
    MARKET_US,
    is_trading_day,
    last_closed_trading_day,
    trading_days as _market_trading_days,
)

WEEKDAY_KO = ("월", "화", "수", "목", "금", "토", "일")
TRADING_DAY_COUNT = 5

MODE_WEEK = "week"
MODE_ROLLING = "rolling"
MODE_CUSTOM = "custom"

MODE_LABELS = {
    MODE_WEEK: "주간 마감",
    MODE_ROLLING: "주중 스냅샷",
    MODE_CUSTOM: "지정 구간",
}

# 월 내 "n주차"가 가리키는 기준일 (1주차=1일, 2주차=8일, ...)
MONTH_WEEK_ANCHORS = (1, 8, 15, 22, 29)
MAX_MONTH_WEEK = len(MONTH_WEEK_ANCHORS)

# 지정 구간의 상한. 주간 분석이라는 목적상 한 달치를 넘으면 의미가 없다.
MAX_RANGE_DAYS = 45


class PeriodError(ValueError):
    """구간 지정이 잘못되었을 때"""


def _is_trading_day(day: date, market: str = MARKET_KR) -> bool:
    """휴장일·주말을 제외한 실제 거래일 여부"""
    return is_trading_day(day, market)


def _last_trading_days(end: date, count: int = TRADING_DAY_COUNT,
                       market: str = MARKET_KR) -> List[date]:
    """end(含)까지 거슬러 올라가며 최근 `count`개 거래일 수집 (오래된 순)"""
    days: List[date] = []
    cursor = end
    guard = 0
    while len(days) < count and guard < count * 7 + 30:
        if _is_trading_day(cursor, market):
            days.append(cursor)
        cursor -= timedelta(days=1)
        guard += 1
    return list(reversed(days))


def _week_window(run_date: date) -> tuple:
    """run_date가 속한 주의 월~일 구간 (일요일 기준 주의 끝)"""
    monday = run_date - timedelta(days=run_date.weekday())
    return monday, monday + timedelta(days=6)


def _weekdays_in_range(start: date, end: date, market: str = MARKET_KR) -> List[date]:
    """[start, end] 구간의 거래일만 오래된 순으로"""
    return _market_trading_days(start, end, market)


def _iso_week_window(year: int, week: int) -> tuple:
    """ISO 주차(year, week)의 월~일 구간"""
    max_week = date(year, 12, 28).isocalendar()[1]
    if not 1 <= week <= max_week:
        raise PeriodError(f"{year}년은 {max_week}주차까지 있습니다 (요청: {week}주차)")
    monday = date.fromisocalendar(year, week, 1)
    return monday, monday + timedelta(days=6)


def _month_week_anchor(year: int, month: int, nth: int) -> date:
    """월 내 n주차의 기준일.

    1주차=1일, 2주차=8일, ... 5주차=29일을 기준으로 삼고, 그 날짜가 속한
    ISO 주(월~일)를 구간으로 쓴다. 그래서 2026년 9월 1주차는 09/01(화)이
    속한 ISO 36주차인 08/31(월)~09/06(일)이 된다.
    """
    if not 1 <= month <= 12:
        raise PeriodError(f"월은 1~12월까지입니다 (요청: {month}월)")
    if not 1 <= nth <= MAX_MONTH_WEEK:
        raise PeriodError(f"주차는 1~{MAX_MONTH_WEEK}주차까지입니다 (요청: {nth}주차)")
    last_day = calendar.monthrange(year, month)[1]
    day = min(MONTH_WEEK_ANCHORS[nth - 1], last_day)
    return date(year, month, day)


@dataclass(frozen=True)
class WeeklyPeriod:
    """주간 분석 구간. `start`/`end`는 달력일, `trading_days`는 실제 거래일."""

    start: date
    end: date
    trading_days: tuple
    mode: str = "week"
    run_date: Optional[date] = None
    # 구간의 기준 시장. trading_days/라벨은 이 시장의 휴장일 달력을 따른다.
    # 국내/해외 휴장일이 달라(`trading_days_for` 참고) 시장별로 달라진다.
    market: str = MARKET_KR

    # --- 거래일 -----------------------------------------------------------
    def trading_days_for(self, market: Optional[str] = None) -> tuple:
        """해당 시장 기준으로 거래일을 다시 계산한다.

        `trading_days` 는 구간의 기준 시장 값이라 그대로 쓰면 overseas 종목에
        국내 휴장일을 유효 거래일로 잘못 센다. 추석에 미국은 거래하므로
        종목별 시장으로 다시 계산한다.
        """
        target = market or self.market
        if target == self.market:
            return self.trading_days
        return tuple(_market_trading_days(self.start, self.end, target))

    def with_market(self, market: str) -> "WeeklyPeriod":
        """기준 시장만 바꾸어 반환 (거래일도 새 시장 달력으로 다시 계산)"""
        if market == self.market:
            return self
        return WeeklyPeriod(
            start=self.start,
            end=self.end,
            trading_days=tuple(_market_trading_days(self.start, self.end, market)),
            mode=self.mode,
            run_date=self.run_date,
            market=market,
        )

    # --- 주차 정보 -------------------------------------------------------
    @property
    def iso_year(self) -> int:
        return self.end.isocalendar()[0]

    @property
    def iso_week(self) -> int:
        return self.end.isocalendar()[1]

    @property
    def year_week_label(self) -> str:
        """'2026년 39주차'"""
        return f"{self.iso_year}년 {self.iso_week}주차"

    # --- 표기 ------------------------------------------------------------
    @property
    def market_label(self) -> str:
        """구간의 기준 시장 표기"""
        return MARKET_LABELS.get(self.market, self.market)

    @property
    def range_label(self) -> str:
        """'09/21(월) ~ 09/27(일)' (연도가 다르면 연도 포함)"""
        left = format_korean_date(self.start, with_year=self.start.year != self.end.year)
        right = format_korean_date(self.end)
        return f"{left} ~ {right}"

    @property
    def trading_label(self) -> str:
        """'거래일 09/21~09/23 (3일)'"""
        return self.trading_label_for(self.market)

    def trading_label_for(self, market: Optional[str] = None) -> str:
        """해당 시장 기준 거래일 라벨.

        휴장일이 시장마다 달라 두 시장 라벨이 다를 수 있다. 예) 추석 연휴
        2026-09-24·25 에 국내는 3거래일, 미국은 5거래일이다.
        """
        days = self.trading_days_for(market)
        if not days:
            return "거래일 없음"
        head = days[0]
        tail = days[-1]
        return f"거래일 {head.strftime('%m/%d')}~{tail.strftime('%m/%d')} ({len(days)}일)"

    @property
    def markets_differ(self) -> bool:
        """국내/해외 거래일 개수가 다른지 (휴장일 차이)"""
        return (len(self.trading_days_for(MARKET_KR))
                != len(self.trading_days_for(MARKET_US)))

    @property
    def mode_label(self) -> str:
        return MODE_LABELS.get(self.mode, MODE_LABELS[MODE_WEEK])

    @property
    def is_custom(self) -> bool:
        """사용자가 직접 지정한 구간인지"""
        return self.mode == MODE_CUSTOM

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "trading_days": [d.isoformat() for d in self.trading_days],
            # 국내/해외 휴장일이 달라 거래일이 다를 수 있으므로 둘 다 남긴다.
            "trading_days_domestic": [d.isoformat() for d in self.trading_days_for(MARKET_KR)],
            "trading_days_foreign": [d.isoformat() for d in self.trading_days_for(MARKET_US)],
            "trading_label_domestic": self.trading_label_for(MARKET_KR),
            "trading_label_foreign": self.trading_label_for(MARKET_US),
            "markets_differ": self.markets_differ,
            "market": self.market,
            "mode": self.mode,
            "run_date": self.run_date.isoformat() if self.run_date else None,
            "iso_year": self.iso_year,
            "iso_week": self.iso_week,
            "year_week_label": self.year_week_label,
            "range_label": self.range_label,
            "trading_label": self.trading_label,
            "mode_label": self.mode_label,
            "is_custom": self.is_custom,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Optional["WeeklyPeriod"]:
        if not data or not data.get("start") or not data.get("end"):
            return None
        try:
            return cls(
                start=date.fromisoformat(data["start"]),
                end=date.fromisoformat(data["end"]),
                trading_days=tuple(date.fromisoformat(d) for d in data.get("trading_days", [])),
                mode=data.get("mode", "week"),
                run_date=date.fromisoformat(data["run_date"]) if data.get("run_date") else None,
                market=data.get("market", MARKET_KR),
            )
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_trading_days(
        cls,
        days: Sequence,
        mode: str = MODE_WEEK,
        run_date: Optional[date] = None,
        market: str = MARKET_KR,
    ) -> Optional["WeeklyPeriod"]:
        """수집된 실제 거래일로 구간 확정 (표시용 권장 경로)

        여러 종목의 거래일을 합쳐 넘기면 같은 날짜가 여러 번 들어오므로
        중복을 제거한다. (정렬 + dedupe)
        """
        unique = set()
        for d in days:
            if isinstance(d, date):
                unique.add(d)
            elif isinstance(d, str):
                try:
                    unique.add(date.fromisoformat(d[:10]))
                except ValueError:
                    continue
        if not unique:
            return None
        parsed = sorted(unique)
        return cls(
            start=parsed[0],
            end=parsed[-1],
            trading_days=tuple(parsed),
            mode=mode,
            run_date=run_date,
            market=market,
        )


def format_korean_date(day: date, with_year: bool = False) -> str:
    """'09/21(월)' 또는 '2025/12/29(월)'"""
    prefix = f"{day.year}/" if with_year else ""
    return f"{prefix}{day.strftime('%m/%d')}({WEEKDAY_KO[day.weekday()]})"


def resolve_period(
    run_date: Optional[date] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    market: str = MARKET_KR,
) -> WeeklyPeriod:
    """분석 요청 구간 계산 (수집 요청용)

    `start`/`end`를 주면 사용자가 지정한 구간(custom)을 그대로 쓴다.
    둘 다 없으면 요청 시점의 기본 규칙(주간 마감/주중 스냅샷)을 따른다.

    `market` 는 구간의 기준 시장이다. 아직 마감되지 않은 세션을 구간에
    넣지 않기 위해 사용한다. `market="all"` 처럼 두 시장을 함께 보면
    마지막 마감 시각이 늦은 시장(미국)을 기준으로 자른다.
    """
    if start or end:
        return period_for_range(start=start, end=end, run_date=run_date, market=market)

    base = run_date or date.today()
    if base.weekday() >= 5:
        # 토/일 -> 이번 주 월~일
        start, end = _week_window(base)
        return WeeklyPeriod(
            start=start,
            end=end,
            trading_days=tuple(_weekdays_in_range(start, end, market)),
            mode=MODE_WEEK,
            run_date=base,
            market=market,
        )
    # 평일 -> 마감된 최근 5거래일 (아직 장이 끝나지 않은 날은 제외)
    days = _last_trading_days(last_closed_trading_day(market), TRADING_DAY_COUNT, market)
    return WeeklyPeriod(
        start=days[0],
        end=days[-1],
        trading_days=tuple(days),
        mode=MODE_ROLLING,
        run_date=base,
        market=market,
    )


def period_for_range(
    start: Optional[date] = None,
    end: Optional[date] = None,
    run_date: Optional[date] = None,
    market: str = MARKET_KR,
) -> WeeklyPeriod:
    """사용자가 지정한 시작일~종료일 구간.

    양쪽 다 주면 그대로 쓴다. 한쪽만 주면 7일 창을 채우되 방향이 의도대로
    asymetric 하다 ('분석 종료일' 기준 최근 N주와 맞추기 위해):
      * 시작일만 -> 시작일부터 7일 (09/01 -> 09/01~09/07)
                   사용자가 고른 날짜가 구간의 첫 거래일이 된다.
      * 종료일만 -> 그 날짜가 속한 주의 월요일부터 (09/04 -> 08/31~09/04)
                   '이 날짜까지의 최근 일주' 를 뜻한다.
    종료일이 시작일보다 빠르면 두 값을 서로 바꾸되, MAX_RANGE_DAYS를 넘으면
    거부한다.
    """
    base = run_date or date.today()
    if start and not end:
        lo = start
        hi = lo + timedelta(days=6)
    elif end and not start:
        hi = end
        lo = hi - timedelta(days=hi.weekday())
    else:
        lo = start or base
        hi = end or base

    if hi < lo:
        lo, hi = hi, lo
    span = (hi - lo).days
    if span > MAX_RANGE_DAYS:
        raise PeriodError(
            f"구간이 {span}일로 너무 깁니다 (최대 {MAX_RANGE_DAYS}일). 더 좁은 범위를 지정해 주세요."
        )

    return WeeklyPeriod(
        start=lo,
        end=hi,
        trading_days=tuple(_weekdays_in_range(lo, hi, market)),
        mode=MODE_CUSTOM,
        run_date=base,
        market=market,
    )


def period_for_iso_week(year: int, week: int, run_date: Optional[date] = None,
                        market: str = MARKET_KR) -> WeeklyPeriod:
    """ISO 주차 지정 -> 그 주의 월~일 구간. 예) 2026년 36주차"""
    start, end = _iso_week_window(year, week)
    return WeeklyPeriod(
        start=start,
        end=end,
        trading_days=tuple(_weekdays_in_range(start, end, market)),
        mode=MODE_CUSTOM,
        run_date=run_date or date.today(),
        market=market,
    )


def period_for_month_week(
    year: int,
    month: int,
    nth: int,
    run_date: Optional[date] = None,
    market: str = MARKET_KR,
) -> WeeklyPeriod:
    """월 내 주차 지정 -> 기준일이 속한 ISO 주 구간.

    예) period_for_month_week(2026, 9, 1) -> 08/31(월) ~ 09/06(일) (ISO 36주차)
    """
    anchor = _month_week_anchor(year, month, nth)
    monday = anchor - timedelta(days=anchor.weekday())
    end = monday + timedelta(days=6)
    return WeeklyPeriod(
        start=monday,
        end=end,
        trading_days=tuple(_weekdays_in_range(monday, end, market)),
        mode=MODE_CUSTOM,
        run_date=run_date or date.today(),
        market=market,
    )


def period_for_week_containing(day: date, run_date: Optional[date] = None,
                               market: str = MARKET_KR) -> WeeklyPeriod:
    """특정 날짜가 속한 ISO 주 구간 (캘린더 주차 클릭용)"""
    monday = day - timedelta(days=day.weekday())
    end = monday + timedelta(days=6)
    return WeeklyPeriod(
        start=monday,
        end=end,
        trading_days=tuple(_weekdays_in_range(monday, end, market)),
        mode=MODE_CUSTOM,
        run_date=run_date or date.today(),
        market=market,
    )


def month_week_for_day(day: date) -> tuple:
    """특정 날짜를 포함하는 (연도, 월, 주차) 삼중항 -> period_for_month_week 입력.

    월 내 주차는 '앵커가 속한 ISO 주'라서 월 끝에서 다음 달로 넘어갈 수 있다.
    예) 2026-08-31(월)은 8월 5주차(08/24~08/30)에 들어가지 않으므로
    9월 1주차(08/31~09/06)로 답한다.
    """
    year, month = day.year, day.month
    nxt_year, nxt_month = (year + 1, 1) if month == 12 else (year, month + 1)
    for y, m in ((year, month), (nxt_year, nxt_month)):
        for nth in range(1, MAX_MONTH_WEEK + 1):
            if period_for_month_week(y, m, nth).covers(day):
                return y, m, nth
    # 방어적: 위 두 달로 안 잡히면 ISO 주 기준 주차로 대체
    return year, month, min(MAX_MONTH_WEEK, max(1, (day.day - 1) // 7 + 1))


def period_for_date_str(value: str) -> Optional[WeeklyPeriod]:
    """'2026-09-27' 같은 문자열로부터 구간 계산 (리포트 폴더명 역추적용)"""
    try:
        return resolve_period(date.fromisoformat(value))
    except (ValueError, TypeError):
        return None


def parse_date(value) -> Optional[date]:
    """'2026-09-01' / date 를 date로. 잘못된 값은 None (주기 도메인 에러 아님)"""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (ValueError, TypeError):
        return None


def parse_int(value) -> Optional[int]:
    """'36' / 36 -> 36. 잘못된 값은 None"""
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def group_by_iso_week(periods: Iterable[WeeklyPeriod]) -> dict:
    """'2026-W39' -> WeeklyPeriod 리스트"""
    grouped: dict = {}
    for p in periods:
        grouped.setdefault(f"{p.iso_year}-W{p.iso_week:02d}", []).append(p)
    return grouped


# --- CLI / HTTP 공용 인자 정의 -------------------------------------------
def add_period_arguments(parser, include_month_week: bool = True) -> None:
    """분석 구간 지정 인자를 argparse 파서에 붙인다

    지정 우선순위: --start/--end > --iso-year/--iso-week > --year/--month/--week
    """
    group = parser.add_argument_group("분석 구간 (미지정 시 요청일 기준 규칙)")
    group.add_argument("--start", help="분석 시작일 (YYYY-MM-DD)")
    group.add_argument("--end", help="분석 종료일 (YYYY-MM-DD)")
    group.add_argument("--iso-year", type=int, help="ISO 연도 (예: 2026)")
    group.add_argument("--iso-week", type=int, help="ISO 주차 (예: 36)")
    if include_month_week:
        group.add_argument("--year", type=int, help="연도 (예: 2026)")
        group.add_argument("--month", type=int, help="월 (1~12)")
        group.add_argument("--week", type=int, help="월 내 주차 (1~5)")


def period_from_values(
    start=None,
    end=None,
    iso_year=None,
    iso_week=None,
    year=None,
    month=None,
    week=None,
    run_date: Optional[date] = None,
    market: str = MARKET_KR,
) -> Optional[WeeklyPeriod]:
    """지정값 -> WeeklyPeriod. 지정이 없으면 None.

    잘못된 값은 PeriodError 로 알린다 (조용히 기본값으로 떨어지지 않는다).
    우선순위: start/end > iso_year+iso_week > year+month+week
    """
    # 원본 값을 keep 해야 한다. 파싱 결과로 덮어쓰면 잘못된 입력이
    # '미지정'으로 조용히 사라져 기본 구간으로 떨어진다.
    raw_start, raw_end = start, end
    start, end = parse_date(start), parse_date(end)
    if _given(raw_start) and start is None:
        raise PeriodError(f"시작일을 YYYY-MM-DD 로 읽을 수 없습니다: {raw_start!r}")
    if _given(raw_end) and end is None:
        raise PeriodError(f"종료일을 YYYY-MM-DD 로 읽을 수 없습니다: {raw_end!r}")
    if start or end:
        return period_for_range(start=start, end=end, run_date=run_date, market=market)

    raw_iso_year, raw_iso_week = iso_year, iso_week
    iso_year, iso_week = parse_int(iso_year), parse_int(iso_week)
    if _given(raw_iso_year) or _given(raw_iso_week):
        # '안 줬음'과 '줬는데 못 읽음'을 구분한다
        if _given(raw_iso_year) and iso_year is None:
            raise PeriodError(f"ISO 연도를 정수로 읽을 수 없습니다: {raw_iso_year!r}")
        if _given(raw_iso_week) and iso_week is None:
            raise PeriodError(f"ISO 주차를 정수로 읽을 수 없습니다: {raw_iso_week!r}")
        if not (iso_year and iso_week):
            raise PeriodError("ISO 주차 지정은 연도와 주차를 함께 지정해야 합니다.")
        return period_for_iso_week(iso_year, iso_week, run_date=run_date, market=market)

    raw_year, raw_month, raw_week = year, month, week
    year, month, week = parse_int(year), parse_int(month), parse_int(week)
    if _given(raw_year) or _given(raw_month) or _given(raw_week):
        if _given(raw_year) and year is None:
            raise PeriodError(f"연도를 정수로 읽을 수 없습니다: {raw_year!r}")
        if _given(raw_month) and month is None:
            raise PeriodError(f"월을 정수로 읽을 수 없습니다: {raw_month!r}")
        if _given(raw_week) and week is None:
            raise PeriodError(f"월 내 주차를 정수로 읽을 수 없습니다: {raw_week!r}")
        if not (year and month and week):
            raise PeriodError("월 내 주차 지정은 연도, 월, 주차를 모두 지정해야 합니다.")
        return period_for_month_week(year, month, week, run_date=run_date, market=market)

    return None


def _given(value) -> bool:
    """값이 '지정된 것으로 볼 만한가' (빈 문자열/None 은 미지정)"""
    return value is not None and str(value).strip() != ""


def period_from_namespace(args, run_date: Optional[date] = None) -> Optional[WeeklyPeriod]:
    """argparse Namespace -> WeeklyPeriod. 지정이 없으면 None."""
    return period_from_values(
        start=getattr(args, "start", None),
        end=getattr(args, "end", None),
        iso_year=getattr(args, "iso_year", None),
        iso_week=getattr(args, "iso_week", None),
        year=getattr(args, "year", None),
        month=getattr(args, "month", None),
        week=getattr(args, "week", None),
        run_date=run_date,
    )
