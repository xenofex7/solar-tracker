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


def _is_all(year) -> bool:
    return year is None or year == "all"


def filter_year(records: list[dict], year) -> list[dict]:
    if _is_all(year):
        return list(records)
    return [r for r in records if r["date"].startswith(f"{year}-")]


def years_in_records(records: list[dict]) -> list[int]:
    return sorted({int(r["date"][:4]) for r in records})


def monthly_actual(records: list[dict], year) -> list[float]:
    totals = [0.0] * 12
    for r in records:
        if not _is_all(year) and not r["date"].startswith(f"{year}-"):
            continue
        m = int(r["date"][5:7])
        totals[m - 1] += r["kwh"]
    return totals


def _eligibility_factor(year: int, month: int, start_date: str | None, today: date | None = None) -> float:
    today = today or date.today()
    days_in = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in)
    lower = month_start
    if start_date:
        sd = date.fromisoformat(start_date)
        if sd > lower:
            lower = sd
    upper = min(month_end, today)
    if upper < lower:
        return 0.0
    return ((upper - lower).days + 1) / days_in


def monthly_targets(
    targets: list[dict],
    year,
    multiplier: int = 1,
    start_date: str | None = None,
    years_available: list[int] | None = None,
) -> list[float]:
    generic = {t["month"]: t["kwh"] for t in targets if t.get("year") is None}
    if _is_all(year):
        years = years_available or list(range(date.today().year - max(0, multiplier - 1), date.today().year + 1))
        out = [0.0] * 12
        for m in range(1, 13):
            for y in years:
                factor = _eligibility_factor(y, m, start_date)
                if factor > 0:
                    out[m - 1] += generic.get(m, 0.0) * factor
        if not years:
            return [generic.get(m, 0.0) * max(1, multiplier) for m in range(1, 13)]
        return out
    specific = {t["month"]: t["kwh"] for t in targets if t.get("year") == year}
    out = []
    for m in range(1, 13):
        base = specific.get(m, generic.get(m, 0.0))
        out.append(base * _eligibility_factor(year, m, start_date))
    return out


def deviation_pct(actual: list[float], target: list[float]) -> list[float | None]:
    result = []
    for a, t in zip(actual, target, strict=False):
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


def daily_series(records: list[dict], year) -> list[dict]:
    if _is_all(year):
        return sorted(records, key=lambda r: r["date"])
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


def monthly_distribution(records: list[dict], year) -> list[dict]:
    buckets: dict[int, list[float]] = defaultdict(list)
    for r in records:
        if not _is_all(year) and not r["date"].startswith(f"{year}-"):
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


def top_days(records: list[dict], year, n: int = 5) -> list[dict]:
    pool = list(records) if _is_all(year) else [r for r in records if r["date"].startswith(f"{year}-")]
    return sorted(pool, key=lambda r: r["kwh"], reverse=True)[:n]


def year_comparison(records: list[dict]) -> dict[int, list[float]]:
    years: dict[int, list[float]] = {}
    for r in records:
        y = int(r["date"][:4])
        m = int(r["date"][5:7])
        years.setdefault(y, [0.0] * 12)
        years[y][m - 1] += r["kwh"]
    return years


def heatmap_data(records: list[dict], year) -> list[dict]:
    if _is_all(year):
        years = years_in_records(records)
        if not years:
            return []
        year = years[-1]
    by_date = {r["date"]: r["kwh"] for r in records}
    out = []
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        iso = d.isoformat()
        out.append({"date": iso, "kwh": round(by_date.get(iso, 0.0), 2)})
        d += timedelta(days=1)
    return out


_MONTH_LABELS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _iter_months(start_iso: str, end_iso: str):
    s = date.fromisoformat(start_iso)
    e = date.fromisoformat(end_iso)
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def _overlap_days(a1: date, a2: date, b1: date, b2: date) -> int:
    s, e = max(a1, b1), min(a2, b2)
    return (e - s).days + 1 if s <= e else 0


