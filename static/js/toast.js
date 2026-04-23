(() => {
  const ICONS = {
    success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>',
    error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  };

  function ensureContainer() {
    let c = document.getElementById('toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toast-container';
      c.className = 'toast-container';
      c.setAttribute('role', 'status');
      c.setAttribute('aria-live', 'polite');
      document.body.appendChild(c);
    }
    return c;
  }

  function showToast(message, type = 'info', duration = 3500) {
    if (!message) return;
    let title = message;
    let sub = '';
    if (typeof message === 'object') {
      title = message.title || '';
      sub = message.sub || '';
    }
    if (!title) return;
    const container = ensureContainer();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icon = ICONS[type] || ICONS.info;
    el.innerHTML = `<span class="toast-icon">${icon}</span><div class="toast-body"><div class="toast-msg"></div><div class="toast-sub"></div></div><button type="button" class="toast-close" aria-label="Close">&times;</button>`;
    el.querySelector('.toast-msg').textContent = title;
    const subEl = el.querySelector('.toast-sub');
    if (sub) subEl.textContent = sub;
    else subEl.remove();
    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));

    let timer = null;
    const dismiss = () => {
      if (timer) { clearTimeout(timer); timer = null; }
      el.classList.remove('show');
      el.classList.add('hide');
      setTimeout(() => el.remove(), 220);
    };
    el.querySelector('.toast-close').addEventListener('click', dismiss);
    if (duration > 0) timer = setTimeout(dismiss, duration);
    return dismiss;
  }

  function queueToast(message, type = 'info') {
    try {
      const list = JSON.parse(sessionStorage.getItem('pendingToasts') || '[]');
      list.push({ message, type });
      sessionStorage.setItem('pendingToasts', JSON.stringify(list));
    } catch (_) { /* ignore */ }
  }

  function flushPending() {
    try {
      const raw = sessionStorage.getItem('pendingToasts');
      if (!raw) return;
      sessionStorage.removeItem('pendingToasts');
      const list = JSON.parse(raw);
      for (const t of list) showToast(t.message, t.type);
    } catch (_) { /* ignore */ }
  }

  window.showToast = showToast;
  window.queueToast = queueToast;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', flushPending);
  } else {
    flushPending();
  }
})();
