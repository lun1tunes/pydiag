from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

main = importlib.import_module("pydiag.presentation.streamlit_app").main


if __name__ == "__main__":
    main()
