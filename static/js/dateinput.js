/* Swiss date input: replaces every input[type="date"] with a dd.mm.yyyy
   text field plus calendar popup - native date inputs render differently
   depending on the OS locale (e.g. mm/dd/yyyy under en-US).
   The original input becomes a hidden field keeping its name, classes and
   ISO value (yyyy-mm-dd), so existing form handlers stay unchanged. */
(() => {
  const T = window.T || {};
  const WEEKDAYS = T.weekdays_short || ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
  const MONTHS_SHORT = T.months_short || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const MONTHS_LONG = T.months_long || MONTHS_SHORT;
  const PLACEHOLDER = T.placeholder_date || 'dd.mm.yyyy';
  const INVALID_MSG = T.err_invalid_date || 'Invalid date (dd.mm.yyyy)';
  const CAL_LABEL = T.btn_calendar || 'Calendar';
  const YEARS_PER_PAGE = 12;

  const SVG_ATTRS = 'width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
  const ICON_CALENDAR = `<svg ${SVG_ATTRS}><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;
  const ICON_PREV = `<svg ${SVG_ATTRS}><polyline points="15 18 9 12 15 6"/></svg>`;
  const ICON_NEXT = `<svg ${SVG_ATTRS}><polyline points="9 18 15 12 9 6"/></svg>`;

  const pad = (n) => String(n).padStart(2, '0');

  const isoToDisplay = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? `${m[3]}.${m[2]}.${m[1]}` : '';
  };

  /* Display text -> ISO. Returns null when unparseable, '' for empty.
     Tolerant: 1- or 2-digit days/months. 31.02. is rejected via Date
     round-trip. */
  const displayToIso = (text) => {
    const trimmed = text.trim();
    if (!trimmed) return '';
    const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(trimmed);
    if (!m) return null;
    const day = Number(m[1]);
    const month = Number(m[2]);
    const year = Number(m[3]);
    if (month < 1 || month > 12 || day < 1 || day > 31) return null;
    const dt = new Date(year, month - 1, day);
    if (dt.getFullYear() !== year || dt.getMonth() !== month - 1 || dt.getDate() !== day) return null;
    return `${year}-${pad(month)}-${pad(day)}`;
  };

  /* ---- Calendar popup (one shared instance, portaled to <body>) ---- */
  let popup = null;
  let active = null; // { hidden, text, wrap }
  let view, viewYear, viewMonth, yearPageStart;

  const closePopup = () => {
    if (!popup) return;
    popup.remove();
    popup = null;
    active = null;
    window.removeEventListener('scroll', position, true);
    window.removeEventListener('resize', position);
    document.removeEventListener('pointerdown', onOutside, true);
    document.removeEventListener('keydown', onKey, true);
  };

  const onOutside = (e) => {
    if (popup.contains(e.target) || active.wrap.contains(e.target)) return;
    closePopup();
  };

  const onKey = (e) => {
    if (e.key === 'Escape') closePopup();
  };

  const position = () => {
    const r = active.wrap.getBoundingClientRect();
    const p = popup.getBoundingClientRect();
    let top = r.bottom + 4;
    if (top + p.height > window.innerHeight - 8 && r.top - p.height - 4 > 8) {
      top = r.top - p.height - 4;
    }
    const left = Math.max(8, Math.min(r.left, window.innerWidth - p.width - 8));
    popup.style.top = `${top}px`;
    popup.style.left = `${left}px`;
  };

  const commit = (iso) => {
    active.hidden.value = iso;
    active.text.value = isoToDisplay(iso);
    active.text.classList.remove('invalid');
    active.text.setCustomValidity('');
    active.hidden.dispatchEvent(new Event('change', { bubbles: true }));
  };

  const navBtn = (icon, onClick) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'date-cal-nav';
    b.innerHTML = icon;
    b.addEventListener('click', onClick);
    return b;
  };

  const render = () => {
    popup.textContent = '';
    const header = document.createElement('div');
    header.className = 'date-cal-header';

    const selectedIso = active.hidden.value;
    const today = new Date();

    if (view === 'days') {
      header.append(navBtn(ICON_PREV, () => {
        viewMonth -= 1;
        if (viewMonth < 0) { viewMonth = 11; viewYear -= 1; }
        render();
      }));
      const label = document.createElement('button');
      label.type = 'button';
      label.className = 'date-cal-label';
      label.textContent = `${MONTHS_LONG[viewMonth]} ${viewYear}`;
      label.addEventListener('click', () => { view = 'months'; render(); });
      header.append(label);
      header.append(navBtn(ICON_NEXT, () => {
        viewMonth += 1;
        if (viewMonth > 11) { viewMonth = 0; viewYear += 1; }
        render();
      }));
      popup.append(header);

      const grid = document.createElement('div');
      grid.className = 'date-cal-grid';
      for (const wd of WEEKDAYS) {
        const el = document.createElement('div');
        el.className = 'date-cal-wd';
        el.textContent = wd;
        grid.append(el);
      }
      const first = new Date(viewYear, viewMonth, 1);
      const start = new Date(first);
      start.setDate(1 - ((first.getDay() + 6) % 7)); // back to Monday
      const last = new Date(viewYear, viewMonth + 1, 0);
      const end = new Date(last);
      end.setDate(last.getDate() + (6 - ((last.getDay() + 6) % 7))); // forward to Sunday
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        const iso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'date-cal-day';
        b.textContent = d.getDate();
        if (d.getMonth() !== viewMonth) b.classList.add('other');
        if (iso === selectedIso) b.classList.add('selected');
        else if (d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth() && d.getDate() === today.getDate()) {
          b.classList.add('today');
        }
        b.addEventListener('click', () => { commit(iso); closePopup(); });
        grid.append(b);
      }
      popup.append(grid);
    } else if (view === 'months') {
      header.append(navBtn(ICON_PREV, () => { viewYear -= 1; render(); }));
      const label = document.createElement('button');
      label.type = 'button';
      label.className = 'date-cal-label';
      label.textContent = viewYear;
      label.addEventListener('click', () => {
        yearPageStart = Math.floor(viewYear / YEARS_PER_PAGE) * YEARS_PER_PAGE;
        view = 'years';
        render();
      });
      header.append(label);
      header.append(navBtn(ICON_NEXT, () => { viewYear += 1; render(); }));
      popup.append(header);

      const grid = document.createElement('div');
      grid.className = 'date-cal-grid wide';
      MONTHS_SHORT.forEach((name, i) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'date-cal-cell';
        b.textContent = name;
        if (i === viewMonth) b.classList.add('selected');
        b.addEventListener('click', () => { viewMonth = i; view = 'days'; render(); });
        grid.append(b);
      });
      popup.append(grid);
    } else {
      header.append(navBtn(ICON_PREV, () => { yearPageStart -= YEARS_PER_PAGE; render(); }));
      const label = document.createElement('div');
      label.className = 'date-cal-label static';
      label.textContent = `${yearPageStart} - ${yearPageStart + YEARS_PER_PAGE - 1}`;
      header.append(label);
      header.append(navBtn(ICON_NEXT, () => { yearPageStart += YEARS_PER_PAGE; render(); }));
      popup.append(header);

      const grid = document.createElement('div');
      grid.className = 'date-cal-grid wide';
      for (let y = yearPageStart; y < yearPageStart + YEARS_PER_PAGE; y += 1) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'date-cal-cell';
        b.textContent = y;
        if (y === viewYear) b.classList.add('selected');
        b.addEventListener('click', () => { viewYear = b.textContent * 1; view = 'months'; render(); });
        grid.append(b);
      }
      popup.append(grid);
    }
    position();
  };

  const openPopup = (field) => {
    if (popup && active === field) { closePopup(); return; }
    closePopup();
    active = field;
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(field.hidden.value);
    const base = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date();
    view = 'days';
    viewYear = base.getFullYear();
    viewMonth = base.getMonth();
    yearPageStart = Math.floor(viewYear / YEARS_PER_PAGE) * YEARS_PER_PAGE;
    popup = document.createElement('div');
    popup.className = 'date-cal';
    document.body.append(popup);
    render();
    window.addEventListener('scroll', position, true);
    window.addEventListener('resize', position);
    document.addEventListener('pointerdown', onOutside, true);
    document.addEventListener('keydown', onKey, true);
  };

  /* ---- Field upgrade ---- */
  const upgrade = (input) => {
    if (input.dataset.dateField) return;
    input.dataset.dateField = '1';

    const wrap = document.createElement('span');
    wrap.className = 'date-field';

    const text = document.createElement('input');
    text.type = 'text';
    text.className = 'date-field-text';
    text.placeholder = PLACEHOLDER;
    text.inputMode = 'numeric';
    text.autocomplete = 'off';
    text.spellcheck = false;
    if (input.required) text.required = true;
    if (input.title) text.title = input.title;
    if (input.id) { text.id = input.id; input.removeAttribute('id'); }

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'date-field-btn';
    btn.tabIndex = -1;
    btn.setAttribute('aria-label', CAL_LABEL);
    btn.title = CAL_LABEL;
    btn.innerHTML = ICON_CALENDAR;

    input.parentNode.insertBefore(wrap, input);
    wrap.append(text, btn, input);
    input.type = 'hidden';
    text.value = isoToDisplay(input.value);

    const field = { hidden: input, text, wrap };

    text.addEventListener('input', () => {
      const iso = displayToIso(text.value);
      if (iso !== null) {
        input.value = iso;
        text.classList.remove('invalid');
        text.setCustomValidity('');
      }
    });
    text.addEventListener('blur', () => {
      const iso = displayToIso(text.value);
      if (iso === null) {
        text.classList.add('invalid');
        text.setCustomValidity(INVALID_MSG);
        return;
      }
      input.value = iso;
      text.value = isoToDisplay(iso);
      text.classList.remove('invalid');
      text.setCustomValidity('');
    });
    btn.addEventListener('click', () => {
      openPopup(field);
    });
  };

  document.querySelectorAll('input[type="date"]').forEach(upgrade);

  // Table rows switch to inline-edit mode by injecting fresh date inputs.
  new MutationObserver((muts) => {
    for (const mut of muts) {
      for (const node of mut.addedNodes) {
        if (node.nodeType !== 1) continue;
        if (node.matches('input[type="date"]')) upgrade(node);
        node.querySelectorAll('input[type="date"]').forEach(upgrade);
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
})();
