from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUFF_CHECK_ARGS = [
    "-m",
    "ruff",
    "check",
    ".",
    "--line-length=100",
    "--target-version=py313",
    "--select=B,E,F,I,UP",
    "--ignore=E501",
    "--per-file-ignores=app.py:E402",
]
RUFF_FORMAT_ARGS = [
    "-m",
    "ruff",
    "format",
    "--check",
    ".",
    "--line-length=100",
    "--target-version=py313",
]


def run(args: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        check=True,
        env={**os.environ, **(env or {})},
    )


def compile_python() -> None:
    files = [
        ROOT / "app.py",
        *sorted((ROOT / "scripts").glob("*.py")),
        *sorted((ROOT / "src" / "pydiag").rglob("*.py")),
    ]
    for path in files:
        py_compile.compile(str(path), doraise=True)


def main() -> int:
    run([str(ROOT / "scripts" / "verify_repository_safety.py")])
    run(
        [
            str(ROOT / "scripts" / "validate_data.py"),
            str(ROOT / "tests" / "fixtures" / "flow_source.yaml"),
            str(ROOT / "tests" / "fixtures" / "wells.yaml"),
        ]
    )
    compile_python()
    run(RUFF_CHECK_ARGS)
    run(RUFF_FORMAT_ARGS)
    run(
        [
            "-m",
            "pytest",
            "--cov=src/pydiag",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
