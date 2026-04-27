import json
import logging
import os
import platform
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_KEY = "phc_tLzWQRbSUvdwPxt7PrBEeYrQWW9TYinN3dq7JonmsupY"
POSTHOG_KEY = os.getenv("POSTHOG_API_KEY", _DEFAULT_KEY)
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://eu.i.posthog.com")
TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "true").strip().lower() not in (
    "false",
    "0",
    "no",
    "off",
)

_DATA_DIR = Path(__file__).parent / "data"
_STATE_FILE = _DATA_DIR / "telemetry.json"
_HEARTBEAT_INTERVAL = 24 * 60 * 60

_lock = threading.Lock()
_client = None


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


def _capture(version):
    if _client is None:
        return
    try:
        _client.capture(
            distinct_id=_instance_id(),
            event="instance_heartbeat",
            properties={
                "version": version,
                "python_version": platform.python_version(),
            },
        )
    except Exception as e:
        logger.debug("telemetry capture failed: %s", e)


def init(version):
    global _client
    if not TELEMETRY_ENABLED or not POSTHOG_KEY:
        logger.info("telemetry disabled")
        return
    try:
        from posthog import Posthog
    except ImportError:
        logger.info("posthog package missing, telemetry disabled")
        return

    _client = Posthog(project_api_key=POSTHOG_KEY, host=POSTHOG_HOST)

    def _loop():
        while True:
            if _claim_heartbeat_slot():
                _capture(version)
            time.sleep(_HEARTBEAT_INTERVAL)

    threading.Thread(target=_loop, daemon=True, name="telemetry").start()
    logger.info("telemetry enabled (instance %s)", _instance_id()[:8])
