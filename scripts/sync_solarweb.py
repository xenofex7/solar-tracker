#!/usr/bin/env python3
"""Solar-Tracker - Fronius Solar.web sync CLI.

Run from the project root with the project venv:

    .venv/bin/python -m scripts.sync_solarweb [options]

Options
-------
--days N            Pull the last N days up to today (default: 30).
--from YYYY-MM-DD   Explicit start date. Overrides --days.
--to YYYY-MM-DD     Explicit end date (default: today).
--list-systems      Print PV systems linked to the API key and exit.
--dry-run           Fetch data but do not write to the database.
--quiet             Suppress per-day output.

Configuration is read from .env / environment:
    SOLARWEB_ACCESS_KEY_ID
    SOLARWEB_ACCESS_KEY_VALUE
    SOLARWEB_PV_SYSTEM_ID   (optional; auto-resolved if exactly one system)

Cron example (daily at 02:30):
    30 2 * * * cd /opt/solar-tracker && .venv/bin/python -m scripts.sync_solarweb --days 3 --quiet
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

# Make the project importable when invoked as a script (not -m).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_ROOT, ".env"))

import db  # noqa: E402
import solarweb_client  # noqa: E402

DEFAULT_DAYS = 30


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="sync_solarweb",
        description="Pull daily PV production from Fronius Solar.web into the local DB.",
    )
    p.add_argument("--days", type=int, default=DEFAULT_DAYS,
                   help=f"Pull last N days (default: {DEFAULT_DAYS}).")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                   help="Explicit start date (overrides --days).")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                   help="Explicit end date (default: today).")
    p.add_argument("--list-systems", action="store_true",
                   help="List PV systems for this API key and exit.")
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch data but do not write to the DB.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress per-day output.")
    p.add_argument("--tz", default=os.environ.get("TZ") or solarweb_client.DEFAULT_TZ,
                   help="Timezone for day bucketing (default: %(default)s).")
    return p.parse_args(argv)


def _resolve_range(args: argparse.Namespace) -> tuple[str, str]:
    today = date.today()
    end = date.fromisoformat(args.date_to) if args.date_to else today
    if args.date_from:
        start = date.fromisoformat(args.date_from)
    else:
        if args.days < 1:
            raise SystemExit("--days must be >= 1")
        start = end - timedelta(days=args.days - 1)
    if start > end:
        raise SystemExit(f"Start ({start}) is after end ({end}).")
    return start.isoformat(), end.isoformat()


def _list_systems() -> int:
    try:
        systems = solarweb_client.list_pv_systems()
    except solarweb_client.SolarwebClientError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not systems:
        print("(no PV systems found for this API key)")
        return 0
    for s in systems:
        pv_id = s.get("pvSystemId") or s.get("id") or "?"
        name = s.get("name") or s.get("pvSystemName") or "(unnamed)"
        peak = s.get("peakPower")
        peak_str = f", peak={peak} W" if peak else ""
        print(f"  {pv_id}  {name}{peak_str}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if args.list_systems:
        return _list_systems()

    start, end = _resolve_range(args)
    if not args.quiet:
        print(f"Solar.web sync: {start} .. {end} (tz={args.tz})")

    try:
        daily = solarweb_client.fetch_daily(start, end, tz=args.tz)
    except solarweb_client.SolarwebClientError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not daily:
        if not args.quiet:
            print("  (no data returned)")
        return 0

    if not args.quiet:
        for day in sorted(daily):
            print(f"  {day}: {daily[day]:.3f} kWh")

    if args.dry_run:
        if not args.quiet:
            print(f"dry-run: would upsert {len(daily)} days")
        return 0

    db.init_db()
    items = [(d, round(kwh, 3)) for d, kwh in daily.items()]
    inserted, updated = db.bulk_upsert_production(items, source="solarweb")
    print(f"done: {len(items)} days (inserted={inserted}, updated={updated})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
