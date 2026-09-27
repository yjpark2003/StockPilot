# -*- coding: utf-8 -*-
"""HTML 리포트 생성 모듈"""
import os
import json
from datetime import date, datetime
from typing import Optional
from jinja2 import Template

from analyzers.period import WeeklyPeriod, resolve_period

# data_alignment 키의 한국어 표기
SECTION_LABELS = {
    "price": "주가",
    "news": "주요 뉴스",
    "financial": "재무 지표",
    "short_interest": "공매도",
    "investor_trend": "투자자별 매매동향",
    "volume_data": "거래량",
}


class HtmlReporter:
    """분석 결과를 HTML 리포트로 생성"""

    # 인라인 HTML 템플릿
    INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ year_week_label }} 주간 주식 분석 리포트 - {{ date }}</title>
    <script defer src="/static/chart.umd.min.js"></script>
    <link rel="stylesheet" href="/static/theme.css">
    <script>
    (function () {
        var stored = null;
        try { stored = localStorage.getItem('stockpilot-theme'); } catch (e) {}
        var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', stored === 'dark' || stored === 'light' ? stored : (prefersDark ? 'dark' : 'light'));
    })();
    </script>
    <style>
        .container { max-width: 1200px; }

        .floating-action { position: fixed; top: 20px; right: 20px; z-index: 1000; display: flex; gap: 8px; }

        .info-bar h3 { font-size: 14px; margin-bottom: 10px; }

        /* 구간 거래일 미수집 경고 */
        .warn-bar {
            margin: 0 0 18px; padding: 14px 16px; border-radius: 8px;
            background: rgba(211, 47, 47, .07); border: 1px solid rgba(211, 47, 47, .32);
        }
        .warn-bar h3 { font-size: 14px; margin: 0 0 8px; color: #c62828; }
        .warn-bar p { margin: 3px 0; font-size: 12.5px; color: var(--text-secondary); }
        .warn-bar p strong { color: #c62828; }
        [data-theme="dark"] .warn-bar { background: rgba(239, 83, 80, .1); border-color: rgba(239, 83, 80, .35); }
        [data-theme="dark"] .warn-bar h3, [data-theme="dark"] .warn-bar p strong { color: #ef9a9a; }
        .stock-summary { margin-bottom: 15px; }
        .stock-summary:last-of-type { margin-bottom: 0; }
        .stock-tags { display: flex; flex-wrap: wrap; gap: 8px; }

        .tabs { display: flex; gap: 8px; margin-bottom: 24px; }
        .tab { padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease; border: 2px solid var(--border); background: var(--surface); font-family: inherit; font-size: 14px; color: var(--text); }
        .tab:hover { border-color: var(--primary); }
        .tab[aria-selected="true"] { background: var(--primary); color: var(--on-primary); border-color: var(--primary); }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .stock-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .stock-card { background: var(--surface); border-radius: 12px; padding: 24px; box-shadow: var(--shadow); transition: transform 0.2s ease, box-shadow 0.2s ease; }
        .stock-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-lg); }
        .stock-card h2 { font-size: 20px; color: var(--primary); margin-bottom: 6px; }
        .stock-card .code { font-size: 12px; color: var(--text-muted); margin-bottom: 16px; }

        .change-rate { font-size: 24px; font-weight: 700; margin: 12px 0; }
        .change-rate.positive { color: var(--positive); }
        .change-rate.negative { color: var(--negative); }
        .change-rate.neutral { color: var(--neutral-sign); }
        .price-info { font-size: 14px; color: var(--text-secondary); margin-bottom: 8px; }

        .chart-container { height: 120px; margin: 16px 0; }

        .trend-positive { color: var(--positive); font-weight: 600; }
        .trend-negative { color: var(--negative); font-weight: 600; }

        .news-list { margin-top: 16px; margin-bottom: 12px; }

        .btn-detail { display: inline-block; margin-top: 12px; padding: 10px 20px; background: var(--primary); color: var(--on-primary); text-decoration: none; border-radius: 8px; font-size: 14px; transition: background-color 0.2s ease; }
        .btn-detail:hover { background: var(--primary-hover); color: var(--on-primary); }

        .market-badge, .ticker-badge { vertical-align: middle; }

        /* 데이터 기준 배지: 구간 일치 / 구간 일부 미수집 / 기준일 스냅샷 / 미지원 */
        .basis-badge {
            display: inline-block; vertical-align: middle;
            font-size: 11px; font-weight: 600; line-height: 1;
            padding: 3px 7px; margin-left: 6px; border-radius: 999px;
            border: 1px solid transparent; white-space: nowrap; cursor: help;
        }
        .basis-period { background: rgba(25, 118, 210, .12); color: #1565c0; border-color: rgba(21, 101, 192, .35); }
        .basis-snapshot { background: rgba(245, 159, 0, .14); color: #b26a00; border-color: rgba(245, 159, 0, .4); }
        .basis-unavailable { background: rgba(158, 158, 158, .16); color: #616161; border-color: rgba(97, 97, 97, .32); }
        .basis-incomplete { background: rgba(211, 47, 47, .12); color: #c62828; border-color: rgba(211, 47, 47, .4); }
        [data-theme="dark"] .basis-period { background: rgba(66, 165, 245, .18); color: #90caf9; border-color: rgba(66, 165, 245, .4); }
        [data-theme="dark"] .basis-snapshot { background: rgba(255, 183, 77, .16); color: #ffcc80; border-color: rgba(255, 183, 77, .38); }
        [data-theme="dark"] .basis-unavailable { background: rgba(174, 174, 174, .16); color: #bdbdbd; border-color: rgba(189, 189, 189, .3); }
        [data-theme="dark"] .basis-incomplete { background: rgba(239, 83, 80, .18); color: #ef9a9a; border-color: rgba(239, 83, 80, .4); }

        .basis-note {
            font-size: 12px; color: var(--text-secondary);
            margin: 6px 0 0; padding: 6px 9px; border-radius: 6px;
            background: rgba(245, 159, 0, .08);
            border-left: 3px solid rgba(245, 159, 0, .55);
        }
        .basis-note-warn { background: rgba(211, 47, 47, .08); border-left-color: rgba(211, 47, 47, .55); }
        [data-theme="dark"] .basis-note-warn { background: rgba(239, 83, 80, .1); border-left-color: rgba(239, 83, 80, .55); }
        .basis-empty { color: var(--text-secondary); font-size: 13px; }
    </style>
</head>
<body>
{% macro basis_badge(align, name) %}{% if align and align.get(name) %}<span class="basis-badge basis-{{ align[name].basis }}" title="{{ align[name].note or align[name].label }}">{{ align[name].label }}</span>{% endif %}{% endmacro %}
{% macro basis_note(align, name) %}{% if align and align.get(name) and align[name].note %}<p class="basis-note">{{ align[name].note }}</p>{% endif %}{% endmacro %}
    <button type="button" class="theme-toggle" id="theme-toggle" aria-label="테마 전환">🌓</button>
    <div class="floating-action">
        <a href="/api/run" class="btn btn-primary">전체 분석 실행</a>
        <a href="/api/run?with_dart=true" class="btn btn-secondary">DART 포함</a>
        <a href="/" class="btn btn-secondary">새로고침</a>
    </div>

    <div class="container">
        <header class="brand">
            <h1>{{ year_week_label }} 주간 리포트</h1>
            <p>{{ range_label }} · {{ trading_label }} · {{ mode_label }}</p>
            <p>{{ date }} 자동 분석 결과 | 국내 {{ domestic_stocks|length }}종목, 해외 {{ foreign_stocks|length }}종목</p>
        </header>

        {% if is_custom %}
        <div class="info-bar">
            <div>
                <h3>🗓 구간 지정 분석 · 데이터 기준</h3>
                <p class="basis-empty">지정 구간(<strong>{{ range_label }}</strong>)에 데이터가 섹션마다 다릅니다. 배지를 확인해 주세요.</p>
                <p><span class="basis-badge basis-period">구간 일치</span> 주가 · 뉴스 — 지정 구간으로 조회</p>
                <p><span class="basis-badge basis-incomplete">구간 일부 미수집</span> 주가 — 구간의 일부 거래일이 소스에 아직 반영되지 않음</p>
                <p><span class="basis-badge basis-snapshot">기준일 스냅샷</span> 재무 · 공매도 — 수집 시점 현재값이라 구간과 무관</p>
                <p><span class="basis-badge basis-unavailable">미지원</span> 투자자별 매매동향 · 거래량 — 소스 폐기</p>
            </div>
        </div>
        {% endif %}

        {% if price_gaps %}
        <div class="warn-bar">
            <div>
                <h3>⚠️ 구간 거래일 데이터 일부 미수집</h3>
                <p class="basis-empty">
                    요청하신 구간의 거래일은 {{ trading_label }} 이지만, 아래 날짜는 소스에 아직 반영되지 않아
                    주가 그래프와 표에서 빠졌습니다. 국내 피드는 보통 1~2거래일 지연됩니다.
                </p>
                {% for day, names in price_gaps %}
                <p><strong>{{ day }}</strong> — {{ names | length }}개 종목 ({{ names | join(', ') }})</p>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <div class="info-bar">
            <div class="stock-summary">
                <h3>📋 국내 종목</h3>
                <div class="stock-tags">
                    {% for stock in domestic_stocks %}
                    <span class="chip {{ 'positive' if stock.price.change_rate > 0 else 'negative' }}">
                        {{ stock.name }} {{ '%+.1f'|format(stock.price.change_rate) }}%
                    </span>
                    {% endfor %}
                </div>
            </div>
            
            <div class="stock-summary">
                <h3>🌍 해외 종목</h3>
                <div class="stock-tags">
                    {% for stock in foreign_stocks %}
                    <span class="chip {{ 'positive' if stock.price.change_rate > 0 else 'negative' }}">
                        {{ stock.name }} {{ '%+.1f'|format(stock.price.change_rate) }}%
                    </span>
                    {% endfor %}
                </div>
            </div>
        </div>

        <div class="tabs" role="tablist" aria-label="시장 선택">
            <button type="button" class="tab active" role="tab" aria-selected="true" aria-controls="domestic" id="tab-domestic" onclick="showTab('domestic')">🇰🇷 국내</button>
            <button type="button" class="tab" role="tab" aria-selected="false" aria-controls="foreign" id="tab-foreign" onclick="showTab('foreign')">🌍 해외</button>
        </div>

        <div id="domestic" class="tab-content active" role="tabpanel" aria-labelledby="tab-domestic">
            <div class="stock-grid">
            {% for stock in domestic_stocks %}
                <div class="stock-card motion-enter" style="--enter-delay: {{ (loop.index0 * 0.05)|round(2) }}s">
                    <h2>{{ stock.name }} <span class="badge badge-ticker">{{ stock.code }}</span> <span class="badge badge-kospi">{{ stock.market }}</span></h2>

                    <div class="change-rate {{ 'positive' if stock.price.change_rate > 0 else ('negative' if stock.price.change_rate < 0 else 'neutral') }} rate-anim" data-rate="{{ stock.price.change_rate }}">
                        {{ '%+.2f'|format(stock.price.change_rate) }}%
                    </div>
                    <div class="price-info">
                        현재가: ₩{{ '{:,.0f}'.format(stock.price.current_price) }}
                    </div>

                    <div class="chart-container">
                        <canvas id="chart-domestic-{{ stock.code }}"></canvas>
                    </div>

                    {% if stock.investor_trend and stock.investor_trend.summary %}
                    <div class="trend-box">
                        <div class="trend-row">
                            <span class="trend-label">외국인</span>
                            <span class="trend-value {{ 'trend-positive' if stock.investor_trend.summary.foreign_total > 0 else 'trend-negative' }}">
                                {{ stock.investor_trend.summary.foreign_trend }}
                                ({{ '{:+,}'.format(stock.investor_trend.summary.foreign_total) }}주)
                            </span>
                        </div>
                        <div class="trend-row">
                            <span class="trend-label">기관</span>
                            <span class="trend-value {{ 'trend-positive' if stock.investor_trend.summary.inst_total > 0 else 'trend-negative' }}">
                                {{ stock.investor_trend.summary.inst_trend }}
                                ({{ '{:+,}'.format(stock.investor_trend.summary.inst_total) }}주)
                            </span>
                        </div>
                        <div class="trend-row">
                            <span class="trend-label">개인</span>
                            <span class="trend-value {{ 'trend-positive' if stock.investor_trend.summary.individual_total > 0 else 'trend-negative' }}">
                                {{ stock.investor_trend.summary.individual_trend }}
                                ({{ '{:+,}'.format(stock.investor_trend.summary.individual_total) }}주)
                            </span>
                        </div>
                        <div class="trend-row">
                            <span class="trend-label">외국인 보유율</span>
                            <span class="trend-value">
                                {{ stock.investor_trend.foreign_ratio }}
                                {% if stock.investor_trend.foreign_ratio_change != 0 %}
                                    <span class="{{ 'trend-positive' if stock.investor_trend.foreign_ratio_change > 0 else 'trend-negative' }}">
                                        ({{ '%+.2f'|format(stock.investor_trend.foreign_ratio_change) }}%p)
                                    </span>
        {% endif %}
                            </span>
                        </div>
                    </div>
                    {% endif %}

                    <div class="news-list">
                        <h3>주요 뉴스{{ basis_badge(stock.data_alignment, 'news') }}</h3>
                        {% for news in stock.news[:2] %}
                        <div class="news-item">
                            <a href="{{ news.link }}" target="_blank">{{ news.title[:60] }}{% if news.title|length > 60 %}...{% endif %}</a>
                            <div class="news-time">
                                {% if news.source %}<span class="news-source">{{ news.source }}</span>{% endif %}
                                {% if news.time %} | {{ news.time }}{% endif %}
                            </div>
                        </div>
                        {% endfor %}
                        {% if not stock.news %}
                        <p class="basis-empty">해당 구간에 발행된 뉴스를 찾지 못했습니다.</p>
                        {% endif %}
                        {% if stock.data_alignment and stock.data_alignment.get('news') and stock.data_alignment['news'].note and stock.news %}
                        <p class="basis-empty">{{ stock.data_alignment['news'].note }}</p>
                        {% endif %}
                    </div>

                    <div class="key-points callout">
                        <h3>주목 포인트</h3>
                        <ul>
                        {% for point in stock.key_points %}
                            <li>{{ point }}</li>
                        {% endfor %}
                        </ul>
                    </div>

                    <a href="domestic_{{ stock.code }}.html" class="btn-detail">상세 보기</a>
                </div>
            {% endfor %}
            </div>
        </div>

        <div id="foreign" class="tab-content" role="tabpanel" aria-labelledby="tab-foreign">
            <div class="stock-grid">
            {% for stock in foreign_stocks %}
                <div class="stock-card motion-enter" style="--enter-delay: {{ (loop.index0 * 0.05)|round(2) }}s">
                    <h2>{{ stock.name }} <span class="badge badge-ticker">{{ stock.code }}</span> <span class="badge badge-nasdaq">{{ stock.market }}</span></h2>

                    <div class="change-rate {{ 'positive' if stock.price.change_rate > 0 else ('negative' if stock.price.change_rate < 0 else 'neutral') }} rate-anim" data-rate="{{ stock.price.change_rate }}">
                        {{ '%+.2f'|format(stock.price.change_rate) }}%
                    </div>
                    <div class="price-info">
                        현재가: ${{ '{:,.2f}'.format(stock.price.current_price) }}
                    </div>

                    <div class="chart-container">
                        <canvas id="chart-foreign-{{ stock.code }}"></canvas>
                    </div>

                    {% if stock.short_interest %}
                    <div class="trend-box">
                        <div class="trend-row">
                            <span class="trend-label">숏 비율</span>
                            <span class="trend-value">{{ stock.short_interest.short_percent }}</span>
                        </div>
                        <div class="trend-row">
                            <span class="trend-label">숏 커버링</span>
                            <span class="trend-value">{{ stock.short_interest.short_covering_days }}</span>
                        </div>
                        <div class="trend-row">
                            <span class="trend-label">공매도 수량</span>
                            <span class="trend-value">{{ stock.short_interest.shares_short }}</span>
                        </div>
                        <div class="trend-row">
                            <span class="trend-label">센티먼트</span>
                            <span class="trend-value">{{ stock.short_interest.sentiment }}</span>
                        </div>
                    </div>
                    {% endif %}

                    <div class="news-list">
                        <h3>주요 뉴스{{ basis_badge(stock.data_alignment, 'news') }}</h3>
                        {% for news in stock.news[:2] %}
                        <div class="news-item">
                            <a href="{{ news.link }}" target="_blank">{{ news.title }}</a>
                            <div class="news-time">{{ news.time }}</div>
                        </div>
                        {% endfor %}
                        {% if not stock.news %}
                        <p class="basis-empty">해당 구간에 발행된 뉴스를 찾지 못했습니다.</p>
                        {% endif %}
                    </div>

                    <div class="key-points callout">
                        <h3>주목 포인트</h3>
                        <ul>
                        {% for point in stock.key_points %}
                            <li>{{ point }}</li>
                        {% endfor %}
                        </ul>
                    </div>

                    <a href="foreign_{{ stock.code }}.html" class="btn-detail">상세 보기</a>
                </div>
            {% endfor %}
            </div>
        </div>

        <footer>
            주간 주식 분석 리포트 | {{ year_week_label }} ({{ range_label }}) · 자동 생성 {{ date }}
        </footer>
    </div>

    <script>
    function showTab(name) {
        document.querySelectorAll('.tab-content').forEach(function(el) { el.classList.remove('active'); el.hidden = true; });
        document.querySelectorAll('.tab').forEach(function(el) { el.classList.remove('active'); el.setAttribute('aria-selected', 'false'); });
        var panel = document.getElementById(name);
        panel.classList.add('active');
        panel.hidden = false;
        var activeTab = document.getElementById('tab-' + name);
        activeTab.classList.add('active');
        activeTab.setAttribute('aria-selected', 'true');
        activeTab.focus();
    }

    // 탭 키보드 탐색 (좌/우 화살표)
    document.querySelectorAll('.tabs').forEach(function(tablist) {
        tablist.addEventListener('keydown', function(e) {
            var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[role="tab"]'));
            var index = tabs.indexOf(document.activeElement);
            if (index === -1) return;
            var next = index;
            if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
            else if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
            else return;
            e.preventDefault();
            showTab(['domestic', 'foreign'][next]);
        });
    });

    // 그래프 생성 함수 (차트 라이브러리 로드 실패 시 폴백 메시지 표시)
    window.addEventListener('load', function() {
        if (typeof Chart === 'undefined') {
            document.querySelectorAll('.chart-container').forEach(function(c) {
                c.textContent = '차트를 불러오지 못했습니다. 네트워크 연결을 확인해주세요.';
                c.style.cssText = 'display:flex;align-items:center;justify-content:center;color:#888;font-size:13px;';
            });
        }
    });

    function resolveCss(name) {
        var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || '';
    }
    function createChart(canvasId, labels, data, colorVar) {
        if (typeof Chart === 'undefined') return;
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        try {
            var color = resolveCss(colorVar) || '#1a237e';
            var grid = resolveCss('--divider') || '#f0f0f0';
            var tick = resolveCss('--text-faint') || '#999';
            new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    borderColor: color,
                    backgroundColor: color + '20',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: true, grid: { display: false }, ticks: { font: { size: 10 }, color: tick } },
                    y: { display: true, grid: { color: grid }, ticks: { font: { size: 10 }, color: tick } }
                }
            }
            });
        } catch (e) {
            if (ctx.parentElement) {
                ctx.parentElement.textContent = '차트 데이터를 표시할 수 없습니다.';
                ctx.parentElement.style.color = 'var(--text-muted)';
                ctx.parentElement.style.fontSize = '13px';
            }
        }
    }

    function destroyCharts() {
        if (window.Chart && Chart.instances) {
            Object.keys(Chart.instances).forEach(function (k) {
                try { Chart.instances[k].destroy(); } catch (e) {}
            });
        }
    }

    function buildCharts() {
        // 국내 종목 그래프
        {% for stock in domestic_stocks %}
        createChart('chart-domestic-{{ stock.code }}',
            {{ stock.price.weekly_data | map(attribute='date') | list | tojson }},
            {{ stock.price.weekly_data | map(attribute='close') | list | tojson }},
            '--primary');
        {% endfor %}

        // 해외 종목 그래프
        {% for stock in foreign_stocks %}
        createChart('chart-foreign-{{ stock.code }}',
            {{ stock.price.weekly_data | map(attribute='date') | list | tojson }},
            {{ stock.price.weekly_data | map(attribute='close') | list | tojson }},
            '--nasdaq');
        {% endfor %}
    }

    if (typeof Chart !== 'undefined') {
        buildCharts();
    } else {
        window.addEventListener('load', function () {
            if (typeof Chart !== 'undefined') buildCharts();
        });
    }
    document.addEventListener('themechange', function () {
        destroyCharts();
        buildCharts();
    });
    </script>
    <script>
    // 저작된 모먼트: 변동률 숫자가 목푯값까지 카운트 (prefers-reduced-motion 시 정적 유지)
    (function () {
        var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reduce) return;
        var els = document.querySelectorAll('.change-rate[data-rate]');
        els.forEach(function (el) {
            var target = parseFloat(el.getAttribute('data-rate'));
            if (isNaN(target)) return;
            var neg = target < 0;
            var abs = Math.abs(target);
            var start = null;
            var dur = 700;
            function step(ts) {
                if (!start) start = ts;
                var p = Math.min((ts - start) / dur, 1);
                var eased = 1 - Math.pow(1 - p, 3);
                var cur = abs * eased;
                el.textContent = (neg ? '-' : '+') + cur.toFixed(2) + '%';
                if (p < 1) { requestAnimationFrame(step); }
                else { el.textContent = (neg ? '-' : '+') + abs.toFixed(2) + '%'; }
            }
            requestAnimationFrame(step);
        });
    })();
    </script>
    <script>
    (function () {
        var btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', function () {
                var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                try { localStorage.setItem('stockpilot-theme', next); } catch (e) {}
                try { document.dispatchEvent(new CustomEvent('themechange')); } catch (e) {}
            });
        }
    })();
    </script>
