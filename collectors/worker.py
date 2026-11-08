"""One-shot collection worker. Only a JSON result is written to stdout."""
import asyncio
import contextlib
import json
import sys


async def collect(request):
    from collectors.yfinance_collector import YfinanceCollector
    from collectors.toss_news import TossNewsCollector
    from collectors.company_guide import CompanyGuideCollector
    from collectors.limits import DEFAULT_LIMITS
    source, method = request['source'], request['method']
    classes = {'yfinance': YfinanceCollector, 'toss': TossNewsCollector, 'company_guide': CompanyGuideCollector}
    allowed = {'yfinance': {'get_weekly_price', 'get_news', 'get_financial_summary', 'get_short_interest'},
               'toss': {'get_news'}, 'company_guide': {'get_financial_summary'}}
    if source not in classes or method not in allowed[source]:
        raise ValueError('지원하지 않는 수집 작업입니다.')
    collector = classes[source]()
    collector.limits = {**DEFAULT_LIMITS, **request.get('limits', {})}
    try:
        data = await getattr(collector, method)(*request.get('args', []), **request.get('kwargs', {}))
        if method == 'get_weekly_price':
            empty = not data.get('weekly_data')
        elif isinstance(data, dict):
            empty = not any(v not in (None, '', 'N/A', '중립') for k, v in data.items() if k != 'stock_type')
        else:
            empty = not data
        result = {'status': 'empty' if empty else 'ok', 'data': data}
    finally:
        # The parent bounds even cancellation-resistant cleanup and reaps its process tree.
        try:
            async with asyncio.timeout(min(5, collector.limits['cleanup'])):
                await collector.close()
        except Exception as error:
            if 'result' not in locals():
                raise
            result.update(status='timeout' if isinstance(error, TimeoutError) else 'error',
                          error=f'수집 후 자원 정리 실패: {error}')
    return result


def main():
    request = json.loads(sys.stdin.readline())
    from playwright.async_api import TimeoutError as BrowserTimeout
    with contextlib.redirect_stdout(sys.stderr):
        try:
            result = asyncio.run(collect(request))
        except (TimeoutError, BrowserTimeout) as error:
            result = {'status': 'timeout', 'error': str(error) or '브라우저 준비 또는 자원 정리 시간 초과'}
        except Exception as error:
            result = {'status': 'error', 'error': str(error)}
    json.dump(result, sys.stdout, ensure_ascii=False, allow_nan=False)
    sys.stdout.write('\n')
    sys.stdout.flush()
    # Keep the ownership tree intact until the parent has read the result and
    # captured/killed any detached browser descendants. Do not orphan them on exit.
    sys.stdin.readline()


if __name__ == '__main__':
    main()
