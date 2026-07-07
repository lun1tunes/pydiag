from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.rendering import component_selected_id_from_state

__all__ = [
    "component_state_from_session",
    "resolve_selected_id",
    "sync_returned_selected_id",
]


def component_state_from_session(
    session_state: Mapping[str, Any],
    component_key: str,
) -> Mapping[str, object] | None:
    component_state = session_state.get(component_key)
    if isinstance(component_state, Mapping):
        return component_state
    return None


def resolve_selected_id(
    session_state: MutableMapping[str, Any],
    graph: FlowGraphDocument,
    wells: WellsDocument,
    component_state: Mapping[str, object] | None,
) -> str | None:
    component_has_selected_id = component_state is not None and "selected_id" in component_state
    selected_id = component_selected_id_from_state(graph, wells, component_state)
    if selected_id is None and not component_has_selected_id:
        return session_state.get("selected_id")
    if component_has_selected_id:
        session_state["selected_id"] = selected_id
    return selected_id


def sync_returned_selected_id(
    session_state: MutableMapping[str, Any],
    graph: FlowGraphDocument,
    wells: WellsDocument,
    selected_id: str | None,
    returned: object,
) -> str | None:
    returned_has_selected_id = isinstance(returned, Mapping) and "selected_id" in returned
    returned_selected_id = component_selected_id_from_state(graph, wells, returned)
    if returned_selected_id != selected_id or (
        returned_has_selected_id and returned_selected_id is None
    ):
        session_state["selected_id"] = returned_selected_id
        return returned_selected_id
    return selected_id
