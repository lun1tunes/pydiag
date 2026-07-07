from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from pydiag.infrastructure.editable_flow_graph_materialization import (  # noqa: E402
    editable_flow_graph_payload_from_figma_payload,
)
from pydiag.infrastructure.flow_source_graph import (  # noqa: E402
    dump_flow_source_payload,
    flow_source_payload_from_editable_payload,
    load_structured_payload,
)
from pydiag.infrastructure.storage_paths import (  # noqa: E402
    RAW_GRAPH_PATH_ENV,
    SOURCE_GRAPH_PATH_ENV,
    raw_graph_path,
    source_graph_path,
)


def inferred_graph_id(path: Path) -> str:
    return path.stem.strip().replace(" ", "_").replace("-", "_") or "flow_source"


def inferred_title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip() or "Flow source"


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) > 4:
        raise SystemExit(
            "Usage: python scripts/materialize_flow_source.py "
            "[raw_graph.json] [target_flow_source.yaml] [graph_id] [title]"
        )

    source = raw_graph_path().resolve()
    target = source_graph_path().resolve()
    graph_id: str | None = None
    title: str | None = None

    if args:
        source = Path(args[0]).resolve()
    if len(args) >= 2:
        target = Path(args[1]).resolve()
    if len(args) >= 3:
        graph_id = args[2].strip() or None
    if len(args) == 4:
        title = args[3].strip() or None

    payload = load_structured_payload(source.read_bytes())
    editable_payload = editable_flow_graph_payload_from_figma_payload(payload)
    source_payload = flow_source_payload_from_editable_payload(
        editable_payload,
        graph_id=graph_id or inferred_graph_id(source),
        title=title or inferred_title(source),
    )
    target.write_text(dump_flow_source_payload(source_payload), encoding="utf-8")
    print(
        "Materialized flow source: "
        f"{target} from {source} "
        f"({len(source_payload['nodes'])} nodes, "
        f"{sum(len(node['transitions']) for node in source_payload['nodes'].values())} transitions). "
        f"Defaults can be overridden via {RAW_GRAPH_PATH_ENV} and {SOURCE_GRAPH_PATH_ENV}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
