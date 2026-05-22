# Solar-Tracker MCP server

Lets an LLM (Claude Desktop, Claude Code, any MCP-aware host) read every
metric from Solar-Tracker and write every input: production entries,
monthly targets, plant settings, investment costs, grid billing rows,
syncs, users, and API tokens.

Use cases:

- Drop an electricity invoice into the chat and have it imported.
- Ask for a year-end report ("How did 2026 compare to target?").
- Tell the model to find gaps in the production history and sync them.
- Adjust monthly targets from a planning spreadsheet.

## Install

From the repo root:

```bash
pip install -e ./mcp_server
```

Or with `uv`:

```bash
uv tool install --from ./mcp_server solar-tracker-mcp
```

This installs a `solar-tracker-mcp` console script.

## Configure

The MCP server talks to a running Solar-Tracker over HTTP. It needs two
env vars:

- `SOLAR_TRACKER_URL` - base URL, default `http://localhost:5000`
- `SOLAR_TRACKER_TOKEN` - API token (create one in the UI under
  **Settings -> API tokens**, choose role `admin` for full write access or
  `readonly` for read-only)

Optional:

- `SOLAR_TRACKER_TIMEOUT` - request timeout in seconds, default `30`

### Claude Desktop

Add to `claude_desktop_config.json` (on macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`).

Use an **absolute path** to the console script, since Claude Desktop does
not inherit your shell's PATH. If you installed into the project venv:

```json
{
  "mcpServers": {
    "solar-tracker": {
      "command": "/absolute/path/to/.venv/bin/solar-tracker-mcp",
      "env": {
        "SOLAR_TRACKER_URL": "http://localhost:5000",
        "SOLAR_TRACKER_TOKEN": "st_paste-your-token-here"
      }
    }
  }
}
```

If you installed with `uv tool install`, the binary lives at
`~/.local/bin/solar-tracker-mcp` (run `which solar-tracker-mcp` to
confirm).

After editing, fully quit and relaunch Claude Desktop. The server appears
in the slash-command menu as `solar-tracker` and the four prompts
(`import_electricity_invoice`, `import_investment_receipt`,
`yearly_report`, `sync_missing_days`) show up as ready-to-run templates.

### Claude Code

```bash
claude mcp add solar-tracker \
  -e SOLAR_TRACKER_URL=http://localhost:5000 \
  -e SOLAR_TRACKER_TOKEN=st_paste-your-token-here \
  -- /absolute/path/to/.venv/bin/solar-tracker-mcp
```

### End-to-end checklist

1. Run Solar-Tracker (`python app.py` or Docker).
2. Open `http://localhost:5000/settings#tokens`, create an `admin` token
   (or `readonly` for read-only access), copy it.
3. `pip install -e ./mcp_server` (or `uv tool install --from ./mcp_server
   solar-tracker-mcp`).
4. Add the JSON snippet above to `claude_desktop_config.json` with your
   absolute binary path and the token.
5. Relaunch Claude Desktop, open a chat, type `/` - you should see the
   `solar-tracker` prompts. Or just ask "what's my solar yield this
   year?" and the model will call `get_summary`.

## What's available

26 tools (read + write), grouped:

**Read** - `get_summary`, `get_production`, `get_targets`, `get_costs`,
`get_grid`, `get_settings`, `get_changelog`, `list_users`,
`list_api_tokens`.

**Write - production** - `add_production`, `delete_production`.

**Write - targets** - `set_target`.

**Write - settings** - `update_settings` (kwp, price_per_kwh, currency,
timezone, start_date, sync_source, auto_sync_on_open,
entries_page_size).

**Write - investment** - `add_cost`, `update_cost`, `delete_cost`.

**Write - grid billing** - `add_grid_billing`, `update_grid_billing`,
`delete_grid_billing`.

**Write - sync** - `sync_home_assistant`, `sync_solarweb`.

**Write - users** - `create_user`, `update_user`, `delete_user`.

**Write - tokens** - `create_api_token`, `delete_api_token`.

4 guided prompts:

- `import_electricity_invoice` - extracts periods/kWh/amount from a bill
  and writes them via `add_grid_billing`.
- `import_investment_receipt` - records expenses via `add_cost`.
- `yearly_report` - combines summary + grid + costs into a written
  report.
- `sync_missing_days` - finds production gaps and syncs the right
  source.

## Security

API tokens are 32-byte random strings prefixed with `st_`. Only their
SHA-256 hash is stored. The raw value is shown exactly once at creation.
Delete unused tokens from the UI. Admin tokens grant full write access;
prefer `readonly` for analysis-only integrations.

The MCP server never persists the token to disk on its own - it reads
it from the environment on each launch.
