# -*- coding: utf-8 -*-
"""HTML 리포트 생성 모듈"""
import os
import json
from datetime import datetime
from typing import Optional
from jinja2 import Template


class HtmlReporter:
    """분석 결과를 HTML 리포트로 생성"""

    # 인라인 HTML 템플릿
    INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>주간 주식 분석 리포트 - {{ date }}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', -apple-system, sans-serif; background: #f5f7fa; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        header { background: linear-gradient(135deg, #1a237e, #0d47a1); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; text-align: center; }
        header h1 { font-size: 28px; margin-bottom: 8px; }
        header p { opacity: 0.9; font-size: 14px; }

        .floating-action { position: fixed; top: 20px; right: 20px; z-index: 1000; display: flex; gap: 8px; }
        .btn { padding: 10px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.2s; border: none; font-size: 13px; text-decoration: none; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
        .btn-primary { background: #1a237e; color: white; }
        .btn-primary:hover { background: #0d47a1; }
        .btn-secondary { background: white; color: #1a237e; }
        .btn-secondary:hover { background: #e8eaf6; }

        .info-bar { background: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
        .stock-summary { margin-bottom: 15px; }
        .stock-summary:last-of-type { margin-bottom: 0; }
        .stock-summary h3 { font-size: 14px; margin-bottom: 10px; color: #1a237e; }
        .stock-tags { display: flex; flex-wrap: wrap; gap: 8px; }
        .stock-tag { background: #f5f7fa; padding: 6px 12px; border-radius: 20px; font-size: 12px; border: 1px solid #e0e0e0; }
        .stock-tag.positive { background: #ffebee; border-color: #ef9a9a; color: #c62828; }
        .stock-tag.negative { background: #e3f2fd; border-color: #90caf9; color: #1565c0; }

        .tabs { display: flex; gap: 8px; margin-bottom: 24px; }
        .tab { padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s; border: 2px solid #e0e0e0; background: white; }
        .tab:hover { border-color: #1a237e; }
        .tab.active { background: #1a237e; color: white; border-color: #1a237e; }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .stock-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .stock-card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); transition: transform 0.2s, box-shadow 0.2s; }
        .stock-card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
        .stock-card h2 { font-size: 20px; color: #1a237e; margin-bottom: 6px; }
        .stock-card .code { font-size: 12px; color: #888; margin-bottom: 16px; }
        .change-rate { font-size: 24px; font-weight: 700; margin: 12px 0; }
        .change-rate.positive { color: #e53935; }
        .change-rate.negative { color: #1565c0; }
        .change-rate.neutral { color: #666; }
        .price-info { font-size: 14px; color: #666; margin-bottom: 8px; }

        .chart-container { height: 120px; margin: 16px 0; }

        .trend-box { background: #f8f9ff; padding: 12px; border-radius: 8px; margin-top: 12px; font-size: 13px; }
        .trend-row { display: flex; justify-content: space-between; padding: 4px 0; }
        .trend-label { color: #666; }
        .trend-value { font-weight: 600; }
        .trend-positive { color: #e53935; }
        .trend-negative { color: #1565c0; }

        .news-list { margin-top: 16px; }
        .news-list h3 { font-size: 14px; color: #1a237e; margin-bottom: 10px; }
        .news-item { padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
        .news-item:last-child { border: none; }
        .news-item a { color: #1565c0; text-decoration: none; font-size: 14px; line-height: 1.5; }
        .news-item a:hover { text-decoration: underline; }
        .news-time { font-size: 12px; color: #999; margin-top: 4px; }
        .news-source { background: #e8eaf6; color: #1a237e; padding: 2px 6px; border-radius: 4px; font-size: 11px; }

        .key-points { background: #f8f9ff; padding: 16px; border-radius: 8px; margin-top: 16px; }
        .key-points h3 { font-size: 14px; color: #1a237e; margin-bottom: 10px; }
        .key-points ul { list-style: none; }
        .key-points li { font-size: 13px; padding: 4px 0; padding-left: 16px; position: relative; }
        .key-points li:before { content: "•"; position: absolute; left: 0; color: #1a237e; }

        .btn-detail { display: inline-block; margin-top: 16px; padding: 10px 20px; background: #1a237e; color: white; text-decoration: none; border-radius: 8px; font-size: 14px; transition: background 0.2s; }
        .btn-detail:hover { background: #0d47a1; }

        .market-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-left: 8px; }
        .badge-kospi { background: #e3f2fd; color: #1565c0; }
        .badge-nasdaq { background: #f3e5f5; color: #7b1fa2; }
        .ticker-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-left: 8px; background: #e8f5e9; color: #2e7d32; }

        footer { text-align: center; padding: 30px; color: #999; font-size: 13px; }
    </style>
</head>
<body>
    <div class="floating-action">
        <a href="/api/run" class="btn btn-primary">전체 분석 실행</a>
        <a href="/api/run?with_dart=true" class="btn btn-secondary">DART 포함</a>
        <a href="/" class="btn btn-secondary">새로고침</a>
    </div>

    <div class="container">
        <header>
            <h1>{{ date }} 주간 리포트</h1>
            <p>자동 분석 결과 | domestic: {{ domestic_stocks|length }}종목, foreign: {{ foreign_stocks|length }}종목</p>
        </header>

        <div class="info-bar">
            <div class="stock-summary">
                <h3>📋 국내 종목</h3>
                <div class="stock-tags">
                    {% for stock in domestic_stocks %}
                    <span class="stock-tag {{ 'positive' if stock.price.change_rate > 0 else 'negative' }}">
                        {{ stock.name }} {{ '%+.1f'|format(stock.price.change_rate) }}%
                    </span>
                    {% endfor %}
                </div>
            </div>
            
            <div class="stock-summary">
                <h3>🌍 해외 종목</h3>
                <div class="stock-tags">
                    {% for stock in foreign_stocks %}
                    <span class="stock-tag {{ 'positive' if stock.price.change_rate > 0 else 'negative' }}">
                        {{ stock.name }} {{ '%+.1f'|format(stock.price.change_rate) }}%
                    </span>
                    {% endfor %}
                </div>
            </div>
        </div>

        <div class="tabs">
            <div class="tab active" onclick="showTab('domestic')">🇰🇷 국내</div>
            <div class="tab" onclick="showTab('foreign')">🌍 해외</div>
        </div>

        <div id="domestic" class="tab-content active">
            <div class="stock-grid">
            {% for stock in domestic_stocks %}
                <div class="stock-card">
                    <h2>{{ stock.name }} <span class="ticker-badge">{{ stock.code }}</span> <span class="market-badge badge-kospi">{{ stock.market }}</span></h2>

                    <div class="change-rate {{ 'positive' if stock.price.change_rate > 0 else ('negative' if stock.price.change_rate < 0 else 'neutral') }}">
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
                        <h3>주요 뉴스</h3>
                        {% for news in stock.news[:2] %}
                        <div class="news-item">
                            <a href="{{ news.link }}" target="_blank">{{ news.title[:60] }}{% if news.title|length > 60 %}...{% endif %}</a>
                            <div class="news-time">
                                {% if news.source %}<span class="news-source">{{ news.source }}</span>{% endif %}
                                {% if news.time %} | {{ news.time }}{% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    </div>

                    <div class="key-points">
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

        <div id="foreign" class="tab-content">
            <div class="stock-grid">
            {% for stock in foreign_stocks %}
                <div class="stock-card">
                    <h2>{{ stock.name }} <span class="ticker-badge">{{ stock.code }}</span> <span class="market-badge badge-nasdaq">{{ stock.market }}</span></h2>

                    <div class="change-rate {{ 'positive' if stock.price.change_rate > 0 else ('negative' if stock.price.change_rate < 0 else 'neutral') }}">
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
                        <h3>주요 뉴스</h3>
                        {% for news in stock.news[:2] %}
                        <div class="news-item">
                            <a href="{{ news.link }}" target="_blank">{{ news.title }}</a>
                            <div class="news-time">{{ news.time }}</div>
                        </div>
                        {% endfor %}
                    </div>

                    <div class="key-points">
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
            주간 주식 분석 리포트 | 자동 생성 {{ date }}
        </footer>
    </div>

    <script>
    function showTab(name) {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
        document.getElementById(name).classList.add('active');
        event.target.classList.add('active');
    }

    // 그래프 생성 함수
    function createChart(canvasId, labels, data, color) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
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
                    x: { display: true, grid: { display: false }, ticks: { font: { size: 10 } } },
                    y: { display: true, grid: { color: '#f0f0f0' }, ticks: { font: { size: 10 } } }
                }
            }
        });
    }

    // 국내 종목 그래프
    {% for stock in domestic_stocks %}
    createChart('chart-domestic-{{ stock.code }}',
        {{ stock.price.weekly_data | map(attribute='date') | list | tojson }},
        {{ stock.price.weekly_data | map(attribute='close') | list | tojson }},
        '#1a237e');
    {% endfor %}

    // 해외 종목 그래프
    {% for stock in foreign_stocks %}
    createChart('chart-foreign-{{ stock.code }}',
        {{ stock.price.weekly_data | map(attribute='date') | list | tojson }},
        {{ stock.price.weekly_data | map(attribute='close') | list | tojson }},
        '#7b1fa2');
    {% endfor %}
    </script>
</body>
</html>"""

    DETAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ stock.name }} 주간 분석 - {{ date }}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', -apple-system, sans-serif; background: #f5f7fa; color: #333; }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        header { background: linear-gradient(135deg, #1a237e, #0d47a1); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; }
        header h1 { font-size: 24px; }
        header .back { color: rgba(255,255,255,0.8); text-decoration: none; font-size: 14px; display: inline-block; margin-bottom: 10px; }
        header .back:hover { color: white; }
        .section { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
        .section h2 { font-size: 18px; color: #1a237e; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid #e8eaf6; }
        .price-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }
        .price-item { text-align: center; padding: 16px; background: #f8f9ff; border-radius: 8px; }
        .price-item .label { font-size: 13px; color: #888; margin-bottom: 6px; }
        .price-item .value { font-size: 20px; font-weight: 700; }

        .chart-container { height: 200px; margin: 16px 0; }

        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #f0f0f0; }
        th { background: #f8f9ff; font-size: 13px; color: #666; }
        td { font-size: 14px; }
        a { color: #1565c0; text-decoration: none; }
        a:hover { text-decoration: underline; }

        .trend-table { width: 100%; }
        .trend-table td { padding: 10px; }
        .trend-positive { color: #e53935; font-weight: 600; }
        .trend-negative { color: #1565c0; font-weight: 600; }

        .key-points { background: #f8f9ff; padding: 20px; border-radius: 8px; }
        .key-points h3 { color: #1a237e; margin-bottom: 12px; }
        .key-points ul { list-style: none; }
        .key-points li { padding: 6px 0; padding-left: 20px; position: relative; font-size: 14px; }
        .key-points li:before { content: "▸"; position: absolute; left: 0; color: #1a237e; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <a href="index.html" class="back">← 목록으로</a>
            <h1>{{ stock.name }} ({{ stock.code }})</h1>
            <p>{{ date }} 주간 분석 리포트 | {{ stock.currency }}</p>
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
                    <div class="value" style="color: {{ '#e53935' if stock.price.change_rate > 0 else '#1565c0' }}">{{ '%+.2f'|format(stock.price.change_rate) }}%</div>
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
            <h2>주간 가격 추이</h2>
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

        {% if stock.market_type == 'domestic' and stock.investor_trend and stock.investor_trend.daily_trend %}
        <div class="section">
            <h2>투자자별 매매동향</h2>
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
            <div style="margin-top: 12px; font-size: 13px; color: #666;">
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
            <h2>주요 뉴스</h2>
            {% for news in stock.news %}
            <div style="padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                <a href="{{ news.link }}" target="_blank">{{ news.title }}</a>
                <div style="font-size:12px; color:#999; margin-top:4px;">{{ news.time }}</div>
            </div>
            {% endfor %}
        </div>

        {% if stock.disclosures %}
        <div class="section">
            <h2>최근 공시</h2>
            {% for disc in stock.disclosures %}
            <div style="padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                <a href="{{ disc.link }}" target="_blank">{{ disc.title }}</a>
                <div style="font-size:12px; color:#999; margin-top:4px;">{{ disc.date }} | {{ disc.type }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="section">
            <h2>재무 지표</h2>
            <div class="price-grid">
                {% for key, value in stock.financial.items() %}
                <div class="price-item">
                    <div class="label">{{ key }}</div>
                    <div class="value" style="font-size:16px;">{{ value }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="section">
            <div class="key-points">
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
    const ctx = document.getElementById('detail-chart');
    if (ctx) {
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ stock.price.weekly_data | map(attribute='date') | list | tojson }},
                datasets: [{
                    data: {{ stock.price.weekly_data | map(attribute='close') | list | tojson }},
                    borderColor: '#1a237e',
                    backgroundColor: '#1a237e20',
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
                    x: { grid: { display: false } },
                    y: { grid: { color: '#f0f0f0' } }
                }
            }
        });
    }
    </script>
</body>
</html>"""

    def __init__(self, report_dir: str = "reports/weekly"):
        self.report_dir = report_dir

    def generate(self, all_results: dict, date_str: Optional[str] = None) -> str:
        """전체 리포트 생성"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        output_dir = os.path.join(self.report_dir, date_str)
        os.makedirs(output_dir, exist_ok=True)

        domestic_stocks = all_results.get("domestic", [])
        foreign_stocks = all_results.get("foreign", [])

        # 인덱스 페이지 생성
        index_template = Template(self.INDEX_TEMPLATE)
        index_html = index_template.render(
            domestic_stocks=domestic_stocks,
            foreign_stocks=foreign_stocks,
            date=date_str,
        )
        index_path = os.path.join(output_dir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_html)
        print(f"인덱스 페이지 생성: {index_path}")

        # 종목별 상세 페이지 생성
        detail_template = Template(self.DETAIL_TEMPLATE)

        # 국내 종목 상세
        for stock in domestic_stocks:
            if "error" not in stock:
                detail_html = detail_template.render(stock=stock, date=date_str)
                detail_path = os.path.join(output_dir, f"domestic_{stock['code']}.html")
                with open(detail_path, "w", encoding="utf-8") as f:
                    f.write(detail_html)
                print(f"상세 리포트 생성: {detail_path}")

        # 해외 종목 상세
        for stock in foreign_stocks:
            if "error" not in stock:
                detail_html = detail_template.render(stock=stock, date=date_str)
                detail_path = os.path.join(output_dir, f"foreign_{stock['code']}.html")
                with open(detail_path, "w", encoding="utf-8") as f:
                    f.write(detail_html)
                print(f"상세 리포트 생성: {detail_path}")

        return output_dir
