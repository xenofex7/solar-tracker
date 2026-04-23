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
  emptyCell: 'rgba(255,255,255,0.04)',
  heatmapText: 'rgba(255,255,255,0.92)',
};

function refreshChartTheme() {
  const cs = getComputedStyle(document.documentElement);
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const text = cs.getPropertyValue('--text').trim() || CHART_COLORS.text;
  const muted = cs.getPropertyValue('--muted').trim() || CHART_COLORS.muted;
  CHART_COLORS.text = text;
  CHART_COLORS.muted = muted;
  CHART_COLORS.grid = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)';
  CHART_COLORS.emptyCell = isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)';
  CHART_COLORS.heatmapText = isLight ? 'rgba(26,32,41,0.95)' : 'rgba(255,255,255,0.92)';
  Chart.defaults.color = CHART_COLORS.text;
  Chart.defaults.borderColor = CHART_COLORS.grid;
}

refreshChartTheme();
Chart.defaults.font.family = '-apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif';

window.addEventListener('themechange', () => {
  refreshChartTheme();
  Object.values(charts).forEach(c => { try { c.update(); } catch (e) {} });
});

const fmtInt = (v) => Math.round(Number(v) || 0).toLocaleString(window.T?.locale || 'de-CH');
const fmtKwh = (v) => `${fmtInt(v)} kWh`;
const fmtChf = (v) => `${fmtInt(v)} CHF`;
const fmtDate = (iso) => {
  if (!iso) return '';
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : iso;
};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const charts = {};

function destroy(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

const todayIso = () => {
  const d = new Date();
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d - tz).toISOString().slice(0, 10);
};

const todayMarker = (xIndex) => ({
  id: 'todayMarker',
  afterDatasetsDraw(chart) {
    if (xIndex == null || xIndex < 0) return;
    const { ctx, chartArea, scales: { x } } = chart;
    const px = x.getPixelForValue(xIndex);
    if (px < chartArea.left - 1 || px > chartArea.right + 1) return;
    ctx.save();
    ctx.strokeStyle = CHART_COLORS.muted;
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(px, chartArea.top);
    ctx.lineTo(px, chartArea.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = CHART_COLORS.text;
    ctx.font = '11px -apple-system, Segoe UI, Roboto, sans-serif';
    const label = window.T?.label_today || 'today';
    const tw = ctx.measureText(label).width;
    const lx = Math.min(px + 4, chartArea.right - tw - 2);
    ctx.fillText(label, lx, chartArea.top + 12);
    ctx.restore();
  },
});

function localizeMonths(months) {
  const names = window.T?.months_short;
  if (!names) return months;
  return months.map(m => names[m - 1] || m);
}

function renderMonthly(data) {
  destroy('monthly');
  const ctx = document.getElementById('chart-monthly');
  charts.monthly = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: localizeMonths(data.months),
      datasets: [
        { label: window.T?.chart_actual_kwh || 'Actual (kWh)',  data: data.monthly_actual,  backgroundColor: CHART_COLORS.actual },
        { label: window.T?.chart_target_kwh || 'Target (kWh)', data: data.monthly_target, backgroundColor: CHART_COLORS.target },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { beginAtZero: true, ticks: { callback: v => fmtKwh(v) } } },
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
      labels: localizeMonths(data.months),
      datasets: [{ label: window.T?.chart_deviation_pct || 'Deviation %', data: data.deviation_pct.map(v => v ?? 0), backgroundColor: colors }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { callback: v => `${v} %` } } },
    },
  });
}

function renderCumulative(data) {
  destroy('cumulative');
  const ctx = document.getElementById('chart-cumulative');
  const now = new Date();
  const monthIdx = (typeof data.year === 'number' && data.year === now.getFullYear())
    ? now.getMonth() + (now.getDate() - 1) / 30
    : null;
  charts.cumulative = new Chart(ctx, {
    type: 'line',
    data: {
      labels: localizeMonths(data.months),
      datasets: [
        { label: window.T?.chart_cumulative_actual || 'Actual cumul.',  data: data.cumulative_actual, borderColor: CHART_COLORS.actualLine, backgroundColor: 'rgba(245,166,35,0.15)', fill: true, tension: 0.2 },
        { label: window.T?.chart_cumulative_target || 'Target cumul.', data: data.cumulative_target, borderColor: CHART_COLORS.targetLine, borderDash: [6,4], fill: false, tension: 0.2 },
      ],
    },
    options: { scales: { y: { beginAtZero: true, ticks: { callback: v => fmtKwh(v) } } } },
    plugins: monthIdx !== null ? [todayMarker(monthIdx)] : [],
  });
}

