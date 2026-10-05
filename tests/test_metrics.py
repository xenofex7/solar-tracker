"""Unit tests for metrics.py - the calculation engine that drives KPIs
and charts. Uses synthetic records/bills so tests are deterministic
and independent of the real SQLite database."""

from __future__ import annotations

from datetime import date

import pytest

import metrics

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _daily(start: str, end: str, kwh_per_day: float) -> list[dict]:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    out = []
    d = s
    while d <= e:
        out.append({"date": d.isoformat(), "kwh": kwh_per_day})
        d = date.fromordinal(d.toordinal() + 1)
    return out


GENERIC_TARGETS = [
    {"year": None, "month": m, "kwh": v}
    for m, v in enumerate([300, 500, 900, 1200, 1500, 1600, 1600, 1400, 1000, 700, 400, 200], start=1)
]


# ---------------------------------------------------------------------------
# monthly_actual
# ---------------------------------------------------------------------------

def test_monthly_actual_sums_per_month():
    records = [
        {"date": "2025-01-15", "kwh": 10},
        {"date": "2025-01-20", "kwh": 5},
        {"date": "2025-02-01", "kwh": 3},
    ]
    out = metrics.monthly_actual(records, 2025)
    assert out[0] == 15  # Jan
    assert out[1] == 3   # Feb
    assert sum(out[2:]) == 0


def test_monthly_actual_filters_other_years():
    records = [
        {"date": "2024-06-01", "kwh": 50},
        {"date": "2025-06-01", "kwh": 20},
    ]
    assert metrics.monthly_actual(records, 2025)[5] == 20


def test_monthly_actual_all_year_sums_across_years():
    records = [
        {"date": "2024-03-01", "kwh": 10},
        {"date": "2025-03-01", "kwh": 15},
    ]
    out = metrics.monthly_actual(records, "all")
    assert out[2] == 25


# ---------------------------------------------------------------------------
# monthly_targets with start_date / future-month cap
# ---------------------------------------------------------------------------

def test_monthly_targets_full_past_year():
    out = metrics.monthly_targets(GENERIC_TARGETS, 2020)
    # No start_date/today cap applied because 2020 is in the past
    # relative to today. With our eligibility_factor, past months
    # get factor 1.
    # NOTE: factor also caps at today. For year=2020 every month is
    # already past, so factor = 1 for all.
    assert out[0] == 300
    assert out[11] == 200


def test_monthly_targets_start_date_zeros_earlier_months():
    # Start on 2020-04-10 - Jan-Mar zero, April prorated
    out = metrics.monthly_targets(GENERIC_TARGETS, 2020, start_date="2020-04-10")
    assert out[0] == 0
    assert out[1] == 0
    assert out[2] == 0
    # April has 30 days, commissioning on day 10 → 21/30 of target
    assert out[3] == pytest.approx(1200 * (30 - 10 + 1) / 30)
    assert out[4] == 1500  # May full


def test_monthly_targets_future_year_is_zero_when_today_is_before():
    # If year is in the future relative to today, all months are 0
    future = date.today().year + 10
    out = metrics.monthly_targets(GENERIC_TARGETS, future)
    assert all(v == 0 for v in out)


def test_monthly_targets_specific_year_overrides_generic():
    targets = GENERIC_TARGETS + [{"year": 2023, "month": 6, "kwh": 9999}]
    out = metrics.monthly_targets(targets, 2023)
    assert out[5] == 9999
    # Other months fall back to generic
    assert out[0] == 300


# ---------------------------------------------------------------------------
# deviation_pct
# ---------------------------------------------------------------------------

def test_deviation_pct_none_when_target_zero():
    assert metrics.deviation_pct([50], [0]) == [None]


def test_deviation_pct_positive_and_negative():
    out = metrics.deviation_pct([120, 80], [100, 100])
    assert out[0] == pytest.approx(20)
    assert out[1] == pytest.approx(-20)


# ---------------------------------------------------------------------------
# self_consumption
# ---------------------------------------------------------------------------

