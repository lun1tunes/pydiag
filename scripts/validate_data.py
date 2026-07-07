from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from pydiag.infrastructure.storage import load_documents  # noqa: E402


def validate_graph_connectivity(graph) -> None:
    node_ids = [node.id for node in graph.nodes]
    if not node_ids:
        raise ValueError("Graph must contain at least one node")

    node_set = set(node_ids)
    incident_nodes = {edge.source for edge in graph.edges} | {edge.target for edge in graph.edges}
    isolated = sorted(node_set - incident_nodes)
    if isolated:
        raise ValueError(f"Graph has isolated nodes without edges: {', '.join(isolated)}")

    adjacency = {node_id: set() for node_id in node_ids}
    for edge in graph.edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)

    seen = {node_ids[0]}
    queue: deque[str] = deque([node_ids[0]])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)

    unreachable = sorted(node_set - seen)
    if unreachable:
        raise ValueError(
            f"Graph is not fully connected; unreachable nodes: {', '.join(unreachable)}"
        )


def main() -> int:
    graph_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    wells_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    graph, wells = load_documents(graph_path, wells_path)
    validate_graph_connectivity(graph)
    print(f"OK: {len(graph.nodes)} nodes, {len(graph.edges)} edges, {len(wells.wells)} wells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
