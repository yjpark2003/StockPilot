(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g,c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  let stocks = [], editing = null, lookupVersion = 0, lookupTimer, lookupController, toastTimer, saving = false;
  const dialog = $('stock-dialog');
  async function request(url, options) {
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '입력값을 확인해주세요.');
    return result;
  }
  function toast(message) {
    clearTimeout(toastTimer); $('manage-toast').textContent = message; $('manage-toast').hidden = false;
    toastTimer = setTimeout(() => { $('manage-toast').hidden = true; }, 4000);
  }
  function render() {
    const query = $('manage-query').value.trim().toLowerCase(), market = $('manage-market').value, type = $('manage-type').value;
    const filtered = stocks.filter(s => (market === 'all' || s.market_type === market) && `${s.name} ${s.id}`.toLowerCase().includes(query) && (type === 'all' || (type === 'ETF' ? (s.type || '').toUpperCase() === 'ETF' : (s.type || '').toUpperCase() !== 'ETF')));
    filtered.sort((a,b) => ($('manage-sort').value === 'code' ? a.id.localeCompare(b.id) : a.name.localeCompare(b.name,'ko')));
    $('manage-count').textContent = `전체 ${stocks.length} · 국내 ${stocks.filter(s => s.market_type === 'domestic').length} · 해외 ${stocks.filter(s => s.market_type === 'foreign').length} / 표시 ${filtered.length}종목`;
    $('stock-list').innerHTML = filtered.map(s => `<article class="manage-card"><h2>${esc(s.name)}</h2><p>${esc(s.id)} · ${esc(s.market)}<br>${s.market_type === 'domestic' ? '국내 · KRW' : '해외 · '+esc(s.currency || 'USD')} · ${esc(s.type || '개별·기타')}</p><div class="manage-actions"><button type="button" class="btn btn-secondary" data-action="edit" data-id="${esc(s.id)}" data-market="${s.market_type}" aria-label="${esc(s.name)} 수정">수정</button><button type="button" class="btn manage-delete" data-action="delete" data-id="${esc(s.id)}" data-market="${s.market_type}" aria-label="${esc(s.name)} 삭제">삭제</button></div></article>`).join('');
    $('manage-status').textContent = filtered.length ? '' : stocks.length ? '조건에 맞는 종목이 없습니다.' : '등록된 종목이 없습니다. 종목 추가로 시작하세요.';
  }
  async function loadStocks() {
    $('manage-status').textContent = '목록을 불러오는 중입니다.';
    try {
      const data = await request('/api/stocks');
      stocks = ['domestic','foreign'].flatMap(market => (data[market] || []).map(s => ({...s,type:s.type || (s.market === 'ETF' ? 'ETF' : ''),market_type:market,id:String(s.code || s.ticker)})));
      render(); return true;
    } catch (_) {
      $('manage-count').textContent = '종목 수 확인 불가';
      $('manage-status').innerHTML = '목록을 불러오지 못했습니다. <button type="button" class="btn btn-secondary" id="retry-stocks">다시 시도</button>';
      $('retry-stocks').onclick = loadStocks; return false;
    }
  }
  function cancelLookup() {
    ++lookupVersion; clearTimeout(lookupTimer);
    if (lookupController) lookupController.abort();
  }
  function setMarket() {
    cancelLookup(); $('lookup-results').innerHTML = ''; $('lookup-status').textContent = '';
    const domestic = $('entry-market').value === 'domestic';
    $('entry-code-label').textContent = domestic ? '종목코드 (6자리)' : '티커';
    $('entry-code').pattern = domestic ? '[0-9]{6}' : '[A-Za-z0-9][A-Za-z0-9.\\-^=]{0,19}';
    $('entry-code').maxLength = domestic ? 6 : 20;
    $('entry-code').inputMode = domestic ? 'numeric' : 'text';
    $('entry-exchange').value = domestic ? 'KOSPI' : 'NASDAQ';
    $('currency-field').hidden = domestic; $('entry-currency').disabled = domestic;
  }
  function open(stock = null) {
    editing = stock; $('stock-form').reset();
    $('entry-market').value = stock ? stock.market_type : 'domestic';
    setMarket(); $('entry-status').textContent = '';
    $('entry-market').disabled = !!stock; $('entry-code').disabled = !!stock;
    $('lookup-section').hidden = !!stock;
    $('dialog-title').textContent = stock ? '종목 수정' : '종목 추가';
    $('save-stock').textContent = stock ? '저장' : '추가';
    $('entry-type').querySelectorAll('[data-custom]').forEach(option => option.remove());
    if (stock) {
      $('entry-code').value = stock.id; $('entry-name').value = stock.name;
      $('entry-exchange').value = stock.market; $('entry-currency').value = stock.currency || 'USD';
      if (stock.type && stock.type !== 'ETF') {
        const option = new Option(stock.type, stock.type); option.dataset.custom = 'true'; $('entry-type').add(option);
      }
      $('entry-type').value = stock.type || '';
    }
    dialog.showModal(); (stock ? $('entry-name') : $('lookup-query')).focus();
  }
  function close() { if (!saving) dialog.close(); }
  dialog.addEventListener('close', cancelLookup);
  dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); });
  $('open-add').onclick = () => open(); $('close-dialog').onclick = close; $('cancel-dialog').onclick = close;
  $('entry-market').addEventListener('change', () => { setMarket(); $('entry-code').value = ''; $('entry-name').value = ''; $('lookup-query').value = ''; });
  $('lookup-query').addEventListener('input', () => {
    cancelLookup(); const version = lookupVersion;
    const query = $('lookup-query').value.trim(), market = $('entry-market').value;
    $('lookup-results').innerHTML = ''; $('lookup-status').textContent = query ? '검색 중…' : '';
    if (!query) return;
    lookupTimer = setTimeout(async () => {
      lookupController = new AbortController();
      try {
        const data = await request('/api/stocks/search?q='+encodeURIComponent(query)+'&market='+market, {signal:lookupController.signal});
        if (version !== lookupVersion || !dialog.open) return;
        const results = data.results || [];
        $('lookup-status').textContent = results.length ? `${results.length}개 결과` : '검색 결과가 없습니다. 아래에 직접 입력할 수 있습니다.';
        $('lookup-results').innerHTML = results.map((s,i) => {
          const id = String(s.code || s.ticker), registered = stocks.some(current => current.market_type === market && current.id === id);
          return `<button type="button" class="lookup-item" data-result="${i}"${registered ? ' disabled' : ''}>${esc(s.name)}${registered ? ' · 이미 등록됨' : ''}<small>${esc(id)} · ${esc(s.market)}</small></button>`;
        }).join('');
        $('lookup-results').querySelectorAll('[data-result]').forEach(button => button.onclick = () => {
          const selected = results[Number(button.dataset.result)];
          $('entry-code').value = selected.code || selected.ticker;
          $('entry-name').value = selected.name; $('entry-exchange').value = selected.market || (market === 'domestic' ? 'KOSPI' : 'NASDAQ');
          $('entry-currency').value = selected.currency || 'USD';
          $('entry-type').value = selected.stock_type === 'ETF' ? 'ETF' : '';
          $('lookup-results').innerHTML = ''; $('lookup-status').textContent = '선택한 종목 정보를 확인한 뒤 추가하세요.'; $('entry-name').focus();
        });
      } catch (error) { if (error.name !== 'AbortError' && version === lookupVersion) $('lookup-status').textContent = '검색하지 못했습니다. 다시 시도하거나 아래에 직접 입력하세요.'; }
    }, 300);
  });
  $('stock-form').addEventListener('submit', async event => {
    event.preventDefault(); if (saving) return;
    const market = $('entry-market').value, id = $('entry-code').value.trim().toUpperCase();
    if (!editing && stocks.some(s => s.market_type === market && s.id === id)) { $('entry-status').textContent = '이미 등록된 종목입니다.'; return; }
    const body = {name:$('entry-name').value.trim(), market:$('entry-exchange').value.trim().toUpperCase(), type:$('entry-type').value || null};
    if (market === 'domestic') body.code = id;
    else { body.ticker = id; body.currency = $('entry-currency').value.trim().toUpperCase(); }
    saving = true; $('save-stock').disabled = true; $('save-stock').textContent = '저장 중…';
    try {
      const data = await request('/api/stocks/'+market+(editing ? '/'+encodeURIComponent(id) : ''), {method:editing ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      saving = false; dialog.close(); toast(data.message); await loadStocks();
    } catch (error) { $('entry-status').textContent = error.message; }
    finally { saving = false; $('save-stock').disabled = false; $('save-stock').textContent = editing ? '저장' : '추가'; }
  });
  $('stock-list').addEventListener('click', async event => {
    const button = event.target.closest('[data-action]'); if (!button) return;
    const stock = stocks.find(s => s.id === button.dataset.id && s.market_type === button.dataset.market);
    if (!stock) return;
    if (button.dataset.action === 'edit') { open(stock); return; }
    if (!confirm(`${stock.name} 종목을 삭제하시겠습니까? 기존 리포트는 유지됩니다.`)) return;
    button.disabled = true;
    try {
      const data = await request('/api/stocks/'+stock.market_type+'/'+encodeURIComponent(stock.id), {method:'DELETE'});
      toast(data.message); await loadStocks();
    } catch (error) { toast(error.message); button.disabled = false; }
  });
  ['manage-query','manage-market','manage-type','manage-sort'].forEach(id => $(id).addEventListener('input',render));
  loadStocks();
})();