function renderDaily(data) {
  destroy('daily');
  const ctx = document.getElementById('chart-daily');
  const labels = data.daily.map(d => d.date);
  const values = data.daily.map(d => d.kwh);
  const t = todayIso();
  const isCurrentYear = typeof data.year === 'number' && data.year === new Date().getFullYear();
  let todayIdx = labels.indexOf(t);
  if (todayIdx < 0 && isCurrentYear && labels.length) {
    todayIdx = labels.findIndex(l => l > t);
    if (todayIdx < 0) todayIdx = labels.length - 1;
  }
  charts.daily = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: window.T?.chart_daily_value || 'Daily value', data: values, borderColor: CHART_COLORS.actualLine, backgroundColor: 'rgba(245,166,35,0.15)', pointRadius: 1.5, fill: true, tension: 0.1 },
        { label: window.T?.chart_7d_avg || '7-day avg', data: data.rolling_avg_7d, borderColor: CHART_COLORS.targetLine, pointRadius: 0, borderWidth: 2, fill: false, tension: 0.2 },
      ],
    },
    options: {
      plugins: {
        tooltip: { callbacks: {
          title: items => fmtDate(items[0].label),
          label: item => `${item.dataset.label}: ${fmtKwh(item.parsed.y)}`,
        } },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 12, callback(v) { return fmtDate(this.getLabelForValue(v)); } } },
        y: { beginAtZero: true, ticks: { callback: v => fmtKwh(v) } },
      },
    },
    plugins: (todayIdx >= 0 && isCurrentYear) ? [todayMarker(todayIdx)] : [],
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

  const weekdays = window.T?.weekdays_short || ['Mo','Tu','We','Th','Fr','Sa','Su'];

  charts.heatmap = new Chart(ctx, {
    type: 'matrix',
    data: {
      datasets: [{
        label: window.T?.chart_daily_kwh || 'Daily kWh',
        data: points,
        backgroundColor(ctx) {
          const v = ctx.dataset.data[ctx.dataIndex].v;
          if (!v) return CHART_COLORS.emptyCell;
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
        tooltip: { callbacks: { title: items => fmtDate(items[0].raw.date), label: item => fmtKwh(item.raw.v) } },
      },
      scales: {
        x: { type: 'linear', min: -0.5, max: 53.5, display: false, grid: { display: false } },
        y: {
          type: 'linear',
          min: -0.5,
          max: 6.5,
          reverse: true,
          ticks: {
            stepSize: 1,
            autoSkip: false,
            callback: v => weekdays[Math.round(v)] ?? '',
          },
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
      labels: localizeMonths(data.months),
      datasets: [
        { label: window.T?.label_min || 'Min',    data: mins,    backgroundColor: 'rgba(52,152,219,0.6)' },
        { label: window.T?.label_median || 'Median', data: medians, backgroundColor: 'rgba(245,166,35,0.85)' },
        { label: window.T?.label_max || 'Max',    data: maxs,    backgroundColor: 'rgba(76,175,80,0.75)' },
      ],
    },
    options: { scales: { y: { beginAtZero: true, ticks: { callback: v => fmtKwh(v) } } } },
  });
}

function renderYearComparison(data) {
  destroy('yearcomp');
  const ctx = document.getElementById('chart-yearcomp');
  const sortedYears = Object.keys(data.year_comparison).sort();
  const currentYear = String(new Date().getFullYear());
  const ordered = [...sortedYears.filter(y => y !== currentYear), currentYear].filter(y => sortedYears.includes(y));
  const currentMonth = new Date().getMonth(); // 0-based
  const datasets = ordered.map((year, i) => {
    const isCurrent = year === currentYear;
    const color = isCurrent ? CHART_COLORS.actualLine : CHART_COLORS.targetLine;
    const vals = data.year_comparison[year];
    const firstNonZero = vals.findIndex(v => v > 0);
    const chartData = vals.map((v, mi) => {
      if (firstNonZero >= 0 && mi < firstNonZero) return null;
      if (isCurrent && mi > currentMonth) return null;
      return v;
    });
    return {
      label: year,
      data: chartData,
      borderColor: color,
      backgroundColor: color + (isCurrent ? '22' : '18'),
      borderWidth: isCurrent ? 2.5 : 1.5,
      tension: 0.25,
      fill: false,
      order: isCurrent ? 0 : ordered.length - i,
    };
  });
  charts.yearcomp = new Chart(ctx, {
    type: 'line',
    data: { labels: localizeMonths(data.months), datasets },
    options: { scales: { y: { beginAtZero: true, ticks: { callback: v => fmtKwh(v) } } } },
  });
}

function renderTopDays(data) {
  const top = document.querySelector('#top-table tbody');
  if (!top) return;
  top.innerHTML = '';
  (data.top_days || []).forEach(r => {
    top.insertAdjacentHTML('beforeend', `<tr><td>${fmtDate(r.date)}</td><td>${fmtKwh(r.kwh)}</td></tr>`);
  });
}

function renderDayQuality(data) {
  destroy('day-quality');
  const ctx = document.getElementById('chart-day-quality');
  if (!ctx) return;
  const dist = data.day_quality;
  const buckets = dist?.buckets || [];
  if (!buckets.length) {
    _hideIfEmpty(ctx, false);
    return;
  }
  _hideIfEmpty(ctx, true);

  const colors = ['#e74c3c', '#e67e22', '#f39c12', '#2ecc71', '#27ae60', '#1a6b3a'];
  const labels = buckets.map(b => b.label);
  const counts = buckets.map(b => b.count);
  const total = counts.reduce((s, c) => s + c, 0);

  const centerText = {
    id: 'centerText',
    beforeDraw(chart) {
      const { chartArea, ctx: c } = chart;
      c.save();
      const cx = (chartArea.left + chartArea.right) / 2;
      const cy = (chartArea.top + chartArea.bottom) / 2;
      c.textAlign = 'center';
      c.textBaseline = 'middle';
      c.font = `bold 22px -apple-system, Segoe UI, Roboto, sans-serif`;
      c.fillStyle = CHART_COLORS.text;
      c.fillText(total, cx, cy - 10);
      c.font = `12px -apple-system, Segoe UI, Roboto, sans-serif`;
      c.fillStyle = CHART_COLORS.muted;
      c.fillText(window.T?.label_days || 'days', cx, cy + 10);
      c.restore();
    },
  };

  const segmentLabels = {
    id: 'segmentLabels',
    afterDatasetsDraw(chart) {
      const { ctx: c, data: d } = chart;
      const meta = chart.getDatasetMeta(0);
      const dataset = d.datasets[0].data;
      const sum = dataset.reduce((a, b) => a + b, 0);
      c.save();
      c.textAlign = 'center';
      c.textBaseline = 'middle';
      meta.data.forEach((arc, i) => {
        const pct = sum > 0 ? dataset[i] / sum : 0;
        if (pct < 0.04) return;
        const midAngle = arc.startAngle + (arc.endAngle - arc.startAngle) / 2;
        const r = (arc.innerRadius + arc.outerRadius) / 2;
        const x = arc.x + Math.cos(midAngle) * r;
        const y = arc.y + Math.sin(midAngle) * r;
        c.font = `bold 11px -apple-system, Segoe UI, Roboto, sans-serif`;
        c.fillStyle = CHART_COLORS.heatmapText;
        c.fillText(`${Math.round(pct * 100)} %`, x, y);
      });
      c.restore();
    },
  };

  charts['day-quality'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: counts, backgroundColor: colors, borderColor: 'rgba(0,0,0,0.25)', borderWidth: 1 }],
    },
    options: {
      cutout: '52%',
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 14, font: { size: 11 } } },
        tooltip: { callbacks: { label: item => `${item.label}: ${item.parsed} ${window.T?.label_days || 'days'}` } },
      },
    },
    plugins: [centerText, segmentLabels],
  });
}

