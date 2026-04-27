# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.0.1] - 2026-04-27
### Added
- Bright and dark logo variants with theme-based swap and centered hero logo on the docs site.
- Logo source files (Pixelmator documents and PNG masters) under `assets/`.

### Changed
- Make logo background transparent and switch the docs site header to solid white in light mode for a seamless logo blend.
- Update dark logo variant.

### Fixed
- Theme-based brand logo swap in the app header (raise selector specificity so only one variant renders).

## [2.0.0] - 2026-04-26
### Added
- User-configurable currency setting.

### Changed
- Replace SVG logo with new square PNG branding.
- Format amounts per currency and numbers per language.
- Rename `amount_chf` column to `amount` for currency-agnostic storage.

## [1.8.1] - 2026-04-26
### Added
- GitHub Pages landing site under `docs/` with DE/EN toggle, light/dark theme, screenshot slider, llms.txt, robots.txt, sitemap.xml, manifest.webmanifest, 404 page and SoftwareApplication JSON-LD.
- README badges, logo and screenshot showcase.
- Dashboard and settings screenshots (12 PNG + 12 WebP variants).

### Changed
- Convert slider screenshots to WebP for a 79% smaller payload (6.6 MB to 1.4 MB) with PNG fallback.
- Harden the changelog markdown link parser against `javascript:` URLs and rebuild settings edit-row inputs without unescaped `innerHTML`; document the missing authentication explicitly in the README.
- Refresh README to v1.8.0 feature set: 14 charts, three KPI groups, realistic Docker tag examples, `FLASK_HOST` documented, project page link, Help section.
- Switch the commit-activity badge to yearly granularity.

### Removed
- Maintainer-only "Releasing a new version" section from the README.

## [1.8.0] - 2026-04-25
### Added
- Effective electricity price KPI.
- Info popover on Payback KPI with total runtime.

## [1.7.0] - 2026-04-23
### Added
- Inline row editing in Anlagekosten, Stromkosten and Produktion tables.
- Info popover on Self-consumption rate KPI explaining the calculation.

### Changed
- Polish scrollbar, form spacing and toast messages.

## [1.6.0] - 2026-04-23
### Added
- KPI info popover and Savings vs. no PV chart.

### Changed
- Make header sticky and move year filter into it.
- Scope Self-consumption & Grid KPIs to selected year.
- Normalize dash typography to ASCII hyphens.

## [1.5.1] - 2026-04-23
### Changed
- Move HA sync status into toast and auto-reload the page on success.
- Rename Home Assistant tab to Synchronisation to allow additional sync sources.
- Tint success/error toasts in light green/red and support an optional subtext line.
- Polish modal close icon to a Lucide SVG X for optical centering.
- Polish Saved confirmation by dropping the trailing period.

### Fixed
- Restore missing [1.4.1] changelog header and add a release.sh guard that verifies every tag has a matching entry.

## [1.5.0] - 2026-04-23
### Added
- System theme mode as default, cycling system/light/dark.
- Toast notifications replacing alert() in settings.
- Changelog modal and mobile hamburger nav menu.
- Light/dark theme toggle with persistence.

### Fixed
- Chart resize via `min-width: 0` on cards, removing full-reload resize handler.

## [1.4.1] - 2026-04-21
### Changed
- Reload page automatically after successful HA sync (1.5 s delay to show result message).
- Polish language switcher to always redirect to dashboard and set uniform KPI tile min-height.

### Fixed
- KPI tile heights are now uniform across all groups by measuring the tallest tile.

## [1.4.0] - 2026-04-21
### Added
- i18n support with language switching and localized UI labels (de, en, fr, es, it).
- Tagesqualität donut chart showing daily production split into 6 quality buckets (red → green).
- Specific Yield chart (kWh/kWp per month) to track panel degradation over time.

### Changed
- Payback chart redesigned as yearly cumulative bars with forecast until investment is recovered.
- Year Comparison now highlights the current year in yellow, older years in blue, with correct z-order and lines that stop at data boundaries.

### Removed
- Bottom 5 Days card - values were always near zero and not useful.

