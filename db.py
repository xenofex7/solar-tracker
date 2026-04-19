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

CREATE TABLE IF NOT EXISTS plant_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    amount_chf REAL NOT NULL,
    date TEXT
);

CREATE TABLE IF NOT EXISTS grid_billing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    kwh REAL NOT NULL,
    amount_chf REAL NOT NULL,
    invoice_no TEXT,
    UNIQUE(kind, period_start, period_end)
);

DROP TABLE IF EXISTS electricity_costs;
"""


@contextmanager
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
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


def bulk_upsert_production(items: list[tuple[str, float]], source: str) -> tuple[int, int]:
    if not items:
        return 0, 0
    now = datetime.utcnow().isoformat(timespec="seconds")
    dates = [d for d, _ in items]
    with connect() as conn:
        placeholders = ",".join("?" * len(dates))
        existing = {
            row["date"]
            for row in conn.execute(
                f"SELECT date FROM daily_production WHERE date IN ({placeholders})",
                dates,
            ).fetchall()
        }
        conn.executemany(
            """
            INSERT INTO daily_production (date, kwh, source, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                kwh = excluded.kwh,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            [(d, k, source, now) for d, k in items],
        )
    inserted = sum(1 for d, _ in items if d not in existing)
    updated = len(items) - inserted
    return inserted, updated


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


def add_cost(label: str, amount_chf: float, date: str | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO plant_costs (label, amount_chf, date) VALUES (?, ?, ?)",
            (label, amount_chf, date or None),
        )
        return cur.lastrowid


def list_costs() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, label, amount_chf, date FROM plant_costs ORDER BY date IS NULL, date, id"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_cost(cost_id: int):
    with connect() as conn:
        conn.execute("DELETE FROM plant_costs WHERE id = ?", (cost_id,))


def total_invested() -> float:
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_chf), 0) AS t FROM plant_costs"
        ).fetchone()
    return float(row["t"])


def upsert_grid_bill(
    kind: str,
    period_start: str,
    period_end: str,
    kwh: float,
    amount_chf: float,
    invoice_no: str | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO grid_billing (kind, period_start, period_end, kwh, amount_chf, invoice_no)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(kind, period_start, period_end) DO UPDATE SET
                kwh = excluded.kwh,
                amount_chf = excluded.amount_chf,
                invoice_no = excluded.invoice_no
            """,
            (kind, period_start, period_end, kwh, amount_chf, invoice_no),
        )
        return cur.lastrowid


def list_grid_bills(kind: str | None = None) -> list[dict]:
    query = "SELECT id, kind, period_start, period_end, kwh, amount_chf, invoice_no FROM grid_billing"
    params: tuple = ()
    if kind:
        query += " WHERE kind = ?"
        params = (kind,)
    query += " ORDER BY period_start, kind"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_grid_bill(bill_id: int):
    with connect() as conn:
        conn.execute("DELETE FROM grid_billing WHERE id = ?", (bill_id,))


def grid_totals() -> dict:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT kind,
                   COALESCE(SUM(kwh), 0) AS kwh,
                   COALESCE(SUM(amount_chf), 0) AS amount
            FROM grid_billing GROUP BY kind
            """
        ).fetchall()
    totals = {"import": {"kwh": 0.0, "amount": 0.0}, "export": {"kwh": 0.0, "amount": 0.0}}
    for r in rows:
        totals[r["kind"]] = {"kwh": float(r["kwh"]), "amount": float(r["amount"])}
    avg_import = (totals["import"]["amount"] / totals["import"]["kwh"]) if totals["import"]["kwh"] else 0.0
    avg_export = (totals["export"]["amount"] / totals["export"]["kwh"]) if totals["export"]["kwh"] else 0.0
    return {
        "import": {**totals["import"], "avg_price": avg_import},
        "export": {**totals["export"], "avg_price": avg_export},
        "net_cost": totals["import"]["amount"] - totals["export"]["amount"],
    }


def available_years() -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(date, 1, 4) AS y FROM daily_production ORDER BY y"
        ).fetchall()
    return [int(r["y"]) for r in rows]
