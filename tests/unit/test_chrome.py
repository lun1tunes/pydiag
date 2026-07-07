from __future__ import annotations

from pydiag.presentation.chrome import inject_css, legend_html


class CaptureStreamlitModule:
    def __init__(self):
        self.rendered: list[str] = []

    def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
        assert unsafe_allow_html is True
        self.rendered.append(body)


def test_legend_html_explains_block_types_and_responsible_colors(documents) -> None:
    graph, _ = documents

    html = legend_html(graph)

    assert "Типы блоков" in html
    assert "Процесс" in html
    assert "Решение" in html
    assert "База данных" in html
    assert "Входные данные" in html
    assert "Событие" in html
    assert "Цвета ответственных" in html
    assert graph.responsibles["planning"].fill in html
    assert graph.responsibles["planning"].border in html
    assert "Планирование" in html
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
    toolbar_block = css.split('[data-testid="stToolbar"] {', maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "display: none" not in toolbar_block
