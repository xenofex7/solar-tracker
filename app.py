import html
import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import available_timezones

from dotenv import load_dotenv
from flask import (
    Flask,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

import auth
import db
import i18n
import metrics
import telemetry
from ha_client import DEFAULT_TZ, HAClientError, fetch_daily
from solarweb_client import SolarwebClientError
from solarweb_client import fetch_daily as solarweb_fetch_daily

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)
db.init_db()
auth.ensure_default_admin()
app.secret_key = auth.get_or_create_secret_key()
app.permanent_session_lifetime = timedelta(days=30)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
    # Sliding window: re-issue the session cookie with a fresh Max-Age on
    # every authenticated request, so active users never get logged out
    # within the 30-day window. After 30 days of inactivity, the cookie
    # expires. This is Flask's default but we set it explicitly to lock
    # the behavior in.
    SESSION_REFRESH_EACH_REQUEST=True,
)

try:
    with open(os.path.join(os.path.dirname(__file__), "VERSION"), encoding="utf-8") as _vf:
        APP_VERSION = _vf.read().strip()
except OSError:
    APP_VERSION = "dev"

telemetry.init(APP_VERSION)


_PUBLIC_PATHS = {"/login", "/set-lang", "/i18n.js"}


@app.before_request
def _load_user():
    g.user = auth.load_current_user()
    path = request.path
    if path in _PUBLIC_PATHS or path.startswith("/static/"):
        return None
    if g.user is None:
        if path.startswith("/api/"):
            return jsonify({"error": "authentication required"}), 401
        return redirect(url_for("login_page", next=path))
    return None


@app.context_processor
def _inject_version():
    return {"app_version": APP_VERSION}


@app.context_processor
def _inject_user():
    user = getattr(g, "user", None)
    return {
        "current_user": user,
        "is_admin": bool(user and user["role"] == auth.ROLE_ADMIN),
    }


_CURRENCY_LOCALE_FMT = {
    "CHF": ("'", "."),
    "EUR": (".", ","),
    "USD": (",", "."),
    "GBP": (",", "."),
    "JPY": (",", "."),
    "CNY": (",", "."),
    "AUD": (",", "."),
    "CAD": (",", "."),
    "SEK": (" ", ","),
    "NOK": (" ", ","),
    "DKK": (".", ","),
    "PLN": (" ", ","),
    "CZK": (" ", ","),
}

_LANG_LOCALE_FMT = {
    "en": (",", "."),
    "de": ("'", "."),
    "fr": (" ", ","),
    "es": (".", ","),
    "it": (".", ","),
}


def _format_with_seps(value, sep_t, sep_d, decimals):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value
    s = f"{v:,.{decimals}f}"
    return s.replace(",", "\x00").replace(".", sep_d).replace("\x00", sep_t)


def _fmt_money_value(value, currency, decimals=0):
    sep_t, sep_d = _CURRENCY_LOCALE_FMT.get((currency or "").upper(), ("'", "."))
    return _format_with_seps(value, sep_t, sep_d, decimals)


def _fmt_num_value(value, lang, decimals=0):
    sep_t, sep_d = _LANG_LOCALE_FMT.get(lang, ("'", "."))
    return _format_with_seps(value, sep_t, sep_d, decimals)


@app.context_processor
def _inject_i18n():
    lang = i18n.get_lang(request)
    cur = _currency()
    return {
        "lang": lang,
        "T": i18n.get_translations(lang),
        "currency": cur,
        "fmt_money": lambda v, decimals=0: _fmt_money_value(v, cur, decimals),
        "fmt_num": lambda v, decimals=0: _fmt_num_value(v, lang, decimals),
    }


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


def _currency() -> str:
    val = (db.get_setting("currency") or "CHF").strip()
    return val or "CHF"


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


_VALID_USERNAME = re.compile(r"^[a-zA-Z0-9_.-]{2,32}$")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    next_url = request.args.get("next") or request.form.get("next") or url_for("dashboard")
    # Don't bounce off-site after login.
    if not next_url.startswith("/"):
        next_url = url_for("dashboard")

    if g.user is not None:
        return redirect(next_url)

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.get_user_by_name(username)
        if user and user["password_hash"] and auth.verify_password(password, user["password_hash"]):
            auth.login(user)
            return redirect(next_url)
        error = "login_failed"

    return render_template("login.html", error=error, next_url=next_url), (
        401 if error else 200
    )


