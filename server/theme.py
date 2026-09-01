# -*- coding: utf-8 -*-
"""공용 테마 초기화 + 전환 스니펫 (라이트/다크)"""

# <head>에 넣는 인라인 스크립트: paint 전에 테마 결정 (FOUC 방지)
THEME_INIT_SCRIPT = """
<script>
(function () {
    var stored = null;
    try { stored = localStorage.getItem('stockpilot-theme'); } catch (e) {}
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var theme = stored === 'dark' || stored === 'light' ? stored : (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
})();
</script>
"""

# <body> 안에 넣는 테마 전환 버튼
THEME_TOGGLE_BTN = """
<button type="button" class="theme-toggle" id="theme-toggle" aria-label="테마 전환">🌓</button>
"""

# 문서 끝에 넣는 전환 토글 스크립트
THEME_TOGGLE_SCRIPT = """
<script>
(function () {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    function current() {
        return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    }
    btn.addEventListener('click', function () {
        var next = current() === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        try { localStorage.setItem('stockpilot-theme', next); } catch (e) {}
        try { document.dispatchEvent(new CustomEvent('themechange')); } catch (e) {}
    });
})();
</script>
"""
