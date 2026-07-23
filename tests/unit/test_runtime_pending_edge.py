from __future__ import annotations

from pydiag.application import CreateGraphSourceEdgeCommand
from pydiag.presentation.runtime import StreamlitAppRuntime


class FakeSession:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {
            "well_drilling_flow_canvas": {
                "pending_edge": {
                    "source": "proc_initial_review",
                    "target": "card_mitigation",
                    "kind": "dashed",
                }
            }
        }
        self.created: list[CreateGraphSourceEdgeCommand] = []
        self.edit_available = True

    def graph_source_edit_available(self) -> bool:
        return self.edit_available

    def graph_source_edit_block_reason(self) -> str | None:
        return None if self.edit_available else "blocked"

    def create_graph_source_edge(self, graph, command: CreateGraphSourceEdgeCommand, **kwargs) -> None:
        _ = graph
        _ = kwargs
        self.created.append(command)


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


class RuntimeWithSession(StreamlitAppRuntime):
    def __init__(self, st_module, session: FakeSession) -> None:
        super().__init__(st_module, documents_gateway=object())  # type: ignore[arg-type]
        self._session = session

    @property
    def session(self):  # type: ignore[override]
        return self._session


def test_runtime_consumes_pending_canvas_edge(documents) -> None:
    graph, _ = documents
    st_module = FakeStreamlit()
    session = FakeSession()
    runtime = RuntimeWithSession(st_module, session)

    runtime._consume_pending_canvas_edge(graph)

    assert len(session.created) == 1
    assert session.created[0].source == "proc_initial_review"
    assert session.created[0].target == "card_mitigation"
    assert session.created[0].kind == "dashed"
    assert session.session_state["well_drilling_flow_canvas"]["pending_edge"] is None


def test_runtime_blocks_pending_canvas_edge_when_edit_unavailable(documents) -> None:
    graph, _ = documents
    st_module = FakeStreamlit()
    session = FakeSession()
    session.edit_available = False
    runtime = RuntimeWithSession(st_module, session)

    runtime._consume_pending_canvas_edge(graph)

    assert session.created == []
    assert st_module.errors == ["blocked"]
