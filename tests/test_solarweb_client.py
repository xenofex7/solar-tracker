"""Tests for solarweb_client. HTTP is mocked so these run offline and
the assertions stay deterministic without depending on Solar.web."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import solarweb_client as sw

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | list | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or ""

    def json(self):
        return self._payload


@pytest.fixture
def env_keys(monkeypatch):
    monkeypatch.setenv("SOLARWEB_ACCESS_KEY_ID", "key-id")
    monkeypatch.setenv("SOLARWEB_ACCESS_KEY_VALUE", "key-secret")
    monkeypatch.setenv("SOLARWEB_PV_SYSTEM_ID", "pv-uuid-123")


@pytest.fixture
def env_keys_no_pvid(monkeypatch):
    monkeypatch.setenv("SOLARWEB_ACCESS_KEY_ID", "key-id")
    monkeypatch.setenv("SOLARWEB_ACCESS_KEY_VALUE", "key-secret")
    monkeypatch.delenv("SOLARWEB_PV_SYSTEM_ID", raising=False)


# ---------------------------------------------------------------------------
# _config
# ---------------------------------------------------------------------------

def test_config_missing_keys_raises(monkeypatch):
    monkeypatch.delenv("SOLARWEB_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("SOLARWEB_ACCESS_KEY_VALUE", raising=False)
    with pytest.raises(sw.SolarwebClientError, match="ACCESS_KEY"):
        sw._config()


# ---------------------------------------------------------------------------
# fetch_daily - happy path
# ---------------------------------------------------------------------------

def test_fetch_daily_parses_wh_to_kwh(env_keys):
    payload = {
        "pvSystemId": "pv-uuid-123",
        "data": [
            {
                "logDateTime": "2026-04-01T00:00:00Z",
                "channels": [
                    {"channelName": "EnergyProductionTotal", "channelType": "Energy", "unit": "Wh", "value": 23450.0},
                ],
            },
            {
                "logDateTime": "2026-04-02T00:00:00Z",
                "channels": [
                    {"channelName": "EnergyProductionTotal", "unit": "Wh", "value": 18000},
                ],
            },
        ],
    }
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(200, payload)) as mock_get:
        out = sw.fetch_daily("2026-04-01", "2026-04-02", tz="Europe/Zurich")

    assert out == {"2026-04-01": 23.45, "2026-04-02": 18.0}
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/pvsystems/pv-uuid-123/aggrdata")
    assert kwargs["params"]["channel"] == "EnergyProductionTotal"
    assert kwargs["params"]["duration"] == "days"
    assert kwargs["headers"]["AccessKeyId"] == "key-id"
    assert kwargs["headers"]["AccessKeyValue"] == "key-secret"


def test_fetch_daily_accepts_kwh_unit(env_keys):
    payload = {
        "data": [
            {
                "logDateTime": "2026-04-01",
                "channels": [
                    {"channelName": "EnergyProductionTotal", "unit": "kWh", "value": 25.5},
                ],
            },
        ],
    }
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(200, payload)):
        out = sw.fetch_daily("2026-04-01", "2026-04-01")
    assert out == {"2026-04-01": 25.5}


def test_fetch_daily_skips_entries_without_production_channel(env_keys):
    payload = {
        "data": [
            {"logDateTime": "2026-04-01T00:00:00Z", "channels": [
                {"channelName": "EnergySelfConsumption", "unit": "Wh", "value": 5000},
            ]},
            {"logDateTime": "2026-04-02T00:00:00Z", "channels": [
                {"channelName": "EnergyProductionTotal", "unit": "Wh", "value": 12000},
            ]},
        ],
    }
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(200, payload)):
        out = sw.fetch_daily("2026-04-01", "2026-04-02")
    assert out == {"2026-04-02": 12.0}


def test_fetch_daily_negative_clamped_to_zero(env_keys):
    payload = {
        "data": [
            {"logDateTime": "2026-04-01T00:00:00Z", "channels": [
                {"channelName": "EnergyProductionTotal", "unit": "Wh", "value": -250},
            ]},
        ],
    }
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(200, payload)):
        out = sw.fetch_daily("2026-04-01", "2026-04-01")
    assert out == {"2026-04-01": 0.0}


def test_fetch_daily_empty_data_returns_empty_dict(env_keys):
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(200, {"data": []})):
        out = sw.fetch_daily("2026-04-01", "2026-04-02")
    assert out == {}


def test_fetch_daily_missing_data_key_returns_empty_dict(env_keys):
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(200, {"unexpected": "shape"})):
        out = sw.fetch_daily("2026-04-01", "2026-04-02")
    assert out == {}


# ---------------------------------------------------------------------------
# fetch_daily - error paths
# ---------------------------------------------------------------------------

def test_fetch_daily_auth_error_translates_to_clear_message(env_keys):
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(401, text="forbidden")):
        with pytest.raises(sw.SolarwebClientError, match="Authentifizierung"):
            sw.fetch_daily("2026-04-01", "2026-04-02")


def test_fetch_daily_5xx_includes_status_code(env_keys):
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(503, text="oops")):
        with pytest.raises(sw.SolarwebClientError, match="503"):
            sw.fetch_daily("2026-04-01", "2026-04-02")


# ---------------------------------------------------------------------------
# PV system auto-resolution
# ---------------------------------------------------------------------------

def test_resolve_pv_system_id_uses_single_system(env_keys_no_pvid):
    list_payload = {"pvSystems": [{"pvSystemId": "auto-uuid", "name": "Home"}]}
    aggr_payload = {"data": []}
    with patch("solarweb_client.requests.get") as mock_get:
        mock_get.side_effect = [_FakeResponse(200, list_payload), _FakeResponse(200, aggr_payload)]
        sw.fetch_daily("2026-04-01", "2026-04-02")
    assert mock_get.call_args_list[1].args[0].endswith("/pvsystems/auto-uuid/aggrdata")


def test_resolve_pv_system_id_errors_when_multiple_systems(env_keys_no_pvid):
    list_payload = {"pvSystems": [
        {"pvSystemId": "a", "name": "A"},
        {"pvSystemId": "b", "name": "B"},
    ]}
    with patch("solarweb_client.requests.get", return_value=_FakeResponse(200, list_payload)):
        with pytest.raises(sw.SolarwebClientError, match="Mehrere PV-Systeme"):
            sw.fetch_daily("2026-04-01", "2026-04-02")