## [1.3.5] - 2026-04-21
### Changed
- `scripts/release.sh` now runs `ruff check` and `pytest` before bumping/tagging, matching CI so broken releases are caught locally.

## [1.3.4] - 2026-04-21
### Fixed
- Ruff I001 import sorting in `ha_client.py` that broke CI on v1.3.3.

## [1.3.3] - 2026-04-21
### Fixed
- HA sync now assigns daily buckets to the correct local calendar day via a configurable `timezone` setting (dropdown in Anlagendaten, default `Europe/Zurich`), replacing the host-local `astimezone()` that mis-attributed days in UTC containers.

## [1.3.2] - 2026-04-20
### Changed
- Exclude `.claude/` from version control.
- Rename Manuelle Eingabe tab to Produktion.

### Fixed
- Settings tabs and form handlers no longer blocked by `script-src 'self'` CSP (inline script extracted to `static/js/settings.js`).
- All-years (Gesamt) target now uses per-month seasonal weights prorated from `start_date`, instead of flat 1/12 proration that inflated the target.

## [1.3.1] - 2026-04-19
### Fixed
- Test file import grouping to satisfy ruff 0.15 isort rules so CI
  passes on GitHub Actions.

## [1.3.0] - 2026-04-19
### Added
- `LICENSE` file (MIT).
- `requirements.lock.txt` with pinned exact versions; Dockerfile
  installs from the lock for reproducible builds.
- `pyproject.toml` with ruff config (line-length, select rules).
- `tests/test_metrics.py` - 21 unit tests covering `monthly_actual`,
  `monthly_targets`, `deviation_pct`, `self_consumption`,
  `financial_series`, `payback`, `monthly_flows`, `cumulative`,
  `rolling_avg` and `summary`.
- GitHub Actions `ci.yml` that runs ruff and pytest on push / PR.
- Chart.js and chartjs-chart-matrix are now bundled locally under
  `static/js/vendor/` instead of being loaded from jsdelivr; stricter
  CSP allows only self-hosted scripts.
- All dashboard canvases get `role="img"` and an `aria-label`
  describing the chart content for screen readers.

### Changed
- Flask app sets `Content-Security-Policy`, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin`
  on every response.
- Global `:focus-visible` outline in the accent color so keyboard
  focus is always visible on the dark theme.

### Fixed
- `renderKpis` now HTML-escapes group titles, labels and class names
  before building the `innerHTML` string - defense in depth in case
  any of those ever become user-controlled.

## [1.2.1] - 2026-04-19
### Changed
- `seed_demo.py` now seeds a full dataset (commissioning date, price,
  plant costs, quarterly grid bills) so the app renders all KPIs and
  charts out of the box; idempotent on re-run.

### Fixed
- `db.set_target` no longer inserts duplicate generic monthly target
  rows when rerun, because SQLite's UNIQUE treats NULL as distinct.
- `seed_demo` seasonal daily kWh is now per-kWp so production scales
  realistically for any plant size.

## [1.2.0] - 2026-04-19
### Added
- SVG logo in the header brand and as browser favicon.

## [1.1.1] - 2026-04-19
### Fixed
- Per-period charts (Energieflüsse, Eigenverbrauchsquote, Finanzfluss)
  now honour the selected year instead of always showing all billing
  periods.

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

[Unreleased]: https://github.com/xenofex7/solar-tracker/compare/v2.0.1...HEAD
[1.0.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.0.0
[1.0.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.0.1
[1.0.2]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.0.2
[1.1.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.1.0
[1.1.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.1.1
[1.2.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.2.0
[1.2.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.2.1
[1.3.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.3.0
[1.3.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.3.1
[1.3.2]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.3.2
[1.3.3]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.3.3
[1.3.4]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.3.4
[1.3.5]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.3.5
[1.4.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.4.0
[1.4.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.4.1
[1.5.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.5.0
[1.5.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.5.1
[1.6.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.6.0
[1.7.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.7.0
[1.8.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.8.0
[1.8.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v1.8.1
[2.0.0]: https://github.com/xenofex7/solar-tracker/releases/tag/v2.0.0
[2.0.1]: https://github.com/xenofex7/solar-tracker/releases/tag/v2.0.1
