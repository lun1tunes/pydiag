from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "materialize_flow_graph.py"

spec = importlib.util.spec_from_file_location("materialize_flow_graph_script", SCRIPT_PATH)
materialize_flow_graph_script = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(materialize_flow_graph_script)


def test_main_defaults_to_runtime_graph_path(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "flow_source.yaml"
    source.write_text("schema_version: flow-source/1.0\nnodes: {}\n", encoding="utf-8")
    target = tmp_path / "flow_graph.json"
    calls: list[tuple[Path, Path]] = []

    def fake_materialize(*, source_path: Path, target_path: Path):
        calls.append((Path(source_path), Path(target_path)))
        return SimpleNamespace(nodes=[object()], edges=[object(), object()])

    monkeypatch.setattr(
        materialize_flow_graph_script,
        "preferred_graph_source_path",
        lambda: source,
    )
    monkeypatch.setattr(materialize_flow_graph_script, "source_graph_path", lambda: source)
    monkeypatch.setattr(
        materialize_flow_graph_script,
        "raw_graph_path",
        lambda: tmp_path / "real_true_data.json",
    )
    monkeypatch.setattr(materialize_flow_graph_script, "configured_graph_path", lambda: None)
    monkeypatch.setattr(materialize_flow_graph_script, "graph_path", lambda: target)
    monkeypatch.setattr(
        materialize_flow_graph_script,
        "materialize_flow_graph_from_source",
        fake_materialize,
    )
    monkeypatch.setattr(materialize_flow_graph_script.sys, "argv", [str(SCRIPT_PATH)])

    exit_code = materialize_flow_graph_script.main()

    assert exit_code == 0
    assert calls == [(source.resolve(), target.resolve())]
