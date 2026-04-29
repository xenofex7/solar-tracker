# Solar-Tracker Cookbook

Short, copy-pasteable recipes for common operational tasks.
Run all commands from the project root.

When the venv is mentioned, swap `.venv/bin/python` for `python` if you
manage your own environment, or for `docker compose exec solar-tracker python`
when running in Docker.

## Table of contents

- [User management](#user-management)
- [Recovery from a lockout](#recovery-from-a-lockout)
- [Backups](#backups)
- [Telemetry](#telemetry)
- [Upgrading](#upgrading)
- [Logs](#logs)
- [Resetting data](#resetting-data)

## User management

```bash
# List all users
.venv/bin/python -m scripts.manage_users list

# Add a read-only user (prompts for password if you omit --password)
.venv/bin/python -m scripts.manage_users add viewer
.venv/bin/python -m scripts.manage_users set-password viewer

# Add an admin user with password set inline
.venv/bin/python -m scripts.manage_users add alice --admin --password s3cret

# Change role
.venv/bin/python -m scripts.manage_users set-role viewer admin

# Delete
.venv/bin/python -m scripts.manage_users delete viewer
```

The last admin cannot be demoted or deleted. The web UI under
**Settings -> Users** does the same things with a click.

## Recovery from a lockout

If you forget the admin password, do this from a shell:

```bash
# Option 1: nuke all users and recreate a passwordless admin
# (returns to zero-config auto-login mode)
.venv/bin/python -m scripts.manage_users reset-admin

# Option 2: nuke and recreate with a known password
.venv/bin/python -m scripts.manage_users reset-admin --password hunter2

# Option 3: only reset the existing admin's password
.venv/bin/python -m scripts.manage_users set-password admin
```

Inside Docker:

```bash
docker compose exec solar-tracker python -m scripts.manage_users reset-admin
```

The CLI is **not** reachable over HTTP. It requires shell access to the
host or container, which is the whole point: out-of-band recovery only.

## Backups

The entire app state lives in a single SQLite file under `data/solar.db`.

```bash
# Hot backup (safe while the app is running)
sqlite3 data/solar.db ".backup data/solar.db.bak"

# Restore from a backup
cp data/solar.db.bak data/solar.db
```

For Docker, mount `./data` as a volume (the default in `docker-compose.yml`)
and back up the directory on the host.

## Telemetry

The app sends an anonymous daily heartbeat (version + a random instance ID).
To disable:

```bash
# In .env or your environment
TELEMETRY_ENABLED=false
```

Then restart the app. Details: see `telemetry.py` and `## Telemetry` in the
README.

## Upgrading

```bash
# Local install
git pull
.venv/bin/pip install -r requirements.txt
# Restart the app

# Docker (pulls the new tag from ghcr.io)
docker compose pull
docker compose up -d
```

The DB schema migrates itself on first start (`db.init_db()`), so an
upgrade is a one-shot pull-and-restart.

## Logs

```bash
# Local: stdout/stderr of the running process

# Docker
docker compose logs -f solar-tracker
docker compose logs --since 1h solar-tracker
```

## Resetting data

Use with care - these wipe state.

```bash
# Wipe all production records but keep settings, users, costs, grid bills
sqlite3 data/solar.db "DELETE FROM daily_production;"

# Full factory reset: stop the app, then
rm data/solar.db
# Restart -> a fresh DB is created with a passwordless admin (auto-login)
```
