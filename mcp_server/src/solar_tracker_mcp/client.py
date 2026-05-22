"""Thin HTTP wrapper around the Solar-Tracker REST API.

Configuration via environment variables:
- SOLAR_TRACKER_URL: base URL of the Solar-Tracker instance (default: http://localhost:5000)
- SOLAR_TRACKER_TOKEN: API token created under Settings -> API tokens
- SOLAR_TRACKER_TIMEOUT: request timeout in seconds (default: 30)

All endpoints return JSON. Errors raise SolarTrackerError with the server's
message, so MCP tools can surface them to the model.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class SolarTrackerError(RuntimeError):
    """Raised when the Solar-Tracker API returns a non-2xx response."""


class SolarTrackerClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("SOLAR_TRACKER_URL") or "http://localhost:5000").rstrip("/")
        self.token = token or os.environ.get("SOLAR_TRACKER_TOKEN", "")
        self.timeout = timeout if timeout is not None else float(os.environ.get("SOLAR_TRACKER_TIMEOUT", "30"))
        if not self.token:
            # Don't hard-fail at construction; some read endpoints might be
            # callable in zero-config auto-login mode. But warn the model.
            self._auth_warning = (
                "SOLAR_TRACKER_TOKEN is not set. Create one under Settings -> "
                "API tokens in the Solar-Tracker UI and set the env var."
            )
        else:
            self._auth_warning = ""
        self._http = httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        self._http.close()

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._headers()
        if json is not None:
            headers["Content-Type"] = "application/json"
        try:
            resp = self._http.request(method, url, headers=headers, params=params, json=json)
        except httpx.HTTPError as e:
            raise SolarTrackerError(f"network error talking to {url}: {e}") from e
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except ValueError:
                payload = {"error": resp.text[:200]}
            raise SolarTrackerError(
                f"{method} {path} -> {resp.status_code}: {payload.get('error', payload)}"
            )
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # ---- HTTP verbs ----
    def get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params=params or None)

    def post(self, path: str, body: Any | None = None) -> Any:
        return self._request("POST", path, json=body if body is not None else {})

    def put(self, path: str, body: Any | None = None) -> Any:
        return self._request("PUT", path, json=body if body is not None else {})

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)
