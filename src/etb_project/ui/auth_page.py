"""Centered login and registration UI for Streamlit."""

from __future__ import annotations

import time

import streamlit as st

from etb_project.ui.auth_credentials import (
    admin_configured,
    admin_username,
    resolve_login,
)
from etb_project.ui.user_store import default_users_db_path, register_user

_AUTH_WINDOW_S = 60.0
_AUTH_MAX_ATTEMPTS = 20

AUTH_PAGE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700&family=DM+Sans:wght@400;500&display=swap');

/*
 * Auth-only layout: fixed max width (same visual card on ultrawide, laptop, or narrow windows),
 * centered with horizontal safe-area padding. Injected only on the login screen.
 */
section[data-testid="stMain"] {
  overflow-x: clip;
}

section[data-testid="stMain"] > div {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 100%;
  min-height: calc(100vh - 5rem);
  padding-top: clamp(1.25rem, 5vh, 3.5rem);
  padding-bottom: clamp(1.25rem, 4vh, 3rem);
  box-sizing: border-box;
}

section[data-testid="stMain"] div.block-container {
  width: min(28rem, calc(100vw - 1.5rem - env(safe-area-inset-left, 0px) - env(safe-area-inset-right, 0px)));
  max-width: 28rem;
  margin-left: auto !important;
  margin-right: auto !important;
  padding-left: max(0.5rem, env(safe-area-inset-left, 0px));
  padding-right: max(0.5rem, env(safe-area-inset-right, 0px));
  box-sizing: border-box;
}

/* Mode switcher + forms fill the fixed-width column */
section[data-testid="stMain"] [data-testid="stRadio"],
section[data-testid="stMain"] [data-testid="stVerticalBlock"] {
  width: 100%;
}

section[data-testid="stMain"] [data-testid="stForm"] {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  /* Sit above the radio widget root if label/collapsed wrappers overlap the form */
  position: relative;
  z-index: 1;
}

/* Text inputs span the full card width (stable across resizes) */
section[data-testid="stMain"] .stTextInput [data-baseweb="input"] {
  width: 100% !important;
  box-sizing: border-box !important;
}

section[data-testid="stMain"] .stTextInput > div[data-baseweb="base-input"] {
  width: 100%;
  max-width: 100%;
}

section[data-testid="stMain"] .stTextInput > label {
  width: 100%;
}

.auth-brand-title {
  font-family: 'Outfit', system-ui, sans-serif;
  font-weight: 700;
  font-size: clamp(2.65rem, 11vw, 4.35rem);
  line-height: 1.04;
  letter-spacing: -0.035em;
  text-align: center;
  margin: 0 0 0.65rem 0;
  padding: 0;
  border: none;
  background: linear-gradient(120deg, #fff 0%, rgba(210, 200, 255, 0.98) 40%, rgba(150, 110, 255, 0.92) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.auth-brand-sub {
  font-family: 'DM Sans', system-ui, sans-serif;
  font-size: clamp(0.875rem, 2.2vw, 0.95rem);
  text-align: center;
  color: rgba(255, 255, 255, 0.65);
  margin: 0 auto 1.25rem;
  max-width: 100%;
  line-height: 1.5;
}

/*
 * Pill-style horizontal radio only on the real option group.
 * Do NOT use [data-testid="stRadio"] > div — the first direct child is often the
 * widget label row (even when label_visibility="collapsed"), not the radiogroup.
 * Styling that div with flex/padding/background can leave an invisible hit-target
 * over the form so username/password fields cannot be focused or typed into.
 */
section[data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] {
  gap: 0.4rem;
  background: rgba(0, 0, 0, 0.28);
  padding: 0.4rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  justify-content: center;
  flex-wrap: wrap;
  width: fit-content;
  max-width: 100%;
  align-self: center;
  box-sizing: border-box;
}

section[data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] label {
  border-radius: 999px !important;
  font-family: 'DM Sans', sans-serif;
  font-weight: 600;
  padding: 0.45rem 1.1rem !important;
  margin: 0 !important;
  border: 1px solid transparent !important;
  background: transparent !important;
}

section[data-testid="stMain"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
  background: rgba(140, 90, 255, 0.4) !important;
  border: 1px solid rgba(190, 170, 255, 0.4) !important;
}

/* Form labels and primary actions (auth screen only injects this CSS) */
section[data-testid="stMain"] label[data-testid="stWidgetLabel"] {
  font-family: 'DM Sans', sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.82) !important;
}

section[data-testid="stMain"] input {
  border-radius: 12px !important;
}