def monthly_flows(
    records: list[dict],
    import_bills: list[dict],
    export_bills: list[dict],
    avg_import_price: float,
) -> list[dict]:
    months = set()
    for b in list(import_bills) + list(export_bills):
        for ym in _iter_months(b["period_start"], b["period_end"]):
            months.add(ym)
    if not months:
        return []

    flows = []
    for (y, m) in sorted(months):
        mfirst = date(y, m, 1)
        mlast = date(y, m, calendar.monthrange(y, m)[1])
        mfirst_iso, mlast_iso = mfirst.isoformat(), mlast.isoformat()

        pv_kwh = sum(r["kwh"] for r in records if mfirst_iso <= r["date"] <= mlast_iso)

        exported = 0.0
        export_credit = 0.0
        for ex in export_bills:
            ex_start = date.fromisoformat(ex["period_start"])
            ex_end = date.fromisoformat(ex["period_end"])
            if _overlap_days(mfirst, mlast, ex_start, ex_end) == 0:
                continue
            pv_in_period = sum(
                r["kwh"] for r in records
                if ex["period_start"] <= r["date"] <= ex["period_end"]
            )
            o_start_iso = max(ex_start, mfirst).isoformat()
            o_end_iso = min(ex_end, mlast).isoformat()
            pv_in_overlap = sum(
                r["kwh"] for r in records if o_start_iso <= r["date"] <= o_end_iso
            )
            if pv_in_period > 0:
                share = pv_in_overlap / pv_in_period
            else:
                total_days = (ex_end - ex_start).days + 1
                share = _overlap_days(mfirst, mlast, ex_start, ex_end) / total_days if total_days else 0
            exported += ex["kwh"] * share
            export_credit += ex["amount_chf"] * share

        imported = 0.0
        import_cost = 0.0
        for imp in import_bills:
            imp_start = date.fromisoformat(imp["period_start"])
            imp_end = date.fromisoformat(imp["period_end"])
            overlap = _overlap_days(mfirst, mlast, imp_start, imp_end)
            if overlap == 0:
                continue
            total_days = (imp_end - imp_start).days + 1
            share = overlap / total_days if total_days else 0
            imported += imp["kwh"] * share
            import_cost += imp["amount_chf"] * share

        self_kwh = max(0.0, pv_kwh - exported)
        self_pct = (self_kwh / pv_kwh * 100.0) if pv_kwh > 0 else 0.0
        flows.append({
            "year": y,
            "month": m,
            "label": f"{_MONTH_LABELS[m-1]} {y}",
            "period_start": mfirst_iso,
            "period_end": mlast_iso,
            "pv_kwh": round(pv_kwh, 2),
            "self_consumed_kwh": round(self_kwh, 2),
            "exported_kwh": round(exported, 2),
            "imported_kwh": round(imported, 2),
            "self_consumption_pct": round(self_pct, 1),
            "export_credit": round(export_credit, 2),
            "import_cost": round(import_cost, 2),
            "self_consumption_savings": round(self_kwh * avg_import_price, 2),
        })
    return flows


def self_consumption(records: list[dict], export_bills: list[dict]) -> dict:
    if not export_bills:
        return {
            "pv_in_export_periods": 0.0,
            "exported_kwh": 0.0,
            "self_consumed_kwh": 0.0,
            "self_consumption_pct": 0.0,
        }
    total_export = sum(b["kwh"] for b in export_bills)
    pv_sum = 0.0
    for bill in export_bills:
        start = bill["period_start"]
        end = bill["period_end"]
        for r in records:
            if start <= r["date"] <= end:
                pv_sum += r["kwh"]
    self_consumed = max(0.0, pv_sum - total_export)
    pct = (self_consumed / pv_sum * 100.0) if pv_sum > 0 else 0.0
    return {
        "pv_in_export_periods": round(pv_sum, 2),
        "exported_kwh": round(total_export, 2),
        "self_consumed_kwh": round(self_consumed, 2),
        "self_consumption_pct": round(pct, 1),
    }


def financial_series(
    records: list[dict],
    import_bills: list[dict],
    export_bills: list[dict],
    fallback_price: float,
) -> tuple[list[dict], dict]:
    rows = sorted(records, key=lambda r: r["date"])

    total_imp_kwh = sum(b["kwh"] for b in import_bills)
    total_imp_amount = sum(b["amount_chf"] for b in import_bills)
    avg_import_price = (total_imp_amount / total_imp_kwh) if total_imp_kwh > 0 else fallback_price

    period_rates = []
    total_pv_in_export = 0.0
    for bill in export_bills:
        start, end = bill["period_start"], bill["period_end"]
        pv_in_period = sum(r["kwh"] for r in rows if start <= r["date"] <= end)
        total_pv_in_export += pv_in_period
        export_kwh = bill["kwh"]
        export_amount = bill["amount_chf"]
        self_kwh = max(0.0, pv_in_period - export_kwh)
        savings = self_kwh * avg_import_price
        rate = ((export_amount + savings) / pv_in_period) if pv_in_period > 0 else fallback_price
        period_rates.append({"start": start, "end": end, "rate": rate})

    def rate_for(d: str) -> float:
        for p in period_rates:
            if p["start"] <= d <= p["end"]:
                return p["rate"]
        return fallback_price

    cum, s = [], 0.0
    for r in rows:
        s += r["kwh"] * rate_for(r["date"])
        cum.append({"date": r["date"], "revenue": round(s, 2)})

    total_exported_kwh = sum(b["kwh"] for b in export_bills)
    total_export_credit = sum(b["amount_chf"] for b in export_bills)
    self_consumed_kwh = max(0.0, total_pv_in_export - total_exported_kwh)
    self_consumption_savings = self_consumed_kwh * avg_import_price
    all_pv = sum(r["kwh"] for r in rows)
    uncovered_pv = max(0.0, all_pv - total_pv_in_export)
    estimated_other = uncovered_pv * fallback_price

    breakdown = {
        "avg_import_price": round(avg_import_price, 4),
        "self_consumption_savings": round(self_consumption_savings, 2),
        "export_credit": round(total_export_credit, 2),
        "estimated_other": round(estimated_other, 2),
        "total_revenue": round(self_consumption_savings + total_export_credit + estimated_other, 2),
        "uncovered_pv_kwh": round(uncovered_pv, 2),
    }
    return cum, breakdown


