async function loadYear(year) {
  const status = document.getElementById('status');
  status.textContent = window.T?.status_loading || 'Loading\u2026';
  const r = await fetch(`/api/summary?year=${year}`);
  if (!r.ok) { status.textContent = window.T?.status_load_error || 'Error loading'; return; }
  const data = await r.json();

  const sel = document.getElementById('year-select');
  if (data.available_years.length) {
    const current = sel.value;
    const allLabel = window.T?.option_all || 'All';
    const opts = [`<option value="all">${allLabel}</option>`]
      .concat(data.available_years.map(y => `<option value="${y}">${y}</option>`));
    sel.innerHTML = opts.join('');
    sel.value = current || String(data.year);
  }

  SolarCharts.renderKpis(data);
  SolarCharts.renderMonthly(data);
  SolarCharts.renderDeviation(data);
  SolarCharts.renderCumulative(data);
  SolarCharts.renderDaily(data);
  SolarCharts.renderHeatmap(data);
  SolarCharts.renderDistribution(data);
  SolarCharts.renderYearComparison(data);
  SolarCharts.renderSpecificYield(data);
  SolarCharts.renderDayQuality(data);
  SolarCharts.renderTopDays(data);
  SolarCharts.renderPayback(data);
  SolarCharts.renderEnergyFlows(data);
  SolarCharts.renderSelfRatio(data);
  SolarCharts.renderFinanceFlow(data);
  status.textContent = '';
}

document.getElementById('year-select').addEventListener('change', (e) => {
  loadYear(e.target.value);
});

let resizeTimer;
let lastWidth = window.innerWidth;
window.addEventListener('resize', () => {
  if (window.innerWidth === lastWidth) return;
  lastWidth = window.innerWidth;
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    loadYear(document.getElementById('year-select').value);
  }, 300);
});

window.addEventListener('themechange', () => {
  loadYear(document.getElementById('year-select').value);
});

loadYear(document.getElementById('year-select').value);
