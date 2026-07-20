from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACK_PATH = ROOT / "scripts" / "project_pack.py"

spec = importlib.util.spec_from_file_location("project_pack", PROJECT_PACK_PATH)
project_pack = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(project_pack)


def raw_figma_payload(
    *,
    start_label: str = "Start",
    end_label: str = "End",
) -> dict[str, object]:
    return {
        "version": 3,
        "elements": [
            {
                "id": "text_start",
                "name": "id=start;kind=process;responsible=planning;time=1 hour",
                "type": "TEXT",
                "characters": start_label,
                "fontSize": 18,
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
            },
            {
                "id": "text_end",
                "name": "id=end;kind=event",
                "type": "TEXT",
                "characters": end_label,
                "fontSize": 18,
                "x": 260,
                "y": 20,
                "width": 160,
                "height": 60,
            },
            {
                "id": "conn_1",
                "name": "id=edge_1;kind=usual;source=start;target=end",
                "type": "CONNECTOR",
                "x": 190,
                "y": 50,
                "width": 70,
                "height": 2,
                "rotation": 0,
            },
        ],
    }


def runtime_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYDIAG_DISABLE_STREAMLIT_SECRETS"] = "1"
    env.pop("PYDIAG_AUTH_USERS_JSON", None)
    env.pop("PYDIAG_ALLOW_INSECURE_ADMIN", None)
    env.pop("PYDIAG_ADMIN_PASSWORD", None)
    env.pop("PYDIAG_GRAPH_PATH", None)
    env.pop("PYDIAG_SOURCE_GRAPH_PATH", None)
    env.pop("PYDIAG_RAW_GRAPH_PATH", None)
    env.pop("PYDIAG_WELLS_PATH", None)
    return env


def restore_from_downloaded_bundle(tmp_path: Path) -> Path:
    archive = tmp_path / "all.txt"
    download_dir = tmp_path / "download"
    restore = tmp_path / "restore"
    download_dir.mkdir(parents=True, exist_ok=True)

    project_pack.pack(ROOT, archive)
    shutil.copy2(archive, download_dir / "all.txt")
    shutil.copy2(PROJECT_PACK_PATH, download_dir / "project_pack.py")

    subprocess.run(
        [
            sys.executable,
            str(download_dir / "project_pack.py"),
            "unpack",
            "--root",
            str(restore),
            "--archive",
            str(download_dir / "all.txt"),
        ],
        check=True,
        cwd=download_dir,
        capture_output=True,
        text=True,
    )
    return restore


def run_restore_script(restore: Path, script: str) -> None:
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=restore,
        env=runtime_env(),
        capture_output=True,
        text=True,
    )


def test_downloaded_bundle_cli_imports_live_source_from_raw_on_explicit_action(
    tmp_path: Path,
) -> None:
    restore = restore_from_downloaded_bundle(tmp_path)

    raw_path = restore / "data" / "real_true_data.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    script = f"""
from pathlib import Path
import json
from streamlit.testing.v1 import AppTest

def click_button(app, label):
    for button in app.button:
        if button.label == label:
            button.click().run(timeout=30)
            return
    raise SystemExit(f"button not found: {{label}}")

app = AppTest.from_file({str(restore / "app.py")!r})
app.run(timeout=30)
if app.exception:
    raise SystemExit(f"app exception: {{app.exception!r}}")

wells_path = Path({str(restore / "data" / "wells.yaml")!r})
wells_example_path = Path({str(restore / "data" / "wells.example.yaml")!r})
source_path = Path({str(restore / "data" / "flow_sources" / "flow_source.yaml")!r})
if wells_path.exists():
    raise SystemExit("wells.yaml should not exist before live schema import")
if not wells_example_path.exists():
    raise SystemExit("missing wells.example.yaml")
if source_path.exists():
    raise SystemExit("flow_source.yaml should not exist before explicit import")

if not any("Пользователи не настроены" in item.value for item in app.warning):
    raise SystemExit("expected missing-users warning was not rendered")

click_button(app, "Импорт json figma")
if app.exception:
    raise SystemExit(f"app exception after import: {{app.exception!r}}")
if not source_path.exists():
    raise SystemExit("missing flow_source.yaml after import")
if not wells_path.exists():
    raise SystemExit("missing wells.yaml after live import")