def test_self_consumption_returns_zeros_when_no_bills():
    out = metrics.self_consumption([{"date": "2025-07-01", "kwh": 50}], [])
    assert out["self_consumed_kwh"] == 0
    assert out["self_consumption_pct"] == 0


def test_self_consumption_computes_pv_minus_export():
    records = _daily("2025-08-01", "2025-08-05", 100)  # 500 kWh in period
    export_bills = [{
        "period_start": "2025-08-01",
        "period_end": "2025-08-05",
        "kwh": 200,
        "amount": 22,
    }]
    out = metrics.self_consumption(records, export_bills)
    assert out["exported_kwh"] == 200
    assert out["pv_in_export_periods"] == 500
    assert out["self_consumed_kwh"] == 300
    assert out["self_consumption_pct"] == 60.0


# ---------------------------------------------------------------------------
# financial_series / payback
# ---------------------------------------------------------------------------

def test_financial_series_uses_fallback_when_no_bills():
    records = _daily("2025-07-01", "2025-07-03", 10)
    cum, breakdown = metrics.financial_series(records, [], [], fallback_price=0.2)
    # 10 kWh × 0.2 = 2 CHF per day, cumulative 2/4/6
    assert cum[0]["revenue"] == 2
    assert cum[-1]["revenue"] == 6
    assert breakdown["total_revenue"] == 6


def test_financial_series_splits_covered_vs_uncovered():
    # Covered period 2025-08-01..02, uncovered 2025-08-03
    records = _daily("2025-08-01", "2025-08-03", 100)
    import_bills = [{
        "period_start": "2025-08-01", "period_end": "2025-08-02",
        "kwh": 10, "amount": 3.0,  # avg 0.30 CHF/kWh
    }]
    export_bills = [{
        "period_start": "2025-08-01", "period_end": "2025-08-02",
        "kwh": 50, "amount": 5.5,
    }]
    _, breakdown = metrics.financial_series(records, import_bills, export_bills, fallback_price=0.1)
    # PV in period = 200, exported 50, self_consumed 150
    # avg_import_price = 0.3
    # self savings = 150 × 0.3 = 45
    # export credit = 5.5
    # uncovered PV = 100, × 0.1 = 10
    # total = 45 + 5.5 + 10 = 60.5
    assert breakdown["avg_import_price"] == pytest.approx(0.3)
    assert breakdown["self_consumption_savings"] == 45
    assert breakdown["export_credit"] == 5.5
    assert breakdown["estimated_other"] == 10
    assert breakdown["total_revenue"] == pytest.approx(60.5)


def test_payback_no_records_returns_defaults():
    out = metrics.payback([], 10000, [], [], 0.2)
    assert out["invested"] == 10000
    assert out["revenue_total"] == 0
    assert out["remaining"] == 10000
    assert out["payback_date"] is None


def test_payback_projects_using_yearly_target_when_available():
    records = _daily("2025-01-01", "2025-01-10", 10)  # 100 kWh total
    pay = metrics.payback(records, 1000, [], [], 0.2, targets=GENERIC_TARGETS)
    assert pay["projection_basis"] == "targets"
    # yearly_yield_estimate = sum(generic) × blended (= fallback here)
    yearly = sum(t["kwh"] for t in GENERIC_TARGETS)
    assert pay["yearly_yield_estimate"] == pytest.approx(yearly * 0.2, rel=1e-3)


def test_payback_annual_return_is_yearly_yield_over_invested():
    records = _daily("2025-01-01", "2025-01-10", 10)
    pay = metrics.payback(records, 20000, [], [], 0.2, targets=GENERIC_TARGETS)
    yearly = sum(t["kwh"] for t in GENERIC_TARGETS) * 0.2
    assert pay["annual_return_pct"] == pytest.approx(yearly / 20000 * 100.0, rel=1e-3)


def test_payback_annual_return_is_none_without_targets():
    records = _daily("2025-01-01", "2025-01-10", 10)
    pay = metrics.payback(records, 20000, [], [], 0.2)
    assert pay["annual_return_pct"] is None


