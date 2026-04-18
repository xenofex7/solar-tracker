import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import requests


class HAClientError(Exception):
    pass


def _config():
    url = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    entity = os.environ.get("HA_ENTITY_ID", "")
    cumulative = os.environ.get("HA_ENTITY_IS_CUMULATIVE", "true").lower() == "true"
    if not url or not token or not entity:
        raise HAClientError(
            "HA_URL, HA_TOKEN und HA_ENTITY_ID müssen in .env gesetzt sein."
        )
    return url, token, entity, cumulative


def _headers(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def fetch_history(start: datetime, end: datetime):
    url, token, entity, _ = _config()
    endpoint = f"{url}/api/history/period/{start.isoformat()}"
    params = {
        "filter_entity_id": entity,
        "end_time": end.isoformat(),
        "minimal_response": "true",
    }
    r = requests.get(endpoint, headers=_headers(token), params=params, timeout=30)
    if r.status_code != 200:
        raise HAClientError(f"HA API {r.status_code}: {r.text[:200]}")
    data = r.json()
    return data[0] if data else []


def _to_local_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts[:10]
    return dt.astimezone().date().isoformat()


def states_to_daily_kwh(states: list, cumulative: bool) -> dict[str, float]:
    per_day: dict[str, list[float]] = defaultdict(list)
    for s in states:
        val = s.get("state")
        if val in (None, "unknown", "unavailable", ""):
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        day = _to_local_date(s.get("last_changed") or s.get("last_updated") or "")
        if not day:
            continue
        per_day[day].append(v)

    result: dict[str, float] = {}
    if cumulative:
        for day, values in sorted(per_day.items()):
            if not values:
                continue
            result[day] = max(0.0, max(values) - min(values))
    else:
        for day, values in per_day.items():
            result[day] = max(values)
    return result


def fetch_daily(start_date: str, end_date: str) -> dict[str, float]:
    _, _, _, cumulative = _config()
    start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(end_date).replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    ) + timedelta(seconds=1)
    states = fetch_history(start, end)
    return states_to_daily_kwh(states, cumulative)
