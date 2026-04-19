# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/xenofex7/solar-tracker/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.0.0