def test_payback_lcoe_divides_investment_by_lifetime_yield():
    records = _daily("2025-01-01", "2025-01-10", 10)
    pay = metrics.payback(records, 24000, [], [], 0.2, targets=GENERIC_TARGETS, lifetime_years=20)
    yearly_kwh = sum(t["kwh"] for t in GENERIC_TARGETS)
    assert pay["lifetime_years"] == 20
    assert pay["lifetime_yield_kwh"] == pytest.approx(yearly_kwh * 20)
    assert pay["lcoe"] == pytest.approx(24000 / (yearly_kwh * 20), rel=1e-3)


def test_payback_lcoe_defaults_to_25_years():
    records = _daily("2025-01-01", "2025-01-10", 10)
    pay = metrics.payback(records, 24000, [], [], 0.2, targets=GENERIC_TARGETS)
    yearly_kwh = sum(t["kwh"] for t in GENERIC_TARGETS)
    assert pay["lifetime_years"] == 25
    assert pay["lcoe"] == pytest.approx(24000 / (yearly_kwh * 25), rel=1e-3)


def test_payback_lcoe_is_none_without_targets():
    records = _daily("2025-01-01", "2025-01-10", 10)
    pay = metrics.payback(records, 24000, [], [], 0.2)
    assert pay["lcoe"] is None


def test_payback_lcoe_ignores_year_specific_targets():
    records = _daily("2025-01-01", "2025-01-10", 10)
    targets = GENERIC_TARGETS + [{"year": 2025, "month": 1, "kwh": 9999}]
    pay = metrics.payback(records, 24000, [], [], 0.2, targets=targets, lifetime_years=10)
    yearly_kwh = sum(t["kwh"] for t in GENERIC_TARGETS)
    assert pay["lifetime_yield_kwh"] == pytest.approx(yearly_kwh * 10)


def test_financial_series_subtracts_operating_cost_from_its_date():
    records = _daily("2025-01-01", "2025-01-04", 10)
    cum, breakdown = metrics.financial_series(
        records, [], [], fallback_price=0.2,
        operating_costs=[{"amount": 1.0, "date": "2025-01-03"}],
    )
    assert [row["revenue"] for row in cum] == [2, 4, 5, 7]
    assert breakdown["total_revenue"] == 8


def test_financial_series_undated_operating_cost_counts_from_the_start():
    records = _daily("2025-01-01", "2025-01-02", 10)
    cum, _ = metrics.financial_series(
        records, [], [], fallback_price=0.2,
        operating_costs=[{"amount": 1.0, "date": None}],
    )
    assert [row["revenue"] for row in cum] == [1, 3]


def test_payback_operating_costs_delay_the_payback_date():
    records = _daily("2025-01-01", "2025-12-31", 10)
    gross = metrics.payback(records, 700, [], [], 0.2)
    net = metrics.payback(
        records, 700, [], [], 0.2,
        operating_costs=[{"amount": 100.0, "date": "2025-01-01"}],
    )
    assert net["payback_date"] > gross["payback_date"]
    assert net["revenue_total"] == pytest.approx(gross["revenue_total"] - 100.0)
    assert net["remaining"] > gross["remaining"]
    assert net["progress_pct"] < gross["progress_pct"]


def test_payback_annual_return_is_net_of_operating_costs():
    records = _daily("2025-01-01", "2025-12-31", 10)
    pay = metrics.payback(
        records, 20000, [], [], 0.2, targets=GENERIC_TARGETS,
        operating_costs=[{"amount": 365.0, "date": "2025-01-01"}],
        start_date="2025-01-01",
    )
    yearly = sum(t["kwh"] for t in GENERIC_TARGETS) * 0.2
    assert pay["operating_cost_total"] == 365.0
    assert pay["annual_operating_cost"] == pytest.approx(365.0)
    assert pay["annual_return_pct"] == pytest.approx((yearly - 365.0) / 20000 * 100.0, rel=1e-3)


