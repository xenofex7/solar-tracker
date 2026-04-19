# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-04-19
### Added
- Footer showing the running app version (read from `VERSION`).
- Commissioning date setting in Anlagendaten: records, monthly
  targets and billing periods before this date are excluded from
  all KPIs and charts so pre-commissioning zeroes do not dilute
  averages and projections. The commissioning month is prorated
  from the configured day.
- Three new dashboard charts broken down per month: energy flows
  (self-consumed, exported, grid import), self-consumption ratio
  over time, financial flow (import cost, self-consumption savings,
  export credit). Quarterly bill data is prorated across months
  (exports by PV share, imports by day count).

### Changed
- Amortisation projection now uses yearly target × blended price
  (falls back to the historical daily average), with a sub-label
  showing the basis (Jahressoll or Verlauf).
- Future months are blank in deviation and cumulative target charts;
  monthly targets cap at today so there are no -100% bars for
  not-yet months.
- Anlagendaten form is a stacked key/value list with dividers, and
  the sync status message gets a small top margin so it no longer
  butts against the form.

### Fixed
- Settings page rendered narrower than the dashboard because `main`
  in the new flex column layout shrank to its content width; `main`
  now has `width: 100%` so both pages fill the same max-width.

## [1.0.2] - 2026-04-19
### Fixed
- HA sync returned a 500 when concurrent readers locked SQLite during
  per-day upserts; it now writes all days in a single transaction.

### Changed
- HA sync response and status text separate HA fetch time from DB
  write time so slow syncs can be attributed to the right side.
- Dashboard reloads on viewport width change so charts resize cleanly.

## [1.0.1] - 2026-04-19
### Fixed
- Worker crash on first boot when two gunicorn workers initialised the
  SQLite schema in parallel; app is now loaded with `--preload` and
  connections set `PRAGMA busy_timeout = 5000`.

## [1.0.0] - 2026-04-19

### Added
- Flask dashboard comparing actual vs. target solar yield with nine
  charts (monthly bars, deviation %, cumulative YTD, daily + 7-day
  rolling average, calendar heatmap, monthly distribution, year
  comparison, top/flop days, KPI tiles).
- Home Assistant sync over WebSocket using Long-Term Statistics
  (`recorder/statistics_during_period`).
- Manual day entry and monthly target management.
- Plant cost tracking with amortization chart and KPIs.
- Quarterly grid billing (import/export) with self-consumption metric
  and split revenue calculation (self-consumption savings vs. export
  credit vs. estimated fallback).
- "All time" (Gesamt) dashboard view.
- Dockerfile and docker compose setup, gunicorn runtime.
- GitHub Actions workflow that publishes multi-arch images to GHCR.

[Unreleased]: https://github.com/xenofex7/solar-tracker/compare/v1.1.0...HEAD
[1.0.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.0.0
[1.0.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.0.1
[1.0.2]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.0.2
[1.1.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.1.0