def cumulative_revenue(records, import_bills, export_bills, fallback_price):
    return financial_series(records, import_bills, export_bills, fallback_price)[0]


def payback(
    records: list[dict],
    invested: float,
    import_bills: list[dict],
    export_bills: list[dict],
    fallback_price: float,
    targets: list[dict] | None = None,
) -> dict:
    cum, breakdown = financial_series(records, import_bills, export_bills, fallback_price)
    if invested <= 0 or not cum:
        return {
            "invested": round(invested, 2),
            "revenue_total": 0.0,
            "remaining": round(invested, 2),
            "payback_date": None,
            "progress_pct": 0.0,
            "avg_daily_revenue": 0.0,
            "projection_basis": "none",
            "yearly_yield_estimate": 0.0,
            "breakdown": breakdown,
        }
    revenue_total = cum[-1]["revenue"] if cum else 0.0
    payback_date = None
    for row in cum:
        if row["revenue"] >= invested:
            payback_date = row["date"]
            break
    remaining = max(0.0, invested - revenue_total)

    # Preferred projection: yearly target kWh × blended effective price
    total_pv = sum(r["kwh"] for r in records)
    blended_price = (revenue_total / total_pv) if total_pv > 0 else fallback_price
    yearly_target_kwh = 0.0
    if targets:
        generic = {t["month"]: t["kwh"] for t in targets if t.get("year") is None}
        yearly_target_kwh = sum(generic.values())
    yearly_yield = yearly_target_kwh * blended_price
    projection_basis = "targets" if yearly_yield > 0 else "history"

    if yearly_yield > 0:
        avg_daily = yearly_yield / 365.0
    elif len(cum) >= 2:
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
        "progress_pct": round(min(100.0, revenue_total / invested * 100.0) if invested > 0 else 0.0, 1),
        "avg_daily_revenue": round(avg_daily, 4),
        "projection_basis": projection_basis,
        "yearly_yield_estimate": round(yearly_yield, 2),
        "blended_price": round(blended_price, 4),
        "breakdown": breakdown,
    }


def summary(records: list[dict], targets: list[dict], year, kwp: float, start_date: str | None = None) -> dict:
    today = date.today()
    sd = date.fromisoformat(start_date) if start_date else None
    if _is_all(year):
        actual = monthly_actual(records, year)
        ytd_actual = round(sum(actual), 2)
        in_scope = list(records)
        if in_scope:
            first_year = int(min(r["date"] for r in in_scope)[:4])
            if sd and sd.year > first_year:
                first_year = sd.year
            years_available = list(range(first_year, today.year + 1))
            target = monthly_targets(targets, year, start_date=start_date, years_available=years_available)
            ytd_target = round(sum(target), 2)
        else:
            ytd_target = 0.0
    else:
        actual = monthly_actual(records, year)
        target = monthly_targets(targets, year, start_date=start_date)
        ytd_actual = round(sum(actual), 2)
        ytd_target = round(sum(target), 2)
        in_scope = [r for r in records if r["date"].startswith(f"{year}-")]

    delta = round(ytd_actual - ytd_target, 2)
    dev = (delta / ytd_target * 100.0) if ytd_target > 0 else None
    best = max(in_scope, key=lambda r: r["kwh"]) if in_scope else None
    spec_yield = round(ytd_actual / kwp, 2) if kwp else None

    return {
        "year": year,
        "ytd_actual": ytd_actual,
        "ytd_target": ytd_target,
        "delta_kwh": delta,
        "delta_pct": round(dev, 2) if dev is not None else None,
        "best_day": best,
        "days_recorded": len(in_scope),
        "specific_yield": spec_yield,
        "kwp": kwp,
    }
