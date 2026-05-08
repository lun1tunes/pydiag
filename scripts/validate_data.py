from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from pydiag.storage import load_documents  # noqa: E402


def main() -> int:
    graph, wells = load_documents()
    print(f"OK: {len(graph.nodes)} nodes, {len(graph.edges)} edges, {len(wells.wells)} wells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
