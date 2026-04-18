# Solar-Tracker

Kleine, lokal laufende WebApp zum Vergleichen von **Ist-** und **Soll-Erträgen** einer
Solaranlage. Ist-Daten kommen aus **Home Assistant** (Long-Term Statistics via
WebSocket) oder per **manueller Eingabe**. Sollwerte sind monatliche kWh-Vorgaben
aus der Anlagen-Planung.

## Schnellstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # HA_URL, HA_TOKEN, HA_ENTITY_ID eintragen
python seed_demo.py       # optional: Demo-Daten für die Charts
python app.py             # öffnet http://localhost:5000
```

## Funktionen

- Dashboard mit 9 Visualisierungen:
  1. Monatsvergleich Ist vs. Soll (Balken)
  2. Abweichung in % pro Monat
  3. Kumulativer Jahresertrag vs. Soll-Linie
  4. Tägliche Produktion + 7-Tage-Mittel
  5. Kalender-Heatmap (alle Tage eines Jahres)
  6. Tagesverteilung pro Monat (Min/Median/Max)
  7. Jahresvergleich
  8. Top/Flop 5 Tage
  9. KPI-Kacheln (YTD Ist/Soll, Δ, bester Tag, spezifischer Ertrag)
- Manuelle Tageseingabe (`/entry`)
- Monatliche Sollwerte + Home-Assistant-Sync (`/settings`)

## Home Assistant

Die App verbindet sich per WebSocket zu `HA_URL` und ruft
`recorder/statistics_during_period` mit `period: "day"` und `types: ["change"]`
ab. Damit kommen die Daten aus den **Long-Term Statistics**, die HA – anders
als die Recorder-History – dauerhaft aufbewahrt (nicht nur `purge_keep_days`).
So lassen sich auch mehrere Jahre rückwirkend abgleichen.

Erwartet wird ein Energy-Sensor mit `device_class: energy` und
`state_class: total_increasing` (oder `total`), z. B. `sensor.solar_total_energy`.
Der Sync überschreibt bestehende Einträge für dieselben Tage – auch manuelle.
