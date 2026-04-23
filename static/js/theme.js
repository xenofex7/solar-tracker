(function () {
  try {
    var saved = localStorage.getItem('theme');
    var prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
    var theme = saved || (prefersLight ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }

  function bind() {
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.addEventListener('click', function () {
        var current = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        var next = current === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', next);
        try { localStorage.setItem('theme', next); } catch (e) {}
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
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
