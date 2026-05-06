(() => {
  const tabs = document.getElementById('settings-tabs');
  const panels = document.querySelectorAll('.tab-panel');
  const activate = (name) => {
    tabs.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    panels.forEach(p => p.classList.toggle('active', p.dataset.tab === name));
  };
  tabs.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-tab]');
    if (!b) return;
    activate(b.dataset.tab);
    history.replaceState(null, '', '#' + b.dataset.tab);
  });
  const initial = (location.hash || '').replace('#', '');
  if (initial && document.querySelector(`.tab-panel[data-tab="${initial}"]`)) activate(initial);
})();

(() => {
  const form = document.getElementById('sync-form');
  const today = new Date();
  const from = new Date(today);
  from.setMonth(from.getMonth() - 3);
  const iso = (d) => {
    const tz = d.getTimezoneOffset() * 60000;
    return new Date(d - tz).toISOString().slice(0, 10);
  };
  form.from.value = iso(from);
  form.to.value = iso(today);
})();

(() => {
  const form = document.getElementById('general-sync-form');
  if (!form) return;
  const cb = form.auto_sync_on_open;
  cb.addEventListener('change', async () => {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_sync_on_open: cb.checked ? '1' : '0' }),
    });
    if (r.ok) {
      window.showToast(window.T?.msg_saved || 'Saved', 'success');
    } else {
      cb.checked = !cb.checked;
      const j = await r.json().catch(() => ({}));
      window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
    }
  });
})();

document.getElementById('plant-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    kwp: e.target.kwp.value,
    price_per_kwh: e.target.price_per_kwh.value,
    currency: e.target.currency.value,
    start_date: e.target.start_date.value,
    timezone: e.target.timezone.value,
  };
  const r = await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (r.ok) {
    window.queueToast(window.T?.msg_saved || 'Saved', 'success');
    location.reload();
  } else {
    const j = await r.json().catch(() => ({}));
    window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
  }
});

document.getElementById('cost-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    label: e.target.label.value,
    amount: Number(e.target.amount.value),
    date: e.target.date.value || null,
  };
  const r = await fetch('/api/costs', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (r.ok) {
    window.queueToast(window.T?.msg_saved || 'Saved', 'success');
    location.reload();
  } else {
    const j = await r.json();
    window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
  }
});

document.querySelectorAll('#costs-table button.del').forEach(btn => {
  btn.addEventListener('click', async () => {
    const tpl = window.T?.confirm_delete_cost || 'Delete "{label}"?';
    if (!confirm(tpl.replace('{label}', btn.dataset.label))) return;
    await fetch(`/api/costs/${btn.dataset.id}`, {method:'DELETE'});
    location.reload();
  });
});

