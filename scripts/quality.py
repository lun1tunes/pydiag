from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def compile_python() -> None:
    files = [
        ROOT / "app.py",
        ROOT / "scripts" / "validate_data.py",
        ROOT / "scripts" / "quality.py",
        ROOT / "scripts" / "venv_run.py",
        *sorted((ROOT / "src" / "pydiag").glob("*.py")),
    ]
    for path in files:
        py_compile.compile(str(path), doraise=True)


def main() -> int:
    run([str(ROOT / "scripts" / "validate_data.py")])
    compile_python()
    run(["-m", "ruff", "check", "."])
    run(["-m", "ruff", "format", "--check", "."])
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
