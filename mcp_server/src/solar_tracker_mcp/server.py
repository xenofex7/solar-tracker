"""Solar-Tracker MCP server.

Exposes the full Solar-Tracker REST API as MCP tools so an LLM can read every
metric and write every input (production entries, monthly targets, plant
settings, investment costs, grid billing, syncs, users, API tokens).

Transport: stdio. Configure your MCP host (Claude Desktop, Claude Code, etc.)
to launch:
    solar-tracker-mcp
with env vars:
    SOLAR_TRACKER_URL=http://localhost:5000
    SOLAR_TRACKER_TOKEN=<token-from-settings-page>
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from solar_tracker_mcp import __version__
from solar_tracker_mcp.client import SolarTrackerClient, SolarTrackerError

mcp = FastMCP(f"solar-tracker v{__version__}")
client = SolarTrackerClient()


def _safe(call):
    """Decorator wrapper that turns SolarTrackerError into a structured error
    dict instead of crashing the MCP server."""

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return call(*args, **kwargs)
        except SolarTrackerError as e:
            return {"error": str(e)}

    wrapped.__name__ = call.__name__
    wrapped.__doc__ = call.__doc__
    return wrapped


# =====================================================================
# READ TOOLS
# =====================================================================


@mcp.tool()
@_safe
def get_summary(year: int | str = "current") -> dict:
    """Return the full dashboard summary for a year.

    Includes monthly actual vs target kWh, deviation percentages, cumulative
    series, daily series with 7-day rolling average, top days, year
    comparisons, heatmap, payback projection, self-consumption, grid totals,
    and effective price per kWh.

    Args:
        year: A year (e.g. 2025), the string "all" for all-time, or
              "current" (default) to use the current calendar year.
    """
    if year == "current":
        from datetime import date
        year = date.today().year
    return client.get("/api/summary", year=str(year))


@mcp.tool()
@_safe
def get_production(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """List daily production entries as {date, kwh, source}.

    Args:
        date_from: ISO date (YYYY-MM-DD), inclusive. Omit for no lower bound.
        date_to: ISO date (YYYY-MM-DD), inclusive. Omit for no upper bound.
    """
    params: dict[str, Any] = {}
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    return client.get("/api/production", **params)


@mcp.tool()
@_safe
def get_targets() -> list[dict]:
    """List monthly kWh targets. year=null means a default that applies to
    every year unless overridden by a year-specific target."""
    return client.get("/api/targets")


@mcp.tool()
@_safe
def get_costs() -> dict:
    """List investment cost items and the total invested."""
    return client.get("/api/costs")


@mcp.tool()
@_safe
def get_grid() -> dict:
    """Return grid billing: import bills, export bills, and aggregated totals
    (kWh, amount, average price per kind, net cost)."""
    return client.get("/api/grid")


@mcp.tool()
@_safe
def get_settings() -> dict:
    """Return all plant settings: kwp, price_per_kwh, currency, timezone,
    start_date, sync_source, auto_sync_on_open, entries_page_size."""
    return client.get("/api/settings")


@mcp.tool()
@_safe
def get_changelog() -> dict:
    """Return the Solar-Tracker changelog rendered as HTML."""
    return client.get("/api/changelog")


@mcp.tool()
@_safe
def list_users() -> dict:
    """List Solar-Tracker user accounts. Requires an admin token."""
    return client.get("/api/users")


@mcp.tool()
@_safe
def list_api_tokens() -> dict:
    """List API tokens (name, role, created_at, last_used_at). Requires an
    admin token. Raw token values are never returned - they are only shown
    once at creation."""
    return client.get("/api/tokens")


# =====================================================================
# WRITE TOOLS - production
# =====================================================================


@mcp.tool()
@_safe
def add_production(date: str, kwh: float) -> dict:
    """Add or overwrite a manual daily production entry.

    Args:
        date: ISO date YYYY-MM-DD.
        kwh: Energy yield in kWh (>= 0).
    """
    return client.post("/api/production", {"date": date, "kwh": kwh})


@mcp.tool()
@_safe
def delete_production(date: str) -> dict:
    """Delete a daily production entry by date."""
    return client.delete(f"/api/production/{date}")


# =====================================================================
# WRITE TOOLS - targets
# =====================================================================


@mcp.tool()
@_safe
def set_target(month: int, kwh: float, year: int | None = None) -> dict:
    """Set the monthly kWh target.

    Args:
        month: 1-12.
        kwh: Target in kWh (>= 0).
        year: If omitted, sets the default target that applies to every year
              not explicitly overridden.
    """
    body: dict[str, Any] = {"month": month, "kwh": kwh}
    if year is not None:
        body["year"] = year
    return client.post("/api/targets", body)


# =====================================================================
# WRITE TOOLS - settings
# =====================================================================


@mcp.tool()
@_safe
def update_settings(
    kwp: float | None = None,
    price_per_kwh: float | None = None,
    currency: str | None = None,
    timezone: str | None = None,
    start_date: str | None = None,
    sync_source: Literal["home_assistant", "solarweb"] | None = None,
    auto_sync_on_open: bool | None = None,
    entries_page_size: Literal["25", "50", "100", "all"] | None = None,
) -> dict:
    """Update plant settings. Pass only the keys you want to change.

    Args:
        kwp: Installed plant capacity in kWp.
        price_per_kwh: Reference price per kWh (used as fallback when grid
                       billing has no average).
        currency: ISO-like currency code (CHF, EUR, USD, ...).
        timezone: IANA timezone (e.g. "Europe/Zurich").
        start_date: Production start date YYYY-MM-DD. Records before this
                    date are excluded from summary metrics.
        sync_source: Which source the dashboard syncs from.
        auto_sync_on_open: Trigger a sync each time the dashboard loads.
        entries_page_size: Default page size on the production entries tab.
    """
    body: dict[str, Any] = {}
    if kwp is not None:
        body["kwp"] = kwp
    if price_per_kwh is not None:
        body["price_per_kwh"] = price_per_kwh
    if currency is not None:
        body["currency"] = currency
    if timezone is not None:
        body["timezone"] = timezone
    if start_date is not None:
        body["start_date"] = start_date
    if sync_source is not None:
        body["sync_source"] = sync_source
    if auto_sync_on_open is not None:
        body["auto_sync_on_open"] = "1" if auto_sync_on_open else "0"
    if entries_page_size is not None:
        body["entries_page_size"] = entries_page_size
    if not body:
        return {"error": "no settings provided"}
    return client.post("/api/settings", body)


# =====================================================================
# WRITE TOOLS - investment costs
# =====================================================================


@mcp.tool()
@_safe
def add_cost(label: str, amount: float, date: str | None = None) -> dict:
    """Add an investment cost item (e.g. solar installer invoice line).

    Args:
        label: Free-form description.
        amount: Amount in the plant's currency (>= 0).
        date: Optional ISO date YYYY-MM-DD.
    """
    body: dict[str, Any] = {"label": label, "amount": amount}
    if date is not None:
        body["date"] = date
    return client.post("/api/costs", body)


@mcp.tool()
@_safe
def update_cost(id: int, label: str, amount: float, date: str | None = None) -> dict:
    """Update an existing investment cost item by id."""
    body: dict[str, Any] = {"label": label, "amount": amount}
    if date is not None:
        body["date"] = date
    return client.put(f"/api/costs/{id}", body)


@mcp.tool()
@_safe
def delete_cost(id: int) -> dict:
    """Delete an investment cost item by id."""
    return client.delete(f"/api/costs/{id}")


# =====================================================================
# WRITE TOOLS - grid billing
# =====================================================================


@mcp.tool()
@_safe
def add_grid_billing(
    kind: Literal["import", "export"],
    period_start: str,
    period_end: str,
    kwh: float,
    amount: float,
    invoice_no: str | None = None,
) -> dict:
    """Add or upsert a grid billing entry from an electricity invoice.

    Upsert key: (kind, period_start, period_end). Posting the same period
    twice updates the existing row.

    Args:
        kind: "import" (you drew from the grid) or "export" (you fed in).
        period_start: ISO date YYYY-MM-DD.
        period_end: ISO date YYYY-MM-DD, >= period_start.
        kwh: Billed kWh (>= 0).
        amount: Billed amount in plant currency (>= 0).
        invoice_no: Optional invoice number from the bill.
    """
    body: dict[str, Any] = {
        "kind": kind,
        "period_start": period_start,
        "period_end": period_end,
        "kwh": kwh,
        "amount": amount,
    }
    if invoice_no is not None:
        body["invoice_no"] = invoice_no
    return client.post("/api/grid", body)


@mcp.tool()
@_safe
def update_grid_billing(
    id: int,
    period_start: str,
    period_end: str,
    kwh: float,
    amount: float,
    invoice_no: str | None = None,
) -> dict:
    """Update an existing grid billing row by id. (kind is not editable; to
    change kind, delete and re-add.)"""
    body: dict[str, Any] = {
        "period_start": period_start,
        "period_end": period_end,
        "kwh": kwh,
        "amount": amount,
    }
    if invoice_no is not None:
        body["invoice_no"] = invoice_no
    return client.put(f"/api/grid/{id}", body)


@mcp.tool()
@_safe
def delete_grid_billing(id: int) -> dict:
    """Delete a grid billing row by id."""
    return client.delete(f"/api/grid/{id}")


# =====================================================================
# WRITE TOOLS - syncs
# =====================================================================


@mcp.tool()
@_safe
def sync_home_assistant(date_from: str, date_to: str | None = None) -> dict:
    """Pull daily production from Home Assistant (Long-Term Statistics).

    Args:
        date_from: ISO date YYYY-MM-DD, inclusive.
        date_to: ISO date YYYY-MM-DD, inclusive. Defaults to today.
    """
    body: dict[str, Any] = {"from": date_from}
    if date_to is not None:
        body["to"] = date_to
    return client.post("/api/sync/ha", body)


@mcp.tool()
@_safe
def sync_solarweb(date_from: str, date_to: str | None = None) -> dict:
    """Pull daily production from Fronius Solar.web (cloud API).

    Args:
        date_from: ISO date YYYY-MM-DD, inclusive.
        date_to: ISO date YYYY-MM-DD, inclusive. Defaults to today.
    """
    body: dict[str, Any] = {"from": date_from}
    if date_to is not None:
        body["to"] = date_to
    return client.post("/api/sync/solarweb", body)


# =====================================================================
# WRITE TOOLS - users
# =====================================================================


@mcp.tool()
@_safe
def create_user(username: str, role: Literal["admin", "readonly"], password: str) -> dict:
    """Create a new Solar-Tracker user. Requires an admin token."""
    return client.post(
        "/api/users",
        {"username": username, "role": role, "password": password},
    )


@mcp.tool()
@_safe
def update_user(
    id: int,
    role: Literal["admin", "readonly"] | None = None,
    password: str | None = None,
    clear_password: bool = False,
) -> dict:
    """Update a user. Pass only what you want to change.

    Args:
        id: User id.
        role: New role.
        password: New password (sets a fresh hash).
        clear_password: If True, removes the password (only valid for the
                        sole-user zero-config admin case).
    """
    body: dict[str, Any] = {}
    if role is not None:
        body["role"] = role
    if password is not None:
        body["password"] = password
    if clear_password:
        body["clear_password"] = True
    if not body:
        return {"error": "no fields to update"}
    return client.put(f"/api/users/{id}", body)


@mcp.tool()
@_safe
def delete_user(id: int) -> dict:
    """Delete a user by id."""
    return client.delete(f"/api/users/{id}")


# =====================================================================
# WRITE TOOLS - API tokens
# =====================================================================


@mcp.tool()
@_safe
def create_api_token(name: str, role: Literal["admin", "readonly"]) -> dict:
    """Create a new API token. The response contains the raw token exactly
    once - persist it immediately, it cannot be retrieved later."""
    return client.post("/api/tokens", {"name": name, "role": role})


@mcp.tool()
@_safe
def delete_api_token(id: int) -> dict:
    """Delete an API token by id."""
    return client.delete(f"/api/tokens/{id}")


# =====================================================================
# PROMPTS - guided multi-step use cases
# =====================================================================


@mcp.prompt()
def import_electricity_invoice() -> str:
    """Guide the model through importing an electricity invoice."""
    return (
        "You are about to import an electricity invoice into Solar-Tracker.\n\n"
        "Steps:\n"
        "1. Read the attached invoice (PDF, image, or pasted text).\n"
        "2. Identify these fields per billing period (there may be one for "
        "import / drawn energy and one for export / feed-in):\n"
        "   - kind: 'import' for energy drawn from the grid, 'export' for "
        "feed-in.\n"
        "   - period_start, period_end: ISO YYYY-MM-DD.\n"
        "   - kwh: billed kWh for that period.\n"
        "   - amount: billed amount in the plant currency. Use `get_settings` "
        "first if you are unsure which currency applies.\n"
        "   - invoice_no: optional, the invoice number printed on the bill.\n"
        "3. For each period, call `add_grid_billing` with those fields.\n"
        "4. Confirm by calling `get_grid` and reporting the new totals to "
        "the user. Highlight any periods that were updated vs newly inserted "
        "(the API upserts on (kind, period_start, period_end)).\n\n"
        "If a field is ambiguous, ask the user before writing."
    )


@mcp.prompt()
def import_investment_receipt() -> str:
    """Guide the model through importing an investment receipt."""
    return (
        "You are about to record an investment expense (e.g. solar installer "
        "invoice, inverter replacement, monitoring hardware).\n\n"
        "Steps:\n"
        "1. Read the attached document.\n"
        "2. Extract:\n"
        "   - label: short description (e.g. 'Inverter Fronius Symo 10', "
        "'Installer invoice 2024').\n"
        "   - amount: total cost in plant currency.\n"
        "   - date: ISO YYYY-MM-DD of the invoice. Optional but recommended.\n"
        "3. If the receipt contains multiple line items that matter "
        "individually for the payback calculation, call `add_cost` once per "
        "line. Otherwise add a single aggregate entry.\n"
        "4. Confirm by calling `get_costs` and reporting the new total."
    )


@mcp.prompt()
def yearly_report() -> str:
    """Generate a yearly performance and finance report."""
    return (
        "Produce a structured yearly report for Solar-Tracker.\n\n"
        "Steps:\n"
        "1. Ask the user which year, or default to the current calendar "
        "year.\n"
        "2. Call `get_summary` for that year and `get_settings` for "
        "currency, kWp, and start_date context.\n"
        "3. Optionally call `get_grid` and `get_costs` for cross-checks.\n"
        "4. Summarize in this order:\n"
        "   a. Headline: total kWh actual vs target, deviation %.\n"
        "   b. Best and worst months (with target deviation).\n"
        "   c. Top production days.\n"
        "   d. Grid: imported kWh and cost, exported kWh and credit, net "
        "cost, self-consumption %, effective price per kWh.\n"
        "   e. Finance: cumulative revenue, payback ETA from "
        "`finance.payback`.\n"
        "   f. Year-over-year comparison from `year_comparison` if multiple "
        "years exist.\n"
        "5. Use the currency from `get_settings`. Format numbers with "
        "thousands separators."
    )


@mcp.prompt()
def sync_missing_days() -> str:
    """Detect gaps in production data and sync them."""
    return (
        "Goal: find missing days in Solar-Tracker's production history and "
        "fill them via the configured sync source.\n\n"
        "Steps:\n"
        "1. Call `get_settings` to learn the configured `sync_source` "
        "('home_assistant' or 'solarweb') and `start_date`.\n"
        "2. Call `get_production` for the full range from start_date (or a "
        "user-provided start) to today.\n"
        "3. Build the expected calendar between those dates and identify "
        "missing dates.\n"
        "4. Group missing dates into contiguous ranges. For each range, "
        "call `sync_home_assistant` or `sync_solarweb` (matching the "
        "configured source) with the range's start and end.\n"
        "5. Re-check with `get_production` and summarize: how many days "
        "filled, how many still missing (those probably had no production), "
        "and any errors returned."
    )


def main() -> None:
    """Entry point for the `solar-tracker-mcp` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
