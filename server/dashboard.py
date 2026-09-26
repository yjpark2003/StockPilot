# -*- coding: utf-8 -*-
"""종목 관리 대시보드 HTML"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>종목 관리 대시보드</title>
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
        .nav { display: flex; gap: 10px; margin-bottom: 20px; justify-content: center; flex-wrap: wrap; }
        .nav a { padding: 10px 20px; background: var(--surface); color: var(--primary); text-decoration: none; border-radius: 8px; font-weight: 600; transition: background-color 0.2s ease, color 0.2s ease; }
        .nav a:hover { background: var(--surface-hover); color: var(--primary); }
        .nav a.active { background: var(--primary); color: var(--on-primary); }
        .stats { display: flex; gap: 20px; margin-bottom: 30px; justify-content: center; flex-wrap: wrap; }
        .stats .stat-card:nth-child(1) { --enter-delay: 0s; }
        .stats .stat-card:nth-child(2) { --enter-delay: 0.05s; }
        .stats .stat-card:nth-child(3) { --enter-delay: 0.10s; }
        .stat-card { background: var(--surface); padding: 20px 40px; border-radius: 12px; box-shadow: var(--shadow-sm); text-align: center; }
        .stat-card h3 { font-size: 32px; color: var(--primary); font-variant-numeric: tabular-nums; }
        .stat-card p { color: var(--text-secondary); font-size: 14px; margin-top: 5px; }

        .stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
        .stock-card { background: var(--surface-subtle); border-radius: 10px; padding: 16px; border: 1px solid var(--border); transition: border-color 0.2s ease, box-shadow 0.2s ease; }
        .stock-card:hover { border-color: var(--primary); box-shadow: var(--shadow-sm); }
        .stock-card .name { font-weight: 600; color: var(--primary); margin-bottom: 6px; font-size: 16px; }
        .stock-card .code { color: var(--text-muted); font-size: 13px; margin-bottom: 4px; font-variant-numeric: tabular-nums; }
        .stock-card .market { color: var(--text-secondary); font-size: 12px; margin-bottom: 10px; }
        .stock-card .actions { display: flex; justify-content: flex-end; }

        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: var(--overlay); z-index: 1000; justify-content: center; align-items: center; }
        .modal.active { display: flex; }
        .modal-content { background: var(--surface); border-radius: 12px; padding: 30px; width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto; box-shadow: var(--shadow-lg); }
        .modal.active .modal-content { animation: sp-settle 0.28s cubic-bezier(0.16, 1, 0.3, 1) both; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h2 { color: var(--primary); }
        .modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: var(--text-secondary); font-family: inherit; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: var(--text); }
        .form-group input { width: 100%; padding: 10px 12px; border: 1px solid var(--input-border); border-radius: 6px; font-size: 14px; font-family: inherit; background: var(--surface); color: var(--text); }
        .form-group input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 15%, transparent); }

        .search-item:focus { background: var(--surface-hover); }
        .search-results { margin-top: 10px; border: 1px solid var(--input-border); border-radius: 6px; max-height: 200px; overflow-y: auto; background: var(--surface); }
        .search-item { padding: 10px 12px; cursor: pointer; border-bottom: 1px solid var(--divider); color: var(--text); }
        .search-item:hover { background: var(--surface-hover); }
        .search-item:last-child { border-bottom: none; }
        .search-item .name { font-weight: 600; color: var(--primary); }
        .search-item .code { color: var(--text-secondary); font-size: 13px; }

        .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 24px; border-radius: 8px; color: #fff; font-weight: 600; z-index: 2000; transform: translateY(100px); opacity: 0; transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease; }
        .toast.success { background: var(--success); }
        .toast.error { background: var(--danger); }
        .toast.show { transform: translateY(0); opacity: 1; }
        .stat-card, .stock-card { will-change: transform; }
        .selected-stock-note { margin-top: 16px; padding: 12px; background: var(--surface-subtle); border-radius: 6px; color: var(--text); }
    </style>
</head>
<body>
    <button type="button" class="theme-toggle" id="theme-toggle" aria-label="테마 전환">🌓</button>
    <div class="container">
        <header class="brand">
            <h1>종목 관리 대시보드</h1>
        </header>
        
        <nav class="nav">
            <a href="/">메인</a>
            <a href="/dashboard" class="active" aria-current="page">종목 관리</a>
        </nav>
        
        <div class="stats">
            <div class="stat-card motion-enter">
                <h3 id="total-count">0</h3>
                <p>전체 종목</p>
            </div>
            <div class="stat-card motion-enter">
                <h3 id="domestic-count">0</h3>
                <p>국내 종목</p>
            </div>
            <div class="stat-card motion-enter">
                <h3 id="foreign-count">0</h3>
                <p>해외 종목</p>
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                <div>
                    <span class="section-title">국내 종목</span>
                    <span class="section-count" id="domestic-info"></span>
                </div>
                <button class="btn btn-primary" onclick="openAddModal('domestic')">+ 추가</button>
            </div>
            <div id="domestic-stocks" class="stock-grid">
                <div class="empty-state">로딩 중...</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                <div>
                    <span class="section-title">해외 종목</span>
                    <span class="section-count" id="foreign-info"></span>
                </div>
                <button class="btn btn-primary" onclick="openAddModal('foreign')">+ 추가</button>
            </div>
            <div id="foreign-stocks" class="stock-grid">
                <div class="empty-state">로딩 중...</div>
            </div>
        </div>
    </div>
    
    <div class="modal" id="addModal" role="dialog" aria-modal="true" aria-labelledby="modal-title" aria-hidden="true">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modal-title">종목 추가</h2>
                <button class="modal-close" onclick="closeModal()" aria-label="닫기">&times;</button>
            </div>
            
            <div class="form-group">
                <label for="search-input">검색어 입력</label>
                <input type="text" id="search-input" placeholder="종목코드 또는 종목명 입력..." oninput="debounceSearch()" autocomplete="off">
                <div id="search-status" role="status" aria-live="polite" style="font-size:12px;color:var(--text-secondary);margin-top:6px;min-height:16px;"></div>
            </div>
            
            <div id="search-results" class="search-results" style="display: none;" role="listbox" aria-label="검색 결과"></div>
            
            <div id="manual-entry" style="display: none; margin-top: 12px; padding: 12px; border: 1px dashed var(--input-border); border-radius: 6px;">
                <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 10px;">검색 결과에 없는 종목은 아래에 직접 입력해주세요.</p>
                <div class="form-group">
                    <label for="manual-code">종목코드</label>
                    <input type="text" id="manual-code" placeholder="예: 005930" maxlength="6" inputmode="numeric" autocomplete="off">
                </div>
                <div class="form-group">
                    <label for="manual-name">종목명</label>
                    <input type="text" id="manual-name" placeholder="예: 삼성전자" autocomplete="off">
                </div>
                <div style="text-align: right;">
                    <button type="button" class="btn btn-secondary" onclick="hideManualEntry()">취소</button>
                    <button type="button" class="btn btn-primary" onclick="selectManualStock()">이 종목 사용</button>
                </div>
            </div>
            
            <div id="selected-stock" style="display: none; margin-top: 16px; padding: 12px; background: var(--surface-subtle); border-radius: 6px;">
                <strong>선택된 종목:</strong> <span id="selected-name"></span> (<span id="selected-code"></span>)
            </div>
            
            <div style="margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end;">
                <button class="btn btn-secondary" onclick="closeModal()">취소</button>
                <button class="btn btn-primary" id="add-btn" onclick="addStock()" disabled>추가</button>
            </div>
        </div>
    </div>
    
    <div id="toast" class="toast"></div>

    <script>
    (function() {
        var currentMarket = 'domestic';
        var selectedStock = null;
        var searchTimeout = null;
        var lastFocusedElement = null;
        
        function esc(str) {
            return String(str == null ? '' : str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }
        
        window.loadStocks = function() {
            document.getElementById('domestic-stocks').innerHTML = '<div class="empty-state">로딩 중...</div>';
            document.getElementById('foreign-stocks').innerHTML = '<div class="empty-state">로딩 중...</div>';
            fetch('/api/stocks')
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    renderDomesticStocks(data.domestic || []);
                    renderForeignStocks(data.foreign || []);
                    document.getElementById('domestic-count').textContent = (data.domestic || []).length;
                    document.getElementById('foreign-count').textContent = (data.foreign || []).length;
                    document.getElementById('total-count').textContent = (data.domestic || []).length + (data.foreign || []).length;
                })
                .catch(function(e) {
                    console.error('종목 로드 오류:', e);
                    var msg = '<div class="empty-state">목록을 불러오지 못했습니다. 새로고침 후 다시 시도해주세요.</div>';
                    document.getElementById('domestic-stocks').innerHTML = msg;
                    document.getElementById('foreign-stocks').innerHTML = msg;
                    document.getElementById('domestic-count').textContent = '0';
                    document.getElementById('foreign-count').textContent = '0';
                    document.getElementById('total-count').textContent = '0';
                });
        };
        
        function renderDomesticStocks(stocks) {
            var container = document.getElementById('domestic-stocks');
            document.getElementById('domestic-info').textContent = '(' + stocks.length + '종목)';
            if (stocks.length === 0) {
                container.innerHTML = '<div class="empty-state">등록된 국내 종목이 없습니다. "+ 추가" 버튼으로 추가해보세요.</div>';
                return;
            }
            var html = '';
            for (var i = 0; i < stocks.length; i++) {
                var s = stocks[i];
                html += '<div class="stock-card pressable motion-enter" style="--enter-delay: ' + (i * 0.04) + 's">';
                html += '<div class="name">' + esc(s.name) + '</div>';
                html += '<div class="code">' + esc(s.code) + '</div>';
                html += '<div class="market">' + esc(s.market || 'KOSPI') + (s.type ? ' | ' + esc(s.type) : '') + '</div>';
                html += '<div class="actions">';
                html += '<button type="button" class="btn btn-danger" data-action="delete-domestic" data-code="' + esc(s.code) + '" data-name="' + esc(s.name) + '">삭제</button>';
                html += '</div></div>';
            }
            container.innerHTML = html;
        }
        
        function renderForeignStocks(stocks) {
            var container = document.getElementById('foreign-stocks');
            document.getElementById('foreign-info').textContent = '(' + stocks.length + '종목)';
            if (stocks.length === 0) {
                container.innerHTML = '<div class="empty-state">등록된 해외 종목이 없습니다. "+ 추가" 버튼으로 추가해보세요.</div>';
                return;
            }
            var html = '';
            for (var i = 0; i < stocks.length; i++) {
                var s = stocks[i];
                html += '<div class="stock-card pressable motion-enter" style="--enter-delay: ' + (i * 0.04) + 's">';
                html += '<div class="name">' + esc(s.name) + '</div>';
                html += '<div class="code">' + esc(s.ticker) + '</div>';
                html += '<div class="market">' + esc(s.market || 'NASDAQ') + (s.type ? ' | ' + esc(s.type) : '') + '</div>';
                html += '<div class="actions">';
                html += '<button type="button" class="btn btn-danger" data-action="delete-foreign" data-ticker="' + esc(s.ticker) + '" data-name="' + esc(s.name) + '">삭제</button>';
                html += '</div></div>';
            }
            container.innerHTML = html;
        }
        
        document.addEventListener('click', function(e) {
            var btn = e.target;
            if (btn.dataset.action === 'delete-domestic') {
                var code = btn.dataset.code;
                var name = btn.dataset.name;
                if (confirm(name + ' 종목을 삭제하시겠습니까?')) {
                    fetch('/api/stocks/domestic/' + code, { method: 'DELETE' })
                        .then(function(res) { return res.json(); })
                        .then(function(data) {
                            if (data.message) {
                                showToast(name + ' 종목이 삭제되었습니다.', 'success');
                                loadStocks();
                            }
                        })
                        .catch(function(e) {
                            showToast('삭제 중 오류가 발생했습니다.', 'error');
                        });
                }
            } else if (btn.dataset.action === 'delete-foreign') {
                var ticker = btn.dataset.ticker;
                var name = btn.dataset.name;
                if (confirm(name + ' 종목을 삭제하시겠습니까?')) {
                    fetch('/api/stocks/foreign/' + ticker, { method: 'DELETE' })
                        .then(function(res) { return res.json(); })
                        .then(function(data) {
                            if (data.message) {
                                showToast(name + ' 종목이 삭제되었습니다.', 'success');
                                loadStocks();
                            }
                        })
                        .catch(function(e) {
                            showToast('삭제 중 오류가 발생했습니다.', 'error');
                        });
                }
            }
        });
        
        window.openAddModal = function(market) {
            currentMarket = market;
            selectedStock = null;
            lastFocusedElement = document.activeElement;
            document.getElementById('modal-title').textContent = market === 'domestic' ? '국내 종목 추가' : '해외 종목 추가';
            document.getElementById('search-input').value = '';
            document.getElementById('search-results').style.display = 'none';
            document.getElementById('search-status').textContent = '';
            document.getElementById('manual-entry').style.display = 'none';
            document.getElementById('manual-code').value = '';
            document.getElementById('manual-name').value = '';
            document.getElementById('selected-stock').style.display = 'none';
            document.getElementById('add-btn').disabled = true;
            var modal = document.getElementById('addModal');
            modal.classList.add('active');
            modal.setAttribute('aria-hidden', 'false');
            document.getElementById('search-input').focus();
        };
        
        window.closeModal = function() {
            var modal = document.getElementById('addModal');
            modal.classList.remove('active');
            modal.setAttribute('aria-hidden', 'true');
            if (lastFocusedElement) lastFocusedElement.focus();
        };
        
        window.debounceSearch = function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(searchStocks, 300);
        };
        
        function searchStocks() {
            var query = document.getElementById('search-input').value.trim();
            var statusEl = document.getElementById('search-status');
            if (query.length < 1) {
                document.getElementById('search-results').style.display = 'none';
                statusEl.textContent = '';
                return;
            }
            statusEl.textContent = '검색 중...';
            document.getElementById('manual-entry').style.display = 'none';
            var market = currentMarket === 'domestic' ? 'domestic' : 'foreign';
            fetch('/api/stocks/search?q=' + encodeURIComponent(query) + '&market=' + market)
                .then(function(res) {
                    if (!res.ok) throw new Error('HTTP ' + res.status);
                    return res.json();
                })
                .then(function(data) {
                    var container = document.getElementById('search-results');
                    if (data.results && data.results.length > 0) {
                        var html = '';
                        for (var i = 0; i < data.results.length; i++) {
                            var r = data.results[i];
                            var info = r.type === 'domestic' ? r.code : r.ticker;
                            html += '<div class="search-item" data-action="select-stock" role="option" tabindex="0" ';
                            html += 'data-type="' + esc(r.type) + '" data-code="' + esc(r.code || r.ticker) + '" ';
                            html += 'data-name="' + esc(r.name) + '" data-market="' + esc(r.market) + '" ';
                            html += 'data-currency="' + esc(r.currency || 'KRW') + '">';
                            html += '<div class="name">' + esc(r.name) + '</div>';
                            html += '<div class="code">' + esc(info) + ' | ' + esc(r.market) + '</div></div>';
                        }
                        container.innerHTML = html;
                        container.style.display = 'block';
                        statusEl.textContent = data.results.length + '개 결과';
                    } else {
                        container.innerHTML = '<div class="search-item" style="cursor: default;">검색 결과 없음</div>' +
                            '<div class="search-item" data-action="show-manual-entry" style="color: var(--primary); font-weight: 600;">직접 입력하기 &rsaquo;</div>';
                        container.style.display = 'block';
                        statusEl.textContent = '';
                    }
                })
                .catch(function(e) {
                    console.error('검색 오류:', e);
                    statusEl.textContent = '검색 중 오류가 발생했습니다. 다시 시도해주세요.';
                    statusEl.style.color = 'var(--danger)';
                });
        }
        
        document.addEventListener('click', function(e) {
            var item = e.target.closest('[data-action="select-stock"]');
            if (item) {
                selectSearchItem(item);
            }
            if (e.target.closest('[data-action="show-manual-entry"]')) {
                showManualEntry();
            }
        });
        
        window.showManualEntry = function() {
            var container = document.getElementById('search-results');
            container.style.display = 'none';
            var panel = document.getElementById('manual-entry');
            panel.style.display = 'block';
            document.getElementById('manual-code').focus();
        };
        
        window.hideManualEntry = function() {
            document.getElementById('manual-entry').style.display = 'none';
        };
        
        window.selectManualStock = function() {
            var code = document.getElementById('manual-code').value.trim();
            var name = document.getElementById('manual-name').value.trim();
            if (!/^[0-9]{6}$/.test(code)) {
                showToast('종목코드는 6자리 숫자여야 합니다.', 'error');
                document.getElementById('manual-code').focus();
                return;
            }
            if (!name) {
                showToast('종목명을 입력해주세요.', 'error');
                document.getElementById('manual-name').focus();
                return;
            }
            selectedStock = {
                type: currentMarket,
                code: code,
                name: name,
                market: 'KOSPI',
                currency: currentMarket === 'domestic' ? 'KRW' : 'USD'
            };
            document.getElementById('selected-name').textContent = selectedStock.name;
            document.getElementById('selected-code').textContent = selectedStock.code;
            document.getElementById('selected-stock').style.display = 'block';
            document.getElementById('search-results').style.display = 'none';
            document.getElementById('add-btn').disabled = false;
            document.getElementById('add-btn').focus();
        };
        
        window.addStock = function() {
            if (!selectedStock) return;
            var addBtn = document.getElementById('add-btn');
            if (addBtn.disabled) return;
            addBtn.disabled = true;
            addBtn.textContent = '추가 중...';
            var url, body;
            if (currentMarket === 'domestic') {
                url = '/api/stocks/domestic';
                body = { code: selectedStock.code, name: selectedStock.name, market: selectedStock.market };
            } else {
                url = '/api/stocks/foreign';
                body = { ticker: selectedStock.code, name: selectedStock.name, market: selectedStock.market, currency: selectedStock.currency };
            }
            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.message) {
                    showToast(data.message, 'success');
                    closeModal();
                    loadStocks();
                } else {
                    showToast(data.detail || '오류가 발생했습니다.', 'error');
                }
            })
            .catch(function(e) {
                showToast('추가 중 오류가 발생했습니다. 네트워크를 확인해주세요.', 'error');
            })
            .finally(function() {
                addBtn.disabled = false;
                addBtn.textContent = '추가';
            });
        };
        
        // 검색 결과 키보드 선택 (Enter/Space)
        document.addEventListener('keydown', function(e) {
            var item = e.target;
            if (item && item.getAttribute('data-action') === 'select-stock' && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault();
                selectSearchItem(item);
            }
            // ESC 키로 모달 닫기
            if (e.key === 'Escape') {
                var modal = document.getElementById('addModal');
                if (modal.classList.contains('active')) closeModal();
            }
        });
        
        // 모달 내 포커스 트랩
        document.getElementById('addModal').addEventListener('keydown', function(e) {
            if (e.key !== 'Tab') return;
            var focusables = document.getElementById('addModal')
                .querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])');
            if (focusables.length === 0) return;
            var first = focusables[0];
            var last = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });
        
        function selectSearchItem(item) {
            selectedStock = {
                type: item.dataset.type,
                code: item.dataset.code,
                name: item.dataset.name,
                market: item.dataset.market,
                currency: item.dataset.currency
            };
            document.getElementById('selected-name').textContent = selectedStock.name;
            document.getElementById('selected-code').textContent = selectedStock.code;
            document.getElementById('selected-stock').style.display = 'block';
            document.getElementById('search-results').style.display = 'none';
            document.getElementById('add-btn').disabled = false;
            document.getElementById('add-btn').focus();
        }
        
        function showToast(message, type) {
            var toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type + ' show';
            setTimeout(function() { toast.classList.remove('show'); }, 3000);
        }
        
        loadStocks();
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
            });
        }
    })();
    </script>
</body>
</html>"""
