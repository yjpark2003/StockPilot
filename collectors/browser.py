"""Browser setup and cleanup have a shared deadline, including context creation."""
import asyncio
from playwright.async_api import async_playwright
from collectors.limits import DEFAULT_LIMITS


async def ensure_browser(collector):
    if collector._browser is not None:
        return
    limits = getattr(collector, 'limits', DEFAULT_LIMITS)
    async with asyncio.timeout(limits['browser_setup']):
        collector._pw = await async_playwright().start()
        collector._browser = await collector._pw.chromium.launch(headless=True, timeout=limits['browser_setup'] * 1000)
        collector._context = await collector._browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        collector._context.set_default_timeout(limits['navigation'] * 1000)
        collector._context.set_default_navigation_timeout(limits['navigation'] * 1000)


async def close_browser(collector):
    browser, pw = collector._browser, getattr(collector, '_pw', None)
    collector._browser = collector._context = collector._pw = None
    async with asyncio.timeout(getattr(collector, 'limits', DEFAULT_LIMITS)['cleanup']):
        try:
            if browser:
                await browser.close()
        finally:
            if pw:
                await pw.stop()


async def open_page(collector):
    limits = getattr(collector, 'limits', DEFAULT_LIMITS)
    async with asyncio.timeout(limits['browser_setup']):
        await ensure_browser(collector)
        return await collector._context.new_page()
