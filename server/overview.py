"""Read saved reports for the overview; no network requests on page loads."""
import json
from pathlib import Path
from urllib.parse import quote

from analyzers.market_calendar import MARKET_KR, MARKET_US
from reporters.results import number, read_results
from server.report_calendar import scan_reports


def load_overview(reports_dir, report_date=None, config=None):
    entries = scan_reports(reports_dir)
    selected = next((e for e in entries if e.date_str == report_date), None) if report_date else (entries[0] if entries else None)
    if not selected:
        return None
    path = Path(reports_dir) / selected.date_str
    payload = read_results(path)
    try:
        meta = json.loads((path / 'meta.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        meta = {}
    previous = next((e for e in entries if e.period.end < selected.period.start), None)
    previous_rows = {}
    if previous:
        previous_rows = {(s['market_type'], s['code']): s for s in
                         read_results(Path(reports_dir) / previous.date_str)['stocks']}
    configured = {(market, str(s.get('code') or s.get('ticker'))): s
                  for market in ('domestic', 'foreign') for s in (config or {}).get(market, [])}
    rows = []
    for raw in payload['stocks']:
        row = dict(raw)
        market = MARKET_KR if row['market_type'] == 'domestic' else MARKET_US
        expected = [d.isoformat() for d in selected.period.trading_days_for(market)]
        observed = {r['date'] for r in row['daily']}
        row['missing_days'] = sorted(set(expected) - observed)
        row['status'] = ('failed' if row.get('error') or not observed else
                         'incomplete' if row['missing_days'] else 'insufficient' if len(observed) < 2 else 'complete')
        row['status_label'] = {'failed': '수집 실패', 'incomplete': '일부 미수집', 'insufficient': '비교 자료 부족', 'complete': '구간 일치'}[row['status']]
        row['report_url'] = f"/reports/{selected.date_str}/{row['market_type']}_{quote(row['code'], safe='')}.html" if row.get('has_detail') else None
        # Report snapshots stay historical; only type falls back to current settings.
        row['stock_type'] = row.get('stock_type') or configured.get((row['market_type'], row['code']), {}).get('type', '')
        row['previous_rate'] = None
        row['rate_delta'] = None
        prior = previous_rows.get((row['market_type'], row['code']))
        previous_expected = [d.isoformat() for d in previous.period.trading_days_for(market)] if previous else []
        if (prior and row['status'] == 'complete' and not prior.get('error')
                and len(expected) == len(previous_expected)
                and set(previous_expected) == {r['date'] for r in prior['daily']}
                and row['change_rate'] is not None and prior['change_rate'] is not None):
            row['previous_rate'] = prior['change_rate']
            row['rate_delta'] = round(row['change_rate'] - prior['change_rate'], 2)
        key = ('kosdaq' if row.get('market', '').upper() == 'KOSDAQ' else 'kospi') if row['market_type'] == 'domestic' else 'us'
        benchmark = payload.get('benchmarks', {}).get(key, {})
        values = {d['date']: number(d.get('close')) for d in benchmark.get('weekly_data', [])}
        dates = sorted(observed)
        row['benchmark_name'] = benchmark.get('name') or {'kospi': 'KOSPI', 'kosdaq': 'KOSDAQ', 'us': 'S&P 500'}[key]
        row['benchmark_delta'] = None
        if (row['status'] == 'complete' and len(dates) >= 2 and row['change_rate'] is not None
                and all(values.get(d) is not None and values[d] > 0 for d in dates)):
            reference_rate = (values[dates[-1]] / values[dates[0]] - 1) * 100
            row['benchmark_delta'] = round(row['change_rate'] - reference_rate, 2)
        rows.append(row)
    return {
        'date': selected.date_str, 'period': selected.period.to_dict(),
        'generated_at': meta.get('generated_at'), 'legacy': payload.get('legacy', False),
        'failed_count': max(meta.get('failed_count', 0), sum(s['status'] == 'failed' for s in rows)),
        'unlisted_failures': max(0, meta.get('failed_count', 0) - sum(s['status'] == 'failed' for s in rows)),
        'stocks': rows, 'previous': {'date': previous.date_str, 'range_label': previous.period.range_label} if previous else None,
        'reports': [{'date': e.date_str, 'label': e.period.range_label, 'week': e.year_week_label} for e in entries],
    }
