# Solar Tracker

A small, locally-hosted web app that compares **actual** vs. **target** solar
yield. Actuals come from **Home Assistant** (Long-Term Statistics via
WebSocket) or **manual entry**. Targets are monthly kWh goals from the plant
planning.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # set HA_URL, HA_TOKEN, HA_ENTITY_ID
python seed_demo.py       # optional: demo data so the charts render
python app.py             # opens http://localhost:5000
```

## Docker

```bash
cp .env.example .env      # set HA_URL, HA_TOKEN, HA_ENTITY_ID
docker compose up -d      # builds and starts on http://localhost:5000
```

The SQLite database lives in `./data` on the host (mounted into the
container), so stopping or rebuilding the container preserves all data.
The container runs gunicorn with two workers.

Pre-built multi-arch images are published to GitHub Container Registry
on every push to `main` and every `v*` tag:

```bash
docker pull ghcr.io/xenofex7/solar-tracker:latest
docker pull ghcr.io/xenofex7/solar-tracker:1.0.0
```

To run the published image, replace the `build: .` line in
`docker-compose.yml` with `image: ghcr.io/xenofex7/solar-tracker:latest`.

## Features

- Dashboard with nine visualisations:
  1. Monthly actual vs. target (bars)
  2. Deviation in % per month
  3. Cumulative yearly yield vs. target line
  4. Daily production + 7-day rolling average
  5. Calendar heatmap (every day of the year)
  6. Daily distribution per month (min/median/max)
  7. Year-over-year comparison
  8. Top / bottom 5 days
  9. KPI tiles (YTD actual/target, Δ, best day, specific yield)
- Manual daily entry (`/entry`)
- Monthly targets + Home Assistant sync (`/settings`)
- Dates as `dd.mm.yyyy`, Swiss thousands (`1'234 kWh`)
- "Today" marker on daily and cumulative charts (current year only)
- YTD target is pro-rated to today for the current year

## Home Assistant

The app connects to `HA_URL` via WebSocket and calls
`recorder/statistics_during_period` with `period: "day"` and
`types: ["change"]`. Data therefore comes from **Long-Term Statistics**, which
Home Assistant keeps indefinitely — unlike the recorder history, which is
purged after `purge_keep_days`. This lets you back-fill and re-sync multiple
years at once.

Expected sensor: an energy sensor with `device_class: energy` and
`state_class: total_increasing` (or `total`), e.g. `sensor.solar_total_energy`.

The sync form on `/settings` defaults to the last six months. Each run
overwrites existing entries for the selected days — including manual ones —
so the database stays in sync with Home Assistant.

## Configuration

`.env` keys:

| Key             | Purpose                                                    |
| --------------- | ---------------------------------------------------------- |
| `HA_URL`        | Base URL of Home Assistant (e.g. `http://ha.local:8123`)   |
| `HA_TOKEN`      | Long-Lived Access Token                                    |
| `HA_ENTITY_ID`  | Statistic entity (e.g. `sensor.solar_total_energy`)        |
| `PLANT_KWP`     | Installed peak power, used for specific yield (kWh/kWp)    |
| `FLASK_PORT`    | HTTP port (default `5000`)                                 |
| `FLASK_DEBUG`   | `true` enables Flask debug mode                            |

The plant size can also be set on `/settings`, which overrides `PLANT_KWP`.
