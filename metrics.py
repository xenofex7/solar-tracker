import calendar
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

MONTHS_DE = [
    "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
]


def _parse(d: str) -> date:
    return date.fromisoformat(d)


def filter_year(records: list[dict], year: int) -> list[dict]:
    return [r for r in records if r["date"].startswith(f"{year}-")]


def monthly_actual(records: list[dict], year: int) -> list[float]:
    totals = [0.0] * 12
    for r in records:
        if not r["date"].startswith(f"{year}-"):
            continue
        m = int(r["date"][5:7])
        totals[m - 1] += r["kwh"]
    return totals


def monthly_targets(targets: list[dict], year: int) -> list[float]:
    specific = {t["month"]: t["kwh"] for t in targets if t.get("year") == year}
    generic = {t["month"]: t["kwh"] for t in targets if t.get("year") is None}
    out = []
    for m in range(1, 13):
        out.append(specific.get(m, generic.get(m, 0.0)))
    return out


def deviation_pct(actual: list[float], target: list[float]) -> list[float | None]:
    result = []
    for a, t in zip(actual, target):
        if t and t > 0:
            result.append((a - t) / t * 100.0)
        else:
            result.append(None)
    return result


def cumulative(values: list[float]) -> list[float]:
    out, s = [], 0.0
    for v in values:
        s += v
        out.append(round(s, 2))
    return out


def daily_series(records: list[dict], year: int) -> list[dict]:
    in_year = [r for r in records if r["date"].startswith(f"{year}-")]
    in_year.sort(key=lambda r: r["date"])
    return in_year


def rolling_avg(values: list[float], window: int = 7) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        chunk = values[i + 1 - window : i + 1]
        out.append(round(sum(chunk) / window, 2))
    return out


def monthly_distribution(records: list[dict], year: int) -> list[dict]:
    buckets: dict[int, list[float]] = defaultdict(list)
    for r in records:
        if not r["date"].startswith(f"{year}-"):
            continue
        m = int(r["date"][5:7])
        buckets[m].append(r["kwh"])
    result = []
    for m in range(1, 13):
        vals = sorted(buckets.get(m, []))
        if not vals:
            result.append({"month": m, "min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0, "count": 0})
            continue
        n = len(vals)
        q1 = vals[n // 4]
        q3 = vals[min(n - 1, (3 * n) // 4)]
        result.append({
            "month": m,
            "min": round(vals[0], 2),
            "q1": round(q1, 2),
            "median": round(median(vals), 2),
            "q3": round(q3, 2),
            "max": round(vals[-1], 2),
            "count": n,
        })
    return result


def top_days(records: list[dict], year: int, n: int = 5) -> dict:
    in_year = [r for r in records if r["date"].startswith(f"{year}-")]
    top = sorted(in_year, key=lambda r: r["kwh"], reverse=True)[:n]
    flop = sorted([r for r in in_year if r["kwh"] > 0], key=lambda r: r["kwh"])[:n]
    return {"top": top, "flop": flop}


def year_comparison(records: list[dict]) -> dict[int, list[float]]:
    years: dict[int, list[float]] = {}
    for r in records:
        y = int(r["date"][:4])
        m = int(r["date"][5:7])
        years.setdefault(y, [0.0] * 12)
        years[y][m - 1] += r["kwh"]
    return years


def heatmap_data(records: list[dict], year: int) -> list[dict]:
    by_date = {r["date"]: r["kwh"] for r in records}
    out = []
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        iso = d.isoformat()
        out.append({"date": iso, "kwh": round(by_date.get(iso, 0.0), 2)})
        d += timedelta(days=1)
    return out


def cumulative_revenue(records: list[dict], price: float) -> list[dict]:
    rows = sorted(records, key=lambda r: r["date"])
    out, s = [], 0.0
    for r in rows:
        s += r["kwh"] * price
        out.append({"date": r["date"], "revenue": round(s, 2)})
    return out


def payback(records: list[dict], invested: float, price: float) -> dict:
    if invested <= 0 or price <= 0 or not records:
        return {
            "invested": round(invested, 2),
            "revenue_total": 0.0,
            "remaining": round(invested, 2),
            "payback_date": None,
            "progress_pct": 0.0,
            "avg_daily_revenue": 0.0,
        }
    cum = cumulative_revenue(records, price)
    revenue_total = cum[-1]["revenue"] if cum else 0.0
    payback_date = None
    for row in cum:
        if row["revenue"] >= invested:
            payback_date = row["date"]
            break
    remaining = max(0.0, invested - revenue_total)
    if len(cum) >= 2:
        window = cum[-365:]
        span = max(1, (date.fromisoformat(window[-1]["date"]) - date.fromisoformat(window[0]["date"])).days)
        avg_daily = (window[-1]["revenue"] - window[0]["revenue"]) / span
    else:
        avg_daily = cum[-1]["revenue"]
    if payback_date is None and avg_daily > 0 and remaining > 0:
        days_needed = remaining / avg_daily
        last_date = date.fromisoformat(cum[-1]["date"])
        projected = last_date + timedelta(days=int(round(days_needed)))
        payback_date = projected.isoformat()
    return {
        "invested": round(invested, 2),
        "revenue_total": round(revenue_total, 2),
        "remaining": round(remaining, 2),
        "payback_date": payback_date,
        "progress_pct": round(min(100.0, revenue_total / invested * 100.0), 1),
        "avg_daily_revenue": round(avg_daily, 4),
    }


def summary(records: list[dict], targets: list[dict], year: int, kwp: float) -> dict:
    actual = monthly_actual(records, year)
    target = monthly_targets(targets, year)
    ytd_actual = round(sum(actual), 2)

    today = date.today()
    if year < today.year:
        ytd_target = round(sum(target), 2)
    elif year > today.year:
        ytd_target = 0.0
    else:
        full = sum(target[: today.month - 1])
        days_in_month = calendar.monthrange(year, today.month)[1]
        partial = target[today.month - 1] * (today.day / days_in_month)
        ytd_target = round(full + partial, 2)

    delta = round(ytd_actual - ytd_target, 2)
    dev = (delta / ytd_target * 100.0) if ytd_target > 0 else None

    in_year = [r for r in records if r["date"].startswith(f"{year}-")]
    best = max(in_year, key=lambda r: r["kwh"]) if in_year else None

    spec_yield = round(ytd_actual / kwp, 2) if kwp else None

    return {
        "year": year,
        "ytd_actual": ytd_actual,
        "ytd_target": ytd_target,
        "delta_kwh": delta,
        "delta_pct": round(dev, 2) if dev is not None else None,
        "best_day": best,
        "days_recorded": len(in_year),
        "specific_yield": spec_yield,
        "kwp": kwp,
    }