@app.route("/logout", methods=["POST", "GET"])
def logout_page():
    auth.logout()
    return redirect(url_for("login_page"))


@app.route("/api/users", methods=["GET"])
@auth.require_role(auth.ROLE_ADMIN)
def api_users_list():
    return jsonify({"items": db.list_users()})


@app.route("/api/users", methods=["POST"])
@auth.require_role(auth.ROLE_ADMIN)
def api_users_create():
    payload = request.get_json(force=True) or {}
    username = (payload.get("username") or "").strip()
    role = (payload.get("role") or "").strip()
    password = payload.get("password") or ""

    # Lockout guard: as soon as a second user exists, zero-config auto-login
    # is disabled. If the calling admin has no password, they would be locked
    # out the moment they finish this request. Force them to secure their own
    # account first.
    caller = auth.current_user()
    if caller and not caller["password_hash"]:
        return jsonify({"error": "set_own_password_first"}), 400

    if not _VALID_USERNAME.match(username):
        return jsonify({"error": "invalid_username"}), 400
    if role not in auth.ROLES:
        return jsonify({"error": "invalid_role"}), 400
    # A user without a password can never log in, and a second passwordless
    # user disables the zero-config auto-login -> guaranteed lockout. The
    # only legitimate passwordless user is the seeded default admin, which
    # is created server-side, never via this endpoint.
    if not password:
        return jsonify({"error": "password_required"}), 400
    if db.get_user_by_name(username):
        return jsonify({"error": "username_taken"}), 409
    new_id = db.create_user(username, role, auth.hash_password(password))
    return jsonify({"ok": True, "id": new_id})


@app.route("/api/users/<int:user_id>", methods=["PUT"])
@auth.require_role(auth.ROLE_ADMIN)
def api_users_update(user_id):
    payload = request.get_json(force=True) or {}
    target = db.get_user_by_id(user_id)
    if not target:
        return jsonify({"error": "not_found"}), 404

    role = payload.get("role")
    password = payload.get("password")
    clear_password = bool(payload.get("clear_password"))

    if role is not None and role not in auth.ROLES:
        return jsonify({"error": "invalid_role"}), 400

    # Don't strand the platform without an admin.
    if role and role != auth.ROLE_ADMIN and target["role"] == auth.ROLE_ADMIN and db.count_admins() <= 1:
        return jsonify({"error": "cannot_demote_last_admin"}), 400

    # Effective post-update state, used for the reachability invariant below.
    effective_role = role or target["role"]
    will_have_password = bool(password) or (
        bool(target["password_hash"]) and not clear_password
    )

    # A passwordless admin is only allowed in zero-config auto-login mode
    # (the single seeded user). With any other user around it is either a
    # platform lockout, or - if another admin still has a password - a
    # zombie admin that can never log in. Demote or delete first instead.
    if (
        effective_role == auth.ROLE_ADMIN
        and not will_have_password
        and db.count_users() != 1
    ):
        return jsonify({"error": "would_lock_platform"}), 400

    pw_hash = None
    if password:
        pw_hash = auth.hash_password(password)

    if not db.update_user(
        user_id,
        role=role,
        password_hash=pw_hash,
        clear_password=clear_password and not password,
    ):
        return jsonify({"error": "no_change"}), 400
    return jsonify({"ok": True})


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@auth.require_role(auth.ROLE_ADMIN)
def api_users_delete(user_id):
    target = db.get_user_by_id(user_id)
    if not target:
        return jsonify({"error": "not_found"}), 404
    if target["role"] == auth.ROLE_ADMIN and db.count_admins() <= 1:
        return jsonify({"error": "cannot_delete_last_admin"}), 400
    current = auth.current_user()
    if current and current["id"] == user_id:
        return jsonify({"error": "cannot_delete_self"}), 400
    db.delete_user(user_id)
    return jsonify({"ok": True})


