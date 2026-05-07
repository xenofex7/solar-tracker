# Solar-Tracker

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo_dark.png">
    <img src="assets/logo_bright.png" alt="Solar-Tracker logo" width="160">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/xenofex7/solar-tracker/tags"><img src="https://img.shields.io/github/v/tag/xenofex7/solar-tracker?sort=semver&label=version" alt="latest tag"></a>
  <a href="https://github.com/xenofex7/solar-tracker/blob/main/LICENSE"><img src="https://img.shields.io/github/license/xenofex7/solar-tracker" alt="license"></a>
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="python 3.12">
  <a href="https://github.com/xenofex7/solar-tracker/pkgs/container/solar-tracker"><img src="https://img.shields.io/badge/docker-ghcr.io-2496ed?logo=docker&logoColor=white" alt="docker image"></a>
  <a href="https://github.com/xenofex7/solar-tracker/actions/workflows/docker.yml"><img src="https://img.shields.io/github/actions/workflow/status/xenofex7/solar-tracker/docker.yml?branch=main&label=docker%20build" alt="docker build"></a>
  <a href="https://github.com/xenofex7/solar-tracker/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/xenofex7/solar-tracker/ci.yml?branch=main&label=ci" alt="ci"></a>
  <img src="https://img.shields.io/github/last-commit/xenofex7/solar-tracker" alt="last commit">
  <img src="https://img.shields.io/github/commit-activity/y/xenofex7/solar-tracker" alt="commit activity">
</p>

<p align="center">
  <a href="https://xenofex7.github.io/solar-tracker/"><strong>xenofex7.github.io/solar-tracker</strong></a>
</p>

A small, locally-hosted web app that compares **actual** vs. **target** solar
yield. Actuals come from **Home Assistant** (Long-Term Statistics via
WebSocket), **Fronius Solar.web** (cloud API, Premium account), or **manual
entry**. Targets are monthly kWh goals from the plant planning.

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

Solar-Tracker ships with a built-in account system (since v2.1) but stays
zero-config: a fresh install seeds a single `admin` user without a password
and auto-logs in just like the old behavior. As soon as you set a password
on `admin` (or add a second user) under **Settings -> Users**, the login
screen kicks in and auto-login is disabled.

Two roles are supported:

- **admin** - full access to the dashboard, settings, and write APIs.
- **readonly** - dashboard and `GET /api/*` only; no settings, no writes.

Read-only users can also call the JSON API via HTTP Basic Auth, e.g.
`curl -u viewer:pw https://solar.example/api/summary?year=2025`.

Passwords are hashed with PBKDF2-HMAC-SHA256 (200k iterations) and the
session secret is read from `FLASK_SECRET_KEY` or auto-generated on first
run. Set `SESSION_COOKIE_SECURE=true` when serving over HTTPS.

If you expose the port to the internet, still put it behind a TLS-terminating
reverse proxy (Caddy/nginx, Tailscale, or a VPN). Defense in depth.

### Recovery / lockout

If you forget the admin password, use the bundled CLI from the project root:

```bash
.venv/bin/python -m scripts.manage_users list
.venv/bin/python -m scripts.manage_users set-password admin           # prompts
.venv/bin/python -m scripts.manage_users reset-admin                  # nuke + reseed passwordless admin (auto-login)
.venv/bin/python -m scripts.manage_users reset-admin --password hunter2
```

Inside Docker, exec into the container:

```bash
docker compose exec solar-tracker python -m scripts.manage_users list
```

More recipes (backup, upgrade, telemetry, logs, factory reset) live in
[`docs/COOKBOOK.md`](docs/COOKBOOK.md).

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

