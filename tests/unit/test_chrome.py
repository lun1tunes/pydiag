from __future__ import annotations

from pydiag.presentation.chrome import (
    CLIPBOARD_GUARD_SESSION_KEY,
    inject_css,
    legend_html,
)


class CaptureStreamlitModule:
    def __init__(self):
        self.rendered: list[str] = []
        self.iframe_calls: list[tuple[str, dict[str, object]]] = []
        self.session_state: dict[str, object] = {}

    def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
        assert unsafe_allow_html is True
        self.rendered.append(body)

    def iframe(self, body: str, **kwargs) -> None:
        self.iframe_calls.append((body, kwargs))

    def set_option(self, key: str, value: object) -> None:
        _ = key, value


def test_legend_html_explains_block_types_without_responsible_colors(documents) -> None:
    graph, _ = documents

    html = legend_html(graph)

    assert "Типы блоков" in html
    assert "Процесс" in html
    assert "Решение" in html
    assert "База данных" in html
    assert "Входные данные" in html
    assert "Событие" in html
    assert "Цвета ответственных" not in html
    assert "legend-dept" not in html
    assert html.count('class="legend-symbol-svg"') == 5
    assert 'fill="#ffffff"' in html
    assert 'stroke="#111827"' in html
    assert "transform:" not in html
    assert "clip-path" not in html
    assert '<polygon points="22,3 40,15 22,27 4,15"' in html
    assert '<polygon points="9,6 40,6 35,24 4,24"' in html
    assert '<rect x="6" y="5" width="32" height="20" rx="10"' in html
    assert '<ellipse cx="22" cy="8"' in html


def test_css_keeps_sidebar_expand_control_available() -> None:
    st_module = CaptureStreamlitModule()

    inject_css(st_module)

    css = st_module.rendered[0]
    header_block = css.split('[data-testid="stHeader"],', maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "display: none" not in header_block
    assert "pointer-events: none" in header_block
    assert '[data-testid="collapsedControl"]' in css
    assert '[data-testid="stExpandSidebarButton"]' in css
    assert '[data-testid="stHeader"] button' in css
    assert "Compact density profile." in css
    assert "--app-page-pad-top:" in css
    assert "--app-sidebar-pad-top:" in css
    assert '[data-testid="stSidebarContent"] {' in css
    assert '[data-testid="stSidebarUserContent"] {' in css
    assert 'div[data-testid="stVerticalBlock"] {' in css
    assert "gap: var(--app-stack-gap);" in css
    assert ".stApp hr {" in css
    hidden_header_actions_block = css.split('[data-testid="stHeaderActionElements"],', maxsplit=1)[1].split(
        "}",
    )[0]
    assert '[data-testid="stStatusWidget"]' not in hidden_header_actions_block
    toolbar_block = css.split('[data-testid="stToolbar"] {', maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "display: none" not in toolbar_block
    assert len(st_module.iframe_calls) == 1
    assert "pydiagClipboardGuard" in st_module.iframe_calls[0][0]
    assert st_module.iframe_calls[0][1] == {"height": 1, "width": 1}

    assert st_module.session_state[CLIPBOARD_GUARD_SESSION_KEY] is True

    inject_css(st_module)
    assert len(st_module.iframe_calls) == 1