SYNC_SOURCES = ("home_assistant", "solarweb")
ENTRIES_PAGE_SIZES = ("25", "50", "100", "all")


def _sync_source() -> str:
    val = (db.get_setting("sync_source") or "home_assistant").strip()
    return val if val in SYNC_SOURCES else "home_assistant"


def _entries_page_size() -> str:
    val = (db.get_setting("entries_page_size") or "25").strip()
    return val if val in ENTRIES_PAGE_SIZES else "25"


@app.route("/")
def dashboard():
    years = db.available_years() or [date.today().year]
    auto_sync = db.get_setting("auto_sync_on_open", "0") == "1"
    return render_template(
        "dashboard.html",
        years=years,
        current_year=years[-1],
        auto_sync_on_open=auto_sync,
        sync_source=_sync_source(),
    )


@app.route("/settings")
@auth.require_role(auth.ROLE_ADMIN)
def settings_page():
    targets = db.get_targets()
    recent = list(reversed(db.get_production()))
    month_totals: dict[str, float] = {}
    for r in recent:
        ym = r["date"][:7]
        month_totals[ym] = month_totals.get(ym, 0.0) + float(r["kwh"] or 0)
    return render_template(
        "settings.html",
        targets=targets,
        kwp=_kwp(),
        price_per_kwh=_price_per_kwh(),
        currency_setting=_currency(),
        start_date=_start_date() or "",
        timezone=_timezone(),
        timezones=sorted(available_timezones()),
        costs=db.list_costs(),
        total_invested=db.total_invested(),
        recent=recent,
        month_totals=month_totals,
        grid_imports=db.list_grid_bills("import"),
        grid_exports=db.list_grid_bills("export"),
        grid_totals=db.grid_totals(),
        ha_url=os.environ.get("HA_URL", ""),
        ha_entity=os.environ.get("HA_ENTITY_ID", ""),
        ha_configured=bool(
            os.environ.get("HA_URL")
            and os.environ.get("HA_TOKEN")
            and os.environ.get("HA_ENTITY_ID")
        ),
        solarweb_pv_id=os.environ.get("SOLARWEB_PV_SYSTEM_ID", ""),
        solarweb_configured=bool(
            os.environ.get("SOLARWEB_ACCESS_KEY_ID")
            and os.environ.get("SOLARWEB_ACCESS_KEY_VALUE")
        ),
        sync_source=_sync_source(),
        entries_page_size=_entries_page_size(),
        auto_sync_on_open=db.get_setting("auto_sync_on_open", "0") == "1",
        users=db.list_users(),
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


_SAFE_LINK_SCHEMES = ("http://", "https://", "mailto:", "/", "#")


def _safe_link(label: str, href: str) -> str:
    h = href.strip()
    if not any(h.lower().startswith(s) for s in _SAFE_LINK_SCHEMES):
        return f"[{label}]({href})"
    return f'<a href="{h}" target="_blank" rel="noopener">{label}</a>'


def _render_changelog_md(md: str) -> str:
    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda m: _safe_link(m.group(1), m.group(2)),
            text,
        )
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
    cur = _currency()
    js = (
        f"window.T={json.dumps(translations, ensure_ascii=False, separators=(',', ':'))};"
        f"window.CURRENCY={json.dumps(cur)};"
    )
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
@auth.require_role(auth.ROLE_ADMIN)
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
@auth.require_role(auth.ROLE_ADMIN)
def api_production_delete(date_str):
    db.delete_production(date_str)
    return jsonify({"ok": True})


@app.route("/api/targets", methods=["GET"])
def api_targets_get():
    return jsonify(db.get_targets())


