const CHART_COLORS = {
  actual: 'rgba(245, 166, 35, 0.85)',
  actualLine: '#f5a623',
  target: 'rgba(52, 152, 219, 0.75)',
  targetLine: '#3498db',
  good: '#4caf50',
  bad: '#e74c3c',
  grid: 'rgba(255,255,255,0.08)',
  text: '#e4ecf2',
  muted: '#8a9aac',
};

Chart.defaults.color = CHART_COLORS.text;
Chart.defaults.borderColor = CHART_COLORS.grid;
Chart.defaults.font.family = '-apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif';

const charts = {};

function destroy(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function renderMonthly(data) {
  destroy('monthly');
  const ctx = document.getElementById('chart-monthly');
  charts.monthly = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.months,
      datasets: [
        { label: 'Ist (kWh)',  data: data.monthly_actual,  backgroundColor: CHART_COLORS.actual },
        { label: 'Soll (kWh)', data: data.monthly_target, backgroundColor: CHART_COLORS.target },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { beginAtZero: true, ticks: { callback: v => v + ' kWh' } } },
    },
  });
}

function renderDeviation(data) {
  destroy('deviation');
  const ctx = document.getElementById('chart-deviation');
  const colors = data.deviation_pct.map(v => v === null ? CHART_COLORS.muted : (v >= 0 ? CHART_COLORS.good : CHART_COLORS.bad));
  charts.deviation = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.months,
      datasets: [{ label: 'Abweichung %', data: data.deviation_pct.map(v => v ?? 0), backgroundColor: colors }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { callback: v => v + ' %' } } },
    },
  });
}

function renderCumulative(data) {
  destroy('cumulative');
  const ctx = document.getElementById('chart-cumulative');
  charts.cumulative = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.months,
      datasets: [
        { label: 'Ist kumuliert',  data: data.cumulative_actual, borderColor: CHART_COLORS.actualLine, backgroundColor: 'rgba(245,166,35,0.15)', fill: true, tension: 0.2 },
        { label: 'Soll kumuliert', data: data.cumulative_target, borderColor: CHART_COLORS.targetLine, borderDash: [6,4], fill: false, tension: 0.2 },
      ],
    },
    options: { scales: { y: { beginAtZero: true, ticks: { callback: v => v + ' kWh' } } } },
  });
}

function renderDaily(data) {
  destroy('daily');
  const ctx = document.getElementById('chart-daily');
  const labels = data.daily.map(d => d.date);
  const values = data.daily.map(d => d.kwh);
  charts.daily = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Tageswert', data: values, borderColor: CHART_COLORS.actualLine, backgroundColor: 'rgba(245,166,35,0.15)', pointRadius: 1.5, fill: true, tension: 0.1 },
        { label: '7-Tage-Mittel', data: data.rolling_avg_7d, borderColor: CHART_COLORS.targetLine, pointRadius: 0, borderWidth: 2, fill: false, tension: 0.2 },
      ],
    },
    options: {
      scales: {
        x: { ticks: { maxTicksLimit: 12 } },
        y: { beginAtZero: true, ticks: { callback: v => v + ' kWh' } },
      },
    },
  });
}

function renderHeatmap(data) {
  destroy('heatmap');
  const ctx = document.getElementById('chart-heatmap');
  const maxKwh = Math.max(1, ...data.heatmap.map(d => d.kwh));
  const points = data.heatmap.map(d => {
    const dt = new Date(d.date);
    const startOfYear = new Date(dt.getFullYear(), 0, 1);
    const dayOfYear = Math.floor((dt - startOfYear) / 86400000);
    const firstDow = (startOfYear.getDay() + 6) % 7;
    const week = Math.floor((dayOfYear + firstDow) / 7);
    const dow = (dt.getDay() + 6) % 7;
    return { x: week, y: dow, v: d.kwh, date: d.date };
  });

  charts.heatmap = new Chart(ctx, {
    type: 'matrix',
    data: {
      datasets: [{
        label: 'Tägliche kWh',
        data: points,
        backgroundColor(ctx) {
          const v = ctx.dataset.data[ctx.dataIndex].v;
          if (!v) return 'rgba(255,255,255,0.04)';
          const alpha = 0.15 + 0.85 * (v / maxKwh);
          return `rgba(245, 166, 35, ${alpha})`;
        },
        borderWidth: 0,
        width: ({ chart }) => (chart.chartArea || {}).width ? (chart.chartArea.width / 54) - 2 : 10,
        height: ({ chart }) => (chart.chartArea || {}).height ? (chart.chartArea.height / 7) - 2 : 10,
      }],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: items => items[0].raw.date, label: item => `${item.raw.v.toFixed(2)} kWh` } },
      },
      scales: {
        x: { type: 'linear', min: -0.5, max: 53.5, display: false, grid: { display: false } },
        y: {
          type: 'category',
          labels: ['Mo','Di','Mi','Do','Fr','Sa','So'],
          offset: true,
          reverse: false,
          ticks: { autoSkip: false },
          grid: { display: false },
        },
      },
    },
  });
}

