#!/usr/bin/env python3
"""Solar-Tracker - Home Assistant sync CLI.

Run from the project root with the project venv:

    .venv/bin/python -m scripts.sync_ha [options]

Options
-------
--days N            Pull the last N days up to today (default: 3).
--from YYYY-MM-DD   Explicit start date. Overrides --days.
--to YYYY-MM-DD     Explicit end date (default: today).
--dry-run           Fetch data but do not write to the database.
--quiet             Suppress per-day output.

Day bucketing uses the `timezone` setting from the database (fallback:
Europe/Zurich), so the CLI and the web app produce identical days.

Configuration is read from .env / environment:
    HA_URL
    HA_TOKEN
    HA_ENTITY_ID

Cron example (daily at 02:30):
    30 2 * * * cd /opt/solar-tracker && .venv/bin/python -m scripts.sync_ha --days 3 --quiet
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_ROOT, ".env"))

from websocket import WebSocketException  # noqa: E402

import db  # noqa: E402
import ha_client  # noqa: E402

DEFAULT_DAYS = 3


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="sync_ha",
        description="Pull daily PV production from Home Assistant into the local DB.",
    )
    p.add_argument("--days", type=int, default=DEFAULT_DAYS,
                   help=f"Pull last N days (default: {DEFAULT_DAYS}).")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                   help="Explicit start date (overrides --days).")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                   help="Explicit end date (default: today).")
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch data but do not write to the DB.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress per-day output.")
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


def _timezone() -> str:
    setting = db.get_setting("timezone") or ha_client.DEFAULT_TZ
    return setting.strip() or ha_client.DEFAULT_TZ


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    start, end = _resolve_range(args)

    db.init_db()
    tz = _timezone()
    if not args.quiet:
        print(f"Home Assistant sync: {start} .. {end} (tz={tz})")

    try:
        daily = ha_client.fetch_daily(start, end, tz=tz)
    except (ha_client.HAClientError, OSError, WebSocketException) as e:
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

    items = [(d, round(kwh, 3)) for d, kwh in daily.items()]
    inserted, updated = db.bulk_upsert_production(items, source="home_assistant")
    print(f"done: {len(items)} days (inserted={inserted}, updated={updated})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