@app.route("/api/targets", methods=["POST"])
@auth.require_role(auth.ROLE_ADMIN)
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
@auth.require_role(auth.ROLE_ADMIN)
def api_settings_post():
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    payload = request.get_json(force=True)
    if "timezone" in payload:
        try:
            ZoneInfo(str(payload["timezone"]))
        except ZoneInfoNotFoundError:
            return jsonify({"error": f"Unbekannte Zeitzone: {payload['timezone']}"}), 400
    if "currency" in payload:
        cur = str(payload["currency"]).strip()
        if not cur or len(cur) > 8:
            return jsonify({"error": "Währung muss 1-8 Zeichen lang sein"}), 400
        payload["currency"] = cur
    if "sync_source" in payload:
        src = str(payload["sync_source"]).strip()
        if src not in SYNC_SOURCES:
            return jsonify({"error": f"Ungueltige sync_source: {src}"}), 400
        payload["sync_source"] = src
    if "entries_page_size" in payload:
        ps = str(payload["entries_page_size"]).strip()
        if ps not in ENTRIES_PAGE_SIZES:
            return jsonify({"error": f"Ungueltige entries_page_size: {ps}"}), 400
        payload["entries_page_size"] = ps
    for key, value in payload.items():
        db.set_setting(key, str(value))
    return jsonify({"ok": True})


@app.route("/api/sync/ha", methods=["POST"])
@auth.require_role(auth.ROLE_ADMIN)
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


@app.route("/api/sync/solarweb", methods=["POST"])
@auth.require_role(auth.ROLE_ADMIN)
def api_sync_solarweb():
    payload = request.get_json(force=True) or {}
    start = payload.get("from")
    end = payload.get("to") or date.today().isoformat()
    if not start:
        return jsonify({"error": "'from' erforderlich (YYYY-MM-DD)"}), 400

    t0 = time.perf_counter()
    try:
        daily = solarweb_fetch_daily(start, end, tz=_timezone())
    except SolarwebClientError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": f"Unerwarteter Fehler: {e}"}), 500
    t_fetch = time.perf_counter() - t0

    t1 = time.perf_counter()
    items = [(d, round(kwh, 3)) for d, kwh in daily.items()]
    inserted, updated = db.bulk_upsert_production(items, source="solarweb")
    t_write = time.perf_counter() - t1

    app.logger.info(
        "Solar.web sync %s..%s: %d days (ins=%d, upd=%d) - fetch %.2fs, write %.2fs",
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
@auth.require_role(auth.ROLE_ADMIN)
def api_costs_post():
    payload = request.get_json(force=True)
    label = (payload.get("label") or "").strip()
    amount = payload.get("amount")
    cdate = payload.get("date") or None
    if not label or amount is None:
        return jsonify({"error": "label und amount erforderlich"}), 400
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
@auth.require_role(auth.ROLE_ADMIN)
def api_costs_put(cost_id):
    payload = request.get_json(force=True)
    label = (payload.get("label") or "").strip()
    amount = payload.get("amount")
    cdate = payload.get("date") or None
    if not label or amount is None:
        return jsonify({"error": "label und amount erforderlich"}), 400
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
@auth.require_role(auth.ROLE_ADMIN)
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
@auth.require_role(auth.ROLE_ADMIN)
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
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "ungültige Werte"}), 400
    if period_end < period_start or kwh < 0 or amount < 0:
        return jsonify({"error": "ungültige Werte"}), 400
    new_id = db.upsert_grid_bill(kind, period_start, period_end, kwh, amount, invoice_no)
    return jsonify({"ok": True, "id": new_id})


@app.route("/api/grid/<int:bill_id>", methods=["PUT"])
@auth.require_role(auth.ROLE_ADMIN)
def api_grid_put(bill_id):
    payload = request.get_json(force=True)
    period_start = (payload.get("period_start") or "").strip()
    period_end = (payload.get("period_end") or "").strip()
    invoice_no = (payload.get("invoice_no") or "").strip() or None
    try:
        datetime.fromisoformat(period_start)
        datetime.fromisoformat(period_end)
        kwh = float(payload.get("kwh"))
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "ungültige Werte"}), 400
    if period_end < period_start or kwh < 0 or amount < 0:
        return jsonify({"error": "ungültige Werte"}), 400
    if not db.update_grid_bill(bill_id, period_start, period_end, kwh, amount, invoice_no):
        return jsonify({"error": "nicht gefunden"}), 404
    return jsonify({"ok": True})


@app.route("/api/grid/<int:bill_id>", methods=["DELETE"])
@auth.require_role(auth.ROLE_ADMIN)
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
