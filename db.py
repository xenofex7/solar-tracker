import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "solar.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_production (
    date TEXT PRIMARY KEY,
    kwh REAL NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_target (
    year INTEGER,
    month INTEGER NOT NULL,
    kwh REAL NOT NULL,
    PRIMARY KEY (year, month)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_production(date: str, kwh: float, source: str) -> str:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        existing = conn.execute(
            "SELECT kwh FROM daily_production WHERE date = ?", (date,)
        ).fetchone()
        conn.execute(
            """
            INSERT INTO daily_production (date, kwh, source, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                kwh = excluded.kwh,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (date, kwh, source, now),
        )
        return "inserted" if existing is None else "updated"


def delete_production(date: str):
    with connect() as conn:
        conn.execute("DELETE FROM daily_production WHERE date = ?", (date,))


def get_production(date_from: str = None, date_to: str = None):
    query = "SELECT date, kwh, source FROM daily_production"
    params = []
    clauses = []
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY date ASC"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def set_target(month: int, kwh: float, year: int | None = None):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO monthly_target (year, month, kwh)
            VALUES (?, ?, ?)
            ON CONFLICT(year, month) DO UPDATE SET kwh = excluded.kwh
            """,
            (year, month, kwh),
        )


def get_targets():
    with connect() as conn:
        rows = conn.execute(
            "SELECT year, month, kwh FROM monthly_target ORDER BY year, month"
        ).fetchall()
    return [dict(r) for r in rows]


def get_target_for(year: int, month: int) -> float | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT kwh FROM monthly_target WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
        if row:
            return row["kwh"]
        row = conn.execute(
            "SELECT kwh FROM monthly_target WHERE year IS NULL AND month = ?",
            (month,),
        ).fetchone()
        return row["kwh"] if row else None


def set_setting(key: str, value: str):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def get_setting(key: str, default=None):
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def available_years() -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(date, 1, 4) AS y FROM daily_production ORDER BY y"
        ).fetchall()
    return [int(r["y"]) for r in rows]
