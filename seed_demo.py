"""Generate a full demo dataset so the app shows off all features without a
real Home Assistant connection. Idempotent - safe to run multiple times."""
import math
import random
from datetime import date, timedelta

import db

MONTHLY_TARGETS = {
    1: 320, 2: 480, 3: 820, 4: 1050, 5: 1250, 6: 1350,
    7: 1380, 8: 1250, 9: 950, 10: 650, 11: 380, 12: 260,
}

PLANT_KWP = 15.0
PRICE_PER_KWH = 0.15
COMMISSIONING = date(date.today().year - 1, 8, 1)

PLANT_COSTS = [
    ("Solar-Bauer", 24000.00, date(COMMISSIONING.year, 7, 15)),
    ("Elektriker", 4500.00, date(COMMISSIONING.year, 7, 20)),
    ("Pronovo Rückerstattung", -7500.00, date(COMMISSIONING.year + 1, 2, 10)),
]

GRID_BILLS = [
    # (kind, period_start, period_end, kwh, amount, invoice_no)
    ("import", date(COMMISSIONING.year, 7, 1), date(COMMISSIONING.year, 9, 30), 1826, 487.90, "DEMO-Q3-I"),
    ("export", date(COMMISSIONING.year, 8, 1), date(COMMISSIONING.year, 9, 30), 1434, 157.75, "DEMO-Q3-E"),
    ("import", date(COMMISSIONING.year, 10, 1), date(COMMISSIONING.year, 12, 31), 2631, 696.00, "DEMO-Q4-I"),
    ("export", date(COMMISSIONING.year, 10, 1), date(COMMISSIONING.year, 12, 31), 44, 4.85, "DEMO-Q4-E"),
]


def seasonal_daily_kwh(d: date) -> float:
    day_of_year = d.timetuple().tm_yday
    per_kwp = 0.5 + 5.0 * (0.5 + 0.5 * math.sin((day_of_year - 80) / 365.0 * 2 * math.pi))
    weather = max(0.15, min(1.5, random.gauss(1.0, 0.3)))
    return round(per_kwp * PLANT_KWP * weather, 2)


def main():
    random.seed(42)
    db.init_db()

    db.set_setting("kwp", str(PLANT_KWP))
    db.set_setting("price_per_kwh", str(PRICE_PER_KWH))
    db.set_setting("start_date", COMMISSIONING.isoformat())
    db.set_setting("currency", "CHF")

    for m, kwh in MONTHLY_TARGETS.items():
        db.set_target(m, kwh, year=None)

    d = COMMISSIONING
    end = date.today()
    prod_count = 0
    while d <= end:
        db.upsert_production(d.isoformat(), seasonal_daily_kwh(d), source="home_assistant")
        d += timedelta(days=1)
        prod_count += 1

    if not db.list_costs():
        for label, amount, cdate in PLANT_COSTS:
            db.add_cost(label, amount, cdate.isoformat())

    for kind, p_start, p_end, kwh, amount, invoice in GRID_BILLS:
        db.upsert_grid_bill(kind, p_start.isoformat(), p_end.isoformat(), kwh, amount, invoice)

    print(f"Seeded {prod_count} production days from {COMMISSIONING} to {end}.")
    print(f"Plant: {PLANT_KWP} kWp, price {PRICE_PER_KWH} CHF/kWh, commissioning {COMMISSIONING}.")
    print(f"Plant costs: {len(PLANT_COSTS)} positions ({'existing, skipped' if db.list_costs() and len(db.list_costs()) != len(PLANT_COSTS) else 'seeded'}).")
    print(f"Grid bills: {len(GRID_BILLS)} quarterly invoices (import + export).")


if __name__ == "__main__":
    main()
