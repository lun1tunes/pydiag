"""Presentation layer public API."""

from __future__ import annotations

from .admin import AdminActions, render_admin_panel, suggest_well_id
from .auth import AuthUser, StreamlitAuthContext
from .chrome import inject_css, legend_html, legend_type_icon, render_header, render_legend
from .inspector import InspectorActions, render_inspector
from .runtime import StreamlitAppRuntime
from .selection import resolve_selection
from .sidebar import KIND_FILTER_LABELS, SidebarActions, SidebarState, render_sidebar

__all__ = [
    "AdminActions",
    "AuthUser",
    "InspectorActions",
    "KIND_FILTER_LABELS",
    "SidebarActions",
    "SidebarState",
    "StreamlitAppRuntime",
    "StreamlitAuthContext",
    "inject_css",
    "legend_html",
    "legend_type_icon",
    "render_admin_panel",
    "render_header",
    "render_inspector",
    "render_legend",
    "render_sidebar",
    "resolve_selection",
    "suggest_well_id",
]
