"""Persist analysis data independently of the presentation templates."""
import json
import math
import os
import re
from pathlib import Path

from bs4 import BeautifulSoup


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def normalize_stock(stock, market):
    code = str(stock.get('code') or stock.get('ticker') or '')
    price = stock.get('price') or {}
    daily = sorted([
        {'date': str(row.get('date', ''))[:10], 'close': number(row.get('close'))}
        for row in price.get('weekly_data', [])
        if isinstance(row, dict) and row.get('date') and number(row.get('close')) is not None
        and number(row.get('close')) > 0
    ], key=lambda row: row['date'])
    alignment = (stock.get('data_alignment') or {}).get('price') or {}
    failed = bool(stock.get('error')) or not daily
    # Use the last observed close, never a live quote for a historical period.
    rate = ((daily[-1]['close'] / daily[0]['close'] - 1) * 100
            if len(daily) >= 2 else None)
    return {
        'code': code, 'name': stock.get('name') or code,
        'market_type': market, 'market': stock.get('market', ''),
        'stock_type': stock.get('stock_type') or stock.get('type') or ('ETF' if stock.get('market', '').upper() == 'ETF' else ''),
        'currency': stock.get('currency') or ('KRW' if market == 'domestic' else 'USD'),
        'last_close': daily[-1]['close'] if daily else None,
        'as_of': daily[-1]['date'] if daily else None,
        'change_rate': round(rate, 2) if rate is not None else None,
        'daily': daily, 'basis': 'unavailable' if failed else alignment.get('basis', 'unknown'),
        'missing_days': alignment.get('missing_days', []),
        'error': str(stock.get('error') or ('구간 주가를 수집하지 못했습니다.' if failed else '')),
        'news': stock.get('news') or [], 'disclosures': stock.get('disclosures') or [],
        'key_points': stock.get('key_points') or [],
        'has_detail': not bool(stock.get('error')) and bool(daily),
    }


def write_results(output_dir, all_results):
    payload = {
        'schema_version': 1,
        'stocks': [normalize_stock(s, market) for market in ('domestic', 'foreign')
                   for s in all_results.get(market, [])],
        'benchmarks': all_results.get('benchmarks', {}),
    }
    target = Path(output_dir) / 'results.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, target)


def read_results(report_dir):
    """Old reports remain readable without re-running external collectors."""
    path = Path(report_dir)
    try:
        payload = json.loads((path / 'results.json').read_text(encoding='utf-8'))
        if payload.get('schema_version') == 1 and isinstance(payload.get('stocks'), list):
            return payload
    except (OSError, ValueError, AttributeError):
        pass
    return read_legacy_results(path)


def read_legacy_results(path):
    try:
        html = (path / 'index.html').read_text(encoding='utf-8')
    except OSError:
        return {'stocks': [], 'benchmarks': {}, 'legacy': True}
    soup = BeautifulSoup(html, 'html.parser')
    charts = {}
    # Read JSON arrays only. Never execute JavaScript embedded in an old report.
    for match in re.finditer(r"createChart\('chart-(domestic|foreign)-([^']+)',\s*(\[[^\]]*\]),\s*(\[[^\]]*\])", html):
        try:
            dates, values = json.loads(match[3]), json.loads(match[4])
            charts[(match[1], match[2])] = [dict(date=d, close=c) for d, c in zip(dates, values)]
        except (ValueError, TypeError):
            continue
    stocks = []
    for card in soup.select('.stock-card'):
        link = card.select_one('a.btn-detail')
        match = re.fullmatch(r'(domestic|foreign)_([\w.\-^=]+)\.html', link.get('href', '') if link else '')
        if not match:
            continue
        market, code = match.groups()
        heading = card.select_one('h2')
        name = next((str(t).strip() for t in heading.contents if isinstance(t, str) and str(t).strip()), code) if heading else code
        news = []
        for item in card.select('.news-item'):
            anchor = item.select_one('a')
            when = item.select_one('.news-time')
            if anchor:
                news.append({'title': anchor.get_text(strip=True), 'link': anchor.get('href', ''),
                             'time': when.get_text(' ', strip=True) if when else ''})
        badge = card.select_one('.badge-kospi, .badge-nasdaq')
        stock = normalize_stock({
            'code': code, 'name': name, 'market': badge.get_text(strip=True) if badge else '',
            'price': {'weekly_data': charts.get((market, code), [])}, 'news': news,
        }, market)
        # Legacy indexes don't contain reliable per-stock price alignment metadata.
        stock['basis'] = 'legacy' if stock['daily'] else 'unavailable'
        stock['has_detail'] = (path / f'{market}_{code}.html').is_file()
        stocks.append(stock)
    return {'stocks': stocks, 'benchmarks': {}, 'legacy': True}
