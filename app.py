"""Streamlit Orion UI with user registration, admin shell, and role-based routing."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from etb_project.ui.admin import (
    render_admin_documents,
    render_admin_health,
    render_admin_logs,
    render_admin_settings,
)
from etb_project.ui.auth_page import render_auth_screen
from etb_project.ui.orion_chat import render_orion
from etb_project.ui.orion_theme import ORION_STYLE_MARKDOWN

load_dotenv()

_ADMIN_SECTIONS = ["Orion", "Logs", "Settings", "System health", "Documents"]


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages: list[dict[str, str]] = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = os.urandom(16).hex()
    if "last_sources" not in st.session_state:
        st.session_state.last_sources = []
    if "auth_role" not in st.session_state:
        st.session_state.auth_role = None
    if "auth_username" not in st.session_state:
        st.session_state.auth_username = None
    if "admin_nav_sel" not in st.session_state:
        st.session_state.admin_nav_sel = "Orion"


def _logout() -> None:
    st.session_state.auth_role = None
    st.session_state.auth_username = None
    st.session_state.admin_nav_sel = "Orion"
    st.session_state.messages = []
    st.session_state.session_id = os.urandom(16).hex()
    st.session_state.last_sources = []


def _render_header_bar() -> None:
    role = st.session_state.get("auth_role")
    user = st.session_state.get("auth_username") or ""
    label = "Administrator" if role == "admin" else "User"
    initial = (user[:1] or "?").upper()
    role_class = "admin" if role == "admin" else "user"

    st.sidebar.markdown(
        f"""
        <div class="orion-sidebar-brand">
          <div class="orion-sidebar-mark">
            <div class="orion-sidebar-orb"></div>
          </div>
          <div class="orion-sidebar-brand-text">
            <div class="orion-sidebar-brand-title">Orion</div>
            <div class="orion-sidebar-brand-sub">Executive AI</div>
          </div>
        </div>
        <div class="orion-sidebar-user">
          <div class="orion-sidebar-avatar">{initial}</div>
          <div class="orion-sidebar-user-text">
            <div class="orion-sidebar-username">{user}</div>
            <div class="orion-sidebar-role orion-sidebar-role-{role_class}">
              <span class="dot"></span>{label}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.sidebar.button("Log out", key="btn_logout", use_container_width=True):
        _logout()
        st.rerun()


def _render_admin_shell() -> None:
    if st.session_state.get("auth_role") != "admin":
        st.error("Unauthorized.")
        return

    _render_header_bar()
    st.sidebar.markdown("---")
    st.session_state.setdefault("admin_nav_sel", "Orion")
    sel = st.sidebar.radio(
        "Section",
        _ADMIN_SECTIONS,
        key="admin_nav_sel",
    )

    if sel == "Orion":
        render_orion()
    elif sel == "Logs":
        render_admin_logs()
    elif sel == "Settings":
        render_admin_settings()
    elif sel == "System health":
        render_admin_health()
    elif sel == "Documents":
        render_admin_documents()


def main() -> None:
    st.set_page_config(
        page_title="Orion",
        page_icon="🛰️",
        layout="wide",
    )
    st.markdown(ORION_STYLE_MARKDOWN, unsafe_allow_html=True)

    ensure_session_state()

    if not st.session_state.auth_role:
        render_auth_screen()
        return

    if st.session_state.auth_role == "user":
        _render_header_bar()
        render_orion()
        return

    if st.session_state.auth_role == "admin":
        _render_admin_shell()
        return

    st.error("Invalid session state.")
    _logout()


if __name__ == "__main__":
    main()