section[data-testid="stMain"] .stFormSubmitButton button {
  border-radius: 12px !important;
  font-family: 'DM Sans', sans-serif;
  font-weight: 600 !important;
  padding: 0.7rem 1rem !important;
  margin-top: 0.35rem;
  background: linear-gradient(135deg, rgba(140, 90, 255, 0.6), rgba(85, 55, 190, 0.75)) !important;
  border: 1px solid rgba(190, 170, 255, 0.45) !important;
}

section[data-testid="stMain"] .stFormSubmitButton button:hover {
  border-color: rgba(255, 255, 255, 0.35) !important;
}

.auth-admin-note {
  font-family: 'DM Sans', sans-serif;
  font-size: 0.84rem;
  text-align: center;
  padding: 0.7rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(255, 200, 120, 0.28);
  background: rgba(255, 170, 50, 0.09);
  color: rgba(255, 235, 210, 0.95);
  margin: 0 auto 1rem;
  max-width: 28rem;
}
"""


def _rate_limit_auth() -> bool:
    now = time.monotonic()
    raw = st.session_state.get("_auth_attempt_times")
    if not isinstance(raw, list):
        raw = []
    window = [t for t in raw if now - t < _AUTH_WINDOW_S]
    if len(window) >= _AUTH_MAX_ATTEMPTS:
        return False
    window.append(now)
    st.session_state["_auth_attempt_times"] = window
    return True


def render_auth_screen() -> None:
    st.markdown(f"<style>\n{AUTH_PAGE_CSS}\n</style>", unsafe_allow_html=True)

    st.markdown(
        '<h1 class="auth-brand-title">Orion</h1>'
        '<p class="auth-brand-sub">Sign in to your workspace, or create an account in a few seconds.</p>',
        unsafe_allow_html=True,
    )

    if not admin_configured():
        st.markdown(
            '<div class="auth-admin-note">Admin sign-in is disabled until '
            "<code>ETB_ADMIN_USERNAME</code> and <code>ETB_ADMIN_PASSWORD</code> "
            "are configured (environment or <code>.streamlit/secrets.toml</code>).</div>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        # Use radio, not st.tabs: Streamlit often mishandles st.form + st.tabs (inactive
        # tab panels, submit not firing, or rerun snapping back to the first tab).
        auth_mode = st.radio(
            "Auth mode",
            ["Sign in", "Create account"],
            horizontal=True,
            key="auth_ui_mode",
            label_visibility="collapsed",
        )

        if auth_mode == "Sign in":
            with st.form("form_login", clear_on_submit=False):
                st.markdown("##### Welcome back")
                st.caption("Enter your credentials below.")
                lu = st.text_input(
                    "Username", key="auth_login_user", placeholder="your.name"
                )
                lp = st.text_input("Password", type="password", key="auth_login_pass")
                submitted = st.form_submit_button(
                    "Sign in",
                    use_container_width=True,
                    type="primary",
                )
                if submitted:
                    if not _rate_limit_auth():
                        st.error("Too many attempts. Wait a minute and try again.")
                    elif not (lu and lu.strip()) or not lp:
                        st.error("Enter username and password.")
                    else:
                        role, err = resolve_login(default_users_db_path(), lu, lp)
                        if role:
                            st.session_state.auth_role = role
                            st.session_state.auth_username = lu.strip()
                            st.rerun()
                        else:
                            st.error(err or "Invalid username or password.")

        else:
            with st.form("form_register", clear_on_submit=False):
                st.markdown("##### New account")
                st.caption("Password must be at least 8 characters.")
                ru = st.text_input(
                    "Username",
                    key="auth_reg_user",
                    placeholder="choose a username",
                )
                rp = st.text_input("Password", type="password", key="auth_reg_pass")
                rp2 = st.text_input(
                    "Confirm password",
                    type="password",
                    key="auth_reg_pass2",
                )
                reg_sub = st.form_submit_button(
                    "Create account",
                    use_container_width=True,
                    type="primary",
                )
                if reg_sub:
                    if not _rate_limit_auth():
                        st.error("Too many attempts. Wait a minute and try again.")
                    elif rp != rp2:
                        st.error("Passwords do not match.")
                    else:
                        reserved = admin_username() if admin_configured() else None
                        ok, msg = register_user(
                            default_users_db_path(),
                            ru,
                            rp,
                            reserved_username=reserved,
                        )
                        if ok:
                            st.success(
                                "You are all set. Switch to **Sign in** to log in."
                            )
                        else:
                            st.error(msg or "Registration failed.")
