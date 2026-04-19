async function loadYear(year) {
  const status = document.getElementById('status');
  status.textContent = 'Lade…';
  const r = await fetch(`/api/summary?year=${year}`);
  if (!r.ok) { status.textContent = 'Fehler beim Laden'; return; }
  const data = await r.json();

  const sel = document.getElementById('year-select');
  if (data.available_years.length) {
    const current = sel.value;
    const opts = ['<option value="all">Gesamt</option>']
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
  SolarCharts.renderTopFlop(data);
  SolarCharts.renderPayback(data);
  status.textContent = '';
}

document.getElementById('year-select').addEventListener('change', (e) => {
  loadYear(e.target.value);
});

loadYear(document.getElementById('year-select').value);
