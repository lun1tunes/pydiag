from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pydiag.storage import load_documents


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
APP_PATH = ROOT / "app.py"


@pytest.fixture
def data_paths(tmp_path: Path) -> tuple[Path, Path]:
    graph_path = tmp_path / "flow_graph.json"
    wells_path = tmp_path / "wells.json"
    shutil.copyfile(DATA_DIR / "flow_graph.json", graph_path)
    shutil.copyfile(DATA_DIR / "wells.json", wells_path)
    return graph_path, wells_path


@pytest.fixture
def documents(data_paths: tuple[Path, Path]):
    return load_documents(*data_paths)

