"""Tests for SQLite user store and login resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from etb_project.ui.auth_credentials import resolve_login
from etb_project.ui.user_store import register_user, verify_user_password


def test_register_and_verify(tmp_path: Path) -> None:
    db = tmp_path / "users.sqlite"
    ok, err = register_user(db, "alice", "password123", reserved_username=None)
    assert ok is True
    assert err is None
    assert verify_user_password(db, "alice", "password123") is True
    assert verify_user_password(db, "alice", "wrong") is False
    assert verify_user_password(db, "nobody", "password123") is False


def test_register_duplicate(tmp_path: Path) -> None:
    db = tmp_path / "users.sqlite"
    assert register_user(db, "bob", "password123")[0] is True
    ok, err = register_user(db, "bob", "otherpass123")
    assert ok is False
    assert err is not None


def test_reserved_username(tmp_path: Path) -> None:
    db = tmp_path / "users.sqlite"
    ok, err = register_user(
        db,
        "superadmin",
        "password123",
        reserved_username="superadmin",
    )
    assert ok is False
    assert err is not None


def test_resolve_login_admin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "users.sqlite"
    monkeypatch.setenv("ETB_ADMIN_USERNAME", "root")
    monkeypatch.setenv("ETB_ADMIN_PASSWORD", "secretpw")
    role, err = resolve_login(db, "root", "secretpw")
    assert role == "admin"
    assert err is None


def test_resolve_login_admin_wrong_password(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = tmp_path / "users.sqlite"
    monkeypatch.setenv("ETB_ADMIN_USERNAME", "root")
    monkeypatch.setenv("ETB_ADMIN_PASSWORD", "secretpw")
    role, err = resolve_login(db, "root", "nope")
    assert role is None
    assert err == "Invalid username or password."


def test_resolve_login_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ETB_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ETB_ADMIN_PASSWORD", raising=False)
    db = tmp_path / "users.sqlite"
    register_user(db, "carol", "password123")
    role, err = resolve_login(db, "carol", "password123")
    assert role == "user"
    assert err is None
