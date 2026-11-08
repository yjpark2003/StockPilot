from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from bs4 import BeautifulSoup

from analyzers.period import period_for_range
from server.report_calendar import ReportEntry, render_calendar
import server.app as server


class ReportCalendarTests(unittest.IsolatedAsyncioTestCase):
    def entries(self):
        return [ReportEntry('2026-11-08', period_for_range(date(2026,11,2),date(2026,11,8))),
                ReportEntry('2026-11-01', period_for_range(date(2026,10,26),date(2026,11,1)))]

    async def test_overview_month_boundary_and_selection(self):
        soup = BeautifulSoup(render_calendar(self.entries(),2026,10,overview=True,selected_report='2026-11-01'),'html.parser')
        selected = soup.select('.cal-selected a')
        self.assertEqual(len(selected),7)
        self.assertTrue(all(a['data-report-date'] == '2026-11-01' and a['aria-current'] == 'true' for a in selected))
        self.assertTrue(all(a['href'].startswith('/?report_date=') for a in selected))
        self.assertNotIn('/history',str(soup))

    async def test_history_retains_direct_report_links(self):
        soup = BeautifulSoup(render_calendar(self.entries(),2026,11),'html.parser')
        self.assertEqual(soup.select_one('.cal-has a')['href'],'/reports/2026-11-01/index.html')
        self.assertIn('/history?y=',soup.select_one('.cal-arrow')['href'])
        self.assertFalse(soup.select('[data-report-date]'))

    async def test_calendar_api_defaults_to_selected_report_and_validates_month(self):
        with tempfile.TemporaryDirectory() as directory:
            for entry in self.entries():
                path = Path(directory)/entry.date_str
                path.mkdir()
                (path/'index.html').write_text('<html></html>')
                (path/'meta.json').write_text(json.dumps(entry.period.to_dict()))
            with patch.object(server,'REPORTS_DIR',directory):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://test') as client:
                    result = (await client.get('/api/report-calendar?report_date=2026-11-01')).json()
                    self.assertEqual((result['year'],result['month']),(2026,11))
                    self.assertEqual(result['total'],2)
                    december = (await client.get('/api/report-calendar?year=2026&month=12&report_date=2026-11-01')).json()
                    self.assertIn('data-calendar-year="2027" data-calendar-month="1"',december['html'])
                    self.assertEqual((await client.get('/api/report-calendar?month=13')).status_code,422)
                    self.assertEqual((await client.get('/api/report-calendar?year=1899')).status_code,422)

    async def test_empty_calendar_and_year_boundary(self):
        soup = BeautifulSoup(render_calendar([],1900,1,overview=True),'html.parser')
        self.assertEqual(soup.select_one('.cal-arrow')['aria-disabled'],'true')
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'REPORTS_DIR',directory):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://test') as client:
                result = (await client.get('/api/report-calendar')).json()
                self.assertEqual(result['total'],0)
                self.assertFalse(BeautifulSoup(result['html'],'html.parser').select('.cal-has'))
