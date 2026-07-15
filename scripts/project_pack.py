#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
from textwrap import dedent

ARCHIVE_FILE = "all.txt"
BEGIN = "===BEGIN_FILE==="
END = "===END_FILE==="
WELLS_EXAMPLE_REL_PATH = Path("data") / "wells.example.yaml"
WELLS_EXAMPLE_TEMPLATE = (
    dedent(
        """
        schema_version: "1.0"
        version: 1
        wells: []
        # Copy this file to data/wells.yaml and replace the example below with real wells:
        # wells:
        #   - id: well_1
        #     name: Скв. 1
        #     current_node_id: replace_with_graph_node_id
        #     history:
        #       - ts: "2026-05-08T08:00:00Z"
        #         node_id: replace_with_graph_node_id
        #         action: create
        #         to_node_id: replace_with_graph_node_id
        #         by: system
        #         comment: initial placement
        #     metadata:
        #       field: Example field
        #       rig: BU-01
        #     is_archived: false
        """
    ).strip()
    + "\n"
)

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    "data",
    "dist",
}

EXCLUDED_FILE_PATHS = {
    ".windsurf/workflows/check_and_pack.yaml",
}

RUNTIME_INCLUDED_FILE_PATHS = {
    ".streamlit/config.toml",
    ".streamlit/secrets.example.toml",
    "README.md",
    "app.py",
    "pytest.ini",
    "requirements.txt",
    "requirements-dev.txt",
}

RUNTIME_INCLUDED_DIR_PREFIXES = {
    "scripts/",
    "src/",
}

CONFIDENTIAL_GLOB_PATTERNS = {
    ".streamlit/secrets.toml",
    "data/**",
    "**/*.json.lock",
    "**/*.pem",
    "**/*.p12",
    "**/*.pfx",
    "**/*.key",
    "**/*.crt",
    "**/.env",
    "**/.env.*",
    "**/id_rsa",
    "**/id_ed25519",
    "**/*service_account*.json",
    "**/*credentials*.json",
    "**/*secret*.json",
    "**/flow_graph.json",
    "**/real_true_data.json",
    "**/wells.yaml",
    "**/wells.yaml.lock",
}

SUPPORTED_BUNDLE_SUFFIXES = {
    ".css",
    ".ini",
    ".js",
    ".md",
    ".py",
    ".toml",
    ".txt",
}


class BundleSafetyError(RuntimeError):
    pass


def relative_posix_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_confidential_rel_path(rel_path: str) -> bool:
    if rel_path == ".streamlit/secrets.toml":
        return True
    if rel_path.startswith("data/"):
        return True
    rel = PurePosixPath(rel_path)
    return any(rel.match(pattern) for pattern in CONFIDENTIAL_GLOB_PATTERNS)


def is_confidential_path(path: Path, root: Path) -> bool:
    return is_confidential_rel_path(relative_posix_path(path, root))


def is_excluded_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = set(rel.parts)
    if parts & EXCLUDED_DIR_NAMES:
        return True
    if rel.as_posix() in EXCLUDED_FILE_PATHS:
        return True
    return False


def should_include_path(path: Path, root: Path) -> bool:
    rel = relative_posix_path(path, root)
    return should_include_rel_path(rel)


def should_include_rel_path(rel: str) -> bool:
    if rel in RUNTIME_INCLUDED_FILE_PATHS:
        return True
    return any(rel.startswith(prefix) for prefix in RUNTIME_INCLUDED_DIR_PREFIXES)


def bundle_input_violation(path: Path, root: Path) -> str | None:
    rel = relative_posix_path(path, root)
    if is_confidential_path(path, root):
        return f"{rel}: confidential runtime files are not allowed in bundle inputs"
    if path.is_symlink():
        return f"{rel}: symlinks are not allowed in runtime bundle inputs"
    if not path.is_file():
        return None
    if rel in RUNTIME_INCLUDED_FILE_PATHS:
        return None
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_BUNDLE_SUFFIXES:
        label = suffix if suffix else "<no suffix>"
        return (
            f"{rel}: unsupported runtime bundle file type {label}; "
            "extend the allowlist explicitly if this asset is required"
        )
    return None


def bundle_output_violation(rel_path: str) -> str | None:
    if is_confidential_rel_path(rel_path):
        return f"{rel_path}: confidential runtime files are not allowed in unpacked bundles"
    if not should_include_rel_path(rel_path):
        return f"{rel_path}: unexpected runtime bundle path"
    suffix = Path(rel_path).suffix.lower()
    if rel_path not in RUNTIME_INCLUDED_FILE_PATHS and suffix not in SUPPORTED_BUNDLE_SUFFIXES:
        label = suffix if suffix else "<no suffix>"
        return (
            f"{rel_path}: unsupported runtime bundle file type {label}; "
            "extend the allowlist explicitly if this asset is required"
        )
    return None


