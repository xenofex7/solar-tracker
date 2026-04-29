"""Tests for the v2.1 user/auth layer.

These tests exercise the real app + db modules against a temp SQLite file,
so they cover the full request flow: auto-login, password login, role
gating on settings + write APIs, and HTTP Basic for read-only API access.
"""

from __future__ import annotations

import importlib
import os
import tempfile

import pytest


@pytest.fixture
def app_ctx(monkeypatch):
    """Spin up app.py against an isolated DB file with auth disabled cookie-secure."""
    tmp_dir = tempfile.mkdtemp(prefix="solar-auth-")
    db_path = os.path.join(tmp_dir, "auth.db")

    # Stable secret for the test run
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("TELEMETRY_ENABLED", "false")

    import db as _db
    monkeypatch.setattr(_db, "DB_PATH", db_path)

    # Force re-import so app.py picks up the patched DB_PATH at module load.
    import app as _app
    importlib.reload(_app)

    client = _app.app.test_client()
    yield _app, client, _db


def _make_auth_basic(username: str, password: str) -> dict:
    import base64
    raw = f"{username}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def test_password_hash_roundtrip():
    import auth
    h = auth.hash_password("hunter2")
    assert auth.verify_password("hunter2", h) is True
    assert auth.verify_password("nope", h) is False
    assert auth.verify_password("hunter2", None) is False


def test_zero_config_auto_login(app_ctx):
    _app, client, _db = app_ctx
    # Fresh DB: only the seeded admin with no password exists -> auto-login.
    assert _db.count_users() == 1
    r = client.get("/")
    assert r.status_code == 200
    # Settings is admin-only and accessible since auto-login = admin.
    r = client.get("/settings")
    assert r.status_code == 200


