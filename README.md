# Solar Tracker

<p align="center">
  <img src="docs/logo.svg" alt="Solar Tracker Logo" width="128">
</p>

<p align="center">
  <a href="https://github.com/xenofex7/solar-tracker/releases"><img src="https://img.shields.io/github/v/release/xenofex7/solar-tracker?display_name=tag&sort=semver" alt="latest release"></a>
  <a href="https://github.com/xenofex7/solar-tracker/blob/main/LICENSE"><img src="https://img.shields.io/github/license/xenofex7/solar-tracker" alt="license"></a>
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="python 3.12">
  <a href="https://github.com/xenofex7/solar-tracker/pkgs/container/solar-tracker"><img src="https://img.shields.io/badge/docker-ghcr.io-2496ed?logo=docker&logoColor=white" alt="docker image"></a>
  <a href="https://github.com/xenofex7/solar-tracker/actions/workflows/docker.yml"><img src="https://img.shields.io/github/actions/workflow/status/xenofex7/solar-tracker/docker.yml?branch=main&label=docker%20build" alt="docker build"></a>
  <a href="https://github.com/xenofex7/solar-tracker/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/xenofex7/solar-tracker/ci.yml?branch=main&label=ci" alt="ci"></a>
  <img src="https://img.shields.io/github/last-commit/xenofex7/solar-tracker" alt="last commit">
  <img src="https://img.shields.io/github/commit-activity/y/xenofex7/solar-tracker" alt="commit activity">
</p>

A small, locally-hosted web app that compares **actual** vs. **target** solar
yield. Actuals come from **Home Assistant** (Long-Term Statistics via
WebSocket) or **manual entry**. Targets are monthly kWh goals from the plant
planning.

## Screenshots

<p align="center">
  <img src="docs/screenshots/dashboard-overview-light.png" alt="Dashboard overview" width="800">
</p>
<p align="center">
  <img src="docs/screenshots/dashboard-charts-light.png" alt="Dashboard charts" width="800">
</p>
<p align="center">
  <img src="docs/screenshots/settings-targets-light.png" alt="Monthly targets" width="400">
  <img src="docs/screenshots/settings-production-light.png" alt="Production sync" width="400">
</p>
<p align="center">
  <img src="docs/screenshots/settings-electricity-light.png" alt="Electricity prices" width="400">
  <img src="docs/screenshots/settings-investment-light.png" alt="Investment settings" width="400">
</p>

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # set HA_URL, HA_TOKEN, HA_ENTITY_ID
python seed_demo.py       # optional: demo data so the charts render
python app.py             # opens http://localhost:5000
```

## Security

Solar-Tracker has **no built-in authentication or authorisation**. Anyone who
can reach the HTTP port can read all data and change settings (targets,
electricity prices, investment costs) and trigger Home Assistant syncs.

Only run it on `localhost` or inside a trusted private network. Do **not**
expose the port directly to the internet. If remote access is needed, put it
behind a reverse proxy that enforces authentication (e.g. Caddy/nginx with
basic auth, Authelia, Tailscale, or a VPN).

## Docker

The published image is hosted on GitHub Container Registry and
`docker-compose.yml` references it by default, so no source checkout
is required to deploy:

```bash
mkdir solar-tracker && cd solar-tracker
curl -O https://raw.githubusercontent.com/xenofex7/solar-tracker/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/xenofex7/solar-tracker/main/.env.example
mv .env.example .env      # set HA_URL, HA_TOKEN, HA_ENTITY_ID
docker compose up -d      # pulls ghcr.io/xenofex7/solar-tracker:latest
```

The SQLite database lives in `./data` on the host (mounted into the
container), so stopping or recreating the container preserves all
data. The container runs gunicorn with two workers.

Available tags: `latest`, `1`, `1.0`, `1.0.0` - see
`ghcr.io/xenofex7/solar-tracker`.

If you have the source checked out, `docker compose build` rebuilds
the image locally (the compose file keeps `build: .` as a fallback).

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
Home Assistant keeps indefinitely - unlike the recorder history, which is
purged after `purge_keep_days`. This lets you back-fill and re-sync multiple
years at once.

Expected sensor: an energy sensor with `device_class: energy` and
`state_class: total_increasing` (or `total`), e.g. `sensor.solar_total_energy`.

The sync form on `/settings` defaults to the last six months. Each run
overwrites existing entries for the selected days - including manual ones -
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
