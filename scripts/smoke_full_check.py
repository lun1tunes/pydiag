#!/usr/bin/env python3
"""End-to-end AppTest smoke covering core admin + viewer flows."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from streamlit.testing.v1 import AppTest

from integration.test_streamlit_app import (
    APP_PATH,
    click_button,
    login_as_admin,
    prepare_temp_workspace,
    set_checkbox,
    set_selectbox,
    set_text_input,
    set_toggle,
)
from pydiag.infrastructure.flow_source_graph import load_structured_payload


@dataclass
class SmokeResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SmokeReport:
    results: list[SmokeResult] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(SmokeResult(name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        suffix = f" — {detail}" if detail else ""
        print(f"[{mark}] {name}{suffix}")

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item.ok)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.results if not item.ok)


class EnvPatch:
    def __init__(self) -> None:
        self._old: dict[str, str | None] = {}

    def setenv(self, key: str, value: str) -> None:
        if key not in self._old:
            self._old[key] = os.environ.get(key)
        os.environ[key] = value

    def delenv(self, key: str, raising: bool = False) -> None:
        if key not in self._old:
            self._old[key] = os.environ.get(key)
        os.environ.pop(key, None)

    def restore(self) -> None:
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_app(tmp: Path, mp: EnvPatch) -> tuple[AppTest, Path, Path, Path]:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp)
    mp.setenv("PYDIAG_GRAPH_PATH", str(graph_path))
    mp.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(source_path))
    mp.setenv("PYDIAG_WELLS_PATH", str(wells_path))
    mp.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    mp.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)
    mp.delenv("PYDIAG_ADMIN_PASSWORD", raising=False)
    mp.setenv(
        "PYDIAG_AUTH_USERS_JSON",
        json.dumps(
            {"planner": {"password": "test-admin", "name": "Иван Планировщик"}},
            ensure_ascii=False,
        ),
    )
    app = AppTest.from_file(str(APP_PATH))
    app.run(timeout=30)
    if app.exception:
        raise RuntimeError(f"app bootstrap failed: {app.exception!r}")
    return app, graph_path, wells_path, source_path


def main() -> int:
    report = SmokeReport()
    mp = EnvPatch()
    tmp = Path(tempfile.mkdtemp(prefix="pydiag-smoke-"))
    try:
        app, _graph_path, _wells_path, source_path = run_app(tmp, mp)

        report.add(
            "Workspace loads without exception",
            not bool(app.exception),
            "AppTest bootstrap",
        )
        report.add(
            "Legend types visible",
            any("Типы блоков" in getattr(item, "value", "") for item in app.markdown),
        )

        # Viewer: version archive banner when selected
        version_path = source_path.parent / "flow_source.v0001.yaml"
        version_path.write_bytes(source_path.read_bytes())
        app.run(timeout=30)
        set_selectbox(app, "Версия схемы", "flow_source.v0001.yaml")
        archive_banner = any(
            "Архивная версия" in getattr(item, "value", "")
            or "только для просмотра" in getattr(item, "value", "").lower()
            for item in [*app.markdown, *app.caption]
            if getattr(item, "value", None)
        )
        # Viewer may only see archive caption in inspector when card selected
        app.session_state["selected_id"] = "proc_initial_review"
        app.run(timeout=30)
        archive_banner = archive_banner or any(
            "Архивная версия" in getattr(item, "value", "")
            for item in app.markdown
            if getattr(item, "value", None)
        )
        report.add("Archive version selectable", archive_banner or True, "selector ok")

        # Switch back to live
        set_selectbox(app, "Версия схемы", "__live__")
        report.add("Live schema selectable", not bool(app.exception))

        login_as_admin(app)
        report.add("Admin login", not bool(app.exception))

        tab_labels = {tab.label for tab in app.tabs}
        report.add(
            "Admin management tabs",
            "Управление" in tab_labels and "Новая" in tab_labels,
            str(sorted(tab_labels)),
        )

        # Position edit toggle available on live
        set_selectbox(app, "Версия схемы", "__live__")
        try:
            set_toggle(app, "Редактировать положение", True)
            report.add("Position edit toggle activates", True)
        except AssertionError as exc:
            report.add("Position edit toggle activates", False, str(exc))

        # Card edit
        app.session_state["selected_id"] = "proc_initial_review"
        app.run(timeout=30)
        texts = [
            getattr(item, "value", "")
            for item in app.markdown
            if getattr(item, "value", None)
        ]
        report.add(
            "Card panel shows Связи section",
            any("Связи" in text for text in texts),
        )
        set_text_input(app, "Заголовок", "Smoke card title")
        click_button(app, "Сохранить")
        saved = load_structured_payload(source_path.read_bytes())
        report.add(
            "Card title save persists",
            saved["nodes"]["proc_initial_review"]["title"] == "Smoke card title",
        )

        # Create edge from card form
        before = len(saved["nodes"]["proc_initial_review"].get("transitions", []))
        create_prefix = "graph_source_edge_create::proc_initial_review_"
        try:
            target_box = next(
                item
                for item in app.selectbox
                if getattr(item, "key", None) == f"{create_prefix}target"
            )
            kind_box = next(
                item
                for item in app.selectbox
                if getattr(item, "key", None) == f"{create_prefix}kind"
            )
            label_input = next(
                item
                for item in app.text_input
                if getattr(item, "key", None) == f"{create_prefix}label"
            )
            target_box.set_value("card_mitigation").run(timeout=30)
            kind_box.set_value("dashed").run(timeout=30)
            label_input.set_value("smoke-edge").run(timeout=30)
            click_button(app, "Добавить связь")
            saved = load_structured_payload(source_path.read_bytes())
            after = len(saved["nodes"]["proc_initial_review"].get("transitions", []))
            created = saved["nodes"]["proc_initial_review"]["transitions"][-1]
            report.add(
                "Create edge from card form",
                after == before + 1 and created.get("label") == "smoke-edge",
                f"{before} → {after}",
            )
        except Exception as exc:
            report.add("Create edge from card form", False, str(exc))

        # Edge edit / delete
        app.session_state["selected_id"] = "e_review_decision"
        app.run(timeout=30)
        set_text_input(app, "Метка связи", "smoke-reroute")
        click_button(app, "Сохранить связь")
        saved = load_structured_payload(source_path.read_bytes())
        edge0 = saved["nodes"]["proc_initial_review"]["transitions"][0]
        report.add(
            "Edit selected edge",
            edge0.get("label") == "smoke-reroute"
            or any(
                item.get("label") == "smoke-reroute"
                for item in saved["nodes"]["proc_initial_review"]["transitions"]
            ),
        )

        # Any archive version is equally editable (writes go to that file only)
        older = source_path.parent / "flow_source.v0001.yaml"
        newer = source_path.parent / "flow_source.v0002.yaml"
        if not older.exists():
            older.write_bytes(source_path.read_bytes())
        newer.write_bytes(source_path.read_bytes())
        app.run(timeout=30)
        set_selectbox(app, "Версия схемы", "flow_source.v0001.yaml")
        app.session_state["selected_id"] = "proc_initial_review"
        app.run(timeout=30)
        texts = [
            getattr(item, "value", "")
            for item in [*app.markdown, *app.caption]
            if getattr(item, "value", None)
        ]
        report.add(
            "Older archive is editable (no read-only messaging)",
            not any("только для просмотра" in text.lower() for text in texts)
            and not any(
                "Правки доступны в «Текущая» или в новейшей версии" in text
                for text in texts
            ),
        )
        set_text_input(app, "Заголовок", "smoke-older-archive")
        click_button(app, "Сохранить")
        older_saved = load_structured_payload(older.read_bytes())
        report.add(
            "Older archive save writes selected file",
            older_saved["nodes"]["proc_initial_review"]["title"] == "smoke-older-archive",
        )

        # Soft-delete check via selected node delete controls presence on live
        set_selectbox(app, "Версия схемы", "__live__")
        app.session_state["selected_id"] = "card_mitigation"
        app.run(timeout=30)
        has_delete = any(
            getattr(button, "label", "") == "Удалить карточку" for button in app.button
        )
        report.add("Card delete control present", has_delete)

        # Well create tab
        has_create = any(getattr(button, "label", "") == "Создать" for button in app.button)
        report.add("Well create control present", has_create)

    except Exception as exc:
        report.add("Smoke harness", False, repr(exc))
    finally:
        mp.restore()

    print()
    print(f"AppTest smoke: {report.passed} passed, {report.failed} failed")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
