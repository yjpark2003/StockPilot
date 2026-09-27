# -*- coding: utf-8 -*-
"""주간 리포트 인덱스 - 연도/주차 기반 캘린더 렌더링

리포트 폴더(`reports/weekly/YYYY-MM-DD/`)마다 `meta.json`이 있으면 그 구간을,
없으면 폴더명으로부터 구간을 역산해 표시한다. 주차 표시는 ISO-8601 기준이다.
"""
import calendar
import html as htmllib
import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from analyzers.period import (
    WeeklyPeriod,
    period_for_date_str,
)

# 월~일 순서 (분석 구간이 월요일 시작이므로 ISO 주차와 정렬)
CALENDAR_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")


@dataclass
class ReportEntry:
    """리포트 1건 + 그에 대응하는 분석 구간"""

    date_str: str
    period: WeeklyPeriod
    domestic_count: int = 0
    foreign_count: int = 0
    from_meta: bool = False

    @property
    def url(self) -> str:
        return f"/reports/{self.date_str}/index.html"

    @property
    def year_week_label(self) -> str:
        return self.period.year_week_label

    @property
    def stock_count(self) -> int:
        return self.domestic_count + self.foreign_count


def _read_meta(report_dir: str) -> Optional[dict]:
    meta_path = os.path.join(report_dir, "meta.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def scan_reports(reports_dir: str) -> List[ReportEntry]:
    """리포트 디렉터리 스캔 -> 최신순 ReportEntry 리스트"""
    if not os.path.isdir(reports_dir):
        return []

    entries: List[ReportEntry] = []
    for name in os.listdir(reports_dir):
        report_dir = os.path.join(reports_dir, name)
        if not os.path.isdir(report_dir) or not os.path.exists(os.path.join(report_dir, "index.html")):
            continue

        meta = _read_meta(report_dir)
        period = WeeklyPeriod.from_dict(meta) if meta else None
        if period is None:
            period = period_for_date_str(name)
        if period is None:
            continue

        entries.append(ReportEntry(
            date_str=name,
            period=period,
            domestic_count=(meta or {}).get("domestic_count", 0),
            foreign_count=(meta or {}).get("foreign_count", 0),
            from_meta=meta is not None,
        ))

    # 최신 실행일 순 (폴더명이 실행일이다). 같은 주차에 리포트가 여럿이면
    # 캘린더에서 가장 최근 것이 표시된다.
    entries.sort(key=lambda e: e.date_str, reverse=True)
    return entries


def _index_by_day(entries: List[ReportEntry]) -> dict:
    """날짜 -> ReportEntry (구간이 겹치면 최신 리포트 우선)"""
    index: dict = {}
    for entry in entries:  # 최신순
        day = entry.period.start
        while day <= entry.period.end:
            index.setdefault(day, entry)
            day += timedelta(days=1)
    return index


def _month_bounds(year: int, month: int) -> tuple:
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return first, date(year, month, last_day)


def _shift_month(year: int, month: int, delta: int) -> tuple:
    index = (year * 12 + (month - 1)) + delta
    return index // 12, (index % 12) + 1


def available_years(entries: List[ReportEntry], today: Optional[date] = None) -> List[int]:
    years = {e.period.end.year for e in entries}
    years.add((today or date.today()).year)
    return sorted(years, reverse=True)


def render_calendar(entries: List[ReportEntry], year: int, month: int, today: Optional[date] = None) -> str:
    """해당 연월의 캘린더 그리드 HTML (월~일, 좌측 ISO 주차 표시)"""
    today = today or date.today()
    first, last = _month_bounds(year, month)
    by_day = _index_by_day(entries)

    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=(6 - last.weekday()))

    nav = _render_nav(year, month)
    head = "".join(f"<th>{d}</th>" for d in CALENDAR_WEEKDAYS)

    rows = []
    cursor = grid_start
    while cursor <= grid_end:
        iso = cursor.isocalendar()
        cells = [f'<td class="cal-week">{iso[1]:02d}주</td>']
        for _ in range(7):
            day = cursor
            in_month = day.month == month
            entry = by_day.get(day)
            cells.append(_render_day(day, entry, in_month, today))
            cursor += timedelta(days=1)
        rows.append('<tr class="cal-row">' + "".join(cells) + "</tr>")

    return f"""
    <div class="cal-nav">
        {nav}
    </div>
    <div class="cal-scroll">
      <table class="cal-table">
        <thead><tr><th class="cal-week">주차</th>{head}</tr></thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


def _render_day(day: date, entry: Optional[ReportEntry], in_month: bool, today: date) -> str:
    classes = ["cal-day"]
    if not in_month:
        classes.append("cal-out")
    if day == today:
        classes.append("cal-today")

    if entry is None:
        return f'<td class="{" ".join(classes)}"><span class="cal-num">{day.day}</span></td>'

    classes.append("cal-has")
    is_period_end = day == entry.period.end
    title = (
        f"{entry.year_week_label} · {entry.period.range_label} · "
        f"국내 {entry.domestic_count} / 해외 {entry.foreign_count}종목"
    )
    badge = f'<span class="cal-badge">{entry.period.iso_week}주차</span>' if is_period_end else ""
    count = f'<span class="cal-count">{entry.stock_count}종목</span>' if entry.stock_count else ""
    return (
        f'<td class="{" ".join(classes)}">'
        f'<a href="{htmllib.escape(entry.url)}" title="{htmllib.escape(title)}">'
        f'<span class="cal-num">{day.day}</span>{badge}{count}'
        f"</a></td>"
    )


def _render_nav(year: int, month: int) -> str:
    py, pm = _shift_month(year, month, -1)
    ny, nm = _shift_month(year, month, 1)
    return f"""
        <a class="cal-arrow" href="/?y={py}&m={pm}" rel="prev" aria-label="이전 달">‹</a>
        <span class="cal-title">{year}년 {month}월</span>
        <a class="cal-arrow" href="/?y={ny}&m={nm}" rel="next" aria-label="다음 달">›</a>
    """


def render_year_options(entries: List[ReportEntry], current_year: int, today: Optional[date] = None) -> str:
    return "".join(
        f'<option value="{y}"{" selected" if y == current_year else ""}>{y}년</option>'
        for y in available_years(entries, today)
    )


def render_week_list(entries: List[ReportEntry], limit: int = 12) -> str:
    """캘린더 아래 주차별 목록 (연도/주차 + 구간 + 종목 수)"""
    if not entries:
        return ""

    items = []
    for entry in entries[:limit]:
        meta_badge = "" if entry.from_meta else '<span class="cal-inferred" title="meta.json 없음 → 실행일로 구간 역산">역산</span>'
        items.append(f"""
            <li class="week-item">
                <a href="{htmllib.escape(entry.url)}">
                    <span class="week-no">{entry.year_week_label}{meta_badge}</span>
                    <span class="week-range">{htmllib.escape(entry.period.range_label)}</span>
                    <span class="week-mode">{entry.period.mode_label}</span>
                    <span class="week-count">국내 {entry.domestic_count} · 해외 {entry.foreign_count}</span>
                </a>
            </li>""")

    more = ""
    if len(entries) > limit:
        more = f'<li class="week-more">외 {len(entries) - limit}건</li>'

    return f"""
        <ul class="week-list">{''.join(items)}{more}
        </ul>
    """


def _to_int(value) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def resolve_view(entries: List[ReportEntry], year, month,
                 today: Optional[date] = None) -> tuple:
    """표시할 연월 결정 (기본: 최신 리포트가 있는 달, 없으면 이번 달)

    잘못된 쿼리 값은 무시하고 안전한 값으로 대체한다.
    """
    today = today or date.today()
    year_i, month_i = _to_int(year), _to_int(month)

    if year_i and month_i and 1 <= month_i <= 12 and 1900 <= year_i <= 2200:
        return year_i, month_i
    if entries:
        newest = entries[0].period.end
        return newest.year, newest.month
    return today.year, today.month


CALENDAR_CSS = """
        .cal-wrap { background: var(--surface); border-radius: 12px; padding: 16px; box-shadow: var(--shadow-sm); }
        .cal-nav { display: flex; align-items: center; justify-content: center; gap: 16px; margin-bottom: 12px; }
        .cal-title { font-size: 18px; font-weight: 700; color: var(--text); min-width: 120px; text-align: center; }
        .cal-arrow { font-size: 26px; line-height: 1; color: var(--text-secondary); text-decoration: none; padding: 0 10px; border-radius: 6px; }
        .cal-arrow:hover { color: var(--primary); background: var(--surface-subtle); }
        .cal-scroll { overflow-x: auto; }
        .cal-table { width: 100%; border-collapse: separate; border-spacing: 4px; table-layout: fixed; }
        .cal-table th { font-size: 12px; font-weight: 600; color: var(--text-secondary); padding: 6px 0; }
        .cal-week { width: 46px; font-size: 11px; color: var(--text-faint); text-align: center; font-weight: 500; }
        .cal-day { height: 62px; vertical-align: top; padding: 4px; border-radius: 8px; background: var(--surface-subtle); }
        .cal-day.cal-out { opacity: 0.32; }
        .cal-day.cal-today { outline: 2px solid var(--primary); outline-offset: -2px; }
        .cal-day.cal-has { background: color-mix(in srgb, var(--primary) 14%, var(--surface)); }
        .cal-day a { display: flex; flex-direction: column; gap: 2px; text-decoration: none; height: 100%; }
        .cal-num { font-size: 13px; font-weight: 600; color: var(--text); }
        .cal-day.cal-has .cal-num { color: var(--primary); }
        .cal-badge { font-size: 10px; font-weight: 700; color: var(--on-primary); background: var(--primary); border-radius: 4px; padding: 1px 4px; align-self: flex-start; }
        .cal-count { font-size: 10px; color: var(--text-secondary); }
        .week-list { list-style: none; margin: 16px 0 0; padding: 0; }
        .week-item { margin-bottom: 8px; }
        .week-item a { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; background: var(--surface-subtle); border-radius: 10px; padding: 12px 14px; text-decoration: none; }
        .week-item a:hover { background: var(--surface-hover); }
        .week-no { font-size: 15px; font-weight: 700; color: var(--primary); }
        .week-range { font-size: 13px; color: var(--text); }
        .week-mode, .week-count { font-size: 12px; color: var(--text-secondary); }
        .cal-inferred { font-size: 10px; color: var(--text-faint); border: 1px solid var(--border); border-radius: 4px; padding: 0 3px; margin-left: 4px; font-weight: 400; }
        .week-more { font-size: 12px; color: var(--text-faint); text-align: center; padding: 6px; }
        .cal-legend { font-size: 12px; color: var(--text-secondary); margin-top: 12px; }
        .cal-legend .swatch { display: inline-block; width: 12px; height: 12px; border-radius: 3px; background: color-mix(in srgb, var(--primary) 40%, var(--surface)); vertical-align: -2px; margin-right: 4px; }
        .year-picker { font-size: 14px; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--input-border); background: var(--surface); color: var(--text); }
"""
