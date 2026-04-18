import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from websocket import create_connection


class HAClientError(Exception):
    pass


def _config():
    url = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    entity = os.environ.get("HA_ENTITY_ID", "")
    if not url or not token or not entity:
        raise HAClientError(
            "HA_URL, HA_TOKEN und HA_ENTITY_ID müssen in .env gesetzt sein."
        )
    return url, token, entity


def _ws_url(http_url: str) -> str:
    p = urlparse(http_url)
    if not p.netloc:
        raise HAClientError(f"Ungültige HA_URL: {http_url}")
    scheme = "wss" if p.scheme == "https" else "ws"
    return f"{scheme}://{p.netloc}/api/websocket"


def _fetch_statistics(start: datetime, end: datetime):
    url, token, entity = _config()
    ws = create_connection(_ws_url(url), timeout=30)
    try:
        hello = json.loads(ws.recv())
        if hello.get("type") != "auth_required":
            raise HAClientError(f"Unerwartete HA-Antwort: {hello}")
        ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(ws.recv())
        if auth.get("type") != "auth_ok":
            raise HAClientError(
                f"HA-Auth fehlgeschlagen: {auth.get('message', auth)}"
            )
        ws.send(json.dumps({
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "statistic_ids": [entity],
            "period": "day",
            "types": ["change"],
        }))
        msg = json.loads(ws.recv())
        if not msg.get("success"):
            err = msg.get("error") or {}
            raise HAClientError(
                f"HA Statistics Fehler: {err.get('message', msg)}"
            )
        return msg.get("result", {}).get(entity, [])
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _row_day(start_value) -> str | None:
    if start_value is None:
        return None
    if isinstance(start_value, (int, float)):
        seconds = start_value / 1000 if start_value > 1e12 else start_value
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(start_value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.astimezone().date().isoformat()


def fetch_daily(start_date: str, end_date: str) -> dict[str, float]:
    start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    end = (
        datetime.fromisoformat(end_date) + timedelta(days=1)
    ).replace(tzinfo=timezone.utc)
    rows = _fetch_statistics(start, end)

    result: dict[str, float] = {}
    for row in rows:
        day = _row_day(row.get("start"))
        change = row.get("change")
        if not day or change is None:
            continue
        try:
            result[day] = max(0.0, float(change))
        except (TypeError, ValueError):
            continue
    return result
