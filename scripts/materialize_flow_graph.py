from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from pydiag.infrastructure import materialize_flow_graph_from_source  # noqa: E402
from pydiag.infrastructure.storage_paths import (  # noqa: E402
    GRAPH_PATH_ENV,
    RAW_GRAPH_PATH_ENV,
    SOURCE_GRAPH_PATH_ENV,
    configured_graph_path,
    graph_path,
    preferred_graph_source_path,
    raw_graph_path,
    source_graph_path,
)


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) > 2:
        raise SystemExit(
            "Usage: python scripts/materialize_flow_graph.py [source_graph.(json|yaml)] [target_flow_graph.json]"
        )

    source = (preferred_graph_source_path() or source_graph_path() or raw_graph_path()).resolve()
    target = (configured_graph_path() or graph_path()).resolve()
    if args:
        source = Path(args[0]).resolve()
    if len(args) == 2:
        target = Path(args[1]).resolve()

    graph = materialize_flow_graph_from_source(source_path=source, target_path=target)
    print(
        "Materialized flow graph: "
        f"{target} ({len(graph.nodes)} nodes, {len(graph.edges)} edges) from {source}. "
        "Defaults can be overridden via "
        f"{SOURCE_GRAPH_PATH_ENV}, {RAW_GRAPH_PATH_ENV} and {GRAPH_PATH_ENV}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
