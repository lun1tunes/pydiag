from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from pydiag.infrastructure import load_payload, normalize_figma_skeleton_payload  # noqa: E402
from pydiag.infrastructure.storage_paths import RAW_GRAPH_PATH_ENV, raw_graph_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    target = raw_graph_path().resolve()
    if args:
        target = Path(args[0]).resolve()
    if not target.exists():
        raise FileNotFoundError(
            f"Raw graph source file not found: {target}. Pass a path or set {RAW_GRAPH_PATH_ENV}."
        )

    payload = load_payload(target.read_bytes())
    normalized = normalize_figma_skeleton_payload(payload)
    target.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Normalized skeleton: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