function renderDistribution(data) {
  destroy('distribution');
  const ctx = document.getElementById('chart-distribution');
  const medians = data.monthly_distribution.map(d => d.median);
  const mins    = data.monthly_distribution.map(d => d.min);
  const maxs    = data.monthly_distribution.map(d => d.max);
  charts.distribution = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.months,
      datasets: [
        { label: 'Min',    data: mins,    backgroundColor: 'rgba(52,152,219,0.6)' },
        { label: 'Median', data: medians, backgroundColor: 'rgba(245,166,35,0.85)' },
        { label: 'Max',    data: maxs,    backgroundColor: 'rgba(76,175,80,0.75)' },
      ],
    },
    options: { scales: { y: { beginAtZero: true, ticks: { callback: v => v + ' kWh' } } } },
  });
}

function renderYearComparison(data) {
  destroy('yearcomp');
  const ctx = document.getElementById('chart-yearcomp');
  const palette = ['#f5a623','#3498db','#4caf50','#e74c3c','#9b59b6','#1abc9c'];
  const datasets = Object.entries(data.year_comparison).map(([year, vals], i) => ({
    label: year,
    data: vals,
    borderColor: palette[i % palette.length],
    backgroundColor: palette[i % palette.length] + '33',
    tension: 0.25,
    fill: false,
  }));
  charts.yearcomp = new Chart(ctx, {
    type: 'line',
    data: { labels: data.months, datasets },
    options: { scales: { y: { beginAtZero: true, ticks: { callback: v => v + ' kWh' } } } },
  });
}

function renderTopFlop(data) {
  const top = document.querySelector('#top-table tbody');
  const flop = document.querySelector('#flop-table tbody');
  top.innerHTML = '';
  flop.innerHTML = '';
  data.top_flop.top.forEach(r => {
    top.insertAdjacentHTML('beforeend', `<tr><td>${r.date}</td><td>${r.kwh.toFixed(2)}</td></tr>`);
  });
  data.top_flop.flop.forEach(r => {
    flop.insertAdjacentHTML('beforeend', `<tr><td>${r.date}</td><td>${r.kwh.toFixed(2)}</td></tr>`);
  });
}

function renderKpis(data) {
  const s = data.summary;
  const delta = s.delta_kwh ?? 0;
  const pct = s.delta_pct;
  const deltaCls = delta >= 0 ? 'good' : 'bad';
  const best = s.best_day ? `${s.best_day.date} · ${s.best_day.kwh.toFixed(2)} kWh` : '—';
  const pctStr = pct === null ? '—' : `${pct.toFixed(1)} %`;
  const spec = s.specific_yield !== null ? `${s.specific_yield} kWh/kWp` : '—';

  const kpis = [
    { label: `Ist YTD ${s.year}`, value: `${s.ytd_actual.toLocaleString('de-DE')} kWh` },
    { label: `Soll YTD ${s.year}`, value: `${s.ytd_target.toLocaleString('de-DE')} kWh` },
    { label: 'Δ absolut', value: `${delta >= 0 ? '+' : ''}${delta.toLocaleString('de-DE')} kWh`, cls: deltaCls },
    { label: 'Δ in %', value: pctStr, cls: deltaCls },
    { label: 'Bester Tag', value: best },
    { label: 'Spez. Ertrag', value: spec },
    { label: 'Erfasste Tage', value: `${s.days_recorded}` },
  ];
  const el = document.getElementById('kpis');
  el.innerHTML = kpis.map(k =>
    `<div class="kpi"><div class="label">${k.label}</div><div class="value ${k.cls || ''}">${k.value}</div></div>`
  ).join('');
}

window.SolarCharts = {
  renderKpis, renderMonthly, renderDeviation, renderCumulative,
  renderDaily, renderHeatmap, renderDistribution, renderYearComparison, renderTopFlop,
};
