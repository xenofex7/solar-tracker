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
  from.setMonth(from.getMonth() - 6);
  const iso = (d) => {
    const tz = d.getTimezoneOffset() * 60000;
    return new Date(d - tz).toISOString().slice(0, 10);
  };
  form.from.value = iso(from);
  form.to.value = iso(today);
})();

document.getElementById('plant-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    kwp: e.target.kwp.value,
    price_per_kwh: e.target.price_per_kwh.value,
    start_date: e.target.start_date.value,
    timezone: e.target.timezone.value,
  };
  const r = await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (r.ok) window.showToast(window.T?.msg_saved || 'Saved', 'success');
  else window.showToast(window.T?.msg_save_error || 'Error saving', 'error');
});

document.getElementById('cost-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    label: e.target.label.value,
    amount_chf: Number(e.target.amount_chf.value),
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
        amount_chf: Number(tr.querySelector('.edit-amount').value),
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
    amount_chf: Number(e.target.amount_chf.value),
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
        amount_chf: Number(tr.querySelector('.edit-amount').value),
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

document.getElementById('sync-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {from: e.target.from.value, to: e.target.to.value};
  const r = await fetch('/api/sync/ha', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
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