def test_payback_lcoe_adds_operating_costs_over_the_service_life():
    records = _daily("2025-01-01", "2025-12-31", 10)
    bare = metrics.payback(records, 24000, [], [], 0.2, targets=GENERIC_TARGETS, lifetime_years=20)
    pay = metrics.payback(
        records, 24000, [], [], 0.2, targets=GENERIC_TARGETS, lifetime_years=20,
        operating_costs=[{"amount": 200.0, "date": "2025-06-01"}],
        start_date="2025-01-01",
    )
    yearly_kwh = sum(t["kwh"] for t in GENERIC_TARGETS)
    assert pay["lcoe"] > bare["lcoe"]
    assert pay["lcoe"] == pytest.approx((24000 + 200.0 * 20) / (yearly_kwh * 20), rel=1e-3)


def test_payback_annual_operating_cost_spreads_over_the_runtime():
    records = _daily("2024-01-01", "2025-12-31", 10)
    pay = metrics.payback(
        records, 20000, [], [], 0.2, targets=GENERIC_TARGETS,
        operating_costs=[
            {"amount": 200.0, "date": "2024-01-01"},
            {"amount": 200.0, "date": "2025-01-01"},
        ],
        start_date="2024-01-01",
    )
    assert pay["annual_operating_cost"] == pytest.approx(400.0 / (731 / 365.0), rel=1e-3)


def test_payback_annual_operating_cost_uses_at_least_one_year():
    records = _daily("2025-01-01", "2025-03-31", 10)
    pay = metrics.payback(
        records, 5000, [], [], 0.2, targets=GENERIC_TARGETS,
        operating_costs=[{"amount": 300.0, "date": "2025-01-01"}],
        start_date="2025-01-01",
    )
    assert pay["annual_operating_cost"] == 300.0


def test_payback_without_operating_costs_matches_the_gross_formulas():
    records = _daily("2025-01-01", "2025-01-10", 10)
    base = metrics.payback(records, 24000, [], [], 0.2, targets=GENERIC_TARGETS)
    assert base == metrics.payback(
        records, 24000, [], [], 0.2, targets=GENERIC_TARGETS, operating_costs=[]
    )
    yearly_kwh = sum(t["kwh"] for t in GENERIC_TARGETS)
    assert base["operating_cost_total"] == 0.0
    assert base["annual_operating_cost"] == 0.0
    assert base["revenue_total"] == pytest.approx(20.0)
    assert base["annual_return_pct"] == pytest.approx(yearly_kwh * 0.2 / 24000 * 100.0, rel=1e-3)
    assert base["lcoe"] == pytest.approx(24000 / (yearly_kwh * 25), rel=1e-3)


# ---------------------------------------------------------------------------
# monthly_flows
# ---------------------------------------------------------------------------

def test_monthly_flows_splits_quarterly_bill_into_months():
    # One export bill covering Aug-Sep with uniform PV → each month
    # gets half of the exported kWh.
    records = _daily("2025-08-01", "2025-09-30", 10)
    export_bills = [{
        "period_start": "2025-08-01", "period_end": "2025-09-30",
        "kwh": 600, "amount": 66,
    }]
    import_bills = [{
        "period_start": "2025-08-01", "period_end": "2025-09-30",
        "kwh": 400, "amount": 100,
    }]
    flows = metrics.monthly_flows(records, import_bills, export_bills, avg_import_price=0.25)
    assert len(flows) == 2
    aug, sep = flows
    # Aug has 31 days × 10 = 310 kWh PV, Sep 30 × 10 = 300. Shares:
    # Aug 310/610 ≈ 50.82 %, Sep 300/610 ≈ 49.18 %.
    assert aug["label"] == "Aug 2025"
    assert aug["pv_kwh"] == 310
    assert aug["exported_kwh"] == pytest.approx(600 * 310 / 610, rel=1e-3)
    # Imports are day-based (31/61 in Aug, 30/61 in Sep)
    assert aug["imported_kwh"] == pytest.approx(400 * 31 / 61, rel=1e-3)
    assert sep["imported_kwh"] == pytest.approx(400 * 30 / 61, rel=1e-3)


def test_monthly_flows_empty_without_bills():
    records = _daily("2025-01-01", "2025-01-05", 10)
    flows = metrics.monthly_flows(records, [], [], avg_import_price=0.25)
    assert flows == []