def test_login_required_once_password_is_set(app_ctx):
    _app, client, _db = app_ctx
    import auth
    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("s3cret"))

    # Without credentials we get redirected to /login.
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]

    # APIs return JSON 401 instead of redirect.
    r = client.get("/api/summary?year=2025")
    assert r.status_code == 401

    # Login with wrong password fails.
    r = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

    # Login with right password works.
    r = client.post(
        "/login",
        data={"username": "admin", "password": "s3cret"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    r = client.get("/")
    assert r.status_code == 200


def test_readonly_user_cannot_reach_settings_or_write(app_ctx):
    _app, client, _db = app_ctx
    import auth

    # Promote default admin to having a password, then create a read-only user.
    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    _db.create_user("viewer", auth.ROLE_READONLY, auth.hash_password("viewpw"))

    # Log in as the read-only user.
    client.post("/login", data={"username": "viewer", "password": "viewpw"})

    # Dashboard works.
    assert client.get("/").status_code == 200

    # /settings is admin-only -> redirect to dashboard.
    r = client.get("/settings", follow_redirects=False)
    assert r.status_code == 302

    # GET APIs work.
    assert client.get("/api/production").status_code == 200
    assert client.get("/api/summary?year=2025").status_code == 200

    # Write APIs are forbidden.
    r = client.post(
        "/api/production",
        json={"date": "2026-01-01", "kwh": 12.3},
    )
    assert r.status_code == 403

    r = client.delete("/api/production/2026-01-01")
    assert r.status_code == 403

    r = client.post("/api/settings", json={"currency": "USD"})
    assert r.status_code == 403

    # User management is admin-only too.
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/users", json={"username": "x", "role": "readonly"}).status_code == 403


def test_admin_can_create_and_delete_users(app_ctx):
    _app, client, _db = app_ctx
    import auth

    # Set admin password and log in.
    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    client.post("/login", data={"username": "admin", "password": "adminpw"})

    # Create a read-only user.
    r = client.post(
        "/api/users",
        json={"username": "alice", "role": "readonly", "password": "alicepw"},
    )
    assert r.status_code == 200, r.get_json()
    new_id = r.get_json()["id"]

    # List users.
    r = client.get("/api/users")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(u["username"] == "alice" and u["role"] == "readonly" for u in items)

    # Cannot demote the last admin.
    r = client.put(f"/api/users/{admin['id']}", json={"role": "readonly"})
    assert r.status_code == 400

    # Cannot delete own account.
    r = client.delete(f"/api/users/{admin['id']}")
    assert r.status_code == 400

    # Delete the read-only user.
    r = client.delete(f"/api/users/{new_id}")
    assert r.status_code == 200
    assert _db.get_user_by_id(new_id) is None


def test_basic_auth_for_api_readonly(app_ctx):
    _app, client, _db = app_ctx
    import auth

    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    _db.create_user("api", auth.ROLE_READONLY, auth.hash_password("apipw"))

    # No auth -> 401.
    r = client.get("/api/production")
    assert r.status_code == 401

    # Wrong basic creds -> 401.
    r = client.get("/api/production", headers=_make_auth_basic("api", "wrong"))
    assert r.status_code == 401

    # Correct basic creds -> 200, GET allowed.
    r = client.get("/api/production", headers=_make_auth_basic("api", "apipw"))
    assert r.status_code == 200

    # But writes are still forbidden for read-only.
    r = client.post(
        "/api/production",
        headers=_make_auth_basic("api", "apipw"),
        json={"date": "2026-01-01", "kwh": 1.0},
    )
    assert r.status_code == 403


def test_invalid_username_rejected(app_ctx):
    _app, client, _db = app_ctx
    import auth

    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    client.post("/login", data={"username": "admin", "password": "adminpw"})

    for bad in ["a", "ab cd", "x" * 40, "evil!", ""]:
        r = client.post(
            "/api/users",
            json={"username": bad, "role": "readonly", "password": "pw"},
        )
        assert r.status_code == 400, f"expected 400 for {bad!r}"


def test_passwordless_admin_cannot_create_users(app_ctx):
    """Auto-login admin must set their own password before adding others,
    otherwise creating a second user locks them out."""
    _app, client, _db = app_ctx
    # Fresh DB: passwordless admin, auto-login active.
    r = client.post(
        "/api/users",
        json={"username": "alice", "role": "readonly", "password": "alicepw"},
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "set_own_password_first"

    # After setting own password, creation works.
    import auth
    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    client.post("/login", data={"username": "admin", "password": "adminpw"})
    r = client.post(
        "/api/users",
        json={"username": "alice", "role": "readonly", "password": "alicepw"},
    )
    assert r.status_code == 200


def test_clear_admin_password_only_as_sole_user(app_ctx):
    """A passwordless admin is only allowed in zero-config auto-login mode
    (single user). With more users around, you cannot clear an admin's
    password - even if another admin still has one (that would just create
    a zombie admin that cannot log in). Demote or delete first instead."""
    _app, client, _db = app_ctx
    import auth

    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    other_id = _db.create_user("admin2", auth.ROLE_ADMIN, auth.hash_password("otherpw"))
    client.post("/login", data={"username": "admin", "password": "adminpw"})

    # Cannot clear admin2's password while another user exists.
    r = client.put(f"/api/users/{other_id}", json={"clear_password": True})
    assert r.status_code == 400
    assert r.get_json()["error"] == "would_lock_platform"

    # Same for own password.
    r = client.put(f"/api/users/{admin['id']}", json={"clear_password": True})
    assert r.status_code == 400

    # Once admin2 is gone, the sole admin can clear their own password.
    assert client.delete(f"/api/users/{other_id}").status_code == 200
    r = client.put(f"/api/users/{admin['id']}", json={"clear_password": True})
    assert r.status_code == 200


def test_clear_password_solo_admin_returns_to_autologin(app_ctx):
    """Single admin who set a password by mistake can clear it and get
    the zero-config auto-login back."""
    _app, client, _db = app_ctx
    import auth

    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    client.post("/login", data={"username": "admin", "password": "adminpw"})

    # Sole admin can clear their own password.
    r = client.put(f"/api/users/{admin['id']}", json={"clear_password": True})
    assert r.status_code == 200
    assert _db.get_user_by_id(admin["id"])["password_hash"] is None

    # New session: auto-login picks up the passwordless admin again.
    fresh = _app.app.test_client()
    assert fresh.get("/").status_code == 200


def test_promote_passwordless_user_to_admin_requires_password(app_ctx):
    """Promoting a passwordless user to admin without supplying a password
    in the same call would create another passwordless admin -> reject."""
    _app, client, _db = app_ctx
    import auth

    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    client.post("/login", data={"username": "admin", "password": "adminpw"})

    ghost_id = _db.create_user("ghost", auth.ROLE_READONLY, None)

    # Without password in the same call -> rejected (would_lock_platform if
    # admin then ever cleared theirs; we err on the safe side).
    r = client.put(f"/api/users/{ghost_id}", json={"role": "admin"})
    assert r.status_code == 400

    # With password in the same call -> allowed.
    r = client.put(
        f"/api/users/{ghost_id}",
        json={"role": "admin", "password": "ghostpw"},
    )
    assert r.status_code == 200


def test_session_is_a_sliding_window(app_ctx):
    """Each authenticated request refreshes the session cookie's expiry,
    so active users never get logged out within the 30-day window. After
    30 days of inactivity the cookie expires and the user must log in
    again. Flask uses the Expires attribute (older format) by default."""
    _app, client, _db = app_ctx
    import time
    from email.utils import parsedate_to_datetime

    import auth

    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))

    lifetime = int(_app.app.permanent_session_lifetime.total_seconds())
    assert lifetime == 30 * 24 * 3600  # 30 days

    def _expires_seconds_from_now(set_cookie: str) -> int:
        import re as _re
        m = _re.search(r"Expires=([^;]+)", set_cookie)
        assert m, f"no Expires in cookie: {set_cookie!r}"
        exp = parsedate_to_datetime(m.group(1).strip())
        return int(exp.timestamp() - time.time())

    # Login issues a session cookie expiring ~30 days from now.
    r1 = client.post(
        "/login",
        data={"username": "admin", "password": "adminpw"},
    )
    assert r1.status_code == 302
    delta1 = _expires_seconds_from_now(r1.headers["Set-Cookie"])
    assert lifetime - 5 <= delta1 <= lifetime, delta1

    # Sleep a moment so the second cookie's Expires would visibly differ.
    time.sleep(1.1)

    # Follow-up request re-issues the cookie with a fresh Expires.
    r2 = client.get("/")
    assert r2.status_code == 200
    set_cookie_followup = r2.headers.get("Set-Cookie", "")
    assert set_cookie_followup, "follow-up request must re-issue the session cookie (sliding window)"
    delta2 = _expires_seconds_from_now(set_cookie_followup)
    assert lifetime - 5 <= delta2 <= lifetime, delta2
    # The window slid forward.
    assert delta2 >= delta1, (delta1, delta2)


def test_create_user_without_password_rejected(app_ctx):
    """Passwordless users created via the API guarantee a lockout once a
    second admin exists, so the endpoint must refuse them."""
    _app, client, _db = app_ctx
    import auth

    admin = _db.get_user_by_name(auth.DEFAULT_ADMIN_USERNAME)
    _db.update_user(admin["id"], password_hash=auth.hash_password("adminpw"))
    client.post("/login", data={"username": "admin", "password": "adminpw"})

    # No password field
    r = client.post(
        "/api/users",
        json={"username": "ghost", "role": "readonly"},
    )
    assert r.status_code == 400

    # Empty password string
    r = client.post(
        "/api/users",
        json={"username": "ghost", "role": "readonly", "password": ""},
    )
    assert r.status_code == 400

    # Sanity: with a real password it works
    r = client.post(
        "/api/users",
        json={"username": "ghost", "role": "readonly", "password": "pw"},
    )
    assert r.status_code == 200
