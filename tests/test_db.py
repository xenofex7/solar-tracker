"""Tests for the SQLite layer against throwaway SQLite files."""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest


@pytest.fixture
def db_path(monkeypatch):
    tmp_dir = tempfile.mkdtemp(prefix="solar-db-")
    path = os.path.join(tmp_dir, "costs.db")
    import db as _db
    monkeypatch.setattr(_db, "DB_PATH", path)
    yield path


def _write_legacy_db(path: str):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE plant_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT
        );
        INSERT INTO plant_costs (label, amount, date)
        VALUES ('Solar-Bauer', 20000, '2024-05-01'), ('Pronovo', -3000, '2024-09-01');
        """
    )
    conn.commit()
    conn.close()


def test_migration_marks_existing_rows_as_investment(db_path):
    import db as _db
    _write_legacy_db(db_path)
    _db.init_db()
    assert [c["kind"] for c in _db.list_costs()] == ["investment", "investment"]
    assert _db.total_invested() == 17000
    assert _db.total_operating() == 0.0


def test_migration_is_idempotent(db_path):
    import db as _db
    _write_legacy_db(db_path)
    _db.init_db()
    _db.init_db()
    assert [c["kind"] for c in _db.list_costs()] == ["investment", "investment"]


def test_fresh_db_splits_the_two_totals(db_path):
    import db as _db
    _db.init_db()
    _db.add_cost("Module", 10000, "2024-05-01")
    _db.add_cost("Versicherung", 120, "2025-01-05", "operating")
    assert {c["label"]: c["kind"] for c in _db.list_costs()} == {
        "Module": "investment",
        "Versicherung": "operating",
    }
    assert _db.total_invested() == 10000
    assert _db.total_operating() == 120


def test_update_cost_switches_kind(db_path):
    import db as _db
    _db.init_db()
    cost_id = _db.add_cost("Zaehlermiete", 60, "2025-02-01")
    assert _db.update_cost(cost_id, "Zaehlermiete", 60, "2025-02-01", "operating") is True
    assert _db.total_invested() == 0.0
    assert _db.total_operating() == 60


def test_record_sync_result_keeps_last_success(db_path):
    import db as _db
    _db.init_db()
    _db.record_sync_result(False, "HA auth failed")
    assert _db.get_setting("last_sync_status") == "error"
    assert _db.get_setting("last_sync_error") == "HA auth failed"
    assert _db.get_setting("last_sync_ok_at") is None

    _db.record_sync_result(True)
    assert _db.get_setting("last_sync_status") == "ok"
    assert _db.get_setting("last_sync_error") == ""
    success_at = _db.get_setting("last_sync_ok_at")
    assert success_at

    _db.record_sync_result(False, "HA auth failed again")
    assert _db.get_setting("last_sync_status") == "error"
    assert _db.get_setting("last_sync_ok_at") == success_at
