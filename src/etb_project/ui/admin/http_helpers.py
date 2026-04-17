"""HTTP helpers for Streamlit admin pages."""

from __future__ import annotations

from typing import Any

import requests

from etb_project.ui.auth_credentials import admin_api_token


def admin_bearer_headers() -> dict[str, str]:
    t = admin_api_token()
    if not t:
        return {}
    return {"Authorization": f"Bearer {t}"}


def format_request_error(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code == 401:
            return "Not authenticated (401). Check ``ETB_ADMIN_API_TOKEN`` matches orchestrator/retriever."
        if code == 403:
            return "Forbidden (403)."
        if code == 404:
            return "Not found (404). Admin API may be disabled (token unset on server)."
        try:
            body = exc.response.json()
            msg = body.get("message") or body.get("detail")
            if isinstance(msg, dict):
                msg = msg.get("message")
            if msg:
                return f"HTTP {code}: {msg}"
        except Exception:
            pass
        return f"HTTP {code} from server."
    return f"Request failed: {exc}"


def get_json(
    url: str, *, timeout: float = 30.0
) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        r = requests.get(url, headers=admin_bearer_headers(), timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as exc:
        return None, format_request_error(exc)


def delete_json(url: str, *, timeout: float = 120.0) -> tuple[bool, str | None]:
    try:
        r = requests.delete(url, headers=admin_bearer_headers(), timeout=timeout)
        r.raise_for_status()
        return True, None
    except requests.RequestException as exc:
        return False, format_request_error(exc)


def post_empty(
    url: str, *, timeout: float = 30.0
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        r = requests.post(url, headers=admin_bearer_headers(), timeout=timeout)
        r.raise_for_status()
        try:
            return r.json(), None
        except Exception:
            return {}, None
    except requests.RequestException as exc:
        return None, format_request_error(exc)
