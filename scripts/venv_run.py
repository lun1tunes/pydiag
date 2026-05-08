from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> Path:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "Scripts" / "python",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Virtual environment Python was not found. Create it first with "
        "`python -m venv .venv` or `py -3.13 -m venv .venv`."
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/venv_run.py <python-args>", file=sys.stderr)
        return 2
    return subprocess.call([str(venv_python()), *sys.argv[1:]], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
