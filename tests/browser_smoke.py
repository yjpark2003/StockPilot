"""Browser checks against the ASGI app with isolated watchlist files and no external requests.

Run: venv/bin/python -m tests.browser_smoke
Screenshots: /tmp/stockpilot-preview/
"""
import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from playwright.async_api import async_playwright

import server.app as server


async def main():
    preview = Path('/tmp/stockpilot-preview')
    preview.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary)
        for filename in ('stocks.yaml', 'foreign_stocks.yaml'):
            source = Path(server.get_config_path(filename))
            if source.exists():
                shutil.copy(source, config / filename)
        errors = []
        with patch.object(server, 'CONFIG_DIR', str(config)):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://stockpilot.test') as client:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
                    async def route_request(route):
                        request = route.request
                        url = urlsplit(request.url)
                        if url.hostname != 'stockpilot.test':
                            await route.abort()
                            return
                        response = await client.request(request.method, url.path + ('?'+url.query if url.query else ''), content=request.post_data_buffer,
                                                        headers={'content-type':request.headers.get('content-type','')})
                        await route.fulfill(status=response.status_code, body=response.content,
                                            headers={k:v for k,v in response.headers.items() if k not in ('content-length','content-encoding')})
                    await context.route('**/*', route_request)
                    page = await context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    await page.goto('http://stockpilot.test/')
                    await page.locator('#stock-rows tr').first.wait_for()
                    total = await page.locator('#stock-rows tr').count()
                    assert total > 0
                    await page.screenshot(path=str(preview/'overview-desktop.png'), full_page=True)
                    await page.locator('[data-market="foreign"]').click()
                    assert 0 < await page.locator('#stock-rows tr').count() < total
                    await page.locator('#stock-query').fill('no-such-stock-test')
                    assert await page.locator('#no-matches').is_visible()
                    await page.locator('#stock-query').fill('')
                    await page.locator('[data-market="all"]').click()
                    await page.locator('#theme-toggle').click()
                    assert await page.locator('html').get_attribute('data-theme') == 'dark'
                    await page.screenshot(path=str(preview/'overview-dark.png'), full_page=True)
                    await page.locator('#theme-toggle').click()
                    await page.set_viewport_size({'width':390,'height':844})
                    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    await page.screenshot(path=str(preview/'overview-mobile.png'),full_page=True)
                    report_link = await page.locator('#stock-rows a').first.get_attribute('href')
                    await page.goto('http://stockpilot.test'+report_link)
                    assert await page.locator('.site-header').count() == 1
                    assert await page.locator('#theme-toggle').count() == 1
                    await page.goto('http://stockpilot.test/history')
                    assert await page.locator('#analysis').is_visible()
                    await page.locator('#run-custom summary').click()
                    await page.locator('#run-start').fill('2026-10-30')
                    await page.locator('#run-end').fill('2026-10-26')
                    await page.locator('#run-end').blur()
                    await page.wait_for_function("document.getElementById('run-preview').textContent.includes('종료일')")
                    assert await page.locator('#run-go').is_disabled()
                    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    await page.screenshot(path=str(preview/'history-mobile.png'),full_page=True)
                    await page.goto('http://stockpilot.test/dashboard')
                    await page.locator('.manage-card').first.wait_for()
                    await page.locator('#open-add').click()
                    await page.locator('#entry-market').select_option('foreign')
                    await page.locator('#entry-code').fill('ZZTEST')
                    await page.locator('#entry-name').fill('브라우저 검증')
                    await page.locator('#entry-type').select_option('ETF')
                    assert await page.locator('#entry-code').evaluate('(el) => el.checkValidity()')
                    await page.locator('#save-stock').click()
                    await page.locator('#stock-dialog').wait_for(state='hidden')
                    await page.locator('#manage-query').fill('ZZTEST')
                    await page.locator('.manage-card').filter(has_text='브라우저 검증').wait_for()
                    await page.locator('[data-action="edit"]').click()
                    await page.locator('#entry-name').fill('수정 검증')
                    await page.locator('#save-stock').click()
                    await page.locator('#stock-dialog').wait_for(state='hidden')
                    await page.locator('.manage-card').filter(has_text='수정 검증').wait_for()
                    await page.locator('#manage-query').fill('')
                    await page.screenshot(path=str(preview/'stocks-mobile.png'),full_page=True)
                    await page.locator('#manage-query').fill('ZZTEST')
                    page.once('dialog', lambda d: d.accept())
                    await page.locator('[data-action="delete"]').click()
                    await page.wait_for_function("document.getElementById('stock-list').children.length === 0")
                    await page.locator('#open-add').click()
                    await page.locator('#lookup-query').fill('삼성전자')
                    await page.wait_for_function("document.getElementById('lookup-status').textContent.includes('개 결과')")
                    assert await page.locator('.lookup-item:disabled').count() > 0
                    await page.keyboard.press('Escape')
                    await page.set_viewport_size({'width':1440,'height':1000})
                    await page.locator('#manage-query').fill('')
                    await page.screenshot(path=str(preview/'stocks-desktop.png'),full_page=True)
                    # Exercise both failed and empty states without touching report files.
                    await page.route('**/api/overview', lambda route: route.fulfill(status=500,body='{}',content_type='application/json'))
                    await page.goto('http://stockpilot.test/')
                    await page.locator('#retry-overview').wait_for()
                    await page.unroute('**/api/overview')
                    await page.locator('#retry-overview').click()
                    await page.locator('#stock-rows tr').first.wait_for()
                    await page.route('**/api/overview', lambda route: route.fulfill(status=200,body='null',content_type='application/json'))
                    await page.reload()
                    await page.wait_for_function("document.getElementById('overview-message').textContent.includes('아직 생성된')")
                    assert not errors, errors
                    await browser.close()
    print('Browser checks passed: overview, filters, navigation, theme, mobile, stock CRUD, duplicate search, invalid period, error/retry, empty state.')
    print('Screenshots:', preview)


if __name__ == '__main__':
    asyncio.run(main())
