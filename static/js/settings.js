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
  };
  const r = await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  alert(r.ok ? 'Gespeichert.' : 'Fehler beim Speichern.');
});

document.getElementById('cost-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    label: e.target.label.value,
    amount_chf: Number(e.target.amount_chf.value),
    date: e.target.date.value || null,
  };
  const r = await fetch('/api/costs', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (r.ok) location.reload();
  else { const j = await r.json(); alert('Fehler: ' + (j.error || 'unbekannt')); }
});

document.querySelectorAll('#costs-table button.del').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (!confirm(`Position "${btn.dataset.label}" löschen?`)) return;
    await fetch(`/api/costs/${btn.dataset.id}`, {method:'DELETE'});
    location.reload();
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
  if (r.ok) location.reload();
  else { const j = await r.json(); alert('Fehler: ' + (j.error || 'unbekannt')); }
});

document.querySelectorAll('#imports-table button.del, #exports-table button.del').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (!confirm('Eintrag löschen?')) return;
    await fetch(`/api/grid/${btn.dataset.id}`, {method:'DELETE'});
    location.reload();
  });
});

document.getElementById('targets-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const inputs = e.target.querySelectorAll('input[data-month]');
  for (const i of inputs) {
    if (i.value === '') continue;
    await fetch('/api/targets', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({month: Number(i.dataset.month), kwh: Number(i.value), year: null})});
  }
  alert('Sollwerte gespeichert.');
});

document.getElementById('entry-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const status = document.getElementById('entry-status');
  const body = {date: e.target.date.value, kwh: Number(e.target.kwh.value)};
  const r = await fetch('/api/production', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  status.textContent = r.ok ? 'Gespeichert.' : `Fehler: ${j.error}`;
  if (r.ok) setTimeout(() => location.reload(), 500);
});

document.querySelectorAll('#entries-table button.del').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (!confirm(`Eintrag vom ${btn.dataset.display} löschen?`)) return;
    await fetch(`/api/production/${btn.dataset.date}`, {method:'DELETE'});
    location.reload();
  });
});

document.getElementById('sync-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const status = document.getElementById('sync-status');
  status.textContent = 'Synchronisiere…';
  const body = {from: e.target.from.value, to: e.target.to.value};
  const r = await fetch('/api/sync/ha', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  if (r.ok) {
    const t = j.timings ? ` · HA ${j.timings.fetch_s}s + DB ${j.timings.write_s}s` : '';
    status.textContent = `Fertig: ${j.days} Tage abgeglichen (${j.inserted} neu, ${j.updated} aktualisiert).${t}`;
  } else {
    status.textContent = `Fehler: ${j.error}`;
  }
});
