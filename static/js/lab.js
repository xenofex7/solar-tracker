// Chart-Lab: preview page for candidate charts. Reuses the global helpers
// from charts.js (CHART_COLORS, CUR, MONEY_LOC, fmt*, charts, destroy).

const LAB_SUBUNIT = { CHF: 'Rp', EUR: 'ct', USD: '¢', GBP: 'p' };

function labPriceUnit() {
  const sub = LAB_SUBUNIT[CUR()];
  return { unit: sub || CUR(), factor: sub ? 100 : 1 };
}

function labMoney2(v) {
  return `${(Number(v) || 0).toLocaleString(MONEY_LOC(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${CUR()}`;
}

// 5 - KPI: revenue rate
function renderLabKpis(data) {
  const el = document.getElementById('lab-kpis');
  const p = data.finance?.payback;
  if (!p || !(p.avg_daily_revenue > 0)) { el.innerHTML = ''; return; }
  const { unit, factor } = labPriceUnit();
  const blended = ((p.blended_price || 0) * factor).toLocaleString(MONEY_LOC(), { maximumFractionDigits: 1 });
  const basis = p.projection_basis === 'targets' ? 'annual target' : 'history';
  el.innerHTML = `<div class="kpi-group"><h3>5 · Revenue rate (KPI)</h3><div class="kpis">
    <div class="kpi"><div class="label">Revenue per day (avg)</div><div class="value">${labMoney2(p.avg_daily_revenue)}<br><span class="sub">${blended} ${unit}/kWh blended · ${basis}</span></div></div>
    <div class="kpi"><div class="label">Projected per year</div><div class="value">${labMoney2(p.avg_daily_revenue * 365)}</div></div>
  </div></div>`;
}

// 1 - Tariff trend: import/export price per month from prorated bills
function renderLabTariff(data) {
  destroy('lab-tariff');
  const ctx = document.getElementById('lab-tariff');
  const periods = data.grid?.periods || [];
  if (!_hideIfEmpty(ctx, periods.length > 0)) return;
  const { unit, factor } = labPriceUnit();
  const imp = periods.map(p => p.imported_kwh > 0 ? p.import_cost / p.imported_kwh * factor : null);
  const exp = periods.map(p => p.exported_kwh > 0 ? p.export_credit / p.exported_kwh * factor : null);
  charts['lab-tariff'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: periods.map(p => p.label),
      datasets: [
        { label: `Import (${unit}/kWh)`, data: imp, borderColor: CHART_COLORS.targetLine, backgroundColor: 'rgba(52,152,219,0.12)', tension: 0.2, spanGaps: true },
        { label: `Export (${unit}/kWh)`, data: exp, borderColor: CHART_COLORS.actualLine, backgroundColor: 'rgba(245,166,35,0.12)', tension: 0.2, spanGaps: true },
      ],
    },
    options: {
      plugins: { tooltip: { callbacks: { label: i => `${i.dataset.label.split(' ')[0]}: ${i.parsed.y.toLocaleString(MONEY_LOC(), { maximumFractionDigits: 1 })} ${unit}/kWh` } } },
      scales: { y: { beginAtZero: true, ticks: { callback: v => `${v} ${unit}` } } },
    },
  });
}