wells_text = wells_path.read_text(encoding="utf-8")
if "wells: []" not in wells_text:
    raise SystemExit("empty wells bootstrap was not created")

source_text = source_path.read_text(encoding="utf-8")
if 'schema_version: "flow-source/1.0"' not in source_text:
    raise SystemExit("unexpected source schema")
if 'version: 3' not in source_text:
    raise SystemExit("unexpected source version")
"""

    run_restore_script(restore, script)


def test_unpacked_bundle_import_from_raw_creates_backup_for_existing_live_source(
    tmp_path: Path,
) -> None:
    restore = restore_from_downloaded_bundle(tmp_path)

    raw_path = restore / "data" / "real_true_data.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    script = f"""
from pathlib import Path
import json
import sys
from streamlit.testing.v1 import AppTest

sys.path.insert(0, {str(restore / "src")!r})
from pydiag.infrastructure.flow_source_graph import dump_flow_source_payload, load_structured_payload

def click_button(app, label):
    for button in app.button:
        if button.label == label:
            button.click().run(timeout=30)
            return
    raise SystemExit(f"button not found: {{label}}")

app = AppTest.from_file({str(restore / "app.py")!r})
app.run(timeout=30)
if app.exception:
    raise SystemExit(f"app exception: {{app.exception!r}}")

raw_path = Path({str(restore / "data" / "real_true_data.json")!r})
source_path = Path({str(restore / "data" / "flow_sources" / "flow_source.yaml")!r})
backup_path = Path({str(restore / "data" / "flow_sources" / "flow_source.v0001.yaml")!r})

click_button(app, "Импорт json figma")
if app.exception:
    raise SystemExit(f"app exception after first import: {{app.exception!r}}")
if not source_path.exists():
    raise SystemExit("missing flow_source.yaml after first import")

source_payload = load_structured_payload(source_path.read_bytes())
source_payload["nodes"]["start"]["title"] = "Manual Start"
source_path.write_text(dump_flow_source_payload(source_payload), encoding="utf-8")

raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
for element in raw_payload["elements"]:
    if element.get("id") == "text_start":
        element["characters"] = "Raw Start Updated"
raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")

click_button(app, "Импорт json figma")
if app.exception:
    raise SystemExit(f"app exception after second import: {{app.exception!r}}")

if not backup_path.exists():
    raise SystemExit("missing backup version after second import")

source_payload = load_structured_payload(source_path.read_bytes())
backup_payload = load_structured_payload(backup_path.read_bytes())
if source_payload["nodes"]["start"]["title"] != "Raw Start Updated":
    raise SystemExit("live source was not refreshed from raw payload")
if backup_payload["nodes"]["start"]["title"] != "Manual Start":
    raise SystemExit("previous live source was not preserved in backup version")
if source_payload["version"] != 4:
    raise SystemExit(f"unexpected imported source version: {{source_payload['version']}}")
"""

    run_restore_script(restore, script)


def test_unpacked_bundle_reload_reports_invalid_raw_without_crashing(tmp_path: Path) -> None:
    restore = restore_from_downloaded_bundle(tmp_path)

    raw_path = restore / "data" / "real_true_data.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    script = f"""
from pathlib import Path
import json
from streamlit.testing.v1 import AppTest

def click_button(app, label):
    for button in app.button:
        if button.label == label:
            button.click().run(timeout=30)
            return
    raise SystemExit(f"button not found: {{label}}")

app = AppTest.from_file({str(restore / "app.py")!r})
app.run(timeout=30)
if app.exception:
    raise SystemExit(f"app exception: {{app.exception!r}}")

graph_path = Path({str(restore / "data" / "flow_graph.json")!r})
raw_path = Path({str(restore / "data" / "real_true_data.json")!r})
source_path = Path({str(restore / "data" / "flow_sources" / "flow_source.yaml")!r})

raw_path.write_text("{{broken json", encoding="utf-8")
click_button(app, "Импорт json figma")

if app.exception:
    raise SystemExit(f"app exception after import failure: {{app.exception!r}}")
if source_path.exists():
    raise SystemExit("live source should not be created from invalid raw payload")
if not any("Не удалось импортировать фактические данные" in item.value for item in app.error):
    raise SystemExit("import failure was not rendered as a user-facing error")
"""

    run_restore_script(restore, script)
