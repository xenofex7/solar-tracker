"""Authentication and authorization helpers.

Slim, dependency-free auth on top of Flask's signed session cookies.

Password storage uses PBKDF2-HMAC-SHA256 from the stdlib (no extra deps).
The session secret is taken from FLASK_SECRET_KEY, otherwise an auto-generated
value is persisted in the settings table on first run.

Roles:
- "admin"    full access (UI + write APIs + user management)
- "readonly" dashboard + GET APIs only

Auto-login rule (zero-config): if there is exactly one user (the seeded
default admin) and that user has no password set, every request is
auto-logged-in as that admin. As soon as a password is set or a second user
is created, normal login is required.

In addition to the session cookie, HTTP Basic Auth is honored on /api/*
routes so read-only users can fetch JSON from scripts.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import os
import secrets
from base64 import b64decode

from flask import g, jsonify, redirect, request, session, url_for

import db

ROLE_ADMIN = "admin"
ROLE_READONLY = "readonly"
ROLES = (ROLE_ADMIN, ROLE_READONLY)

DEFAULT_ADMIN_USERNAME = "admin"

_PBKDF2_ITER = 200_000
_PBKDF2_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """Return a self-describing password hash string."""
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITER
    )
    return f"{_PBKDF2_ALGO}${_PBKDF2_ITER}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check of a password against a stored hash string."""
    if not stored or not password:
        return False
    try:
        algo, iter_s, salt_hex, hash_hex = stored.split("$", 3)
    except ValueError:
        return False
    if algo != _PBKDF2_ALGO:
        return False
    try:
        iters = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iters
    )
    return hmac.compare_digest(candidate, expected)


def get_or_create_secret_key() -> str:
    """Stable session secret across restarts.

    Priority: env FLASK_SECRET_KEY > settings table > newly generated value
    written to the settings table.
    """
    env = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if env:
        return env
    stored = db.get_setting("session_secret")
    if stored:
        return stored
    new_secret = secrets.token_hex(32)
    db.set_setting("session_secret", new_secret)
    return new_secret


def ensure_default_admin() -> None:
    """Seed the default admin user if no users exist at all."""
    if db.count_users() == 0:
        db.create_user(DEFAULT_ADMIN_USERNAME, ROLE_ADMIN, password_hash=None)


def auto_login_user() -> dict | None:
    """Return the user dict for the auto-login admin, or None.

    Auto-login is only allowed when the platform is in zero-config mode:
    a single user exists, that user is an admin, and they have no password.
    """
    if db.count_users() != 1:
        return None
    user = db.get_user_by_name(DEFAULT_ADMIN_USERNAME)
    if not user:
        return None
    if user["role"] != ROLE_ADMIN:
        return None
    if user["password_hash"]:
        return None
    return user


def _basic_auth_user() -> dict | None:
    """Return the user authenticated via HTTP Basic, or None."""
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("basic "):
        return None
    try:
        raw = b64decode(header.split(" ", 1)[1].strip()).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if ":" not in raw:
        return None
    username, password = raw.split(":", 1)
    user = db.get_user_by_name(username)
    if not user or not user["password_hash"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def load_current_user() -> dict | None:
    """Resolve the current user from session, Basic Auth, or auto-login."""
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.get_user_by_id(user_id)
        if user:
            return user
        # Stale session: drop it.
        session.pop("user_id", None)

    if request.path.startswith("/api/"):
        basic = _basic_auth_user()
        if basic is not None:
            return basic

    return auto_login_user()


def login(user: dict) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True


def logout() -> None:
    session.clear()


def current_user() -> dict | None:
    return getattr(g, "user", None)


def is_admin() -> bool:
    user = current_user()
    return bool(user and user["role"] == ROLE_ADMIN)


def _wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            if _wants_json():
                return jsonify({"error": "authentication required"}), 401
            return redirect(url_for("login_page", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def require_role(role: str):
    def decorator(view):
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                if _wants_json():
                    return jsonify({"error": "authentication required"}), 401
                return redirect(url_for("login_page", next=request.path))
            if role == ROLE_ADMIN and user["role"] != ROLE_ADMIN:
                if _wants_json():
                    return jsonify({"error": "forbidden"}), 403
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapper

    return decorator
