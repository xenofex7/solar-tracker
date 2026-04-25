import html
import json
import logging
import os
import re
import time
from datetime import date, datetime
from zoneinfo import available_timezones

from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for

import db
import i18n
import metrics
from ha_client import DEFAULT_TZ, HAClientError, fetch_daily

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)
db.init_db()

try:
    with open(os.path.join(os.path.dirname(__file__), "VERSION"), encoding="utf-8") as _vf:
        APP_VERSION = _vf.read().strip()
except OSError:
    APP_VERSION = "dev"


@app.context_processor
def _inject_version():
    return {"app_version": APP_VERSION}


@app.context_processor
def _inject_i18n():
    lang = i18n.get_lang(request)
    return {"lang": lang, "T": i18n.get_translations(lang)}


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    return response


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
        return f"{float(value):,.0f}".replace(",", "'")
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


def _timezone() -> str:
    return (db.get_setting("timezone") or DEFAULT_TZ).strip() or DEFAULT_TZ


def _start_date() -> str | None:
    val = (db.get_setting("start_date") or "").strip()
    if not val:
        return None
    try:
        datetime.fromisoformat(val)
    except ValueError:
        return None
    return val


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
        start_date=_start_date() or "",
        timezone=_timezone(),
        timezones=sorted(available_timezones()),
        costs=db.list_costs(),
        total_invested=db.total_invested(),
        recent=recent,
        grid_imports=db.list_grid_bills("import"),
        grid_exports=db.list_grid_bills("export"),
        grid_totals=db.grid_totals(),
        ha_url=os.environ.get("HA_URL", ""),
        ha_entity=os.environ.get("HA_ENTITY_ID", ""),
    )


@app.route("/set-lang")
def set_lang():
    lang = request.args.get("lang", i18n.FALLBACK)
    if lang not in i18n.SUPPORTED:
        lang = i18n.FALLBACK
    next_url = url_for("dashboard")
    resp = make_response(redirect(next_url))
    resp.set_cookie("lang", lang, max_age=365 * 24 * 3600, samesite="Lax")
    return resp


def _render_changelog_md(md: str) -> str:
    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        return text

    out: list[str] = []
    in_list = False
    in_para: list[str] = []

    def flush_para() -> None:
        if in_para:
            out.append(f"<p>{' '.join(in_para)}</p>")
            in_para.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw_line in md.splitlines():
        line = raw_line.rstrip()
        if not line:
            flush_para()
            close_list()
            continue
        if line.startswith("# "):
            flush_para()
            close_list()
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_para()
            close_list()
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            flush_para()
            close_list()
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("- "):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
        else:
            close_list()
            in_para.append(inline(line))

    flush_para()
    close_list()
    return "\n".join(out)


@app.route("/api/changelog")
def api_changelog():
    path = os.path.join(os.path.dirname(__file__), "CHANGELOG.md")
    try:
        with open(path, encoding="utf-8") as f:
            md = f.read()
    except OSError:
        return jsonify({"html": ""})
    return jsonify({"html": _render_changelog_md(md)})


