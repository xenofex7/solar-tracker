"""Fronius Solar.web API v1 client.

Fetches daily PV production from the Solar.web cloud API. Mirrors the
shape of `ha_client.fetch_daily` so the rest of the app can stay
storage-agnostic: returns `{ "YYYY-MM-DD": kwh, ... }` and the caller
hands it to `db.bulk_upsert_production(..., source="solarweb")`.

Required environment variables:
    SOLARWEB_ACCESS_KEY_ID      from Solar.web > Settings > API
    SOLARWEB_ACCESS_KEY_VALUE   the secret half of the key pair
    SOLARWEB_PV_SYSTEM_ID       UUID of the PV system (auto-resolved if
                                only one system is on the account)

Endpoint reference:
    GET /swqapi/pvsystems/{pvSystemId}/aggrdata
        ?from=YYYY-MM-DD&to=YYYY-MM-DD
        &channel=EnergyProductionTotal&duration=days

Notes:
- A Solar.web Premium account is required for API access; without it
  every call returns 401/403.
- Values come back in Wh by default; we convert to kWh.
- The endpoint paths follow the public Solar.web v1 spec; should the
  API ever change, only this module needs adjustments.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

DEFAULT_TZ = "Europe/Zurich"
BASE_URL = "https://api.solarweb.com/swqapi"
DEFAULT_TIMEOUT = 30
PRODUCTION_CHANNEL = "EnergyProductionTotal"

log = logging.getLogger(__name__)


class SolarwebClientError(Exception):
    pass


def _config() -> tuple[str, str, str | None]:
    key_id = os.environ.get("SOLARWEB_ACCESS_KEY_ID", "").strip()
    key_value = os.environ.get("SOLARWEB_ACCESS_KEY_VALUE", "").strip()
    pv_id = os.environ.get("SOLARWEB_PV_SYSTEM_ID", "").strip() or None
    if not key_id or not key_value:
        raise SolarwebClientError(
            "SOLARWEB_ACCESS_KEY_ID und SOLARWEB_ACCESS_KEY_VALUE muessen in .env gesetzt sein."
        )
    return key_id, key_value, pv_id


def _headers(key_id: str, key_value: str) -> dict[str, str]:
    return {
        "AccessKeyId": key_id,
        "AccessKeyValue": key_value,
        "Accept": "application/json",
    }


def _get(path: str, params: dict | None = None) -> dict:
    key_id, key_value, _ = _config()
    url = f"{BASE_URL}{path}"
    try:
        r = requests.get(
            url,
            headers=_headers(key_id, key_value),
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        raise SolarwebClientError(f"Netzwerkfehler: {e}") from e
    if r.status_code in (401, 403):
        raise SolarwebClientError(
            f"Solar.web Authentifizierung fehlgeschlagen ({r.status_code}). "
            "Pruefe AccessKeyId/Value und ob das Konto Premium-Zugang hat."
        )
    if r.status_code >= 400:
        raise SolarwebClientError(
            f"Solar.web API Fehler {r.status_code}: {r.text[:300]}"
        )
    try:
        return r.json()
    except ValueError as e:
        raise SolarwebClientError(f"Ungueltige JSON-Antwort: {e}") from e


def list_pv_systems() -> list[dict]:
    """Return PV systems linked to the account. Lightweight; useful for
    discovering the SOLARWEB_PV_SYSTEM_ID."""
    payload = _get("/pvsystems")
    if isinstance(payload, dict):
        return payload.get("pvSystems") or payload.get("data") or []
    if isinstance(payload, list):
        return payload
    return []


def _resolve_pv_system_id(explicit: str | None) -> str:
    if explicit:
        return explicit
    systems = list_pv_systems()
    if not systems:
        raise SolarwebClientError(
            "Kein PV-System im Solar.web Konto gefunden."
        )
    if len(systems) > 1:
        ids = ", ".join(str(s.get("pvSystemId") or s.get("id") or "?") for s in systems)
        raise SolarwebClientError(
            f"Mehrere PV-Systeme gefunden ({ids}). Setze SOLARWEB_PV_SYSTEM_ID."
        )
    sys0 = systems[0]
    pv_id = sys0.get("pvSystemId") or sys0.get("id")
    if not pv_id:
        raise SolarwebClientError("Antwort von /pvsystems enthaelt keine pvSystemId.")
    return pv_id


def _resolve_tz(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz or DEFAULT_TZ)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TZ)


def _entry_day(log_datetime: object, zone: ZoneInfo) -> str | None:
    if log_datetime is None:
        return None
    try:
        dt = datetime.fromisoformat(str(log_datetime).replace("Z", "+00:00"))
    except ValueError:
        try:
            return date.fromisoformat(str(log_datetime)[:10]).isoformat()
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone)
    return dt.astimezone(zone).date().isoformat()


def _entry_kwh(channels: object) -> float | None:
    """Pull the production value (in kWh) from a channels list. Solar.web
    typically returns Wh; if the unit is missing we still assume Wh
    because that is the documented default for energy channels."""
    if not isinstance(channels, list):
        return None
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        name = ch.get("channelName") or ch.get("name")
        if name != PRODUCTION_CHANNEL:
            continue
        value = ch.get("value")
        if value is None:
            return None
        try:
            wh = float(value)
        except (TypeError, ValueError):
            return None
        unit = (ch.get("unit") or "Wh").lower()
        if unit == "kwh":
            return max(0.0, wh)
        # default + "wh"
        return max(0.0, wh / 1000.0)
    return None


def fetch_daily(
    start_date: str,
    end_date: str,
    tz: str | None = None,
) -> dict[str, float]:
    """Return `{ "YYYY-MM-DD": kwh }` for the inclusive [start_date, end_date]
    range. Days without data are simply absent from the result (caller
    should treat absence as "unknown", not zero)."""
    _, _, pv_id_env = _config()
    pv_id = _resolve_pv_system_id(pv_id_env)
    zone = _resolve_tz(tz)

    payload = _get(
        f"/pvsystems/{pv_id}/aggrdata",
        params={
            "from": start_date,
            "to": end_date,
            "channel": PRODUCTION_CHANNEL,
            "duration": "days",
        },
    )

    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        log.warning("Solar.web aggrdata: kein 'data'-Array in Antwort: %r", payload)
        return {}

    result: dict[str, float] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        day = _entry_day(entry.get("logDateTime") or entry.get("date"), zone)
        if not day:
            continue
        kwh = _entry_kwh(entry.get("channels"))
        if kwh is None:
            continue
        result[day] = round(kwh, 3)
    return result
