import os
from datetime import date, datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for

import db
import metrics
from ha_client import HAClientError, fetch_daily

load_dotenv()

app = Flask(__name__)


@app.template_filter("ddmmyyyy")
def _fmt_ddmmyyyy(value):
    if not value:
        return ""
    s = str(value)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
    return s


@app.template_filter("chf")
def _fmt_chf(value):
    try:
        return "{:,.0f}".format(float(value)).replace(",", "'")
    except (TypeError, ValueError):
        return value


def _kwp() -> float:
    val = db.get_setting("kwp") or os.environ.get("PLANT_KWP", "0")
    try:
        return float(val)
    except ValueError:
        return 0.0


def _price_per_kwh() -> float:
    val = db.get_setting("price_per_kwh") or "0"
    try:
        return float(val)
    except ValueError:
        return 0.0


@app.route("/")
def dashboard():
    years = db.available_years() or [date.today().year]
    return render_template("dashboard.html", years=years, current_year=years[-1])


@app.route("/settings")
def settings_page():
    targets = db.get_targets()
    recent = list(reversed(db.get_production()[-30:]))
    return render_template(
        "settings.html",
        targets=targets,
        kwp=_kwp(),
        price_per_kwh=_price_per_kwh(),
        costs=db.list_costs(),
        total_invested=db.total_invested(),
        recent=recent,
        grid_imports=db.list_grid_bills("import"),
        grid_exports=db.list_grid_bills("export"),
        grid_totals=db.grid_totals(),
        ha_url=os.environ.get("HA_URL", ""),
        ha_entity=os.environ.get("HA_ENTITY_ID", ""),
    )


@app.route("/entry")
def entry_page():
    return redirect(url_for("settings_page") + "#entry", code=301)


@app.route("/api/production", methods=["GET"])
def api_production():
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    return jsonify(db.get_production(date_from, date_to))


@app.route("/api/production", methods=["POST"])
def api_production_post():
    payload = request.get_json(force=True)
    d = payload.get("date")
    kwh = payload.get("kwh")
    if not d or kwh is None:
        return jsonify({"error": "date und kwh erforderlich"}), 400
    try:
        datetime.fromisoformat(d)
        kwh = float(kwh)
    except (ValueError, TypeError):
        return jsonify({"error": "ungültiges Format"}), 400
    if kwh < 0:
        return jsonify({"error": "kwh muss >= 0 sein"}), 400
    db.upsert_production(d, kwh, source="manual")
    return jsonify({"ok": True})


@app.route("/api/production/<date_str>", methods=["DELETE"])
def api_production_delete(date_str):
    db.delete_production(date_str)
    return jsonify({"ok": True})


@app.route("/api/targets", methods=["GET"])
def api_targets_get():
    return jsonify(db.get_targets())


@app.route("/api/targets", methods=["POST"])
def api_targets_post():
    payload = request.get_json(force=True)
    month = payload.get("month")
    kwh = payload.get("kwh")
    year = payload.get("year")
    if month is None or kwh is None:
        return jsonify({"error": "month und kwh erforderlich"}), 400
    try:
        month = int(month)
        kwh = float(kwh)
        year = int(year) if year not in (None, "", "null") else None
    except (ValueError, TypeError):
        return jsonify({"error": "ungültiges Format"}), 400
    if not (1 <= month <= 12) or kwh < 0:
        return jsonify({"error": "ungültige Werte"}), 400
    db.set_target(month, kwh, year)
    return jsonify({"ok": True})


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    payload = request.get_json(force=True)
    for key, value in payload.items():
        db.set_setting(key, str(value))
    return jsonify({"ok": True})


@app.route("/api/sync/ha", methods=["POST"])
def api_sync_ha():
    payload = request.get_json(force=True) or {}
    start = payload.get("from")
    end = payload.get("to") or date.today().isoformat()
    if not start:
        return jsonify({"error": "'from' erforderlich (YYYY-MM-DD)"}), 400
    try:
        daily = fetch_daily(start, end)
    except HAClientError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": f"Unerwarteter Fehler: {e}"}), 500

    inserted = 0
    updated = 0
    for d, kwh in daily.items():
        result = db.upsert_production(d, round(kwh, 3), source="home_assistant")
        if result == "inserted":
            inserted += 1
        else:
            updated += 1
    return jsonify({
        "ok": True,
        "inserted": inserted,
        "updated": updated,
        "days": inserted + updated,
    })


@app.route("/api/costs", methods=["GET"])
def api_costs_get():
    return jsonify({
        "items": db.list_costs(),
        "total": round(db.total_invested(), 2),
    })