function renderKpis(data) {
  const T = window.T || {};
  const s = data.summary;
  const delta = s.delta_kwh ?? 0;
  const pct = s.delta_pct;
  const deltaCls = delta >= 0 ? 'good' : 'bad';
  const best = s.best_day ? `${fmtDate(s.best_day.date)}<br><span class="sub">${fmtKwh(s.best_day.kwh)}</span>` : '-';
  const pctStr = pct === null ? '-' : `${pct.toLocaleString(T.locale || 'de-CH', {maximumFractionDigits: 1})} %`;
  const spec = s.specific_yield !== null ? `${fmtInt(s.specific_yield)} kWh/kWp` : '-';

  const scopeLabel = s.year === 'all' ? (T.label_total || 'total') : `YTD ${s.year}`;
  const production = [
    { label: `${T.kpi_actual || 'Actual'} ${scopeLabel}`, value: fmtKwh(s.ytd_actual) },
    { label: `${T.kpi_target || 'Target'} ${scopeLabel}`, value: fmtKwh(s.ytd_target) },
    { label: T.kpi_delta_abs || 'Δ absolute', value: `${delta >= 0 ? '+' : '-'}${fmtKwh(Math.abs(delta))}`, cls: deltaCls },
    { label: T.kpi_delta_pct || 'Δ in %', value: pctStr, cls: deltaCls },
    { label: T.kpi_best_day || 'Best day', value: best },
    { label: T.kpi_specific_yield || 'Spec. yield', value: spec },
    { label: T.kpi_days_recorded || 'Days recorded', value: fmtInt(s.days_recorded) },
  ];

  const finance = [];
  const fin = data.finance;
  if (fin && fin.payback && fin.payback.invested > 0) {
    const p = fin.payback;
    const remainingStr = (iso) => {
      if (!iso) return '';
      const target = new Date(iso);
      const now = new Date();
      if (target <= now) return T.kpi_payback_reached || 'reached';
      let months = (target.getFullYear() - now.getFullYear()) * 12 + (target.getMonth() - now.getMonth());
      if (target.getDate() < now.getDate()) months -= 1;
      if (months < 0) months = 0;
      const y = Math.floor(months / 12);
      const m = months % 12;
      const fmt = (tpl, vars) => tpl.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
      if (y === 0) return fmt(T.kpi_remaining_months || '{m} mo. left', { m });
      if (m === 0) return fmt(T.kpi_remaining_years || '{y} yr. left', { y });
      return fmt(T.kpi_remaining_years_months || '{y} yr. {m} mo. left', { y, m });
    };
    const basisLabel = p.projection_basis === 'targets'
      ? (T.kpi_basis_targets || 'Annual target')
      : (T.kpi_basis_history || 'History');
    const paybackVal = p.payback_date
      ? `${fmtDate(p.payback_date)}<br><span class="sub">${remainingStr(p.payback_date)} · ${basisLabel}</span>`
      : '-';
    const progressCls = p.progress_pct >= 100 ? 'good' : '';
    const b = p.breakdown || {};
    const parts = [];
    if (b.self_consumption_savings > 0) parts.push(`${T.kpi_breakdown_self || 'SC'} ${fmtChf(b.self_consumption_savings)}`);
    if (b.export_credit > 0) parts.push(`${T.kpi_breakdown_export || 'Exp.'} ${fmtChf(b.export_credit)}`);
    if (b.estimated_other > 0) parts.push(`${T.kpi_breakdown_estimated || 'est.'} ${fmtChf(b.estimated_other)}`);
    const revSub = parts.length ? `<br><span class="sub">${parts.join(' · ')}</span>` : '';
    finance.push(
      { label: T.kpi_investment || 'Investment', value: fmtChf(p.invested) },
      { label: T.kpi_revenue_total || 'Revenue to date', value: `${fmtChf(p.revenue_total)}${revSub}` },
      { label: T.kpi_progress || 'Progress', value: `${p.progress_pct.toLocaleString(T.locale || 'de-CH', {maximumFractionDigits: 1})} %`, cls: progressCls },
      { label: T.kpi_payback || 'Payback', value: paybackVal },
    );
  }

  const energy = [];
  const grid = data.grid;
  if (grid && grid.totals && (grid.totals['import'].amount > 0 || grid.totals['export'].amount > 0)) {
    const sc = grid.self_consumption || {};
    const net = grid.totals.net_cost || 0;
    const scPct = sc.self_consumption_pct ?? 0;
    const pctCls = scPct >= 30 ? 'good' : '';
    energy.push(
      { label: T.kpi_net_cost || 'Net electricity cost', value: fmtChf(net) },
      { label: T.kpi_self_consumed || 'Self-consumed', value: fmtKwh(sc.self_consumed_kwh ?? 0) },
      { label: T.kpi_self_ratio || 'Self-cons. rate', value: `${scPct.toLocaleString(T.locale || 'de-CH', {maximumFractionDigits: 1})} %`, cls: pctCls },
    );
  }

  const groups = [
    { title: T.kpi_group_production || 'Production', kpis: production },
    { title: T.kpi_group_finance || 'Finances', kpis: finance },
    { title: T.kpi_group_energy || 'Self-consumption & Grid', kpis: energy },
  ].filter(g => g.kpis.length);

  const el = document.getElementById('kpis');
  el.innerHTML = groups.map(g =>
    `<div class="kpi-group"><h3>${esc(g.title)}</h3><div class="kpis">${g.kpis.map(k =>
      `<div class="kpi"><div class="label">${esc(k.label)}</div><div class="value ${esc(k.cls || '')}">${k.value}</div></div>`
    ).join('')}</div></div>`
  ).join('');
}