</body>
</html>"""

    DETAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ stock.name }} {{ year_week_label }} 주간 분석 - {{ date }}</title>
    <script defer src="/static/chart.umd.min.js"></script>
    <link rel="stylesheet" href="/static/theme.css">
    <script>
    (function () {
        var stored = null;
        try { stored = localStorage.getItem('stockpilot-theme'); } catch (e) {}
        var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', stored === 'dark' || stored === 'light' ? stored : (prefersDark ? 'dark' : 'light'));
    })();
    </script>
    <style>
        .container { max-width: 900px; }
        header.brand .back { color: var(--on-primary-sub); }
        header.brand .back:hover { color: var(--on-primary); }

        .chart-container { height: 200px; margin: 16px 0; }

        .trend-table { width: 100%; }
        .trend-table td { padding: 10px; }

        .key-points { padding: 20px; border-radius: 8px; }
        .key-points ul { list-style: none; }
        .key-points li { padding: 6px 0; padding-left: 20px; position: relative; }
        .key-points li::before { content: "▸"; position: absolute; left: 0; color: var(--primary); }

        .news-row { padding: 12px 0; border-bottom: 1px solid var(--divider); }
        .news-row:last-child { border: none; }

        /* 데이터 기준 배지: 구간 일치 / 구간 일부 미수집 / 기준일 스냅샷 / 미지원 */
        .basis-badge {
            display: inline-block; vertical-align: middle;
            font-size: 11px; font-weight: 600; line-height: 1;
            padding: 3px 7px; margin-left: 8px; border-radius: 999px;
            border: 1px solid transparent; white-space: nowrap; cursor: help;
        }
        .basis-period { background: rgba(25, 118, 210, .12); color: #1565c0; border-color: rgba(21, 101, 192, .35); }
        .basis-snapshot { background: rgba(245, 159, 0, .14); color: #b26a00; border-color: rgba(245, 159, 0, .4); }
        .basis-unavailable { background: rgba(158, 158, 158, .16); color: #616161; border-color: rgba(97, 97, 97, .32); }
        .basis-incomplete { background: rgba(211, 47, 47, .12); color: #c62828; border-color: rgba(211, 47, 47, .4); }
        [data-theme="dark"] .basis-period { background: rgba(66, 165, 245, .18); color: #90caf9; border-color: rgba(66, 165, 245, .4); }
        [data-theme="dark"] .basis-snapshot { background: rgba(255, 183, 77, .16); color: #ffcc80; border-color: rgba(255, 183, 77, .38); }
        [data-theme="dark"] .basis-unavailable { background: rgba(174, 174, 174, .16); color: #bdbdbd; border-color: rgba(189, 189, 189, .3); }
        [data-theme="dark"] .basis-incomplete { background: rgba(239, 83, 80, .18); color: #ef9a9a; border-color: rgba(239, 83, 80, .4); }

        .basis-note {
            font-size: 13px; color: var(--text-secondary);
            margin: 10px 0 0; padding: 8px 11px; border-radius: 6px;
            background: rgba(245, 159, 0, .08);
            border-left: 3px solid rgba(245, 159, 0, .55);
        }
        .basis-empty { color: var(--text-secondary); font-size: 14px; margin: 10px 0 0; }
    </style>
</head>
<body>
{% macro basis_badge(align, name) %}{% if align and align.get(name) %}<span class="basis-badge basis-{{ align[name].basis }}" title="{{ align[name].note or align[name].label }}">{{ align[name].label }}</span>{% endif %}{% endmacro %}
{% macro basis_note(align, name) %}{% if align and align.get(name) and align[name].note %}<p class="basis-note">{{ align[name].note }}</p>{% endif %}{% endmacro %}
    <button type="button" class="theme-toggle" id="theme-toggle" aria-label="테마 전환">🌓</button>
    <div class="container motion-settle">
        <header class="brand">
            <a href="index.html" class="back">← 목록으로</a>
            <h1>{{ stock.name }} ({{ stock.code }})</h1>
            <p>{{ year_week_label }} 주간 분석 리포트 | {{ range_label }} · {{ stock.currency }}</p>
        </header>

        <div class="section">
            <h2>주가 정보</h2>
            <div class="price-grid">
                <div class="price-item">
                    <div class="label">현재가</div>
                    <div class="value">{{ '₩{:,.0f}'.format(stock.price.current_price) if stock.currency == 'KRW' else '${:,.2f}'.format(stock.price.current_price) }}</div>
                </div>
                <div class="price-item">
                    <div class="label">주간 변동률</div>
                    <div class="value {{ 'pos-strong' if stock.price.change_rate > 0 else 'neg-strong' }} rate-anim" data-rate="{{ stock.price.change_rate }}">{{ '%+.2f'|format(stock.price.change_rate) }}%</div>
                </div>
                <div class="price-item">
                    <div class="label">주간 시작가</div>
                    <div class="value">{{ '₩{:,.0f}'.format(stock.price.start_price) if stock.currency == 'KRW' else '${:,.2f}'.format(stock.price.start_price) }}</div>
                </div>
                <div class="price-item">
                    <div class="label">주간 종가</div>
                    <div class="value">{{ '₩{:,.0f}'.format(stock.price.end_price) if stock.currency == 'KRW' else '${:,.2f}'.format(stock.price.end_price) }}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>주간 가격 추이{{ basis_badge(stock.data_alignment, 'price') }}</h2>
            {% if stock.data_alignment and stock.data_alignment.get('price') and stock.data_alignment['price'].note %}
            <p class="basis-note basis-note-warn">{{ stock.data_alignment['price'].note }}</p>
            {% endif %}
            <div class="chart-container">
                <canvas id="detail-chart"></canvas>
            </div>
            <table>
                <thead>
                    <tr><th>날짜</th><th>종가</th></tr>
                </thead>
                <tbody>
                {% for item in stock.price.weekly_data %}
                    <tr>
                        <td>{{ item.date }}</td>
                        <td>{{ '₩{:,.0f}'.format(item.close) if stock.currency == 'KRW' else '${:,.2f}'.format(item.close) }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

        {% if is_custom and stock.data_alignment %}
        <div class="section">
            <h2>구간 지정 분석 · 데이터 기준</h2>
            <p class="basis-empty">
                이 리포트는 지정 구간 <strong>{{ range_label }}</strong> ({{ trading_label }})으로 조회했습니다.
                섹션마다 데이터 기준이 다릅니다.
            </p>
            <table>
                <thead><tr><th>구분</th><th>기준</th><th>설명</th></tr></thead>
                <tbody>
                {% for section, info in stock.data_alignment.items() %}
                    <tr>
                        <td>{{ SECTION_LABELS.get(section, section) }}</td>
                        <td><span class="basis-badge basis-{{ info.basis }}">{{ info.label }}</span></td>
                        <td class="muted">{{ info.note or '-' }}{% if info.count is defined %} ({{ info.count }}건){% endif %}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        {% if stock.market_type == 'domestic' and stock.investor_trend and stock.investor_trend.daily_trend %}
        <div class="section">
            <h2>투자자별 매매동향{{ basis_badge(stock.data_alignment, 'investor_trend') }}</h2>
            <table class="trend-table">
                <thead>
                    <tr>
                        <th>날짜</th>
                        <th>기관</th>
                        <th>외국인</th>
                        <th>개인</th>
                    </tr>
                </thead>
                <tbody>
                {% for item in stock.investor_trend.daily_trend %}
                    <tr>
                        <td>{{ item.date }}</td>
                        <td class="{{ 'trend-positive' if item.inst_net > 0 else 'trend-negative' }}">{{ '{:+,}'.format(item.inst_net) }}</td>
                        <td class="{{ 'trend-positive' if item.foreign_net > 0 else 'trend-negative' }}">{{ '{:+,}'.format(item.foreign_net) }}</td>
                        <td class="{{ 'trend-positive' if item.individual_net > 0 else 'trend-negative' }}">{{ '{:+,}'.format(item.individual_net) }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            <div class="muted" style="margin-top: 12px; font-size: 13px;">
                외국인 보유율: <strong>{{ stock.investor_trend.foreign_ratio }}</strong>
                {% if stock.investor_trend.foreign_ratio_change != 0 %}
                    <span class="{{ 'trend-positive' if stock.investor_trend.foreign_ratio_change > 0 else 'trend-negative' }}">
                        ({{ '%+.2f'|format(stock.investor_trend.foreign_ratio_change) }}%p)
                    </span>
                {% endif %}
            </div>
        </div>
        {% endif %}

        {% if stock.market_type == 'foreign' and stock.short_interest %}
        <div class="section">
            <h2>숏 포지션 / 공매도</h2>
            <div class="price-grid">
                <div class="price-item">
                    <div class="label">숏 비율</div>
                    <div class="value" style="font-size: 16px;">{{ stock.short_interest.short_percent }}</div>
                </div>
                <div class="price-item">
                    <div class="label">숏 커버링 일수</div>
                    <div class="value" style="font-size: 16px;">{{ stock.short_interest.short_covering_days }}</div>
                </div>
                <div class="price-item">
                    <div class="label">공매도 수량</div>
                    <div class="value" style="font-size: 16px;">{{ stock.short_interest.shares_short }}</div>
                </div>
                <div class="price-item">
                    <div class="label">센티먼트</div>
                    <div class="value" style="font-size: 14px;">{{ stock.short_interest.sentiment }}</div>
                </div>
            </div>
        </div>
        {% endif %}

        <div class="section">
            <h2>주요 뉴스{{ basis_badge(stock.data_alignment, 'news') }}</h2>
            {% for news in stock.news %}
            <div class="news-row">
                <a href="{{ news.link }}" target="_blank">{{ news.title }}</a>
                <div class="muted" style="font-size:12px; margin-top:4px;">{{ news.time }}</div>
            </div>
            {% endfor %}
            {% if not stock.news %}
            <p class="basis-empty">해당 구간에 발행된 뉴스를 찾지 못했습니다. (국내: 토스증권이 최근 6건만 제공 / 해외: 야후 피드가 최근 며칠치만 제공)</p>
            {% endif %}
            {{ basis_note(stock.data_alignment, 'news') }}
        </div>

        {% if stock.disclosures %}
        <div class="section">
            <h2>최근 공시</h2>
            {% for disc in stock.disclosures %}
            <div class="news-row">
                <a href="{{ disc.link }}" target="_blank">{{ disc.title }}</a>
                <div class="muted" style="font-size:12px; margin-top:4px;">{{ disc.date }} | {{ disc.type }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="section">
            <h2>재무 지표{{ basis_badge(stock.data_alignment, 'financial') }}</h2>
            <div class="price-grid">
                {% for key, value in stock.financial.items() %}
                <div class="price-item">
                    <div class="label">{{ key }}</div>
                    <div class="value" style="font-size:16px;">{{ value }}</div>
                </div>
                {% endfor %}
            </div>
            {{ basis_note(stock.data_alignment, 'financial') }}
        </div>

        <div class="section">
            <div class="key-points callout">
                <h3>앞으로 1주간 주목 포인트</h3>
                <ul>
                {% for point in stock.key_points %}
                    <li>{{ point }}</li>
                {% endfor %}
                </ul>
            </div>
        </div>
    </div>

    <script>
    function resolveCss(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '';
    }
    function buildDetailChart() {
        var detailCtx = document.getElementById('detail-chart');
        if (!detailCtx) return;
        if (detailCtx.__chart) { try { detailCtx.__chart.destroy(); } catch (e) {} }
        try {
            var dColor = resolveCss('--primary') || '#1a237e';
            var dGrid = resolveCss('--divider') || '#f0f0f0';
            var dTick = resolveCss('--text-faint') || '#999';
            detailCtx.__chart = new Chart(detailCtx, {
                type: 'line',
                data: {
                    labels: {{ stock.price.weekly_data | map(attribute='date') | list | tojson }},
                    datasets: [{
                        data: {{ stock.price.weekly_data | map(attribute='close') | list | tojson }},
                        borderColor: dColor,
                        backgroundColor: dColor + '20',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: dTick } },
                        y: { grid: { color: dGrid }, ticks: { color: dTick } }
                    }
                }
            });
        } catch (e) {
            if (detailCtx.parentElement) {
                detailCtx.parentElement.textContent = '차트 데이터를 표시할 수 없습니다.';
                detailCtx.parentElement.style.color = 'var(--text-muted)';
                detailCtx.parentElement.style.fontSize = '14px';
            }
        }
    }
    function showDetailChartError() {
        var detailCtx = document.getElementById('detail-chart');
        if (detailCtx && detailCtx.parentElement) {
            detailCtx.parentElement.textContent = '차트를 불러오지 못했습니다. 네트워크 연결을 확인해주세요.';
            detailCtx.parentElement.style.cssText = 'display:flex;align-items:center;justify-content:center;color:#888;font-size:14px;';
        }
    }
    if (typeof Chart !== 'undefined') {
        buildDetailChart();
    } else {
        window.addEventListener('load', function () {
            if (typeof Chart !== 'undefined') buildDetailChart();
            else showDetailChartError();
        });
    }
    document.addEventListener('themechange', function () { buildDetailChart(); });
    </script>
    <script>
    // 저작된 모먼트 연속: 주간 변동률 카운트 (prefers-reduced-motion 시 정적 유지)
    (function () {
        var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reduce) return;
        var el = document.querySelector('[data-rate]');
        if (!el) return;
        var target = parseFloat(el.getAttribute('data-rate'));
        if (isNaN(target)) return;
        var neg = target < 0;
        var abs = Math.abs(target);
        var start = null;
        var dur = 700;
        function step(ts) {
            if (!start) start = ts;
            var p = Math.min((ts - start) / dur, 1);
            var eased = 1 - Math.pow(1 - p, 3);
            el.textContent = (neg ? '-' : '+') + (abs * eased).toFixed(2) + '%';
            if (p < 1) { requestAnimationFrame(step); }
            else { el.textContent = (neg ? '-' : '+') + abs.toFixed(2) + '%'; }
        }
        requestAnimationFrame(step);
    })();
    </script>
    <script>
    (function () {
        var btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', function () {
                var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                try { localStorage.setItem('stockpilot-theme', next); } catch (e) {}
                try { document.dispatchEvent(new CustomEvent('themechange')); } catch (e) {}
            });
        }
    })();
    </script>
</body>
</html>"""

    def __init__(self, report_dir: str = "reports/weekly"):
        self.report_dir = report_dir

    def _resolve_period(self, all_results: dict, period: Optional[WeeklyPeriod], run_date: date):
        """표시/저장할 구간 확정

        1) 요청 구간 계산 (미전달 시 실행일 기준)
        2) 자동 구간일 때만 실제 수집된 거래일로 좁힌다 (휴장일 반영)

        지정 구간(is_custom)은 좁히지 않는다. 좁히면 사용자가 요청한
        5거래일 중 3일만 온 situation을 리포트상 3거래일 구간으로 보이게 되어
        '데이터가 빠졌다'는 사실 자체가 사라진다. 누락은 배지와 경고로 알린다.
        """
        requested = period or resolve_period(run_date)

        if requested.is_custom:
            return requested

        # 모든 성공 종목의 거래일을 합쳐 가장 넓은 실제 구간을 구한다
        collected = []
        for stock in all_results.get("domestic", []) + all_results.get("foreign", []):
            if "error" in stock:
                continue
            for row in (stock.get("price") or {}).get("weekly_data", []):
                if row.get("date"):
                    collected.append(row["date"])

        actual = WeeklyPeriod.from_trading_days(
            collected, mode=requested.mode, run_date=run_date
        )
        if not actual:
            return requested

        # 실제 거래일이 요청 구간 밖(과거/미래)으로 튀면 요청 구간을 신뢰
        if actual.end < requested.start or actual.start > requested.end:
            return requested
        return actual

    def generate(
        self,
        all_results: dict,
        date_str: Optional[str] = None,
        period: Optional[WeeklyPeriod] = None,
        run_date: Optional[date] = None,
    ) -> str:
        """전체 리포트 생성

        폴더명은 기본적으로 실행일이지만, 사용자가 구간을 직접 지정한
        경우에는 그 구간의 종료일을 쓴다. 그래야 과거 주차 분석이
        오늘짜 리포트 폴더를 덮어쓰지 않는다.
        """
        if run_date is None:
            run_date = date.fromisoformat(date_str) if date_str else date.today()
        if date_str is None:
            if period and period.is_custom:
                date_str = period.end.isoformat()
            else:
                date_str = run_date.strftime("%Y-%m-%d")

        period = self._resolve_period(all_results, period, run_date)
        period_ctx = {
            "year_week_label": period.year_week_label,
            "range_label": period.range_label,
            "trading_label": period.trading_label,
            "mode_label": period.mode_label,
            "is_custom": period.is_custom,
        }

        output_dir = os.path.join(self.report_dir, date_str)
        os.makedirs(output_dir, exist_ok=True)

        # 실패한 종목은 템플릿이 price/news 를 요구하므로 렌더링에서 제외
        def usable(stocks: list) -> list:
            return [s for s in stocks if "error" not in s and s.get("price")]

        raw_domestic = all_results.get("domestic", [])
        raw_foreign = all_results.get("foreign", [])
        domestic_stocks = usable(raw_domestic)
        foreign_stocks = usable(raw_foreign)
        failed_count = (len(raw_domestic) - len(domestic_stocks)) + (
            len(raw_foreign) - len(foreign_stocks)
        )
        if failed_count:
            print(f"분석 실패로 제외된 종목: {failed_count}건")

        # 구간 메타데이터 저장 (대시보드 캘린더가 사용)
        meta = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "date": date_str,
            "domestic_count": len(domestic_stocks),
            "foreign_count": len(foreign_stocks),
            "failed_count": failed_count,
            **period.to_dict(),
        }
        meta_path = os.path.join(output_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"구간 메타데이터 생성: {meta_path}")

        # 구간 거래일 중 소스에 없는 날짜를 모아 상단 경고에 쓴다.
        # 소스(yfinance 국내 피드)는 최근 거래일이 1~2일 늦게 반영되므로
        # '구간 일치' 배지만으로는 이 사실을 알 수 없다.
        missing_by_day = {}
        for stocks in (domestic_stocks, foreign_stocks):
            for s in stocks:
                p_align = (s.get("data_alignment") or {}).get("price") or {}
                for d in p_align.get("missing_days") or []:
                    missing_by_day.setdefault(d, []).append(
                        f"{s.get('name', s.get('code'))} ({s.get('market_type', '')})"
                    )
        price_gaps = sorted(missing_by_day.items())

        # 인덱스 페이지 생성
        index_template = Template(self.INDEX_TEMPLATE)
        index_html = index_template.render(
            domestic_stocks=domestic_stocks,
            foreign_stocks=foreign_stocks,
            date=date_str,
            price_gaps=price_gaps,
            **period_ctx,
        )
        index_path = os.path.join(output_dir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_html)
        print(f"인덱스 페이지 생성: {index_path}")

        # 종목별 상세 페이지 생성
        detail_template = Template(self.DETAIL_TEMPLATE)

        # 종목별 상세 (국내/해외)
        for stocks, prefix in ((domestic_stocks, "domestic"), (foreign_stocks, "foreign")):
            for stock in stocks:
                detail_html = detail_template.render(
                    stock=stock, date=date_str, SECTION_LABELS=SECTION_LABELS, **period_ctx
                )
                detail_path = os.path.join(output_dir, f"{prefix}_{stock['code']}.html")
                with open(detail_path, "w", encoding="utf-8") as f:
                    f.write(detail_html)
                print(f"상세 리포트 생성: {detail_path}")

        return output_dir
