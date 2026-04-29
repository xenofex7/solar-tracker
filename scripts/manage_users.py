#!/usr/bin/env python3
"""Solar-Tracker user management CLI.

Run from the project root with the project venv:

    .venv/bin/python -m scripts.manage_users <command> [args]

Commands
--------
list                          Show all users.
add <name> [--admin] [--password PW]
                              Create a user (default role: readonly,
                              no password = auto-login disabled but the
                              user cannot log in until a password is set).
set-password <name> [PW]      Set or change a password. Prompts if PW omitted.
clear-password <name>         Remove the password (used for the zero-config
                              auto-login admin).
set-role <name> admin|readonly
                              Change a user's role.
delete <name>                 Delete a user.
reset-admin [--password PW]   One-shot recovery: delete all users and seed a
                              fresh admin (passwordless if --password not
                              given, restoring the zero-config auto-login).

Safety
------
- The last admin cannot be demoted or deleted.
- Usernames must match [A-Za-z0-9_.-]{2,32}.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys

# Make the project importable when invoked as a script (not -m).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import auth  # noqa: E402
import db  # noqa: E402

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{2,32}$")


def _validate_username(name: str) -> str:
    if not USERNAME_RE.match(name or ""):
        sys.exit(f"error: invalid username {name!r} (allowed: A-Z a-z 0-9 _ . -, length 2-32)")
    return name


def _require_user(name: str) -> dict:
    user = db.get_user_by_name(name)
    if not user:
        sys.exit(f"error: user {name!r} not found")
    return user


def _prompt_password() -> str:
    pw1 = getpass.getpass("New password: ")
    if not pw1:
        sys.exit("error: empty password")
    pw2 = getpass.getpass("Repeat password: ")
    if pw1 != pw2:
        sys.exit("error: passwords do not match")
    return pw1


def cmd_list(_args) -> None:
    users = db.list_users()
    if not users:
        print("(no users)")
        return
    width = max(len(u["username"]) for u in users)
    print(f"{'id':>3}  {'username'.ljust(width)}  role      password")
    print(f"{'-' * 3}  {'-' * width}  {'-' * 8}  {'-' * 8}")
    for u in users:
        pw = "set" if u["has_password"] else "(none)"
        print(f"{u['id']:>3}  {u['username'].ljust(width)}  {u['role']:<8}  {pw}")


def cmd_add(args) -> None:
    _validate_username(args.username)
    if db.get_user_by_name(args.username):
        sys.exit(f"error: user {args.username!r} already exists")
    role = auth.ROLE_ADMIN if args.admin else auth.ROLE_READONLY
    pw_hash = auth.hash_password(args.password) if args.password else None
    new_id = db.create_user(args.username, role, pw_hash)
    print(f"created user #{new_id}: {args.username} (role={role}, password={'set' if pw_hash else '(none)'})")


def cmd_set_password(args) -> None:
    user = _require_user(args.username)
    pw = args.password or _prompt_password()
    db.update_user(user["id"], password_hash=auth.hash_password(pw))
    print(f"password updated for {args.username}")


def cmd_clear_password(args) -> None:
    user = _require_user(args.username)
    db.update_user(user["id"], clear_password=True)
    print(f"password cleared for {args.username}")
    if db.count_users() == 1 and user["role"] == auth.ROLE_ADMIN:
        print("note: zero-config auto-login is now active (single passwordless admin)")


def cmd_set_role(args) -> None:
    user = _require_user(args.username)
    if args.role not in auth.ROLES:
        sys.exit(f"error: role must be one of {auth.ROLES}")
    if (
        user["role"] == auth.ROLE_ADMIN
        and args.role != auth.ROLE_ADMIN
        and db.count_admins() <= 1
    ):
        sys.exit("error: refusing to demote the last admin")
    db.update_user(user["id"], role=args.role)
    print(f"role updated for {args.username}: {args.role}")


def cmd_delete(args) -> None:
    user = _require_user(args.username)
    if user["role"] == auth.ROLE_ADMIN and db.count_admins() <= 1:
        sys.exit("error: refusing to delete the last admin")
    db.delete_user(user["id"])
    print(f"deleted user {args.username}")


def cmd_reset_admin(args) -> None:
    """Wipe all users and seed a fresh admin.

    Without --password the seeded admin has no password set, which puts
    the platform back into the zero-config auto-login state.
    """
    with db.connect() as conn:
        conn.execute("DELETE FROM users")
    pw_hash = auth.hash_password(args.password) if args.password else None
    new_id = db.create_user(auth.DEFAULT_ADMIN_USERNAME, auth.ROLE_ADMIN, pw_hash)
    print(
        f"reset complete: created admin #{new_id} "
        f"({'with password' if pw_hash else 'no password -> auto-login'})"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manage_users",
        description="Solar-Tracker user management CLI.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all users.").set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Create a user.")
    p_add.add_argument("username")
    p_add.add_argument("--admin", action="store_true", help="Create as admin (default: readonly).")
    p_add.add_argument("--password", help="Set password. Omit to leave empty.")
    p_add.set_defaults(func=cmd_add)

    p_setpw = sub.add_parser("set-password", help="Set or change a password.")
    p_setpw.add_argument("username")
    p_setpw.add_argument("password", nargs="?", help="If omitted, prompts twice.")
    p_setpw.set_defaults(func=cmd_set_password)

    p_clr = sub.add_parser("clear-password", help="Remove a user's password.")
    p_clr.add_argument("username")
    p_clr.set_defaults(func=cmd_clear_password)

    p_role = sub.add_parser("set-role", help="Change a user's role.")
    p_role.add_argument("username")
    p_role.add_argument("role", choices=list(auth.ROLES))
    p_role.set_defaults(func=cmd_set_role)

    p_del = sub.add_parser("delete", help="Delete a user.")
    p_del.add_argument("username")
    p_del.set_defaults(func=cmd_delete)

    p_reset = sub.add_parser(
        "reset-admin",
        help="Wipe all users and seed a fresh admin (recovery).",
    )
    p_reset.add_argument("--password", help="Optional password for the seeded admin.")
    p_reset.set_defaults(func=cmd_reset_admin)

    return p


def main(argv: list[str] | None = None) -> None:
    db.init_db()
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