@app.route("/i18n.js")
def i18n_js():
    lang = i18n.get_lang(request)
    translations = i18n.get_translations(lang)
    js = f"window.T={json.dumps(translations, ensure_ascii=False, separators=(',', ':'))};"
    resp = make_response(js)
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store"
    return resp


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
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    payload = request.get_json(force=True)
    if "timezone" in payload:
        try:
            ZoneInfo(str(payload["timezone"]))
        except ZoneInfoNotFoundError:
            return jsonify({"error": f"Unbekannte Zeitzone: {payload['timezone']}"}), 400
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

    t0 = time.perf_counter()
    try:
        daily = fetch_daily(start, end, tz=_timezone())
    except HAClientError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": f"Unerwarteter Fehler: {e}"}), 500
    t_fetch = time.perf_counter() - t0

    t1 = time.perf_counter()
    items = [(d, round(kwh, 3)) for d, kwh in daily.items()]
    inserted, updated = db.bulk_upsert_production(items, source="home_assistant")
    t_write = time.perf_counter() - t1

    app.logger.info(
        "HA sync %s..%s: %d days (ins=%d, upd=%d) - fetch %.2fs, write %.2fs",
        start, end, len(items), inserted, updated, t_fetch, t_write,
    )

    return jsonify({
        "ok": True,
        "inserted": inserted,
        "updated": updated,
        "days": inserted + updated,
        "timings": {"fetch_s": round(t_fetch, 2), "write_s": round(t_write, 2)},
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


@app.route("/api/costs/<int:cost_id>", methods=["PUT"])
def api_costs_put(cost_id):
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
    if not db.update_cost(cost_id, label, amount, cdate):
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify({"ok": True})


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


@app.route("/api/grid/<int:bill_id>", methods=["PUT"])
def api_grid_put(bill_id):
    payload = request.get_json(force=True)
    period_start = (payload.get("period_start") or "").strip()
    period_end = (payload.get("period_end") or "").strip()
    invoice_no = (payload.get("invoice_no") or "").strip() or None
    try:
        datetime.fromisoformat(period_start)
        datetime.fromisoformat(period_end)
        kwh = float(payload.get("kwh"))
        amount = float(payload.get("amount_chf"))
    except (TypeError, ValueError):
        return jsonify({"error": "ungültige Werte"}), 400
    if period_end < period_start or kwh < 0 or amount < 0:
        return jsonify({"error": "ungültige Werte"}), 400
    if not db.update_grid_bill(bill_id, period_start, period_end, kwh, amount, invoice_no):
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify({"ok": True})


@app.route("/api/grid/<int:bill_id>", methods=["DELETE"])
def api_grid_delete(bill_id):
    db.delete_grid_bill(bill_id)
    return jsonify({"ok": True})


@app.route("/api/summary")
def api_summary():
    year_param = request.args.get("year", str(date.today().year))
    if year_param == "all":
        year = "all"
    else:
        try:
            year = int(year_param)
        except ValueError:
            year = date.today().year
    records = db.get_production()
    start_date = _start_date()
    if start_date:
        records = [r for r in records if r["date"] >= start_date]
    targets = db.get_targets()
    kwp = _kwp()
    price = _price_per_kwh()
    invested = db.total_invested()

    actual = metrics.monthly_actual(records, year)
    years_in_data = metrics.years_in_records(records)
    multiplier = len(years_in_data) if year == "all" else 1
    target = metrics.monthly_targets(
        targets, year, multiplier=multiplier,
        start_date=start_date, years_available=years_in_data,
    )
    dev = metrics.deviation_pct(actual, target)
    cum_a = metrics.cumulative(actual)
    cum_t = metrics.cumulative(target)
    daily = metrics.daily_series(records, year)
    daily_vals = [r["kwh"] for r in daily]
    roll = metrics.rolling_avg(daily_vals, window=7)
    dist = metrics.monthly_distribution(records, year)
    tops = metrics.top_days(records, year, n=5)
    day_qual = metrics.day_quality_distribution(records, year)
    year_cmp = metrics.year_comparison(records)
    spec_yield_cmp = {
        y: [round(v / kwp, 2) if kwp > 0 else 0 for v in vals]
        for y, vals in year_cmp.items()
    }
    heat = metrics.heatmap_data(records, year)
    summ = metrics.summary(records, targets, year, kwp, start_date=start_date)
    imports = db.list_grid_bills("import")
    exports = db.list_grid_bills("export")
    cum_rev = metrics.cumulative_revenue(records, imports, exports, price)
    pay = metrics.payback(records, invested, imports, exports, price, targets=targets)
    if start_date:
        pay["start_date"] = start_date
    sc = metrics.self_consumption(records, exports)
    grid_tot = db.grid_totals()
    avg_import_price = grid_tot.get("import", {}).get("avg_price") or price
    flows = metrics.monthly_flows(records, imports, exports, avg_import_price)
    if start_date:
        flows = [f for f in flows if f["period_end"] >= start_date]
    if isinstance(year, int):
        flows = [f for f in flows if f["year"] == year]
        imp_kwh = sum(f["imported_kwh"] for f in flows)
        imp_amt = sum(f["import_cost"] for f in flows)
        exp_kwh = sum(f["exported_kwh"] for f in flows)
        exp_amt = sum(f["export_credit"] for f in flows)
        pv_in_flows = sum(f["pv_kwh"] for f in flows)
        sc_kwh = sum(f["self_consumed_kwh"] for f in flows)
        grid_tot = {
            "import": {
                "kwh": round(imp_kwh, 2),
                "amount": round(imp_amt, 2),
                "avg_price": (imp_amt / imp_kwh) if imp_kwh else 0.0,
            },
            "export": {
                "kwh": round(exp_kwh, 2),
                "amount": round(exp_amt, 2),
                "avg_price": (exp_amt / exp_kwh) if exp_kwh else 0.0,
            },
            "net_cost": round(imp_amt - exp_amt, 2),
        }
        sc = {
            "pv_in_export_periods": round(pv_in_flows, 2),
            "exported_kwh": round(exp_kwh, 2),
            "self_consumed_kwh": round(sc_kwh, 2),
            "self_consumption_pct": round((sc_kwh / pv_in_flows * 100.0) if pv_in_flows > 0 else 0.0, 1),
        }
    sc["savings_vs_no_pv"] = round(sc["self_consumed_kwh"] * grid_tot["import"]["avg_price"], 2)
    consumption = sc["self_consumed_kwh"] + grid_tot["import"]["kwh"]
    sc["effective_price_per_kwh"] = round(grid_tot["net_cost"] / consumption, 4) if consumption > 0 else 0.0
    sc["total_consumption_kwh"] = round(consumption, 2)

    return jsonify({
        "year": year,
        "months": list(range(1, 13)),
        "monthly_actual": [round(v, 2) for v in actual],
        "monthly_target": [round(v, 2) for v in target],
        "deviation_pct": dev,
        "cumulative_actual": cum_a,
        "cumulative_target": cum_t,
        "daily": daily,
        "rolling_avg_7d": roll,
        "monthly_distribution": dist,
        "top_days": tops,
        "day_quality": day_qual,
        "year_comparison": year_cmp,
        "specific_yield_comparison": spec_yield_cmp,
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
            "periods": flows,
        },
        "available_years": db.available_years(),
    })


def main():
    port = int(os.environ.get("PORT") or os.environ.get("FLASK_PORT") or "5000")
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
