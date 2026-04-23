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

    var navToggle = document.getElementById('nav-toggle');
    var navMenu = document.getElementById('nav-menu');
    var header = document.querySelector('header');
    if (navToggle && navMenu && header) {
      var close = function () {
        header.classList.remove('nav-open');
        navToggle.setAttribute('aria-expanded', 'false');
      };
      navToggle.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = header.classList.toggle('nav-open');
        navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      navMenu.querySelectorAll('a').forEach(function (a) {
        a.addEventListener('click', close);
      });
      document.addEventListener('click', function (e) {
        if (!header.classList.contains('nav-open')) return;
        if (navMenu.contains(e.target) || navToggle.contains(e.target)) return;
        close();
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') close();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