document.querySelectorAll('#costs-table button.edit').forEach(btn => {
  btn.addEventListener('click', () => {
    const tr = btn.closest('tr');
    if (tr.classList.contains('editing')) return;
    tr.classList.add('editing');
    const { id, date, label, amount } = tr.dataset;
    const cells = tr.cells;
    cells[0].innerHTML = `<input type="date" class="edit-date" value="${date}">`;
    cells[1].innerHTML = `<input type="text" class="edit-label">`;
    cells[1].querySelector('.edit-label').value = label;
    cells[2].innerHTML = `<input type="number" class="edit-amount num" step="0.01" value="${amount}">`;
    cells[3].innerHTML = `
      <button class="save icon" type="button" aria-label="${window.T?.btn_save || 'Save'}" title="${window.T?.btn_save || 'Save'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
      <button class="cancel icon" type="button" aria-label="${window.T?.btn_cancel || 'Cancel'}" title="${window.T?.btn_cancel || 'Cancel'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    `;
    cells[3].querySelector('button.cancel').addEventListener('click', () => location.reload());
    cells[3].querySelector('button.save').addEventListener('click', async () => {
      const body = {
        date: tr.querySelector('.edit-date').value || null,
        label: tr.querySelector('.edit-label').value,
        amount: Number(tr.querySelector('.edit-amount').value),
      };
      const r = await fetch(`/api/costs/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      if (r.ok) {
        window.queueToast(window.T?.msg_saved || 'Saved', 'success');
        location.reload();
      } else {
        const j = await r.json().catch(() => ({}));
        window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
      }
    });
  });
});

document.getElementById('grid-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    kind: e.target.kind.value,
    period_start: e.target.period_start.value,
    period_end: e.target.period_end.value,
    kwh: Number(e.target.kwh.value),
    amount: Number(e.target.amount.value),
    invoice_no: e.target.invoice_no.value || null,
  };
  const r = await fetch('/api/grid', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (r.ok) {
    window.queueToast(window.T?.msg_saved || 'Saved', 'success');
    location.reload();
  } else {
    const j = await r.json();
    window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
  }
});

document.querySelectorAll('#imports-table button.del, #exports-table button.del').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (!confirm(window.T?.confirm_delete_grid || 'Delete entry?')) return;
    await fetch(`/api/grid/${btn.dataset.id}`, {method:'DELETE'});
    location.reload();
  });
});

document.querySelectorAll('#imports-table button.edit, #exports-table button.edit').forEach(btn => {
  btn.addEventListener('click', () => {
    const tr = btn.closest('tr');
    if (tr.classList.contains('editing')) return;
    tr.classList.add('editing');
    const { id, periodStart, periodEnd, kwh, amount, invoice } = tr.dataset;
    const cells = tr.cells;
    cells[0].innerHTML = `<input type="date" class="edit-start" value="${periodStart}"> <input type="date" class="edit-end" value="${periodEnd}">`;
    cells[1].innerHTML = `<input type="number" class="edit-kwh num" step="0.01" min="0" value="${kwh}">`;
    cells[2].innerHTML = `<input type="number" class="edit-amount num" step="0.01" min="0" value="${amount}">`;
    cells[3].textContent = '';
    cells[4].innerHTML = `<input type="text" class="edit-invoice">`;
    cells[4].querySelector('.edit-invoice').value = invoice;
    cells[5].innerHTML = `
      <button class="save icon" type="button" aria-label="${window.T?.btn_save || 'Save'}" title="${window.T?.btn_save || 'Save'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
      <button class="cancel icon" type="button" aria-label="${window.T?.btn_cancel || 'Cancel'}" title="${window.T?.btn_cancel || 'Cancel'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    `;
    cells[5].querySelector('button.cancel').addEventListener('click', () => location.reload());
    cells[5].querySelector('button.save').addEventListener('click', async () => {
      const body = {
        period_start: tr.querySelector('.edit-start').value,
        period_end: tr.querySelector('.edit-end').value,
        kwh: Number(tr.querySelector('.edit-kwh').value),
        amount: Number(tr.querySelector('.edit-amount').value),
        invoice_no: tr.querySelector('.edit-invoice').value || null,
      };
      const r = await fetch(`/api/grid/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      if (r.ok) {
        window.queueToast(window.T?.msg_saved || 'Saved', 'success');
        location.reload();
      } else {
        const j = await r.json().catch(() => ({}));
        window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
      }
    });
  });
});

document.getElementById('targets-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const inputs = e.target.querySelectorAll('input[data-month]');
  for (const i of inputs) {
    if (i.value === '') continue;
    await fetch('/api/targets', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({month: Number(i.dataset.month), kwh: Number(i.value), year: null})});
  }
  window.showToast(window.T?.msg_targets_saved || 'Targets saved', 'success');
});

document.getElementById('entry-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {date: e.target.date.value, kwh: Number(e.target.kwh.value)};
  const r = await fetch('/api/production', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  if (r.ok) {
    window.queueToast(window.T?.msg_saved || 'Saved', 'success');
    setTimeout(() => location.reload(), 400);
  } else {
    window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
  }
});

(() => {
  const table = document.getElementById('entries-table');
  const pager = document.getElementById('entries-pager');
  if (!table || !pager) return;

  const tbody = table.querySelector('tbody');
  const dataRows = [...tbody.querySelectorAll('tr[data-date]')];
  const headerRows = [...tbody.querySelectorAll('tr.month-header')];
  const info = document.getElementById('entries-pager-info');
  const prev = document.getElementById('entries-pager-prev');
  const next = document.getElementById('entries-pager-next');
  const sizeButtons = pager.querySelectorAll('button.pager-size');

  let pageSize = table.dataset.pageSize || '25';
  let page = 0;

  const sizeNum = () => (pageSize === 'all' ? dataRows.length || 1 : parseInt(pageSize, 10));
  const totalPages = () => Math.max(1, Math.ceil(dataRows.length / sizeNum()));

  const render = () => {
    const tp = totalPages();
    if (page >= tp) page = tp - 1;
    if (page < 0) page = 0;
    const size = sizeNum();
    const start = page * size;
    const end = start + size;
    const visibleMonths = new Set();
    dataRows.forEach((row, i) => {
      const visible = i >= start && i < end;
      row.hidden = !visible;
      if (visible) visibleMonths.add(row.dataset.month);
    });
    headerRows.forEach((h) => {
      h.hidden = !visibleMonths.has(h.dataset.month);
    });

    if (dataRows.length === 0) {
      info.textContent = window.T?.label_no_entries || 'No entries';
    } else {
      const tpl = window.T?.label_page_info || 'Page {page} of {total} ({from}-{to} of {count})';
      info.textContent = tpl
        .replace('{page}', page + 1)
        .replace('{total}', tp)
        .replace('{from}', start + 1)
        .replace('{to}', Math.min(end, dataRows.length))
        .replace('{count}', dataRows.length);
    }
    prev.disabled = page <= 0;
    next.disabled = page >= tp - 1;
    sizeButtons.forEach((b) => {
      if (b.dataset.size === pageSize) {
        b.setAttribute('aria-pressed', 'true');
      } else {
        b.removeAttribute('aria-pressed');
      }
    });
  };

  prev.addEventListener('click', () => { page -= 1; render(); });
  next.addEventListener('click', () => { page += 1; render(); });

  sizeButtons.forEach((b) => {
    b.addEventListener('click', async () => {
      if (b.dataset.size === pageSize) return;
      pageSize = b.dataset.size;
      page = 0;
      render();
      const r = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries_page_size: pageSize }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
      }
    });
  });

  render();
})();

document.querySelectorAll('#entries-table button.del').forEach(btn => {
  btn.addEventListener('click', async () => {
    const tpl = window.T?.confirm_delete_prod || 'Delete entry from {date}?';
    if (!confirm(tpl.replace('{date}', btn.dataset.display))) return;
    await fetch(`/api/production/${btn.dataset.date}`, {method:'DELETE'});
    location.reload();
  });
});

document.querySelectorAll('#entries-table button.edit').forEach(btn => {
  btn.addEventListener('click', () => {
    const tr = btn.closest('tr');
    if (tr.classList.contains('editing')) return;
    tr.classList.add('editing');
    const { date, kwh } = tr.dataset;
    const cells = tr.cells;
    cells[1].innerHTML = `<input type="number" class="edit-kwh num" step="0.01" min="0" value="${kwh}">`;
    cells[3].innerHTML = `
      <button class="save icon" type="button" aria-label="${window.T?.btn_save || 'Save'}" title="${window.T?.btn_save || 'Save'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
      <button class="cancel icon" type="button" aria-label="${window.T?.btn_cancel || 'Cancel'}" title="${window.T?.btn_cancel || 'Cancel'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    `;
    cells[3].querySelector('button.cancel').addEventListener('click', () => location.reload());
    cells[3].querySelector('button.save').addEventListener('click', async () => {
      const body = { date, kwh: Number(tr.querySelector('.edit-kwh').value) };
      const r = await fetch('/api/production', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      if (r.ok) {
        window.queueToast(window.T?.msg_saved || 'Saved', 'success');
        location.reload();
      } else {
        const j = await r.json().catch(() => ({}));
        window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
      }
    });
  });
});

(() => {
  const select = document.getElementById('sync-source-select');
  const form = document.getElementById('sync-form');
  if (!select || !form) return;

  const submit = document.getElementById('sync-submit');
  const SOURCE_ENDPOINT = {
    home_assistant: '/api/sync/ha',
    solarweb: '/api/sync/solarweb',
  };

  const isConfigured = (src) => {
    if (src === 'home_assistant') return select.dataset.haConfigured === '1';
    if (src === 'solarweb') return select.dataset.solarwebConfigured === '1';
    return false;
  };

  const refreshUI = () => {
    const src = select.value;
    document.querySelectorAll('.sync-source-info').forEach((el) => {
      el.hidden = el.dataset.source !== src;
    });
    submit.disabled = !isConfigured(src);
  };

  select.addEventListener('change', async () => {
    refreshUI();
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sync_source: select.value }),
    });
    if (r.ok) {
      window.showToast(window.T?.msg_saved || 'Saved', 'success');
    } else {
      const j = await r.json().catch(() => ({}));
      window.showToast((window.T?.msg_error_prefix || 'Error: ') + (j.error || '?'), 'error');
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const endpoint = SOURCE_ENDPOINT[select.value];
    if (!endpoint) return;
    const body = { from: e.target.from.value, to: e.target.to.value };
    const r = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (r.ok) {
      const tpl = window.T?.msg_sync_done || '{days} days synced · {inserted} new · {updated} updated';
      const sub = tpl
        .replace('{days}', j.days)
        .replace('{inserted}', j.inserted)
        .replace('{updated}', j.updated);
      window.queueToast({ title: window.T?.msg_sync_done_title || 'Done', sub }, 'success');
      location.reload();
    } else {
      window.showToast((window.T?.msg_error_prefix || 'Error: ') + j.error, 'error');
    }
  });

  refreshUI();
})();

/* ---- Users tab (v2.1) ---- */
function userErrorMessage(code) {
  // Backend returns machine-readable codes; we resolve them to translated text.
  const T = window.T || {};
  const map = {
    set_own_password_first: T.warn_set_own_password,
    invalid_username: T.err_invalid_username,
    invalid_role: T.err_invalid_role,
    password_required: T.err_password_required,
    username_taken: T.err_username_taken,
    not_found: T.err_not_found,
    no_change: T.err_no_change,
    cannot_demote_last_admin: T.err_cannot_demote_last_admin,
    cannot_delete_last_admin: T.err_cannot_delete_last_admin,
    cannot_delete_self: T.err_cannot_delete_self,
    would_lock_platform: T.err_would_lock_platform,
  };
  return map[code] || ((T.msg_error_prefix || 'Error: ') + (code || '?'));
}

const userForm = document.getElementById('user-form');
if (userForm) {
  userForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pw = e.target.password.value || '';
    const pwc = e.target.password_confirm.value || '';
    if (pw !== pwc) {
      window.showToast(window.T?.err_password_mismatch || 'Passwords do not match.', 'error');
      return;
    }
    const body = {
      username: e.target.username.value.trim(),
      role: e.target.role.value,
      password: pw,
    };
    const r = await fetch('/api/users', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    if (r.ok) {
      window.queueToast(window.T?.msg_saved || 'Saved', 'success');
      location.reload();
    } else {
      const j = await r.json().catch(() => ({}));
      window.showToast(userErrorMessage(j.error), 'error');
    }
  });

  document.querySelectorAll('#users-table button.del').forEach(btn => {
    btn.addEventListener('click', async () => {
      const tpl = window.T?.confirm_delete_user || 'Delete user "{name}"?';
      if (!confirm(tpl.replace('{name}', btn.dataset.username))) return;
      const r = await fetch(`/api/users/${btn.dataset.id}`, {method:'DELETE'});
      if (r.ok) {
        location.reload();
      } else {
        const j = await r.json().catch(() => ({}));
        window.showToast(userErrorMessage(j.error), 'error');
      }
    });
  });

  document.querySelectorAll('#users-table button.edit').forEach(btn => {
    btn.addEventListener('click', () => {
      const tr = btn.closest('tr');
      if (tr.classList.contains('editing')) return;
      tr.classList.add('editing');
      const { id, role } = tr.dataset;
      const cells = tr.cells;
      const adminLabel = window.T?.role_admin || 'Admin';
      const roLabel = window.T?.role_readonly || 'Read-only';
      const pwHint = window.T?.placeholder_password_change || 'New password (leave blank to keep)';
      cells[1].innerHTML = `
        <select class="edit-role">
          <option value="admin"${role === 'admin' ? ' selected' : ''}>${adminLabel}</option>
          <option value="readonly"${role === 'readonly' ? ' selected' : ''}>${roLabel}</option>
        </select>`;
      const clearLabel = window.T?.label_clear_password || 'Remove password';
      const clearTitle = window.T?.title_clear_password || '';
      const pwConfirmHint = window.T?.placeholder_password_confirm || 'Confirm';
      cells[2].innerHTML = `
        <input type="password" class="edit-password" autocomplete="new-password" placeholder="${pwHint}">
        <input type="password" class="edit-password-confirm" autocomplete="new-password" placeholder="${pwConfirmHint}">
        <label class="clear-pw-toggle" title="${clearTitle}">
          <input type="checkbox" class="edit-clear-password"> ${clearLabel}
        </label>`;
      cells[3].innerHTML = `
        <button class="save icon" type="button" aria-label="${window.T?.btn_save || 'Save'}" title="${window.T?.btn_save || 'Save'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></button>
        <button class="cancel icon" type="button" aria-label="${window.T?.btn_cancel || 'Cancel'}" title="${window.T?.btn_cancel || 'Cancel'}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
      `;
      cells[3].querySelector('button.cancel').addEventListener('click', () => location.reload());
      cells[3].querySelector('button.save').addEventListener('click', async () => {
        const pwValue = tr.querySelector('.edit-password').value;
        const pwConfirm = tr.querySelector('.edit-password-confirm').value;
        const clearPw = tr.querySelector('.edit-clear-password').checked;
        const newRole = tr.querySelector('.edit-role').value;

        // Only check confirmation when a new password is being set; an empty
        // field means "keep existing".
        if (pwValue && pwValue !== pwConfirm) {
          window.showToast(window.T?.err_password_mismatch || 'Passwords do not match.', 'error');
          return;
        }

        // Are we editing our own row?
        const selfId = document.getElementById('users-table')?.dataset.selfId || '';
        const editingSelf = selfId && String(tr.dataset.id) === String(selfId);
        const oldRole = tr.dataset.role;

        if (editingSelf && clearPw && !pwValue) {
          const msg = window.T?.confirm_self_clear_password
            || 'Remove your own password? Next session will require auto-login (only works if you are the sole user). Continue?';
          if (!confirm(msg)) return;
        }
        if (editingSelf && newRole !== oldRole && newRole !== 'admin') {
          const msg = window.T?.confirm_self_demote
            || 'Demote your own admin account? You will lose access to settings immediately on next page load. Continue?';
          if (!confirm(msg)) return;
        }

        const body = {
          role: newRole,
          password: pwValue || undefined,
          clear_password: clearPw && !pwValue ? true : undefined,
        };
        const r = await fetch(`/api/users/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
        if (r.ok) {
          window.queueToast(window.T?.msg_saved || 'Saved', 'success');
          location.reload();
        } else {
          const j = await r.json().catch(() => ({}));
          window.showToast(userErrorMessage(j.error), 'error');
        }
      });
    });
  });
}