function renderPayback(data) {
  destroy('payback');
  const ctx = document.getElementById('chart-payback');
  if (!ctx) return;
  const fin = data.finance;
  const invested = fin?.payback?.invested || 0;
  const series = fin?.cumulative_revenue || [];
  if (invested <= 0 || !series.length) {
    _hideIfEmpty(ctx, false);
    return;
  }
  _hideIfEmpty(ctx, true);

  // Cumulative revenue per year-end
  const cumByYear = {};
  series.forEach(r => { cumByYear[r.date.slice(0, 4)] = r.revenue; });
  const actualYears = Object.keys(cumByYear).sort();
  const lastCum = cumByYear[actualYears[actualYears.length - 1]] || 0;

  // Build forecast years: cumulative from last actual until investment recovered
  const yearlyEst = fin.payback?.yearly_yield_estimate || 0;
  const forecastByYear = {};
  if (yearlyEst > 0 && fin.payback?.remaining > 0) {
    let cum = lastCum;
    let y = parseInt(actualYears[actualYears.length - 1]) + 1;
    while (cum < invested && y < 2080) {
      cum = Math.min(cum + yearlyEst, invested);
      forecastByYear[String(y)] = cum;
      y++;
    }
  }

  const allYears = [...new Set([...actualYears, ...Object.keys(forecastByYear)])].sort();
  const actualData   = allYears.map(y => cumByYear[y]     ?? null);
  const forecastData = allYears.map(y => forecastByYear[y] ?? null);
  const investedLine = allYears.map(() => invested);

  charts.payback = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: allYears,
      datasets: [
        {
          label: window.T?.chart_cumulative_revenue || 'Revenue (CHF)',
          data: actualData,
          backgroundColor: CHART_COLORS.actual,
          order: 2,
        },
        {
          label: 'Forecast (CHF)',
          data: forecastData,
          backgroundColor: 'rgba(245,166,35,0.28)',
          borderColor: CHART_COLORS.actualLine,
          borderWidth: 1,
          order: 2,
        },
        {
          type: 'line',
          label: window.T?.chart_investment || 'Investment (CHF)',
          data: investedLine,
          borderColor: CHART_COLORS.targetLine,
          borderDash: [6, 4],
          pointRadius: 0,
          fill: false,
          order: 1,
        },
      ],
    },
    options: {
      plugins: {
        tooltip: { callbacks: { label: item => `${item.dataset.label}: ${fmtChf(item.parsed.y)}` } },
      },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => fmtChf(v) } },
      },
    },
  });
}

