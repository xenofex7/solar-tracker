(function () {
  var MODES = ['system', 'light', 'dark'];
  var mql = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;

  function systemTheme() { return mql && mql.matches ? 'light' : 'dark'; }
  function readMode() {
    try {
      var saved = localStorage.getItem('theme-mode');
      if (MODES.indexOf(saved) >= 0) return saved;
      var legacy = localStorage.getItem('theme');
      if (legacy === 'light' || legacy === 'dark') return legacy;
    } catch (e) {}
    return 'system';
  }
  function apply(mode) {
    var theme = mode === 'system' ? systemTheme() : mode;
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-theme-mode', mode);
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme, mode: mode } }));
  }

  apply(readMode());

  // Apply persisted sidebar collapse state before first paint to avoid a flash.
  try {
    if (localStorage.getItem('sidebar-collapsed') === '1') {
      document.documentElement.setAttribute('data-sidebar', 'collapsed');
    }
  } catch (e) {}

  if (mql) {
    var onChange = function () { if (readMode() === 'system') apply('system'); };
    if (mql.addEventListener) mql.addEventListener('change', onChange);
    else if (mql.addListener) mql.addListener(onChange);
  }

  function modeLabel(mode) {
    var T = window.T || {};
    if (mode === 'light') return T.theme_light || 'Light';
    if (mode === 'dark') return T.theme_dark || 'Dark';
    return T.theme_system || 'System';
  }
  function updateBtn(btn) {
    if (!btn) return;
    var mode = readMode();
    var label = modeLabel(mode);
    btn.setAttribute('aria-label', label);
    btn.setAttribute('title', label);
    var span = btn.querySelector('.theme-toggle-label');
    if (span) span.textContent = label;
  }

  function bind() {
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      updateBtn(btn);
      btn.addEventListener('click', function () {
        var current = readMode();
        var next = MODES[(MODES.indexOf(current) + 1) % MODES.length];
        try { localStorage.setItem('theme-mode', next); localStorage.removeItem('theme'); } catch (e) {}
        apply(next);
        updateBtn(btn);
      });
    }

    var sidebar = document.getElementById('sidebar');
    var openBtn = document.getElementById('sidebar-open');
    var closeBtn = document.getElementById('sidebar-close');
    var backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar && openBtn) {
      var closeSidebar = function () {
        document.body.classList.remove('sidebar-open');
        openBtn.setAttribute('aria-expanded', 'false');
      };
      openBtn.addEventListener('click', function () {
        document.body.classList.add('sidebar-open');
        openBtn.setAttribute('aria-expanded', 'true');
      });
      if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
      if (backdrop) backdrop.addEventListener('click', closeSidebar);
      sidebar.querySelectorAll('.sidebar-nav a').forEach(function (a) {
        a.addEventListener('click', closeSidebar);
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeSidebar();
      });
    }

    var collapseBtn = document.getElementById('sidebar-collapse');
    if (collapseBtn) {
      collapseBtn.addEventListener('click', function () {
        var root = document.documentElement;
        var collapsed = root.getAttribute('data-sidebar') === 'collapsed';
        if (collapsed) root.removeAttribute('data-sidebar');
        else root.setAttribute('data-sidebar', 'collapsed');
        try { localStorage.setItem('sidebar-collapsed', collapsed ? '0' : '1'); } catch (e) {}
        window.dispatchEvent(new Event('resize'));
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
