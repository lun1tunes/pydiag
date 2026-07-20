from __future__ import annotations

from pydiag.infrastructure.flow_source_graph import (
    graph_source_node_draft_from_payload,
    load_structured_payload,
)
from tests.integration.test_streamlit_app import (
    login_as_admin,
    prepare_temp_workspace,
    run_app_with_temp_data,
)


def test_admin_form_fields_follow_selected_node(tmp_path, monkeypatch) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)
    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    assert not app.exception
    login_as_admin(app)

    payload = load_structured_payload(source_path.read_bytes())
    draft_a = graph_source_node_draft_from_payload(payload, "proc_initial_review")
    draft_b = graph_source_node_draft_from_payload(payload, "card_mitigation")

    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    assert not app.exception
    assert app.session_state["graph_source_node_title::proc_initial_review"] == draft_a.title
    assert app.session_state["graph_source_node_kind::proc_initial_review"] == draft_a.kind
    assert int(app.session_state["graph_source_node_layout_w::proc_initial_review"]) == int(
        draft_a.layout_w
    )

    app.session_state["selected_id"] = "card_mitigation"
    app.run(timeout=30)
    assert not app.exception
    assert app.session_state["graph_source_node_title::card_mitigation"] == draft_b.title
    assert app.session_state["graph_source_node_kind::card_mitigation"] == draft_b.kind
    assert int(app.session_state["graph_source_node_layout_w::card_mitigation"]) == int(
        draft_b.layout_w
    )
