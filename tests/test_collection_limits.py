import asyncio
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from analyzers.period import period_for_range
from analyzers.weekly_analyzer import WeeklyAnalyzer
from collectors.browser import open_page, close_browser
from collectors.execution import StageRunner
from collectors.limits import DEFAULT_LIMITS
from reporters.results import normalize_stock
import httpx
import server.app as server


def running(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] not in ('Z', 'X')
    except FileNotFoundError:
        return False


class CollectionLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_worker_error_protocol_without_network(self):
        result = await StageRunner().run('news','invalid',{'source':'invalid','method':'get_news'},5)
        self.assertEqual(result['status'],'error')
        self.assertIn('지원하지 않는',result['error'])

    async def test_progress_api_remains_responsive_during_blocking_worker(self):
        saved = dict(server.analysis_progress)
        entered = asyncio.Event()
        runner = StageRunner(worker_command=[sys.executable,'-c','import time; time.sleep(60)'])
        async def analysis(market, with_dart, progress_callback, period=None, stage_callback=None):
            await progress_callback(1,1,'테스트','테스트 시작')
            async def event(data):
                await stage_callback(data)
                entered.set()
            await runner.run('news','toss',{},2,callback=event)
            await stage_callback({'stage':'report','summary':{'complete':0,'partial':1,'failed':0}})
            return '/tmp/test-report/2026-11-08'
        try:
            with patch('scripts.run_analysis.run_analysis',side_effect=analysis), patch('scripts.run_analysis.load_config',return_value={'stocks':[{}]}):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://test') as client:
                    response = await client.get('/run-analysis?market=domestic')
                    self.assertIn('stage-timer',response.text)
                    await asyncio.wait_for(entered.wait(),2)
                    started = time.monotonic()
                    progress = (await client.get('/api/progress')).json()
                    self.assertLess(time.monotonic()-started,.3)
                    self.assertTrue(progress['is_running'])
                    self.assertEqual(progress['stage'],'news')
                    self.assertEqual(progress['stage_limit_seconds'],2)
                    for _ in range(100):
                        if not server.analysis_progress['is_running']:
                            break
                        await asyncio.sleep(.03)
                    self.assertEqual(server.analysis_progress['status'],'completed')
                    self.assertEqual(server.analysis_progress['collection_summary']['partial'],1)
        finally:
            server.analysis_progress.clear()
            server.analysis_progress.update(saved)

    async def test_hung_worker_and_detached_child_are_killed_without_blocking_loop(self):
        with tempfile.TemporaryDirectory() as folder:
            pidfile = Path(folder) / 'pids.json'
            runner = StageRunner(worker_command=[sys.executable, '-m', 'tests.collection_worker_fixture', 'hang', str(pidfile)])
            ticks = 0
            async def heartbeat():
                nonlocal ticks
                for _ in range(10):
                    await asyncio.sleep(.05)
                    ticks += 1
            started = time.monotonic()
            result, _ = await asyncio.gather(runner.run('news', 'toss', {}, 2), heartbeat())
            self.assertEqual(result['status'], 'timeout')
            self.assertGreater(ticks, 5)
            self.assertLess(time.monotonic() - started, 2.8)
            self.assertTrue(pidfile.exists())
            self.assertTrue(all(not running(pid) for pid in json.loads(pidfile.read_text())))

    async def test_cancellation_also_cleans_up_children(self):
        with tempfile.TemporaryDirectory() as folder:
            pidfile = Path(folder) / 'pids.json'
            runner = StageRunner(worker_command=[sys.executable, '-m', 'tests.collection_worker_fixture', 'hang', str(pidfile)])
            task = asyncio.create_task(runner.run('news', 'toss', {}, 10))
            for _ in range(100):
                if pidfile.exists():
                    break
                await asyncio.sleep(.02)
            self.assertTrue(pidfile.exists())
            await asyncio.sleep(.1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(all(not running(pid) for pid in json.loads(pidfile.read_text())))

    async def test_three_timeouts_open_circuit_for_same_source_and_method(self):
        runner = StageRunner(worker_command=[sys.executable, '-c', 'import time; time.sleep(60)'])
        for _ in range(3):
            result = await runner.run('news', 'yfinance', {'method':'get_news'}, 1.1)
            self.assertEqual(result['status'], 'timeout')
        result = await runner.run('news', 'yfinance', {'method':'get_news'}, 30)
        self.assertEqual(result['status'], 'skipped')
        self.assertNotIn(('yfinance','get_weekly_price'),runner.failures)

    async def test_empty_feed_and_failure_are_distinct(self):
        for mode in ('empty','error'):
            runner = StageRunner(worker_command=[sys.executable, '-m', 'tests.collection_worker_fixture', mode])
            result = await runner.run('news','toss',{},3)
            self.assertEqual(result['status'],mode)

    async def test_stock_deadline_preserves_price_and_moves_to_next_stock(self):
        limits = {**DEFAULT_LIMITS, 'stock':2.4, 'price':2, 'news':2, 'financial':2}
        events = []
        async def event(data):
            events.append(data)
        analyzer = WeeklyAnalyzer(limits=limits, stage_callback=event,
                                  period=period_for_range(date(2026,11,2),date(2026,11,8)))
        analyzer.runner = StageRunner(worker_command=[sys.executable,'-m','tests.collection_worker_fixture','stock'])
        started = time.monotonic()
        results = await analyzer.analyze_all([{'code':'005930','name':'첫 종목'}, {'code':'000660','name':'다음 종목'}])
        self.assertLess(time.monotonic() - started, 6)
        self.assertEqual(len(results),2)
        for result in results:
            self.assertEqual(result['price']['end_price'],110)
            self.assertEqual(result['analysis_status'],'partial')
            self.assertEqual(result['collection_status']['news']['status'],'timeout')
            self.assertEqual(normalize_stock(result,'domestic')['collection_status']['news']['status'],'timeout')
        self.assertTrue(any(e.get('started_at') and e.get('limit_seconds') for e in events))

    async def test_browser_preparation_and_shutdown_deadlines(self):
        class Fake:
            limits = {**DEFAULT_LIMITS,'browser_setup':.05,'cleanup':.05}
            _browser = None
            _context = None
        async def forever(*args, **kwargs):
            await asyncio.Event().wait()
        fake = Fake()
        with patch('collectors.browser.ensure_browser',side_effect=forever):
            with self.assertRaises(TimeoutError):
                await open_page(fake)
        fake._browser = type('Browser',(),{'close':forever})()
        fake._pw = type('Driver',(),{'stop':AsyncMock()})()
        with self.assertRaises(TimeoutError):
            await close_browser(fake)
        self.assertIsNone(fake._browser)
