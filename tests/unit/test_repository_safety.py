from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "verify_repository_safety.py"

spec = importlib.util.spec_from_file_location("verify_repository_safety", SCRIPT_PATH)
verify_repository_safety = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(verify_repository_safety)


def test_forbidden_tracked_paths_reject_confidential_runtime_files() -> None:
    forbidden = verify_repository_safety.forbidden_tracked_paths(
        [
            ".streamlit/config.toml",
            ".streamlit/secrets.toml",
            "data/flow_sources/flow_source.yaml",
            "data/flow_graph.json",
            "src/pydiag/service_account.json",
            "data/wells.yaml",
        ]
    )

    assert forbidden == [
        ".streamlit/secrets.toml",
        "data/flow_graph.json",
        "data/flow_sources/flow_source.yaml",
        "data/wells.yaml",
        "src/pydiag/service_account.json",
    ]


def test_forbidden_archive_paths_rejects_all_runtime_data_roots() -> None:
    forbidden = verify_repository_safety.forbidden_archive_paths(
        [
            "app.py",
            "data/flow_sources/flow_source.v0001.yaml",
            "data/real_true_data.json",
            ".streamlit/secrets.toml",
        ]
    )

    assert forbidden == [
        ".streamlit/secrets.toml",
        "data/flow_sources/flow_source.v0001.yaml",
        "data/real_true_data.json",
    ]


def test_forbidden_tracked_paths_allows_test_fixtures() -> None:
    forbidden = verify_repository_safety.forbidden_tracked_paths(
        [
            "tests/fixtures/wells.yaml",
            "tests/fixtures/real_true_data.json",
            "tests/fixtures/service_account.json",
        ]
    )

    assert forbidden == []