@app.route("/api/costs", methods=["POST"])
def api_costs_post():
    payload = request.get_json(force=True)
    label = (payload.get("label") or "").strip()
    amount = payload.get("amount_chf")
    cdate = payload.get("date") or None
    if not label or amount is None:
        return jsonify({"error": "label und amount_chf erforderlich"}), 400
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "ungültiger Betrag"}), 400
    if cdate:
        try:
            datetime.fromisoformat(cdate)
        except ValueError:
            return jsonify({"error": "ungültiges Datum"}), 400
    new_id = db.add_cost(label, amount, cdate)
    return jsonify({"ok": True, "id": new_id})


@app.route("/api/costs/<int:cost_id>", methods=["DELETE"])
def api_costs_delete(cost_id):
    db.delete_cost(cost_id)
    return jsonify({"ok": True})


@app.route("/api/grid", methods=["GET"])
def api_grid_get():
    return jsonify({
        "imports": db.list_grid_bills("import"),
        "exports": db.list_grid_bills("export"),
        "totals": db.grid_totals(),
    })


@app.route("/api/grid", methods=["POST"])
def api_grid_post():
    payload = request.get_json(force=True)
    kind = (payload.get("kind") or "").strip()
    period_start = (payload.get("period_start") or "").strip()
    period_end = (payload.get("period_end") or "").strip()
    invoice_no = (payload.get("invoice_no") or "").strip() or None
    if kind not in ("import", "export"):
        return jsonify({"error": "kind muss 'import' oder 'export' sein"}), 400
    try:
        datetime.fromisoformat(period_start)
        datetime.fromisoformat(period_end)
        kwh = float(payload.get("kwh"))
        amount = float(payload.get("amount_chf"))
    except (TypeError, ValueError):
        return jsonify({"error": "ungültige Werte"}), 400
    if period_end < period_start or kwh < 0 or amount < 0:
        return jsonify({"error": "ungültige Werte"}), 400
    new_id = db.upsert_grid_bill(kind, period_start, period_end, kwh, amount, invoice_no)
    return jsonify({"ok": True, "id": new_id})


@app.route("/api/grid/<int:bill_id>", methods=["DELETE"])
def api_grid_delete(bill_id):
    db.delete_grid_bill(bill_id)
    return jsonify({"ok": True})


@app.route("/api/summary")
def api_summary():
    year = int(request.args.get("year", date.today().year))
    records = db.get_production()
    targets = db.get_targets()
    kwp = _kwp()
    price = _price_per_kwh()
    invested = db.total_invested()

    actual = metrics.monthly_actual(records, year)
    target = metrics.monthly_targets(targets, year)
    dev = metrics.deviation_pct(actual, target)
    cum_a = metrics.cumulative(actual)
    cum_t = metrics.cumulative(target)
    daily = metrics.daily_series(records, year)
    daily_vals = [r["kwh"] for r in daily]
    roll = metrics.rolling_avg(daily_vals, window=7)
    dist = metrics.monthly_distribution(records, year)
    tops = metrics.top_days(records, year, n=5)
    year_cmp = metrics.year_comparison(records)
    heat = metrics.heatmap_data(records, year)
    summ = metrics.summary(records, targets, year, kwp)
    imports = db.list_grid_bills("import")
    exports = db.list_grid_bills("export")
    cum_rev = metrics.cumulative_revenue(records, imports, exports, price)
    pay = metrics.payback(records, invested, imports, exports, price)
    sc = metrics.self_consumption(records, exports)
    grid_tot = db.grid_totals()

    return jsonify({
        "year": year,
        "months": metrics.MONTHS_DE,
        "monthly_actual": [round(v, 2) for v in actual],
        "monthly_target": [round(v, 2) for v in target],
        "deviation_pct": dev,
        "cumulative_actual": cum_a,
        "cumulative_target": cum_t,
        "daily": daily,
        "rolling_avg_7d": roll,
        "monthly_distribution": dist,
        "top_flop": tops,
        "year_comparison": year_cmp,
        "heatmap": heat,
        "summary": summ,
        "finance": {
            "price_per_kwh": price,
            "cumulative_revenue": cum_rev,
            "payback": pay,
        },
        "grid": {
            "totals": grid_tot,
            "self_consumption": sc,
        },
        "available_years": db.available_years(),
    })


def main():
    db.init_db()
    port = int(os.environ.get("PORT") or os.environ.get("FLASK_PORT") or "5000")
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="127.0.0.1", port=port, debug=debug)


if __name__ == "__main__":
    main()
