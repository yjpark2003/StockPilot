import asyncio
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import httpx

from analyzers.period import period_for_range
from reporters.results import normalize_stock, read_results, write_results
from reporters.html_reporter import HtmlReporter
from collectors.yfinance_collector import YfinanceCollector
from server.overview import load_overview
import server.app as server


def stock(prices=None, **values):
    return {'code': '005930', 'name': '테스트', 'market': 'KOSPI', 'currency': 'KRW',
            'price': {'weekly_data': prices or [], 'end_price': 999, 'current_price': 9999,
                      'start_price': 100, 'change_rate': 99},
            'news': [], 'key_points': [], 'financial': {}, 'data_alignment': {}, **values}


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def report(self, start, end, prices, benchmarks=None, failed=None):
        period = period_for_range(date.fromisoformat(start), date.fromisoformat(end))
        path = self.root / end
        path.mkdir()
        (path / 'index.html').write_text('<html><body></body></html>')
        (path / 'meta.json').write_text(json.dumps(period.to_dict()))
        write_results(path, {'domestic': [stock(prices)] + (failed or []), 'benchmarks': benchmarks or {}})
        return path

    def test_last_observed_close_and_missing_is_not_flat(self):
        missing = normalize_stock(stock(), 'domestic')
        self.assertIsNone(missing['change_rate'])
        self.assertIsNone(missing['last_close'])
        self.assertTrue(missing['error'])
        result = normalize_stock(stock([{'date': '2026-10-26', 'close': 100},
                                        {'date': '2026-10-27', 'close': 110}]), 'domestic')
        self.assertEqual(result['last_close'], 110)
        self.assertEqual(result['change_rate'], 10)
        single = normalize_stock(stock([{'date':'2026-10-26','close':100}]), 'domestic')
        self.assertIsNone(single['change_rate'])

    def test_full_period_comparison_benchmark_and_failure(self):
        previous = [{'date':f'2026-10-{d}', 'close':100 + i*2} for i,d in enumerate(range(19,24))]
        current = [{'date':f'2026-10-{d}', 'close':100 + i*3} for i,d in enumerate(range(26,31))]
        self.report('2026-10-19', '2026-10-25', previous)
        self.report('2026-10-26', '2026-11-01', current,
                    {'kospi': {'name':'KOSPI','weekly_data':previous[:0] + [dict(d,close=100+i) for i,d in enumerate(current)]}},
                    [{'code':'000001','name':'실패','error':'소스 오류'}])
        result = load_overview(self.root)
        row = result['stocks'][0]
        self.assertEqual(row['status'], 'complete')
        self.assertEqual(row['rate_delta'], 4)
        self.assertEqual(row['benchmark_delta'], 8)
        self.assertEqual(result['failed_count'], 1)
        self.assertFalse(result['stocks'][1]['has_detail'])

    def test_partial_period_cannot_compare(self):
        prices = [{'date':f'2026-10-{d}', 'close':100+d} for d in range(26,30)]
        self.report('2026-10-26','2026-11-01',prices)
        row = load_overview(self.root)['stocks'][0]
        self.assertEqual(row['status'], 'incomplete')
        self.assertEqual(row['missing_days'], ['2026-10-30'])
        self.assertIsNone(row['rate_delta'])
        self.assertIsNone(row['benchmark_delta'])

    def test_different_trading_day_counts_cannot_compare(self):
        self.report('2026-10-20', '2026-10-25', [{'date':f'2026-10-{d}', 'close':100+d} for d in range(20,24)])
        self.report('2026-10-26', '2026-11-01', [{'date':f'2026-10-{d}', 'close':100+d} for d in range(26,31)])
        self.assertIsNone(load_overview(self.root)['stocks'][0]['rate_delta'])

    def test_requested_price_range_is_not_truncated_to_five_days(self):
        import pandas as pd
        dates = pd.bdate_range('2026-10-19', periods=10)
        history = pd.DataFrame({'Close':range(100,110),'Volume':[10]*10},index=dates)
        fake = SimpleNamespace(history=lambda **kwargs: history)
        with patch('collectors.yfinance_collector.yf.Ticker',return_value=fake):
            result = asyncio.run(YfinanceCollector().get_weekly_price('TEST',start='2026-10-19',end='2026-10-30',include_live_quote=False))
            self.assertEqual(len(result['weekly_data']),10)
            self.assertEqual(result['change_rate'],9)

    def test_legacy_report_recovery_without_live_quote(self):
        path = self.root / 'legacy'
        path.mkdir()
        (path/'index.html').write_text('''<div class="stock-card"><h2>테스트 <span>005930</span></h2>
          <div class="price-info">현재가: 99999</div><a class="btn-detail" href="domestic_005930.html">상세</a></div>
          <script>createChart('chart-domestic-005930', ["2026-10-26","2026-10-27"], [100,110], '--primary');</script>''')
        result = read_results(path)
        self.assertTrue(result['legacy'])
        self.assertEqual(result['stocks'][0]['last_close'],110)
        self.assertEqual(result['stocks'][0]['name'],'테스트')

    def test_report_generation_preserves_failures_and_escapes_names(self):
        reporter = HtmlReporter(report_dir=str(self.root))
        values = [{'date':'2026-10-26','close':100}, {'date':'2026-10-27','close':100}]
        flat = stock(values,name='<script>bad()</script>')
        flat['price']['change_rate'] = 0
        reporter.generate({'domestic':[flat,
                                       {'code':'000001','name':'실패','error':'연결 실패'}, stock(code='000002',name='가격 없음')]},
                          period=period_for_range(date(2026,10,26),date(2026,11,1)))
        path = self.root / '2026-11-01'
        html = (path/'index.html').read_text()
        self.assertIn('수집 실패 2종목',html)
        self.assertNotIn('<script>bad()</script>',html)
        self.assertIn('chip neutral',html)
        result = read_results(path)
        self.assertEqual(len(result['stocks']),3)
        self.assertFalse((path/'domestic_000002.html').exists())

    def test_api_validation_and_crud_on_temporary_config(self):
        async def scenario():
            for name in ('stocks.yaml','foreign_stocks.yaml'):
                (self.root/name).write_text('stocks: []\n' if name == 'stocks.yaml' else 'foreign_stocks: []\n')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://test') as client:
                with patch.object(server,'CONFIG_DIR',str(self.root)), patch.object(server,'REPORTS_DIR',str(self.root/'reports')):
                    for url in ('/','/dashboard','/history'):
                        response = await client.get(url)
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(response.text.count('id="theme-toggle"'),1)
                    self.assertIsNone((await client.get('/api/overview')).json())
                    self.assertEqual((await client.get('/api/overview?report_date=../../etc')).status_code,422)
                    self.assertEqual((await client.post('/api/stocks/domestic',json={'code':'bad','name':'테스트'})).status_code,422)
                    body = {'ticker':'brk-b','name':'버크셔','type':'ETF'}
                    self.assertEqual((await client.post('/api/stocks/foreign',json=body)).status_code,200)
                    self.assertEqual((await client.post('/api/stocks/foreign',json=body)).status_code,400)
                    body.update(ticker='BRK-B',name='수정',type=None)
                    self.assertEqual((await client.put('/api/stocks/foreign/BRK-B',json=body)).status_code,200)
                    row = (await client.get('/api/stocks')).json()['foreign'][0]
                    self.assertEqual(row['name'],'수정')
                    self.assertNotIn('type',row)
                    self.assertEqual((await client.delete('/api/stocks/foreign/BRK-B')).status_code,200)
                    self.assertEqual((await client.delete('/api/stocks/foreign/BRK-B')).status_code,404)
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
