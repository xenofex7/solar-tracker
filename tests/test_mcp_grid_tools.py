"""Tests for the grid billing MCP tools. The HTTP client is swapped for a
recorder so the tools can be called without a running Solar-Tracker."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from solar_tracker_mcp import server


class _RecordingClient:
    def __init__(self):
        self.calls = []

    def post(self, path, body=None):
        self.calls.append(("POST", path, body))
        return {"ok": True, "id": 15}

    def put(self, path, body=None):
        self.calls.append(("PUT", path, body))
        return {"ok": True}


@pytest.fixture
def recorder():
    recording = _RecordingClient()
    with patch.object(server, "client", recording):
        yield recording


def test_add_grid_billing_stringifies_numeric_invoice_no(recorder):
    server.add_grid_billing("import", "2026-07-01", "2026-09-30", 91, 53.60, 4824534)

    method, path, body = recorder.calls[0]
    assert (method, path) == ("POST", "/api/grid")
    assert body == {
        "kind": "import",
        "period_start": "2026-07-01",
        "period_end": "2026-09-30",
        "kwh": 91,
        "amount": 53.60,
        "invoice_no": "4824534",
    }


def test_add_grid_billing_keeps_a_string_invoice_no(recorder):
    server.add_grid_billing("export", "2026-07-01", "2026-09-30", 3241, 293.0, "7014581")

    assert recorder.calls[0][2]["invoice_no"] == "7014581"


def test_add_grid_billing_omits_an_absent_invoice_no(recorder):
    server.add_grid_billing("export", "2026-07-01", "2026-09-30", 3241, 293.0)

    assert "invoice_no" not in recorder.calls[0][2]


def test_update_grid_billing_stringifies_numeric_invoice_no(recorder):
    server.update_grid_billing(15, "2026-07-01", "2026-09-30", 91, 53.60, 4824534)

    method, path, body = recorder.calls[0]
    assert (method, path) == ("PUT", "/api/grid/15")
    assert body["invoice_no"] == "4824534"
