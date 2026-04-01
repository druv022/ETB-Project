"""SQLite-backed user accounts for the Streamlit UI (bcrypt password hashes)."""

from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path

import bcrypt

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")

_MAX_PASSWORD_LEN = 1024
_DUMMY_HASH = bcrypt.hashpw(b"__dummy__", bcrypt.gensalt(rounds=4)).decode("ascii")


def default_users_db_path() -> Path:
    raw = os.environ.get("ETB_USERS_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    cwd = Path.cwd()
    data_dir = cwd / "data"
    return data_dir / "users.sqlite"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path), check_same_thread=False)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """)
    conn.commit()


def validate_username(username: str) -> str | None:
    u = username.strip()
    if not u or len(u) > 64:
        return "Username must be 1–64 characters after trimming."
    if not _USERNAME_RE.match(u):
        return "Username may only contain letters, digits, and . _ -"
    return None


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > _MAX_PASSWORD_LEN:
        return f"Password must be at most {_MAX_PASSWORD_LEN} characters."
    return None


def register_user(
    db_path: Path,
    username: str,
    password: str,
    *,
    reserved_username: str | None = None,
) -> tuple[bool, str | None]:
    """Register a new user. Returns (ok, error_message)."""
    err = validate_username(username)
    if err:
        return False, err
    err = validate_password(password)
    if err:
        return False, err
    u = username.strip()
    if reserved_username is not None and u == reserved_username.strip():
        return False, "This username is reserved."

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (u, pw_hash, time.time()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return False, "Username already taken."
    finally:
        conn.close()
    return True, None


def verify_user_password(db_path: Path, username: str, password: str) -> bool:
    """Return True if username exists and password matches."""
    u = username.strip()
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (u,),
        ).fetchone()
    finally:
        conn.close()

    if row:
        stored = row[0]
        return bcrypt.checkpw(
            password.encode("utf-8"),
            stored.encode("ascii") if isinstance(stored, str) else stored,
        )

    bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH.encode("ascii"))
    return False
