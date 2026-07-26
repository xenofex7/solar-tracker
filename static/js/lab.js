// Chart-Lab: preview page for candidate charts. Reuses the global helpers
// from charts.js (CHART_COLORS, MONEY_LOC, charts, destroy, _hideIfEmpty).

// 3 - Self-sufficiency (autarky) vs. self-consumption rate per month
function renderLabAutarky(data) {
  destroy('lab-autarky');
  const ctx = document.getElementById('lab-autarky');
  const periods = data.grid?.periods || [];
  if (!_hideIfEmpty(ctx, periods.length > 0)) return;
  const autarky = periods.map(p => {
    const cons = p.self_consumed_kwh + p.imported_kwh;
    return cons > 0 ? p.self_consumed_kwh / cons * 100 : null;
  });
  charts['lab-autarky'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: periods.map(p => p.label),
      datasets: [
        { label: 'Self-sufficiency % (of consumption)', data: autarky, borderColor: CHART_COLORS.good, backgroundColor: 'rgba(76,175,80,0.12)', fill: true, tension: 0.25 },
        { label: 'Self-consumption % (of production)', data: periods.map(p => p.self_consumption_pct), borderColor: CHART_COLORS.actualLine, tension: 0.25, fill: false },
      ],
    },
    options: {
      plugins: { tooltip: { callbacks: { label: i => `${i.dataset.label}: ${i.parsed.y.toLocaleString(MONEY_LOC(), { maximumFractionDigits: 1 })} %` } } },
      scales: { y: { beginAtZero: true, suggestedMax: 100, ticks: { callback: v => `${v} %` } } },
    },
  });
}

async function labLoad(year) {
  const status = document.getElementById('status');
  status.textContent = window.T?.status_loading || 'Loading…';
  const r = await fetch(`/api/summary?year=${year}`);
  if (!r.ok) { status.textContent = window.T?.status_load_error || 'Error loading'; return; }
  const data = await r.json();
  renderLabAutarky(data);
  status.textContent = '';
}

document.getElementById('year-select').addEventListener('change', (e) => labLoad(e.target.value));
labLoad(document.getElementById('year-select').value);