function _hideIfEmpty(ctx, show) {
  if (!ctx) return false;
  const card = ctx.closest('.card');
  if (card) card.style.display = show ? '' : 'none';
  return show;
}

function renderEnergyFlows(data) {
  destroy('energy-flows');
  const ctx = document.getElementById('chart-energy-flows');
  const periods = data.grid?.periods || [];
  if (!_hideIfEmpty(ctx, periods.length > 0)) return;
  const labels = periods.map(p => p.label);
  charts['energy-flows'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: window.T?.chart_self_consumption || 'Self-consumption', data: periods.map(p => p.self_consumed_kwh), backgroundColor: CHART_COLORS.actual, stack: 'pv' },
        { label: window.T?.chart_export || 'Grid export', data: periods.map(p => p.exported_kwh), backgroundColor: CHART_COLORS.good, stack: 'pv' },
        { label: window.T?.chart_import || 'Grid import', data: periods.map(p => p.imported_kwh), backgroundColor: 'rgba(52,152,219,0.75)', stack: 'grid' },
      ],
    },
    options: {
      plugins: {
        tooltip: { callbacks: { label: item => `${item.dataset.label}: ${fmtKwh(item.parsed.y)}` } },
      },
      scales: {
        x: { stacked: true },
        y: { stacked: true, beginAtZero: true, ticks: { callback: v => fmtKwh(v) } },
      },
    },
  });
}

