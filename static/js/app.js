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
  SolarCharts.renderSavingsVsNoPv(data);
  status.textContent = '';
}

document.getElementById('year-select').addEventListener('change', (e) => {
  loadYear(e.target.value);
});


window.addEventListener('themechange', () => {
  loadYear(document.getElementById('year-select').value);
});

document.addEventListener('click', (e) => {
  const btn = e.target.closest('.kpi-info');
  document.querySelectorAll('.kpi-popover[data-open]').forEach(pop => {
    if (btn && pop.parentElement.contains(btn)) return;
    pop.removeAttribute('data-open');
    pop.parentElement.querySelector('.kpi-info')?.setAttribute('aria-expanded', 'false');
  });
  if (!btn) return;
  const pop = btn.parentElement.querySelector('.kpi-popover');
  if (!pop) return;
  const isOpen = pop.hasAttribute('data-open');
  if (isOpen) {
    pop.removeAttribute('data-open');
    pop.classList.remove('flip-left');
    btn.setAttribute('aria-expanded', 'false');
  } else {
    pop.setAttribute('data-open', '');
    btn.setAttribute('aria-expanded', 'true');
    pop.classList.remove('flip-left');
    const r = pop.getBoundingClientRect();
    if (r.right > window.innerWidth - 8) pop.classList.add('flip-left');
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.kpi-popover[data-open]').forEach(pop => {
      pop.removeAttribute('data-open');
      pop.parentElement.querySelector('.kpi-info')?.setAttribute('aria-expanded', 'false');
    });
  }
});

loadYear(document.getElementById('year-select').value);
