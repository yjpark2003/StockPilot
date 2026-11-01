(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const signed = (n, unit = '%') => n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}${unit}`;
  const tone = n => n > 0 ? 'pos' : n < 0 ? 'neg' : 'neutral-sign';
  const safeLink = value => { try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? u.href : ''; } catch (_) { return ''; } };
  let data = null, market = 'all', request = 0;
  function sparkline(row) {
    const values = row.daily.map(d => d.close);
    if (values.length < 2) return '<span class="muted">데이터 부족</span>';
    const lo = Math.min(...values), hi = Math.max(...values), range = hi - lo || 1;
    const points = values.map((v,i) => `${2 + i * 96 / (values.length-1)},${hi === lo ? 16 : 29 - (v-lo)*26/range}`).join(' ');
    return `<svg class="sparkline ${tone(row.change_rate)}" viewBox="0 0 100 32" role="img" aria-label="${esc(row.name)} 구간 종가 추이"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
  }
  function render() {
    if (!data) return;
    const selectedMarket = data.stocks.filter(s => market === 'all' || s.market_type === market);
    const eligible = selectedMarket.filter(s => s.status === 'complete' && s.change_rate != null);
    $('count-up').textContent = eligible.filter(s => s.change_rate > 0).length;
    $('count-down').textContent = eligible.filter(s => s.change_rate < 0).length;
    $('count-flat').textContent = eligible.filter(s => s.change_rate === 0).length;
    $('count-attention').textContent = selectedMarket.filter(s => s.status !== 'complete' || s.change_rate == null).length + (market === 'all' ? data.unlisted_failures : 0);
    document.querySelectorAll('[data-market]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.market === market));
      button.className = `btn btn-${button.dataset.market === market ? 'primary' : 'secondary'}`;
      const label = {all:'전체',domestic:'국내',foreign:'해외'}[button.dataset.market];
      button.textContent = `${label} ${data.stocks.filter(s => button.dataset.market === 'all' || s.market_type === button.dataset.market).length}`;
    });
    const ranked = [...eligible].sort((a,b) => b.change_rate - a.change_rate);
    const high = ranked.find(s => s.change_rate > 0), low = [...ranked].reverse().find(s => s.change_rate < 0);
    $('highlights').innerHTML = [[high,'가장 큰 상승'],[low,'가장 큰 하락']].map(([s,label]) => `<div class="highlight"><span>${label}</span>${s ? `${esc(s.name)} <strong class="${tone(s.change_rate)}">${signed(s.change_rate)}</strong>` : '해당 종목 없음'}</div>`).join('');
    const query = $('stock-query').value.trim().toLowerCase(), type = $('stock-type').value;
    let rows = selectedMarket.filter(s => `${s.name} ${s.code}`.toLowerCase().includes(query) && (type === 'all' || (type === 'ETF' ? s.stock_type.toUpperCase() === 'ETF' : s.stock_type.toUpperCase() !== 'ETF')));
    const order = $('stock-sort').value;
    rows.sort((a,b) => order === 'name' ? a.name.localeCompare(b.name, 'ko') : order === 'attention' ? Number(b.status !== 'complete') - Number(a.status !== 'complete') : a.change_rate == null ? (b.change_rate == null ? 0 : 1) : b.change_rate == null ? -1 : order === 'change-asc' ? a.change_rate-b.change_rate : b.change_rate-a.change_rate);
    $('result-count').textContent = `(${rows.length}종목)`;
    $('no-matches').hidden = rows.length !== 0;
    $('stock-rows').innerHTML = rows.map(s => {
      const price = s.last_close == null ? '—' : new Intl.NumberFormat('ko-KR', {style:'currency',currency:s.currency,maximumFractionDigits:s.currency === 'KRW' ? 0 : 2}).format(s.last_close);
      const identity = s.report_url ? `<a href="${esc(s.report_url)}">${esc(s.name)}</a>` : `<strong>${esc(s.name)}</strong>`;
      return `<tr><td data-label="종목" class="stock-identity">${identity}<small>${esc(s.code)} · ${esc(s.market || (s.market_type === 'domestic' ? '국내' : '해외'))}${s.stock_type ? ' · '+esc(s.stock_type) : ''}</small></td>
        <td data-label="마지막 종가 / 기준일">${esc(price)}<span class="cell-secondary">${esc(s.as_of || '기준일 없음')} · ${esc(s.currency)}</span></td>
        <td data-label="구간 등락률" class="${tone(s.change_rate)}"><strong>${signed(s.change_rate)}</strong></td>
        <td data-label="가격 추이">${sparkline(s)}</td>
        <td data-label="이전 구간 대비" class="${tone(s.rate_delta)}">${signed(s.rate_delta, '%p')}<span class="cell-secondary">${s.previous_rate == null ? '비교 불가' : '이전 '+signed(s.previous_rate)}</span></td>
        <td data-label="지수 대비" class="${tone(s.benchmark_delta)}">${signed(s.benchmark_delta, '%p')}<span class="cell-secondary">${esc(s.benchmark_name)}</span></td>
        <td data-label="데이터 상태"><span class="status-pill ${s.status}">${esc(s.status_label)}</span>${s.missing_days.length ? `<span class="cell-secondary">누락 ${esc(s.missing_days.join(', '))}</span>` : ''}${s.error ? `<span class="cell-secondary">${esc(s.error)}</span>` : ''}</td></tr>`;
    }).join('');
    const seen = new Set(), stories = [];
    selectedMarket.forEach(s => [...s.news, ...s.disclosures].forEach(n => {
      const key = n.link || n.title;
      if (!n.title || seen.has(key)) return;
      seen.add(key); stories.push({...n,stock:s.name});
    }));
    $('overview-news').innerHTML = stories.slice(0,8).map(n => {
      const link = safeLink(n.link);
      return `<article class="overview-story">${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a>` : esc(n.title)}<small>${esc(n.stock)} · ${esc(n.time || n.date || n.pub_date || '발행일 미상')}</small></article>`;
    }).join('') || '<p class="empty-state">해당 구간에 수집된 뉴스·공시가 없습니다.</p>';
  }
  async function load(date) {
    const current = ++request;
    $('overview-message').hidden = false;
    $('overview-message').textContent = '분석 결과를 불러오는 중입니다.';
    $('overview-content').hidden = true;
    try {
      const response = await fetch('/api/overview' + (date ? '?report_date='+encodeURIComponent(date) : ''));
      if (!response.ok) throw new Error('목록 요청 실패');
      const next = await response.json();
      if (current !== request) return;
      data = next;
      if (!data) {
        $('report-date').innerHTML = '<option value="">리포트 없음</option>';
        $('overview-message').innerHTML = '아직 생성된 리포트가 없습니다. <a href="/history#analysis">첫 분석을 실행하세요 →</a>';
        return;
      }
      $('report-date').innerHTML = data.reports.map(r => `<option value="${esc(r.date)}"${r.date === data.date ? ' selected' : ''}>${esc(r.week)} · ${esc(r.label)} (저장 ${esc(r.date)})</option>`).join('');
      $('generated-at').textContent = data.generated_at ? `생성 ${data.generated_at.replace('T',' ')} · 서버 시각` : '생성 시각 정보 없음';
      $('comparison-note').textContent = data.previous ? `이전 비교 구간: ${data.previous.range_label} (저장 ${data.previous.date})` : '비교할 이전 구간이 없습니다.';
      $('recent-reports').innerHTML = data.reports.slice(0,5).map(r => `<div class="overview-story"><a href="/reports/${encodeURIComponent(r.date)}/index.html">${esc(r.week)}</a><small>${esc(r.label)}</small></div>`).join('');
      const messages = [];
      if (data.legacy) messages.push('기존 HTML 리포트에서 복원한 결과입니다. 지수 비교는 새 분석부터 제공하며, 상품 유형은 현재 등록 설정을 참고합니다.');
      if (data.unlisted_failures) messages.push(`기존 리포트에서 제외된 실패 종목 ${data.unlisted_failures}건이 있습니다. 종목명과 원인은 새 분석부터 저장됩니다.`);
      $('overview-message').textContent = messages.join(' ');
      $('overview-message').className = 'notice';
      $('overview-message').hidden = !messages.length;
      $('overview-content').hidden = false;
      render();
    } catch (_) {
      if (current !== request) return;
      $('overview-message').innerHTML = '분석 결과를 불러오지 못했습니다. <button type="button" class="btn btn-secondary" id="retry-overview">다시 시도</button>';
      $('retry-overview').onclick = () => load(date);
    }
  }
  document.querySelectorAll('[data-market]').forEach(button => button.addEventListener('click', () => { market = button.dataset.market; render(); }));
  ['stock-query','stock-type','stock-sort'].forEach(id => $(id).addEventListener('input', render));
  $('report-date').addEventListener('change', () => {
    const date = $('report-date').value;
    history.replaceState(null,'','/?report_date='+encodeURIComponent(date));
    load(date);
  });
  load(new URLSearchParams(location.search).get('report_date'));
})();