function renderSelfRatio(data) {
  destroy('self-ratio');
  const ctx = document.getElementById('chart-self-ratio');
  const periods = data.grid?.periods || [];
  if (!_hideIfEmpty(ctx, periods.length > 0)) return;
  const labels = periods.map(p => p.label);
  const values = periods.map(p => p.self_consumption_pct);
  charts['self-ratio'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: window.T?.chart_self_ratio || 'Self-consumption rate', data: values,
        borderColor: CHART_COLORS.actualLine,
        backgroundColor: 'rgba(245,166,35,0.18)',
        fill: true, tension: 0.25, pointRadius: 4,
      }],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: item => `${item.parsed.y.toLocaleString(window.T?.locale || 'de-CH', {maximumFractionDigits: 1})} %` } },
      },
      scales: { y: { beginAtZero: true, suggestedMax: 100, ticks: { callback: v => `${v} %` } } },
    },
  });
}

function renderFinanceFlow(data) {
  destroy('finance-flow');
  const ctx = document.getElementById('chart-finance-flow');
  const periods = data.grid?.periods || [];
  if (!_hideIfEmpty(ctx, periods.length > 0)) return;
  const labels = periods.map(p => p.label);
  charts['finance-flow'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: window.T?.chart_import_costs || 'Import costs', data: periods.map(p => -p.import_cost), backgroundColor: 'rgba(231,76,60,0.8)' },
        { label: window.T?.chart_self_consumption_saved || 'Self-consumption saved', data: periods.map(p => p.self_consumption_savings), backgroundColor: CHART_COLORS.actual },
        { label: window.T?.chart_export || 'Grid export', data: periods.map(p => p.export_credit), backgroundColor: CHART_COLORS.good },
      ],
    },
    options: {
      plugins: {
        tooltip: { callbacks: { label: item => `${item.dataset.label}: ${fmtChf(Math.abs(item.parsed.y))}` } },
      },
      scales: {
        x: { stacked: true },
        y: { stacked: true, ticks: { callback: v => fmtChf(v) } },
      },
    },
  });
}

function renderSpecificYield(data) {
  destroy('spec-yield');
  const ctx = document.getElementById('chart-spec-yield');
  if (!ctx) return;
  const cmp = data.specific_yield_comparison;
  if (!cmp || !Object.keys(cmp).length) { _hideIfEmpty(ctx, false); return; }
  _hideIfEmpty(ctx, true);

  const sortedYears = Object.keys(cmp).sort();
  const currentYear = String(new Date().getFullYear());
  const currentMonth = new Date().getMonth();
  const ordered = [...sortedYears.filter(y => y !== currentYear), currentYear].filter(y => sortedYears.includes(y));

  const datasets = ordered.map((year, i) => {
    const isCurrent = year === currentYear;
    const color = isCurrent ? CHART_COLORS.actualLine : CHART_COLORS.targetLine;
    const vals = cmp[year];
    const firstNonZero = vals.findIndex(v => v > 0);
    const chartData = vals.map((v, mi) => {
      if (firstNonZero >= 0 && mi < firstNonZero) return null;
      if (isCurrent && mi > currentMonth) return null;
      return v || null;
    });
    return {
      label: year,
      data: chartData,
      borderColor: color,
      backgroundColor: color + (isCurrent ? '22' : '18'),
      borderWidth: isCurrent ? 2.5 : 1.5,
      tension: 0.25,
      fill: false,
      order: isCurrent ? 0 : ordered.length - i,
    };
  });

  charts['spec-yield'] = new Chart(ctx, {
    type: 'line',
    data: { labels: localizeMonths(data.months), datasets },
    options: {
      plugins: {
        tooltip: { callbacks: { label: item => `${item.dataset.label}: ${item.parsed.y} kWh/kWp` } },
      },
      scales: { y: { beginAtZero: true, ticks: { callback: v => `${v} kWh/kWp` } } },
    },
  });
}

window.SolarCharts = {
  renderKpis, renderMonthly, renderDeviation, renderCumulative,
  renderDaily, renderHeatmap, renderDistribution, renderYearComparison,
  renderTopDays, renderDayQuality, renderSpecificYield,
  renderPayback, renderEnergyFlows, renderSelfRatio, renderFinanceFlow,
};
