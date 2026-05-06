import json
import logging
import os
import platform
import threading
import time
import uuid
from pathlib import Path
from urllib import request as _urlrequest
from urllib.error import URLError

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "https://umami.pac-build.ch"
_DEFAULT_WEBSITE_ID = "ed481344-4502-46d7-ac2e-e3fc305da58e"
UMAMI_HOST = os.getenv("UMAMI_HOST", _DEFAULT_HOST).rstrip("/")
UMAMI_WEBSITE_ID = os.getenv("UMAMI_WEBSITE_ID", _DEFAULT_WEBSITE_ID)
TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "true").strip().lower() not in (
    "false",
    "0",
    "no",
    "off",
)

_DATA_DIR = Path(__file__).parent / "data"
_STATE_FILE = _DATA_DIR / "telemetry.json"
_HEARTBEAT_INTERVAL = 24 * 60 * 60
_HTTP_TIMEOUT = 10

_lock = threading.Lock()
_started = False


def _read_state():
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(state):
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(_STATE_FILE)
    except OSError as e:
        logger.debug("could not persist telemetry state: %s", e)


def _instance_id():
    with _lock:
        state = _read_state()
        if "instance_id" not in state:
            state["instance_id"] = str(uuid.uuid4())
            _write_state(state)
        return state["instance_id"]


def _claim_heartbeat_slot():
    with _lock:
        state = _read_state()
        now = time.time()
        if now - state.get("last_heartbeat", 0) < _HEARTBEAT_INTERVAL:
            return False
        if "instance_id" not in state:
            state["instance_id"] = str(uuid.uuid4())
        state["last_heartbeat"] = now
        _write_state(state)
        return True


def _send(version):
    instance_id = _instance_id()
    payload = {
        "type": "event",
        "payload": {
            "website": UMAMI_WEBSITE_ID,
            "hostname": "solar-tracker",
            "language": "en",
            "screen": "0x0",
            "url": "/heartbeat",
            "referrer": "",
            "name": "instance_heartbeat",
            "data": {
                "version": version,
                "python_version": platform.python_version(),
                "instance_id": instance_id,
            },
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = _urlrequest.Request(
        f"{UMAMI_HOST}/api/send",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"solar-tracker/{version} (+heartbeat; {instance_id})",
        },
    )
    try:
        with _urlrequest.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            resp.read()
    except (URLError, TimeoutError, OSError) as e:
        logger.debug("telemetry send failed: %s", e)


def init(version):
    global _started
    if not TELEMETRY_ENABLED or not UMAMI_WEBSITE_ID:
        logger.info("telemetry disabled")
        return
    if _started:
        return
    _started = True

    def _loop():
        while True:
            if _claim_heartbeat_slot():
                _send(version)
            time.sleep(_HEARTBEAT_INTERVAL)

    threading.Thread(target=_loop, daemon=True, name="telemetry").start()
    logger.info("telemetry enabled (instance %s)", _instance_id()[:8])