def bundle_input_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for path in root.rglob("*"):
        if is_excluded_path(path, root):
            continue
        if not should_include_path(path, root):
            continue
        violation = bundle_input_violation(path, root)
        if violation is not None:
            violations.append(violation)
    return sorted(set(violations))


def ensure_safe_bundle_inputs(root: Path) -> None:
    violations = bundle_input_violations(root)
    if not violations:
        return
    message = "Unsafe runtime bundle inputs:\n" + "\n".join(
        f"- {item}" for item in violations
    )
    raise BundleSafetyError(message)


def collect_files(root: Path, *, archive_path: Path | None = None) -> list[Path]:
    ensure_safe_bundle_inputs(root)
    files: list[Path] = []
    archive_resolved = archive_path.resolve() if archive_path is not None else None
    default_archive_resolved = (root / ARCHIVE_FILE).resolve()
    for path in root.rglob("*"):
        if is_excluded_path(path, root):
            continue
        if not should_include_path(path, root):
            continue
        if not path.is_file():
            continue
        resolved_path = path.resolve()
        if resolved_path == default_archive_resolved:
            continue
        if archive_resolved is not None and resolved_path == archive_resolved:
            continue
        files.append(path)

    return sorted(set(files), key=lambda p: str(p.relative_to(root)))


def pack(root: Path, output_file: Path) -> None:
    files = collect_files(root, archive_path=output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="") as out:
        for path in files:
            rel = path.relative_to(root).as_posix()
            content = path.read_text(encoding="utf-8")
            out.write(f"{BEGIN}\t{rel}\t{len(content)}\n")
            out.write(content)
            out.write("\n")
            out.write(f"{END}\n")

    print(f"Packed {len(files)} files into {output_file}")


def ensure_runtime_scaffold(root: Path) -> None:
    wells_example_path = root / WELLS_EXAMPLE_REL_PATH
    if not wells_example_path.exists():
        wells_example_path.parent.mkdir(parents=True, exist_ok=True)
        wells_example_path.write_text(WELLS_EXAMPLE_TEMPLATE, encoding="utf-8")


def unpack(root: Path, input_file: Path) -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Archive file not found: {input_file}")

    restored = 0
    root_resolved = root.resolve()

    with input_file.open("r", encoding="utf-8") as src:
        while True:
            header = src.readline()
            if not header:
                break
            if not header.startswith(f"{BEGIN}\t"):
                raise ValueError("Invalid archive format: malformed BEGIN header")

            payload = header.rstrip("\n").split("\t", maxsplit=2)
            if len(payload) != 3:
                raise ValueError("Invalid archive format: malformed BEGIN payload")
            _, rel_path, raw_len = payload
            content_len = int(raw_len)

            content = src.read(content_len)
            if len(content) != content_len:
                raise ValueError("Invalid archive format: truncated file content")

            separator = src.read(1)
            if separator != "\n":
                raise ValueError("Invalid archive format: missing content separator")

            end_line = src.readline().rstrip("\n")
            if end_line != END:
                raise ValueError("Invalid archive format: missing END marker")

            rel_target = PurePosixPath(rel_path)
            if rel_target.is_absolute() or ".." in rel_target.parts:
                raise ValueError(
                    f"Invalid archive format: unsafe target path {rel_path!r}"
                )
            violation = bundle_output_violation(rel_path)
            if violation is not None:
                raise ValueError(f"Invalid archive format: {violation}")

            target = (root / Path(*rel_target.parts)).resolve()
            if target != root_resolved and root_resolved not in target.parents:
                raise ValueError(
                    f"Invalid archive format: unsafe target path {rel_path!r}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            restored += 1

    ensure_runtime_scaffold(root)
    print(f"Restored {restored} files from {input_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pack the production runtime bundle (app, src, config)"
            " into a text archive while excluding confidential schema/data files."
        )
    )
    parser.add_argument(
        "mode",
        choices=("pack", "unpack"),
        help=f"pack: create {ARCHIVE_FILE}, unpack: restore files from the archive",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--archive",
        default=None,
        help=f"Archive file path (default: <root>/{ARCHIVE_FILE})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    archive = (
        (root / ARCHIVE_FILE) if args.archive is None else Path(args.archive).resolve()
    )

    if args.mode == "pack":
        pack(root, archive)
    else:
        unpack(root, archive)


if __name__ == "__main__":
    main()
