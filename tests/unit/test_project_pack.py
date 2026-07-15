from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACK_PATH = ROOT / "scripts" / "project_pack.py"

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


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_runtime_tree(root: Path) -> None:
    write_file(root / "app.py", "print('app')\n")
    write_file(root / "README.md", "# runtime\n")
    write_file(root / "requirements.txt", "streamlit\n")
    write_file(root / "requirements-dev.txt", "pytest\n")
    write_file(root / "pytest.ini", "[pytest]\n")
    write_file(root / ".streamlit" / "config.toml", "[server]\n")
    write_file(root / ".streamlit" / "secrets.example.toml", "[users.admin]\n")
    write_file(
        root / "scripts" / "materialize_flow_source.py", "print('materialize')\n"
    )
    write_file(root / "src" / "pydiag" / "__init__.py", "")
    write_file(
        root / "src" / "pydiag" / "presentation" / "streamlit_app.py",
        "def main():\n    return None\n",
    )
    write_file(
        root / "src" / "pydiag" / "rendering" / "flow_canvas_assets" / "flow_canvas.js",
        "console.log('ok');\n",
    )


def test_collect_files_includes_runtime_files_only() -> None:
    files = {
        path.relative_to(ROOT).as_posix() for path in project_pack.collect_files(ROOT)
    }

    assert "app.py" in files
    assert "requirements.txt" in files
    assert "requirements-dev.txt" in files
    assert "scripts/materialize_flow_graph.py" in files
    assert "src/pydiag/presentation/streamlit_app.py" in files
    assert "src/pydiag/rendering/flow_canvas_assets/flow_canvas.js" in files

    assert not any(path.startswith("data/") for path in files)
    assert "data/flow_graph.json" not in files
    assert "data/wells.yaml" not in files
    assert "data/real_true_data.json" not in files
    assert ".streamlit/secrets.toml" not in files
    assert "all.txt" not in files
    assert "tests/conftest.py" not in files


def test_pack_omits_confidential_runtime_data(tmp_path: Path) -> None:
    archive_path = tmp_path / "project_bundle.txt"

    project_pack.pack(ROOT, archive_path)

    archive_text = archive_path.read_text(encoding="utf-8")
    headers = archive_header_paths(archive_text)

    assert "app.py" in headers
    assert "requirements.txt" in headers

    assert not any(path.startswith("data/") for path in headers)
    assert "data/flow_graph.json" not in headers
    assert "data/wells.yaml" not in headers
    assert "data/real_true_data.json" not in headers
    assert ".streamlit/secrets.toml" not in headers


def test_collect_files_rejects_unsupported_runtime_json_files(tmp_path: Path) -> None:
    make_runtime_tree(tmp_path)
    write_file(
        tmp_path / "src" / "pydiag" / "service_account.json", '{"token": "secret"}\n'
    )

    with pytest.raises(project_pack.BundleSafetyError, match="service_account.json"):
        project_pack.collect_files(tmp_path)


def test_collect_files_rejects_runtime_symlinks(tmp_path: Path) -> None:
    make_runtime_tree(tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("host secret\n", encoding="utf-8")
    link = tmp_path / "src" / "pydiag" / "hostlink.txt"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    with pytest.raises(project_pack.BundleSafetyError, match="hostlink.txt"):
        project_pack.collect_files(tmp_path)


def test_unpack_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.txt"
    archive.write_text(
        f"{project_pack.BEGIN}\t../outside.txt\t4\nboom\n{project_pack.END}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsafe target path"):
        project_pack.unpack(tmp_path / "restore", archive)


def test_unpack_rejects_confidential_runtime_paths(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.txt"
    content = "wells: []"
    archive.write_text(
        f"{project_pack.BEGIN}\tdata/wells.yaml\t{len(content)}\n{content}\n{project_pack.END}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="confidential runtime files"):
        project_pack.unpack(tmp_path / "restore", archive)


def test_unpack_rejects_unexpected_runtime_paths(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.txt"
    archive.write_text(
        f"{project_pack.BEGIN}\tnotes.md\t5\nhello\n{project_pack.END}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unexpected runtime bundle path"):
        project_pack.unpack(tmp_path / "restore", archive)


def test_unpack_creates_wells_example_yaml(tmp_path: Path) -> None:
    source = tmp_path / "source"
    restore = tmp_path / "restore"
    archive = tmp_path / "bundle.txt"
    make_runtime_tree(source)

    project_pack.pack(source, archive)
    project_pack.unpack(restore, archive)

    wells_example = restore / "data" / "wells.example.yaml"
    content = wells_example.read_text(encoding="utf-8")

    assert wells_example.exists()
    assert 'schema_version: "1.0"' in content
    assert "wells: []" in content
    assert "Copy this file to data/wells.yaml" in content
    assert "current_node_id: replace_with_graph_node_id" in content
