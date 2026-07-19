from __future__ import annotations
from pathlib import Path

from pydiag.presentation.chrome import CLIPBOARD_SHORTCUT_GUARD_HTML


ROOT = Path(__file__).resolve().parents[2]


def test_streamlit_config_uses_viewer_toolbar_mode() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'toolbarMode = "viewer"' in config


def test_clipboard_shortcut_guard_stops_modifier_copy_keys() -> None:
    assert "pydiagClipboardGuard" in CLIPBOARD_SHORTCUT_GUARD_HTML
    assert 'key === "c"' in CLIPBOARD_SHORTCUT_GUARD_HTML
    assert "event.stopPropagation()" in CLIPBOARD_SHORTCUT_GUARD_HTML
    assert "event.ctrlKey || event.metaKey" in CLIPBOARD_SHORTCUT_GUARD_HTML
