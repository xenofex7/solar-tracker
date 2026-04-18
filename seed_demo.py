"""Generate demo data for one year so charts render without a Home Assistant connection."""
import math
import random
from datetime import date, timedelta

import db

MONTHLY_TARGETS = {
    1: 320, 2: 480, 3: 820, 4: 1050, 5: 1250, 6: 1350,
    7: 1380, 8: 1250, 9: 950, 10: 650, 11: 380, 12: 260,
}


def seasonal_daily_kwh(d: date) -> float:
    day_of_year = d.timetuple().tm_yday
    base = 15 + 45 * (0.5 + 0.5 * math.sin((day_of_year - 80) / 365.0 * 2 * math.pi))
    weather = max(0.15, min(1.5, random.gauss(1.0, 0.3)))
    return round(base * weather, 2)


def main():
    db.init_db()
    for m, kwh in MONTHLY_TARGETS.items():
        db.set_target(m, kwh, year=None)
    db.set_setting("kwp", "10.0")

    year = date.today().year - 1
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        db.upsert_production(d.isoformat(), seasonal_daily_kwh(d), source="manual")
        d += timedelta(days=1)

    this_year = date.today().year
    d = date(this_year, 1, 1)
    today = date.today()
    while d <= today:
        db.upsert_production(d.isoformat(), seasonal_daily_kwh(d), source="manual")
        d += timedelta(days=1)

    print(f"Seeded demo data for {year} and {this_year} (bis {today}).")


if __name__ == "__main__":
    main()
