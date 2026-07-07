from __future__ import annotations

import pydiag.presentation.streamlit_app as streamlit_app
from pydiag.infrastructure import JsonDocumentsGateway


def test_runtime_uses_module_streamlit_and_local_canvas() -> None:
    runtime = streamlit_app.runtime()

    assert runtime.st_module is streamlit_app.st
    assert isinstance(runtime.documents_gateway, JsonDocumentsGateway)
    assert runtime.render_canvas is streamlit_app.render_flow_canvas


def test_main_delegates_to_runtime(monkeypatch) -> None:
    calls: list[str] = []

    class FakeRuntime:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(streamlit_app, "runtime", lambda: FakeRuntime())

    streamlit_app.main()

    assert calls == ["run"]
