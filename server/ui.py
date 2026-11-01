"""Shared navigation for server pages and saved reports."""
from server.theme import THEME_TOGGLE_BTN


def navigation(active=''):
    links = [('overview', '/', '동향'), ('history', '/history', '리포트 기록'), ('stocks', '/dashboard', '종목 관리')]
    items = ''.join(f'<a href="{url}"' + (' aria-current="page"' if key == active else '') + f'>{label}</a>' for key, url, label in links)
    return f'<header class="site-header"><a class="site-logo" href="/">StockPilot<span>주식 동향 분석</span></a><nav aria-label="주 메뉴">{items}</nav>{THEME_TOGGLE_BTN}</header>'
