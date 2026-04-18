import os
from datetime import date, datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

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


@app.route("/")
def dashboard():
    years = db.available_years() or [date.today().year]
    return render_template("dashboard.html", years=years, current_year=years[-1])


@app.route("/settings")
def settings_page():
    targets = db.get_targets()
    return render_template(
        "settings.html",
        targets=targets,
        kwp=_kwp(),
        ha_url=os.environ.get("HA_URL", ""),
        ha_entity=os.environ.get("HA_ENTITY_ID", ""),
    )


@app.route("/entry")
def entry_page():
    recent = db.get_production()[-30:]
    return render_template("entry.html", recent=list(reversed(recent)))


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


@app.route("/api/summary")
def api_summary():
    year = int(request.args.get("year", date.today().year))
    records = db.get_production()
    targets = db.get_targets()
    kwp = _kwp()

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
        "available_years": db.available_years(),
    })


def main():
    db.init_db()
    port = int(os.environ.get("PORT") or os.environ.get("FLASK_PORT") or "5000")
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="127.0.0.1", port=port, debug=debug)


if __name__ == "__main__":
    main()
