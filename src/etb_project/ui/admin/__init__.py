"""Streamlit admin-only sections (requires ``auth_role == admin``)."""

from etb_project.ui.admin.documents import render_admin_documents
from etb_project.ui.admin.health import render_admin_health
from etb_project.ui.admin.logs import render_admin_logs
from etb_project.ui.admin.settings_view import render_admin_settings

__all__ = [
    "render_admin_documents",
    "render_admin_health",
    "render_admin_logs",
    "render_admin_settings",
]
