# -*- coding: utf-8 -*-
"""종목 관리 대시보드 HTML"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>종목 관리 대시보드</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', -apple-system, sans-serif; background: #f5f7fa; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: linear-gradient(135deg, #1a237e, #0d47a1); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; text-align: center; }
        header h1 { font-size: 28px; margin-bottom: 8px; }
        .nav { display: flex; gap: 10px; margin-bottom: 20px; justify-content: center; }
        .nav a { padding: 10px 20px; background: white; color: #1a237e; text-decoration: none; border-radius: 8px; font-weight: 600; transition: all 0.2s; }
        .nav a:hover { background: #e8eaf6; }
        .nav a.active { background: #1a237e; color: white; }
        .stats { display: flex; gap: 20px; margin-bottom: 30px; justify-content: center; }
        .stat-card { background: white; padding: 20px 40px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }
        .stat-card h3 { font-size: 32px; color: #1a237e; }
        .stat-card p { color: #666; font-size: 14px; margin-top: 5px; }
        .section { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee; }
        .section-title { font-size: 20px; color: #1a237e; font-weight: 600; }
        .section-count { color: #666; font-size: 14px; }
        .btn { padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s; border: none; font-size: 14px; }
        .btn-primary { background: #1a237e; color: white; }
        .btn-primary:hover { background: #0d47a1; }
        .btn-danger { background: #e53935; color: white; padding: 6px 12px; font-size: 12px; }
        .btn-danger:hover { background: #c62828; }
        .btn-secondary { background: #f5f5f5; color: #333; }
        .btn-secondary:hover { background: #e0e0e0; }
        .stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
        .stock-card { background: #f8f9ff; border-radius: 10px; padding: 16px; border: 1px solid #e0e0e0; transition: all 0.2s; }
        .stock-card:hover { border-color: #1a237e; box-shadow: 0 4px 12px rgba(26,35,126,0.1); }
        .stock-card .name { font-weight: 600; color: #1a237e; margin-bottom: 6px; font-size: 16px; }
        .stock-card .code { color: #888; font-size: 13px; margin-bottom: 4px; }
        .stock-card .market { color: #666; font-size: 12px; margin-bottom: 10px; }
        .stock-card .actions { display: flex; justify-content: flex-end; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; }
        .modal.active { display: flex; }
        .modal-content { background: white; border-radius: 12px; padding: 30px; width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h2 { color: #1a237e; }
        .modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: #666; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: #333; }
        .form-group input { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        .form-group input:focus { outline: none; border-color: #1a237e; }
        .search-results { margin-top: 10px; border: 1px solid #ddd; border-radius: 6px; max-height: 200px; overflow-y: auto; }
        .search-item { padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #eee; }
        .search-item:hover { background: #f5f7fa; }
        .search-item:last-child { border-bottom: none; }
        .search-item .name { font-weight: 600; color: #1a237e; }
        .search-item .code { color: #666; font-size: 13px; }
        .empty-state { text-align: center; padding: 40px; color: #999; }
        .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 24px; border-radius: 8px; color: white; font-weight: 600; z-index: 2000; transform: translateY(100px); opacity: 0; transition: all 0.3s; }
        .toast.success { background: #43a047; }
        .toast.error { background: #e53935; }
        .toast.show { transform: translateY(0); opacity: 1; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>종목 관리 대시보드</h1>
        </header>
        
        <nav class="nav">
            <a href="/">메인</a>
            <a href="/dashboard" class="active">종목 관리</a>
        </nav>
        
        <div class="stats">
            <div class="stat-card">
                <h3 id="total-count">0</h3>
                <p>전체 종목</p>
            </div>
            <div class="stat-card">
                <h3 id="domestic-count">0</h3>
                <p>국내 종목</p>
            </div>
            <div class="stat-card">
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
    
    <div class="modal" id="addModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modal-title">종목 추가</h2>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            
            <div class="form-group">
                <label>검색어 입력</label>
                <input type="text" id="search-input" placeholder="종목코드 또는 종목명 입력..." oninput="debounceSearch()">
            </div>
            
            <div id="search-results" class="search-results" style="display: none;"></div>
            
            <div id="selected-stock" style="display: none; margin-top: 16px; padding: 12px; background: #f5f7fa; border-radius: 6px;">
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
        
        window.loadStocks = function() {
            fetch('/api/stocks')
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    renderDomesticStocks(data.domestic || []);
                    renderForeignStocks(data.foreign || []);
                    document.getElementById('domestic-count').textContent = (data.domestic || []).length;
                    document.getElementById('foreign-count').textContent = (data.foreign || []).length;
                    document.getElementById('total-count').textContent = (data.domestic || []).length + (data.foreign || []).length;
                })
                .catch(function(e) {
                    console.error('종목 로드 오류:', e);
                });
        };
        
        function renderDomesticStocks(stocks) {
            var container = document.getElementById('domestic-stocks');
            document.getElementById('domestic-info').textContent = '(' + stocks.length + '종목)';
            if (stocks.length === 0) {
                container.innerHTML = '<div class="empty-state">등록된 국내 종목이 없습니다.</div>';
                return;
            }
            var html = '';
            for (var i = 0; i < stocks.length; i++) {
                var s = stocks[i];
                html += '<div class="stock-card">';
                html += '<div class="name">' + s.name + '</div>';
                html += '<div class="code">' + s.code + '</div>';
                html += '<div class="market">' + (s.market || 'KOSPI') + (s.type ? ' | ' + s.type : '') + '</div>';
                html += '<div class="actions">';
                html += '<button class="btn btn-danger" data-action="delete-domestic" data-code="' + s.code + '" data-name="' + s.name + '">삭제</button>';
                html += '</div></div>';
            }
            container.innerHTML = html;
        }
        
        function renderForeignStocks(stocks) {
            var container = document.getElementById('foreign-stocks');
            document.getElementById('foreign-info').textContent = '(' + stocks.length + '종목)';
            if (stocks.length === 0) {
                container.innerHTML = '<div class="empty-state">등록된 해외 종목이 없습니다.</div>';
                return;
            }
            var html = '';
            for (var i = 0; i < stocks.length; i++) {
                var s = stocks[i];
                html += '<div class="stock-card">';
                html += '<div class="name">' + s.name + '</div>';
                html += '<div class="code">' + s.ticker + '</div>';
                html += '<div class="market">' + (s.market || 'NASDAQ') + (s.type ? ' | ' + s.type : '') + '</div>';
                html += '<div class="actions">';
                html += '<button class="btn btn-danger" data-action="delete-foreign" data-ticker="' + s.ticker + '" data-name="' + s.name + '">삭제</button>';
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
            document.getElementById('modal-title').textContent = market === 'domestic' ? '국내 종목 추가' : '해외 종목 추가';
            document.getElementById('search-input').value = '';
            document.getElementById('search-results').style.display = 'none';
            document.getElementById('selected-stock').style.display = 'none';
            document.getElementById('add-btn').disabled = true;
            document.getElementById('addModal').classList.add('active');
        };
        
        window.closeModal = function() {
            document.getElementById('addModal').classList.remove('active');
        };
        
        window.debounceSearch = function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(searchStocks, 300);
        };
        
        function searchStocks() {
            var query = document.getElementById('search-input').value.trim();
            if (query.length < 1) {
                document.getElementById('search-results').style.display = 'none';
                return;
            }
            var market = currentMarket === 'domestic' ? 'domestic' : 'foreign';
            fetch('/api/stocks/search?q=' + encodeURIComponent(query) + '&market=' + market)
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    var container = document.getElementById('search-results');
                    if (data.results && data.results.length > 0) {
                        var html = '';
                        for (var i = 0; i < data.results.length; i++) {
                            var r = data.results[i];
                            var info = r.type === 'domestic' ? r.code : r.ticker;
                            html += '<div class="search-item" data-action="select-stock" ';
                            html += 'data-type="' + r.type + '" data-code="' + (r.code || r.ticker) + '" ';
                            html += 'data-name="' + r.name + '" data-market="' + r.market + '" ';
                            html += 'data-currency="' + (r.currency || 'KRW') + '">';
                            html += '<div class="name">' + r.name + '</div>';
                            html += '<div class="code">' + info + ' | ' + r.market + '</div></div>';
                        }
                        container.innerHTML = html;
                        container.style.display = 'block';
                    } else {
                        container.innerHTML = '<div class="search-item">검색 결과 없음</div>';
                        container.style.display = 'block';
                    }
                })
                .catch(function(e) {
                    console.error('검색 오류:', e);
                });
        }
        
        document.addEventListener('click', function(e) {
            var item = e.target.closest('[data-action="select-stock"]');
            if (item) {
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
            }
        });
        
        window.addStock = function() {
            if (!selectedStock) return;
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
                showToast('추가 중 오류가 발생했습니다.', 'error');
            });
        };
        
        function showToast(message, type) {
            var toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type + ' show';
            setTimeout(function() { toast.classList.remove('show'); }, 3000);
        }
        
        loadStocks();
    })();
    </script>
</body>
</html>"""