# ---------------------------------------------------------------------------
# cumulative / rolling_avg
# ---------------------------------------------------------------------------

def test_cumulative_runs_sum():
    assert metrics.cumulative([10, 20, 30]) == [10, 30, 60]


def test_rolling_avg_none_until_full_window():
    vals = [10, 20, 30, 40, 50, 60, 70]
    out = metrics.rolling_avg(vals, window=3)
    assert out[0] is None
    assert out[1] is None
    assert out[2] == pytest.approx((10 + 20 + 30) / 3)
    assert out[-1] == pytest.approx((50 + 60 + 70) / 3)


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def test_summary_past_year_uses_full_targets():
    records = _daily("2020-01-01", "2020-12-31", 5)
    summ = metrics.summary(records, GENERIC_TARGETS, 2020, kwp=10)
    # 366 (leap) × 5 = 1830; but our _daily uses Jan 1 - Dec 31 = 366 days for 2020
    assert summ["ytd_actual"] == pytest.approx(1830)
    assert summ["ytd_target"] == sum(t["kwh"] for t in GENERIC_TARGETS)
    assert summ["specific_yield"] == pytest.approx(183.0, rel=1e-3)


def test_summary_future_year_has_zero_target():
    future = date.today().year + 10
    summ = metrics.summary([], GENERIC_TARGETS, future, kwp=10)
    assert summ["ytd_target"] == 0


def test_summary_specific_yield_annual_normalizes_the_span():
    records = _daily("2024-01-01", "2025-12-31", 5)
    summ = metrics.summary(records, GENERIC_TARGETS, "all", kwp=10)
    # 731 days x 5 kWh / 10 kWp = 365.5 kWh/kWp over the whole span, ~182.5 per year
    assert summ["specific_yield"] == pytest.approx(365.5, rel=1e-3)
    assert summ["specific_yield_annual"] == pytest.approx(182.5, rel=1e-2)


# ---------------------------------------------------------------------------
# year_end_forecast
# ---------------------------------------------------------------------------

FORECAST_TODAY = date(2025, 7, 1)
HALF_YEAR_ON_TARGET = [
    {"date": f"2025-{m:02d}-15", "kwh": kwh}
    for m, kwh in enumerate([300, 500, 900, 1200, 1500, 1600], start=1)
]
ANNUAL_TARGET = sum(t["kwh"] for t in GENERIC_TARGETS)


def test_year_end_forecast_on_target_pace_reaches_the_annual_target():
    f = metrics.year_end_forecast(HALF_YEAR_ON_TARGET, GENERIC_TARGETS, 2025, today=FORECAST_TODAY)
    assert f["year_end_target"] == pytest.approx(ANNUAL_TARGET)
    assert f["pace_pct"] == pytest.approx(100.0, abs=2.0)
    assert f["year_end_kwh"] == pytest.approx(ANNUAL_TARGET, rel=0.02)
    assert f["from_month"] == 7


def test_year_end_forecast_scales_with_the_pace_so_far():
    half = [{**r, "kwh": r["kwh"] / 2} for r in HALF_YEAR_ON_TARGET]
    f = metrics.year_end_forecast(half, GENERIC_TARGETS, 2025, today=FORECAST_TODAY)
    assert f["pace_pct"] == pytest.approx(50.0, abs=2.0)
    assert f["year_end_kwh"] == pytest.approx(ANNUAL_TARGET * 0.5, rel=0.05)


def test_year_end_forecast_keeps_closed_months_as_actuals():
    f = metrics.year_end_forecast(HALF_YEAR_ON_TARGET, GENERIC_TARGETS, 2025, today=FORECAST_TODAY)
    assert f["monthly"][:6] == [300, 500, 900, 1200, 1500, 1600]


def test_year_end_forecast_honors_the_commissioning_date():
    f = metrics.year_end_forecast(
        HALF_YEAR_ON_TARGET, GENERIC_TARGETS, 2025,
        start_date="2025-04-01", today=FORECAST_TODAY,
    )
    assert f["cumulative_target"][2] == 0.0
    assert f["year_end_target"] < ANNUAL_TARGET


