from __future__ import annotations

import streamlit as st

from pydiag.infrastructure import FileAuthSessionStore, JsonDocumentsGateway
from pydiag.presentation.auth_persistence import auth_session_ttl_seconds
from pydiag.presentation.runtime import StreamlitAppRuntime
from pydiag.rendering.flow_canvas_component import render_flow_canvas

st.set_page_config(
    page_title="Схема планирования и строительства скважин",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Keep developer hotkeys ("C" clear-cache, "R" rerun) out of the way of clipboard shortcuts.
st.set_option("client.toolbarMode", "viewer")


def runtime() -> StreamlitAppRuntime:
    return StreamlitAppRuntime(
        st_module=st,
        documents_gateway=JsonDocumentsGateway(),
        auth_session_store=FileAuthSessionStore(),
        auth_session_ttl_seconds=auth_session_ttl_seconds(),
        render_canvas=render_flow_canvas,
    )


def main() -> None:
    runtime().run()


__all__ = [
    "StreamlitAppRuntime",
    "main",
    "render_flow_canvas",
    "runtime",
    "st",
]