// 2 - Payback as a daily cumulative revenue line + investment + forecast
function renderLabPaybackDaily(data) {
  destroy('lab-payback-daily');
  const ctx = document.getElementById('lab-payback-daily');
  const fin = data.finance;
  const series = fin?.cumulative_revenue || [];
  const invested = fin?.payback?.invested || 0;
  if (!_hideIfEmpty(ctx, series.length > 0 && invested > 0)) return;

  const labels = series.map(r => r.date);
  const actual = series.map(r => r.revenue);
  const forecast = new Array(labels.length).fill(null);

  const avgDaily = fin.payback?.avg_daily_revenue || 0;
  if (avgDaily > 0 && actual[actual.length - 1] < invested) {
    forecast[forecast.length - 1] = actual[actual.length - 1];
    let cum = actual[actual.length - 1];
    let [y, m] = labels[labels.length - 1].split('-').map(Number);
    let guard = 0;
    while (cum < invested && guard < 600) {
      m += 1;
      if (m > 12) { m = 1; y += 1; }
      cum = Math.min(cum + avgDaily * 30.44, invested);
      labels.push(`${y}-${String(m).padStart(2, '0')}-01`);
      actual.push(null);
      forecast.push(cum);
      guard += 1;
    }
  }

  charts['lab-payback-daily'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: (window.T?.chart_cumulative_revenue || 'Revenue ({currency})').replace('{currency}', CUR()), data: actual, borderColor: CHART_COLORS.actualLine, backgroundColor: 'rgba(245,166,35,0.15)', fill: true, pointRadius: 0, borderWidth: 2 },
        { label: (window.T?.chart_forecast || 'Forecast ({currency})').replace('{currency}', CUR()), data: forecast, borderColor: CHART_COLORS.actualLine, borderDash: [5, 5], pointRadius: 0, borderWidth: 1.5, fill: false },
        { label: (window.T?.chart_investment || 'Investment ({currency})').replace('{currency}', CUR()), data: labels.map(() => invested), borderColor: CHART_COLORS.targetLine, borderDash: [6, 4], pointRadius: 0, fill: false },
      ],
    },
    options: {
      plugins: { tooltip: { callbacks: { title: items => fmtDate(items[0].label), label: i => `${i.dataset.label}: ${fmtMoney(i.parsed.y)}` } } },
      scales: {
        x: { ticks: { maxTicksLimit: 14, callback(v) { return fmtDate(this.getLabelForValue(v)); } } },
        y: { beginAtZero: true, ticks: { callback: v => fmtMoney(v) } },
      },
    },
  });
}

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

// 4 - Monthly distribution as a boxplot (floating bars + median points)
function renderLabBoxplot(data) {
  destroy('lab-boxplot');
  const ctx = document.getElementById('lab-boxplot');
  const dist = data.monthly_distribution || [];
  if (!_hideIfEmpty(ctx, dist.some(d => d.count > 0))) return;
  charts['lab-boxplot'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: localizeMonths(data.months),
      datasets: [
        { label: 'Min-Max', data: dist.map(d => d.count ? [d.min, d.max] : null), backgroundColor: 'rgba(138,154,172,0.35)', barPercentage: 0.18, grouped: false, order: 3 },
        { label: 'Q1-Q3', data: dist.map(d => d.count ? [d.q1, d.q3] : null), backgroundColor: CHART_COLORS.actual, barPercentage: 0.55, grouped: false, order: 2 },
        { label: window.T?.label_median || 'Median', data: dist.map(d => d.count ? d.median : null), type: 'line', showLine: false, pointRadius: 5, pointStyle: 'rectRounded', pointBackgroundColor: CHART_COLORS.text, borderColor: CHART_COLORS.text, order: 1 },
      ],
    },
    options: {
      plugins: {
        tooltip: { callbacks: { label: (i) => {
          const d = dist[i.dataIndex];
          if (i.dataset.label === 'Min-Max') return `Min ${fmtKwh(d.min)} · Max ${fmtKwh(d.max)}`;
          if (i.dataset.label === 'Q1-Q3') return `Q1 ${fmtKwh(d.q1)} · Q3 ${fmtKwh(d.q3)} · ${d.count} days`;
          return `${window.T?.label_median || 'Median'} ${fmtKwh(d.median)}`;
        } } },
      },
      scales: { y: { beginAtZero: true, ticks: { callback: v => fmtKwh(v) } } },
    },
  });
}

async function labLoad(year) {
  const status = document.getElementById('status');
  status.textContent = window.T?.status_loading || 'Loading…';
  const r = await fetch(`/api/summary?year=${year}`);
  if (!r.ok) { status.textContent = window.T?.status_load_error || 'Error loading'; return; }
  const data = await r.json();
  renderLabKpis(data);
  renderLabTariff(data);
  renderLabPaybackDaily(data);
  renderLabAutarky(data);
  renderLabBoxplot(data);
  status.textContent = '';
}

document.getElementById('year-select').addEventListener('change', (e) => labLoad(e.target.value));
labLoad(document.getElementById('year-select').value);