def test_year_end_forecast_only_for_the_current_year_with_targets():
    assert metrics.year_end_forecast(HALF_YEAR_ON_TARGET, GENERIC_TARGETS, "all", today=FORECAST_TODAY) is None
    assert metrics.year_end_forecast(HALF_YEAR_ON_TARGET, GENERIC_TARGETS, 2024, today=FORECAST_TODAY) is None
    assert metrics.year_end_forecast(HALF_YEAR_ON_TARGET, [], 2025, today=FORECAST_TODAY) is None


# ---------------------------------------------------------------------------
# monthly_band
# ---------------------------------------------------------------------------

def test_monthly_band_is_none_without_a_prior_year():
    records = _daily("2026-01-01", "2026-09-30", 10)
    assert metrics.monthly_band(records, today=date(2026, 10, 5)) is None


def test_monthly_band_needs_two_prior_years_for_a_corridor():
    records = _daily("2025-08-01", "2025-12-31", 10) + _daily("2026-01-01", "2026-02-28", 20)
    assert metrics.monthly_band(records, today=date(2026, 3, 15)) is None


def test_monthly_band_ignores_months_without_prior_year_data():
    records = (
        _daily("2024-01-01", "2024-12-31", 10)
        + _daily("2025-08-01", "2025-12-31", 20)
        + _daily("2026-01-01", "2026-06-30", 30)
    )
    band = metrics.monthly_band(records, today=date(2026, 7, 15))
    assert band["prior_years"] == [2024, 2025]
    assert band["months"] == list(range(1, 13))
    assert band["min"][0] == pytest.approx(310)
    assert band["max"][0] == pytest.approx(310)
    assert band["min"][7] == pytest.approx(310)
    assert band["max"][7] == pytest.approx(620)
    assert band["median"][7] == pytest.approx(465)
    assert band["current"][0] == pytest.approx(930)
    assert band["current"][6] is None


# ---------------------------------------------------------------------------
# degradation
# ---------------------------------------------------------------------------

def test_degradation_needs_enough_shared_full_months():
    records = _daily("2025-09-01", "2025-12-31", 10) + _daily("2026-09-01", "2026-12-31", 9)
    assert metrics.degradation(records, kwp=10) is None


def test_degradation_is_none_without_kwp():
    records = _daily("2025-01-01", "2025-12-31", 10) + _daily("2026-01-01", "2026-12-31", 9)
    assert metrics.degradation(records, kwp=0) is None


def test_degradation_compares_the_same_full_months():
    records = _daily("2025-01-01", "2025-12-31", 10) + _daily("2026-01-01", "2026-12-31", 9)
    deg = metrics.degradation(records, kwp=10)
    assert deg["from_year"] == 2025
    assert deg["to_year"] == 2026
    assert deg["month_count"] == 12
    assert deg["from_specific_yield"] == pytest.approx(365.0)
    assert deg["to_specific_yield"] == pytest.approx(328.5)
    assert deg["pct_per_year"] == pytest.approx(-10.0, abs=0.01)


def test_degradation_skips_months_that_are_incomplete_in_one_year():
    records = (
        _daily("2025-01-01", "2025-12-31", 10)
        + _daily("2026-01-01", "2026-06-30", 9)
        + _daily("2026-07-02", "2026-12-31", 9)
    )
    deg = metrics.degradation(records, kwp=10)
    assert deg["month_count"] == 11
    assert 7 not in deg["months"]
    assert deg["pct_per_year"] == pytest.approx(-10.0, abs=0.01)


def test_degradation_annualizes_over_a_multi_year_span():
    records = _daily("2023-01-01", "2023-12-31", 10) + _daily("2025-01-01", "2025-12-31", 8.1)
    deg = metrics.degradation(records, kwp=10)
    assert deg["from_year"] == 2023
    assert deg["to_year"] == 2025
    assert deg["month_count"] == 12
    assert deg["pct_per_year"] == pytest.approx(-10.0, abs=0.01)