Available tags: `latest`, plus pinned major / minor / patch tags
(e.g. `1`, `1.8`, `1.8.0`). See
[ghcr.io/xenofex7/solar-tracker](https://github.com/xenofex7/solar-tracker/pkgs/container/solar-tracker).

If you have the source checked out, `docker compose build` rebuilds
the image locally (the compose file keeps `build: .` as a fallback).

## Features

### Dashboard

- 14 charts including monthly actual vs. target, deviation in %,
  cumulative yearly yield, daily production with 7-day rolling average,
  calendar heatmap, daily distribution per month (min/median/max),
  year-on-year comparison, top 5 days, specific yield (kWh/kWp) and
  day quality donut.
- Payback chart with cumulative revenue vs. investment and forecast.
- Energy and finance flow charts per billing period (import, export,
  self-consumption, savings vs. no PV).
- KPI tiles in three groups:
  - **Production:** YTD actual / target, Δ absolute / %, best day,
    specific yield, days recorded.
  - **Finances:** investment, revenue to date, progress, payback date.
  - **Self-consumption & grid:** net cost, savings vs. no PV, effective
    electricity price, self-consumed, self-consumption rate.

### Data sources

- Home Assistant (Long-Term Statistics via WebSocket).
- Fronius Solar.web (cloud API, Premium account required).
- Manual daily entry on `/entry`.
- Quarterly grid bills (import + export) on `/settings`.

### Other

- 5 languages (DE, EN, FR, IT, ES), light + dark mode.
- Dates as `dd.mm.yyyy`, Swiss thousands (`1'234 kWh`).
- "Today" marker on daily and cumulative charts (current year only).
- YTD target is pro-rated to today for the current year.

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

## Fronius Solar.web

As an alternative to Home Assistant, Solar-Tracker can pull daily PV
production directly from the Fronius Solar.web cloud API. This requires a
**Solar.web Premium** subscription and an API access key pair, which you
generate in your Solar.web account under API access.

Configure `SOLARWEB_ACCESS_KEY_ID` and `SOLARWEB_ACCESS_KEY_VALUE` in `.env`.
`SOLARWEB_PV_SYSTEM_ID` is optional - if exactly one PV system is linked to
the account it is auto-resolved on first use.

In **Settings -> Datensynchronisation**, pick "Fronius Solar.web" as the data
source. The dashboard auto-sync and the manual sync button will then both
pull from Solar.web instead of Home Assistant. Sources without credentials
are listed but greyed out.

For manual or cron-based syncs:

```bash
.venv/bin/python -m scripts.sync_solarweb --days 30
.venv/bin/python -m scripts.sync_solarweb --from 2026-01-01 --to 2026-04-30
.venv/bin/python -m scripts.sync_solarweb --list-systems
```

The HTTP endpoint is `POST /api/sync/solarweb` (admin-only).

## Configuration

`.env` keys:

| Key             | Purpose                                                    |
| --------------- | ---------------------------------------------------------- |
| `HA_URL`        | Base URL of Home Assistant (e.g. `http://ha.local:8123`)   |
| `HA_TOKEN`      | Long-Lived Access Token                                    |
| `HA_ENTITY_ID`  | Statistic entity (e.g. `sensor.solar_total_energy`)        |
| `SOLARWEB_ACCESS_KEY_ID`    | Fronius Solar.web API access key ID (Premium)  |
| `SOLARWEB_ACCESS_KEY_VALUE` | Fronius Solar.web API access key secret        |
| `SOLARWEB_PV_SYSTEM_ID`     | Optional; auto-resolved if account has exactly one system |
| `PLANT_KWP`     | Installed peak power, used for specific yield (kWh/kWp)    |
| `FLASK_HOST`    | Bind address (default `127.0.0.1`, set `0.0.0.0` in Docker) |
| `FLASK_PORT`    | HTTP port (default `5000`)                                 |
| `FLASK_DEBUG`   | `true` enables Flask debug mode                            |
| `TELEMETRY_ENABLED` | `false` opts out of anonymous instance telemetry      |

The plant size can also be set on `/settings`, which overrides `PLANT_KWP`.

## Telemetry

Solar-Tracker sends one anonymous heartbeat per day so I can see how many
instances are running and which versions are in the wild. The payload is:

- a random `instance_id` (UUID generated on first start, persisted in `data/telemetry.json`)
- the app `version`
- the Python version

No user data, no IP, no Home Assistant values, no request tracking. Events are
sent to a privately-hosted Umami instance. To opt out, set
`TELEMETRY_ENABLED=false` in your `.env`.

## Help

Bug reports and feature requests are welcome on
[GitHub Issues](https://github.com/xenofex7/solar-tracker/issues).
