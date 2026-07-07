#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PACK_PATH = ROOT / "scripts" / "project_pack.py"
ALLOWED_CONFIDENTIAL_TRACKED_PREFIXES = (
    "tests/fixtures/",
)

REQUIRED_ARCHIVE_PATHS = {
    ".streamlit/config.toml",
    "app.py",
    "requirements.txt",
    "src/pydiag/presentation/streamlit_app.py",
}

spec = importlib.util.spec_from_file_location("project_pack", PROJECT_PACK_PATH)
project_pack = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(project_pack)


def archive_header_paths(archive_text: str) -> set[str]:
    paths: set[str] = set()
    for line in archive_text.splitlines():
        if not line.startswith(f"{project_pack.BEGIN}\t"):
            continue
        _, rel_path, _ = line.split("\t", maxsplit=2)
        paths.add(rel_path)
    return paths


def forbidden_tracked_paths(paths: Iterable[str]) -> list[str]:
    forbidden: list[str] = []
    for rel_path in sorted(set(paths)):
        if rel_path.startswith(ALLOWED_CONFIDENTIAL_TRACKED_PREFIXES):
            continue
        if project_pack.is_confidential_rel_path(rel_path):
            forbidden.append(rel_path)
    return forbidden


def forbidden_archive_paths(paths: Iterable[str]) -> list[str]:
    forbidden: list[str] = []
    for rel_path in sorted(set(paths)):
        if project_pack.is_confidential_rel_path(rel_path):
            forbidden.append(rel_path)
    return forbidden


def tracked_repo_paths() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--", "."],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=False,
    ).stdout
    return [path.decode("utf-8") for path in output.split(b"\0") if path]


def build_runtime_archive_paths() -> set[str]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "project_bundle.txt"
        project_pack.pack(ROOT, archive_path)
        archive_text = archive_path.read_text(encoding="utf-8")
    return archive_header_paths(archive_text)


def main() -> int:
    tracked = tracked_repo_paths()
    tracked_forbidden = forbidden_tracked_paths(tracked)
    if tracked_forbidden:
        raise SystemExit(
            "Tracked confidential runtime files are forbidden:\n"
            + "\n".join(f"- {path}" for path in tracked_forbidden)
        )

    input_violations = project_pack.bundle_input_violations(ROOT)
    if input_violations:
        raise SystemExit(
            "Unsafe runtime bundle inputs are forbidden:\n"
            + "\n".join(f"- {item}" for item in input_violations)
        )

    archive_paths = build_runtime_archive_paths()
    missing = sorted(REQUIRED_ARCHIVE_PATHS - archive_paths)
    leaked = forbidden_archive_paths(archive_paths)
    if missing or leaked:
        lines = ["Runtime bundle safety check failed:"]
        if missing:
            lines.append("Missing required archive paths:")
            lines.extend(f"- {path}" for path in missing)
        if leaked:
            lines.append("Forbidden archive paths:")
            lines.extend(f"- {path}" for path in leaked)
        raise SystemExit("\n".join(lines))

    print("Repository safety checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
