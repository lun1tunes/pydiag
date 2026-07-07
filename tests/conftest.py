from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pydiag.infrastructure import (
    load_documents,
    load_graph_doc,
    materialize_flow_graph_from_source,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "tests" / "fixtures"
FLOW_SOURCE_FIXTURE_PATH = FIXTURES_DIR / "flow_source.yaml"
WELLS_FIXTURE_PATH = FIXTURES_DIR / "wells.yaml"
APP_PATH = ROOT / "app.py"


@pytest.fixture
def data_paths(tmp_path: Path) -> tuple[Path, Path]:
    graph_path = tmp_path / "flow_graph.json"
    wells_path = tmp_path / "wells.yaml"
    materialize_flow_graph_from_source(
        source_path=FLOW_SOURCE_FIXTURE_PATH,
        target_path=graph_path,
    )
    shutil.copyfile(WELLS_FIXTURE_PATH, wells_path)
    return graph_path, wells_path


@pytest.fixture
def documents(data_paths: tuple[Path, Path]):
    return load_documents(*data_paths)


@pytest.fixture
def graph_payload(data_paths: tuple[Path, Path]):
    graph_path, _ = data_paths
    return load_graph_doc(graph_path).model_dump(mode="json")
