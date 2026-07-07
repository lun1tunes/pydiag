from __future__ import annotations

import ast
from pathlib import Path

import pydiag as root_package
import pydiag.application as application_package
import pydiag.application.documents_gateway as application_documents_gateway
import pydiag.application.flow_position_edit as application_flow_position_edit
import pydiag.application.flow_view as application_flow_view
import pydiag.application.flow_view_state as application_flow_view_state
import pydiag.application.session_state as application_session_state
import pydiag.application.well_admin as application_well_admin
import pydiag.common as common_package
import pydiag.common.errors as common_errors
import pydiag.domain as domain_package
import pydiag.domain.models as domain_models
import pydiag.domain.services as domain_services
import pydiag.infrastructure as infrastructure_package
import pydiag.infrastructure.figma_import as infra_figma_import
import pydiag.infrastructure.json_documents_gateway as infra_json_documents_gateway
import pydiag.infrastructure.storage as infra_storage
import pydiag.infrastructure.storage_io as infra_storage_io
import pydiag.infrastructure.storage_loading as infra_storage_loading
import pydiag.infrastructure.storage_materialization as infra_storage_materialization
import pydiag.infrastructure.storage_paths as infra_storage_paths
import pydiag.infrastructure.storage_writes as infra_storage_writes
import pydiag.presentation as presentation_package
import pydiag.presentation.auth as presentation_auth
import pydiag.presentation.auth_config as presentation_auth_config
import pydiag.presentation.auth_models as presentation_auth_models
import pydiag.presentation.auth_policy as presentation_auth_policy
import pydiag.presentation.auth_session as presentation_auth_session
import pydiag.presentation.auth_sources as presentation_auth_sources
import pydiag.presentation.chrome as presentation_chrome
import pydiag.presentation.runtime as presentation_runtime
import pydiag.presentation.sidebar as presentation_sidebar
import pydiag.presentation.streamlit_app as presentation_streamlit_app
import pydiag.rendering as rendering_package
import pydiag.rendering.flow_adapter as rendering_flow_adapter
import pydiag.rendering.flow_canvas_adapter as rendering_flow_canvas_adapter
import pydiag.rendering.flow_canvas_bounds as rendering_flow_canvas_bounds
import pydiag.rendering.flow_canvas_component as rendering_flow_canvas_component
import pydiag.rendering.flow_canvas_payload as rendering_flow_canvas_payload
import pydiag.rendering.flow_canvas_state as rendering_flow_canvas_state
import pydiag.rendering.flow_edge_labels as rendering_flow_edge_labels
import pydiag.rendering.flow_edge_rendering as rendering_flow_edge_rendering
import pydiag.rendering.flow_edge_routing as rendering_flow_edge_routing
import pydiag.rendering.flow_figma_text_styles as rendering_flow_figma_text_styles
import pydiag.rendering.flow_layout_positions as rendering_flow_layout_positions
import pydiag.rendering.flow_layout_routing as rendering_flow_layout_routing
import pydiag.rendering.flow_node_filters as rendering_flow_node_filters
import pydiag.rendering.flow_node_markup as rendering_flow_node_markup
import pydiag.rendering.flow_node_overlays as rendering_flow_node_overlays
import pydiag.rendering.flow_node_render_specs as rendering_flow_node_render_specs
import pydiag.rendering.flow_node_rendering as rendering_flow_node_rendering
import pydiag.rendering.flow_node_shape_backgrounds as rendering_flow_node_shape_backgrounds
import pydiag.rendering.flow_node_styles as rendering_flow_node_styles
import pydiag.rendering.flow_render_math as rendering_flow_render_math
import pydiag.rendering.flow_render_metrics as rendering_flow_render_metrics
import pydiag.rendering.flow_render_snapshot as rendering_flow_render_snapshot
import pydiag.rendering.flow_route_geometry as rendering_flow_route_geometry
import pydiag.rendering.flow_route_lanes as rendering_flow_route_lanes
import pydiag.rendering.flow_route_paths as rendering_flow_route_paths
import pydiag.rendering.flow_route_ports as rendering_flow_route_ports
import pydiag.rendering.flow_streamlit_edges as rendering_flow_streamlit_edges
import pydiag.rendering.flow_streamlit_nodes as rendering_flow_streamlit_nodes
import pydiag.rendering.flow_streamlit_primitives as rendering_flow_streamlit_primitives

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "pydiag"


def python_files(package_dir: Path) -> list[Path]:
    return sorted(path for path in package_dir.rglob("*.py") if "__pycache__" not in path.parts)


def module_name(path: Path) -> str:
    relative = path.relative_to(SRC_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def file_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current_module = module_name(path)
    current_package = (
        current_module if path.name == "__init__.py" else current_module.rsplit(".", 1)[0]
    )
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            imports.add(resolve_import_path(current_package, node.level, node.module))
    return {item for item in imports if item}


def resolve_import_path(current_package: str, level: int, module: str | None) -> str:
    if level == 0:
        return module or ""
    package_parts = current_package.split(".")
    base_parts = package_parts[: len(package_parts) - (level - 1)]
    if module:
        return ".".join([*base_parts, module])
    return ".".join(base_parts)


def matching_imports(path: Path, forbidden_prefixes: set[str]) -> list[str]:
    imports = file_imports(path)
    return sorted(
        item
        for item in imports
        if any(item == prefix or item.startswith(prefix + ".") for prefix in forbidden_prefixes)
    )


def assert_no_forbidden_imports(package: str, forbidden_prefixes: set[str]) -> None:
    package_dir = PACKAGE_ROOT / package
    offenders: dict[str, list[str]] = {}
    for path in python_files(package_dir):
        bad = matching_imports(path, forbidden_prefixes)
        if bad:
            offenders[module_name(path)] = bad
    assert not offenders, offenders


def assert_no_forbidden_imports_in_files(
    paths: list[Path],
    forbidden_prefixes: set[str],
) -> None:
    offenders: dict[str, list[str]] = {}
    for path in paths:
        bad = matching_imports(path, forbidden_prefixes)
        if bad:
            offenders[module_name(path)] = bad
    assert not offenders, offenders


def presentation_file(filename: str) -> Path:
    return PACKAGE_ROOT / "presentation" / filename


def application_file(filename: str) -> Path:
    return PACKAGE_ROOT / "application" / filename


def rendering_file(filename: str) -> Path:
    return PACKAGE_ROOT / "rendering" / filename


def test_domain_layer_stays_independent_from_outer_layers() -> None:
    assert_no_forbidden_imports(
        "domain",
        {
            "streamlit",
            "pydiag.application",
            "pydiag.presentation",
            "pydiag.infrastructure",
            "pydiag.rendering",
            "pydiag.common",
        },
    )


def test_infrastructure_layer_does_not_depend_on_application_or_presentation() -> None:
    assert_no_forbidden_imports(
        "infrastructure",
        {
            "streamlit",
            "pydiag.application",
            "pydiag.presentation",
            "pydiag.rendering",
        },
    )


def test_rendering_layer_does_not_depend_on_application_presentation_or_infrastructure() -> None:
    assert_no_forbidden_imports(
        "rendering",
        {
            "pydiag.application",
            "pydiag.presentation",
            "pydiag.infrastructure",
        },
    )


def test_application_layer_avoids_streamlit_presentation_and_infrastructure() -> None:
    assert_no_forbidden_imports(
        "application",
        {
            "streamlit",
            "pydiag.presentation",
            "pydiag.infrastructure",
        },
    )


def test_internal_packages_do_not_reference_removed_root_level_modules() -> None:
    removed_root_modules = {
        "pydiag.models",
        "pydiag.services",
        "pydiag.storage",
        "pydiag.figma_import",
        "pydiag.flow_adapter",
        "pydiag.flow_canvas_adapter",
        "pydiag.flow_canvas_component",
    }
    offenders: dict[str, list[str]] = {}
    for package in ("application", "domain", "infrastructure", "presentation", "rendering"):
        for path in python_files(PACKAGE_ROOT / package):
            bad = matching_imports(path, removed_root_modules)
            if bad:
                offenders[module_name(path)] = bad
    assert not offenders, offenders


def test_removed_root_level_compatibility_modules_do_not_exist() -> None:
    removed_paths = [
        PACKAGE_ROOT / "models.py",
        PACKAGE_ROOT / "services.py",
        PACKAGE_ROOT / "storage.py",
        PACKAGE_ROOT / "figma_import.py",
        PACKAGE_ROOT / "flow_adapter.py",
        PACKAGE_ROOT / "flow_canvas_adapter.py",
        PACKAGE_ROOT / "flow_canvas_component.py",
    ]

    assert all(not path.exists() for path in removed_paths)


def test_layer_packages_expose_curated_public_api() -> None:
    assert {
        "application",
        "common",
        "domain",
        "infrastructure",
        "presentation",
        "rendering",
    } <= set(root_package.__all__)
    assert application_package.DocumentsGateway is application_documents_gateway.DocumentsGateway
    assert application_package.CreateWellCommand is application_well_admin.CreateWellCommand
    assert application_package.render_flow is application_flow_view.render_flow
    assert (
        application_package.graph_with_positions
        is application_flow_position_edit.graph_with_positions
    )
    assert application_package.WellAdminService is application_well_admin.WellAdminService
    assert (
        application_package.flow_state_timestamp is application_flow_view_state.flow_state_timestamp
    )
    assert application_package.load_app_data is application_session_state.load_app_data
    assert common_package.FileLockTimeoutError is common_errors.FileLockTimeoutError
    assert domain_package.FlowGraphDocument is domain_models.FlowGraphDocument
    assert domain_package.move_well_to_node is domain_services.move_well_to_node
    assert infrastructure_package.load_documents is infra_storage.load_documents
    assert (
        infrastructure_package.flow_graph_payload_from_figma_payload
        is infra_figma_import.flow_graph_payload_from_figma_payload
    )
    assert infrastructure_package.graph_path is infra_storage.graph_path
    assert (
        infrastructure_package.materialize_flow_graph_from_raw_source
        is infra_storage.materialize_flow_graph_from_raw_source
    )
    assert infrastructure_package.raw_graph_path is infra_storage.raw_graph_path
    assert (
        infrastructure_package.JsonDocumentsGateway
        is infra_json_documents_gateway.JsonDocumentsGateway
    )
    assert presentation_package.AuthUser is presentation_auth_models.AuthUser
    assert presentation_package.StreamlitAppRuntime is presentation_runtime.StreamlitAppRuntime
    assert presentation_package.StreamlitAuthContext is presentation_auth.StreamlitAuthContext
    assert presentation_package.KIND_FILTER_LABELS is presentation_sidebar.KIND_FILTER_LABELS
    assert rendering_package.KIND_LABELS is rendering_flow_node_rendering.KIND_LABELS
    assert (
        rendering_package.build_node_render_specs
        is rendering_flow_node_rendering.build_node_render_specs
    )
    assert (
        rendering_package.build_flow_canvas_payload
        is rendering_flow_canvas_adapter.build_flow_canvas_payload
    )
    assert (
        rendering_package.build_streamlit_nodes
        is rendering_flow_streamlit_nodes.build_streamlit_nodes
    )
    assert (
        rendering_package.build_streamlit_edges
        is rendering_flow_streamlit_edges.build_streamlit_edges
    )
    assert rendering_package.flow_canvas_height is rendering_flow_render_metrics.flow_canvas_height
    assert rendering_package.layout_positions is rendering_flow_layout_routing.layout_positions
    assert (
        rendering_package.render_flow_canvas is rendering_flow_canvas_component.render_flow_canvas
    )
    assert {
        "CreateWellCommand",
        "DocumentsGateway",
        "WellAdminService",
        "render_flow",
        "load_app_data",
    } <= set(application_package.__all__)
    assert {"FlowGraphDocument", "move_well_to_node"} <= set(domain_package.__all__)
    assert {
        "JsonDocumentsGateway",
        "load_documents",
        "flow_graph_payload_from_figma_payload",
        "materialize_flow_graph_from_raw_source",
    } <= set(infrastructure_package.__all__)
    assert {"StreamlitAppRuntime", "render_sidebar"} <= set(presentation_package.__all__)
    assert {"build_flow_canvas_payload", "render_flow_canvas"} <= set(rendering_package.__all__)


def test_rendering_package_facade_stays_lazy() -> None:
    imports = file_imports(PACKAGE_ROOT / "rendering" / "__init__.py")
    assert imports == {"importlib", "typing"}


def test_rendering_layout_routing_facade_stays_thin() -> None:
    imports = file_imports(PACKAGE_ROOT / "rendering" / "flow_layout_routing.py")
    assert imports == {
        "pydiag.domain.models",
        "pydiag.rendering.flow_edge_labels",
        "pydiag.rendering.flow_edge_routing",
        "pydiag.rendering.flow_layout_positions",
        "pydiag.rendering.flow_node_render_specs",
        "pydiag.rendering.flow_route_geometry",
    }


def test_rendering_flow_adapter_facade_stays_thin() -> None:
    assert (
        rendering_flow_adapter.build_streamlit_nodes
        is rendering_flow_streamlit_nodes.build_streamlit_nodes
    )
    assert (
        rendering_flow_adapter.build_streamlit_edges
        is rendering_flow_streamlit_edges.build_streamlit_edges
    )
    assert (
        rendering_flow_adapter.flow_canvas_height
        is rendering_flow_render_metrics.flow_canvas_height
    )
    assert rendering_flow_adapter.edge_color is rendering_flow_edge_rendering.edge_color
    assert (
        rendering_flow_adapter.StreamlitFlowNode
        is rendering_flow_streamlit_primitives.StreamlitFlowNode
    )
    imports = file_imports(PACKAGE_ROOT / "rendering" / "flow_adapter.py")
    assert imports == {
        "pydiag.rendering.flow_edge_labels",
        "pydiag.rendering.flow_edge_rendering",
        "pydiag.rendering.flow_edge_routing",
        "pydiag.rendering.flow_layout_positions",
        "pydiag.rendering.flow_node_overlays",
        "pydiag.rendering.flow_node_rendering",
        "pydiag.rendering.flow_render_metrics",
        "pydiag.rendering.flow_streamlit_edges",
        "pydiag.rendering.flow_streamlit_nodes",
        "pydiag.rendering.flow_streamlit_primitives",
    }


def test_streamlit_app_module_exposes_app_facing_api() -> None:
    assert (
        presentation_streamlit_app.StreamlitAppRuntime is presentation_runtime.StreamlitAppRuntime
    )
    assert {
        "main",
        "render_flow_canvas",
        "runtime",
        "st",
    } <= set(presentation_streamlit_app.__all__)


def test_application_session_state_stays_out_of_rendering_modules() -> None:
    assert_no_forbidden_imports_in_files(
        [application_file("session_state.py")],
        {"pydiag.rendering"},
    )


def test_application_documents_gateway_stays_port_only() -> None:
    imports = file_imports(application_file("documents_gateway.py"))
    assert imports == {
        "typing",
        "pydiag.common.graph_versions",
        "pydiag.domain.models",
    }


def test_application_flow_view_state_stays_pure_of_rendering_and_session_workflows() -> None:
    assert_no_forbidden_imports_in_files(
        [application_file("flow_view_state.py")],
        {
            "pydiag.rendering",
            "pydiag.application.session_state",
        },
    )


def test_application_flow_view_stays_a_thin_canvas_coordinator() -> None:
    imports = file_imports(application_file("flow_view.py"))
    assert imports == {
        "collections.abc",
        "typing",
        "pydiag.domain.models",
        "pydiag.rendering",
        "pydiag.application.flow_view_context",
        "pydiag.application.flow_view_selection",
        "pydiag.application.flow_view_state",
    }
    assert_no_forbidden_imports_in_files(
        [application_file("flow_view.py")],
        {
            "pydiag.application.session_state",
            "pydiag.rendering.flow_adapter",
        },
    )


def test_application_flow_view_context_stays_position_edit_only() -> None:
    imports = file_imports(application_file("flow_view_context.py"))
    assert imports == {
        "collections.abc",
        "dataclasses",
        "typing",
        "pydiag.domain.models",
        "pydiag.application.flow_position_edit",
    }
    assert_no_forbidden_imports_in_files(
        [application_file("flow_view_context.py")],
        {
            "pydiag.application.flow_view",
            "pydiag.application.flow_view_selection",
            "pydiag.application.session_state",
            "pydiag.presentation",
            "pydiag.rendering",
        },
    )


def test_application_flow_view_selection_stays_selection_sync_only() -> None:
    imports = file_imports(application_file("flow_view_selection.py"))
    assert imports == {
        "collections.abc",
        "typing",
        "pydiag.domain.models",
        "pydiag.rendering",
    }
    assert_no_forbidden_imports_in_files(
        [application_file("flow_view_selection.py")],
        {
            "pydiag.application.flow_view",
            "pydiag.application.flow_view_context",
            "pydiag.application.session_state",
            "pydiag.presentation",
        },
    )


def test_application_well_admin_stays_out_of_session_and_rendering() -> None:
    assert_no_forbidden_imports_in_files(
        [application_file("well_admin.py")],
        {
            "pydiag.application.session_state",
            "pydiag.rendering",
        },
    )


def test_application_uses_rendering_package_api_instead_of_rendering_internals() -> None:
    offenders: dict[str, list[str]] = {}
    for filename in ("flow_position_edit.py", "flow_view.py", "flow_view_selection.py"):
        path = application_file(filename)
        internal_imports = sorted(
            item for item in file_imports(path) if item.startswith("pydiag.rendering.flow_")
        )
        if internal_imports:
            offenders[module_name(path)] = internal_imports
    assert not offenders, offenders


def test_infrastructure_storage_paths_stay_environment_only() -> None:
    assert infra_storage.graph_path is infra_storage_paths.graph_path
    assert infra_storage.raw_graph_path is infra_storage_paths.raw_graph_path
    assert_no_forbidden_imports_in_files(
        [PACKAGE_ROOT / "infrastructure" / "storage_paths.py"],
        {
            "pydiag.infrastructure.storage",
            "pydiag.infrastructure.storage_io",
            "pydiag.infrastructure.storage_loading",
            "pydiag.infrastructure.storage_writes",
            "pydiag.infrastructure.figma_import",
        },
    )


def test_infrastructure_storage_io_stays_low_level() -> None:
    assert infra_storage.save_json_atomic is infra_storage_io.save_json_atomic
    assert_no_forbidden_imports_in_files(
        [PACKAGE_ROOT / "infrastructure" / "storage_io.py"],
        {
            "pydiag.infrastructure.storage",
            "pydiag.infrastructure.storage_loading",
            "pydiag.infrastructure.storage_writes",
            "pydiag.infrastructure.figma_import",
        },
    )


def test_infrastructure_storage_loading_stays_read_focused() -> None:
    assert infra_storage.load_documents is infra_storage_loading.load_documents
    assert_no_forbidden_imports_in_files(
        [PACKAGE_ROOT / "infrastructure" / "storage_loading.py"],
        {
            "pydiag.infrastructure.storage",
            "pydiag.infrastructure.storage_io",
            "pydiag.infrastructure.storage_writes",
        },
    )


def test_infrastructure_storage_materialization_stays_narrow() -> None:
    assert (
        infra_storage.materialize_flow_graph_from_raw_source
        is infra_storage_materialization.materialize_flow_graph_from_raw_source
    )
    assert_no_forbidden_imports_in_files(
        [PACKAGE_ROOT / "infrastructure" / "storage_materialization.py"],
        {
            "pydiag.infrastructure.storage",
            "pydiag.infrastructure.storage_loading",
            "pydiag.infrastructure.storage_writes",
        },
    )


def test_infrastructure_storage_facade_stays_thin() -> None:
    assert (
        infra_storage.save_graph_positions_with_version_check
        is infra_storage_writes.save_graph_positions_with_version_check
    )
    imports = file_imports(PACKAGE_ROOT / "infrastructure" / "storage.py")
    assert imports == {
        "pydiag.common.errors",
        "pydiag.infrastructure.graph_versions",
        "pydiag.infrastructure.storage_io",
        "pydiag.infrastructure.storage_loading",
        "pydiag.infrastructure.storage_materialization",
        "pydiag.infrastructure.storage_paths",
        "pydiag.infrastructure.storage_writes",
    }


def test_infrastructure_json_documents_gateway_stays_thin() -> None:
    imports = file_imports(PACKAGE_ROOT / "infrastructure" / "json_documents_gateway.py")
    assert imports == {
        "collections.abc",
        "dataclasses",
        "pathlib",
        "pydiag.common.graph_versions",
        "pydiag.domain.models",
        "pydiag.infrastructure.graph_versions",
        "pydiag.infrastructure.storage",
    }


def test_rendering_node_rendering_facade_stays_thin() -> None:
    assert rendering_flow_node_rendering.KIND_LABELS is rendering_flow_node_filters.KIND_LABELS
    assert (
        rendering_flow_node_rendering.build_node_render_specs
        is rendering_flow_node_render_specs.build_node_render_specs
    )
    assert (
        rendering_flow_node_rendering.NodeRenderSpec
        is rendering_flow_node_render_specs.NodeRenderSpec
    )
    assert (
        rendering_flow_node_rendering.node_matches_filters
        is rendering_flow_node_filters.node_matches_filters
    )
    assert (
        rendering_flow_node_rendering.wells_grouped_by_node
        is rendering_flow_node_filters.wells_grouped_by_node
    )
    imports = file_imports(PACKAGE_ROOT / "rendering" / "flow_node_rendering.py")
    assert imports == {
        "pydiag.rendering.flow_node_filters",
        "pydiag.rendering.flow_node_render_specs",
    }


def test_rendering_render_math_helpers_stay_low_level() -> None:
    assert rendering_flow_render_math.ceil_to_step is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_render_math.py")],
        {
            "pydiag.rendering.flow_node_rendering",
            "pydiag.rendering.flow_node_overlays",
            "pydiag.rendering.flow_node_render_specs",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_streamlit_nodes",
        },
    )


def test_rendering_node_filter_helpers_stay_support_only() -> None:
    assert rendering_flow_node_filters.node_matches_filters is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_node_filters.py")],
        {
            "pydiag.rendering.flow_node_rendering",
            "pydiag.rendering.flow_node_render_specs",
            "pydiag.rendering.flow_node_styles",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_streamlit_nodes",
        },
    )


def test_rendering_node_render_spec_helpers_stay_support_only() -> None:
    assert rendering_flow_node_render_specs.build_node_render_specs is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_node_render_specs.py")],
        {
            "pydiag.rendering.flow_node_rendering",
            "pydiag.rendering.flow_node_styles",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_streamlit_nodes",
        },
    )


def test_rendering_node_markup_helpers_stay_independent_from_adapters_and_component() -> None:
    assert rendering_flow_node_markup.node_content is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_node_markup.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_node_style_helpers_stay_independent_from_adapters_and_component() -> None:
    assert rendering_flow_node_styles.node_style is not None
    assert (
        rendering_flow_node_styles.figma_font_weight
        is rendering_flow_figma_text_styles.figma_font_weight
    )
    assert (
        rendering_flow_node_styles.figma_text_align
        is rendering_flow_figma_text_styles.figma_text_align
    )
    assert (
        rendering_flow_node_styles.figma_vertical_align
        is rendering_flow_figma_text_styles.figma_vertical_align
    )
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_node_styles.py")],
        {
            "pydiag.rendering.flow_node_rendering",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_figma_text_style_helpers_stay_support_only() -> None:
    assert rendering_flow_figma_text_styles.figma_text_style is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_figma_text_styles.py")],
        {
            "pydiag.rendering.flow_node_styles",
            "pydiag.rendering.flow_node_rendering",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_shape_background_helpers_stay_low_level() -> None:
    assert rendering_flow_node_shape_backgrounds.polygon_background is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_node_shape_backgrounds.py")],
        {
            "pydiag.rendering.flow_node_styles",
            "pydiag.rendering.flow_node_rendering",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_node_overlay_helpers_stay_independent_from_adapters_and_component() -> None:
    assert rendering_flow_node_overlays.duration_label is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_node_overlays.py")],
        {
            "pydiag.rendering.flow_node_rendering",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_layout_position_helpers_stay_independent_from_routing_adapters_and_component() -> (
    None
):
    assert rendering_flow_layout_positions.layout_positions is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_layout_positions.py")],
        {
            "pydiag.rendering.flow_layout_routing",
            "pydiag.rendering.flow_edge_routing",
            "pydiag.rendering.flow_edge_labels",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_edge_routing_helpers_stay_independent_from_labels_adapters_and_component() -> (
    None
):
    assert rendering_flow_edge_routing.build_edge_routes_for_geometries is not None
    assert (
        rendering_flow_edge_routing.build_edge_routes_for_geometries
        is rendering_flow_route_paths.build_edge_routes_for_geometries
    )
    assert (
        rendering_flow_edge_routing.route_target_side
        is rendering_flow_route_ports.route_target_side
    )
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_edge_routing.py")],
        {
            "pydiag.rendering.flow_layout_positions",
            "pydiag.rendering.flow_layout_routing",
            "pydiag.rendering.flow_edge_labels",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_route_geometry",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_edge_label_helpers_stay_independent_from_routing_adapters_and_component() -> (
    None
):
    assert rendering_flow_edge_labels.edge_label_position is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_edge_labels.py")],
        {
            "pydiag.rendering.flow_layout_routing",
            "pydiag.rendering.flow_edge_routing",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_layout_routing_helpers_stay_as_a_thin_public_facade() -> None:
    assert rendering_package.layout_positions is rendering_flow_layout_routing.layout_positions
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_layout_routing.py")],
        {
            "pydiag.rendering.flow_layout_routing",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_route_geometry_helpers_stay_low_level() -> None:
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_route_geometry.py")],
        {
            "pydiag.rendering.flow_layout_routing",
            "pydiag.rendering.flow_layout_positions",
            "pydiag.rendering.flow_edge_routing",
            "pydiag.rendering.flow_edge_labels",
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )
    assert rendering_flow_route_geometry.port_point is not None


def test_rendering_route_port_helpers_stay_support_only() -> None:
    assert rendering_flow_route_ports.route_source_side is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_route_ports.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_edge_labels",
            "pydiag.rendering.flow_edge_routing",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
        },
    )


def test_rendering_route_lane_helpers_stay_low_level() -> None:
    assert rendering_flow_route_lanes.row_route_lane_y is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_route_lanes.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_edge_labels",
            "pydiag.rendering.flow_edge_routing",
            "pydiag.rendering.flow_layout_positions",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
        },
    )


def test_rendering_route_path_helpers_stay_support_only() -> None:
    assert rendering_flow_route_paths.build_edge_routes_for_geometries is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_route_paths.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_edge_labels",
            "pydiag.rendering.flow_edge_routing",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
        },
    )


def test_rendering_edge_rendering_helpers_stay_shared_and_adapter_free() -> None:
    assert rendering_flow_edge_rendering.edge_color is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_edge_rendering.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_render_snapshot",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_render_snapshot_stays_shared_and_adapter_free() -> None:
    assert rendering_flow_render_snapshot.build_flow_render_snapshot is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_render_snapshot.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_render_metrics",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_render_metrics_stay_shared_and_adapter_free() -> None:
    assert rendering_flow_render_metrics.flow_canvas_height is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_render_metrics.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_streamlit_primitives_stay_compatibility_only() -> None:
    assert rendering_flow_streamlit_primitives.StreamlitFlowNode is not None
    imports = file_imports(rendering_file("flow_streamlit_primitives.py"))
    assert imports == {
        "typing",
        "streamlit_flow.elements",
    }


def test_rendering_streamlit_overlay_node_helpers_live_in_owner_module() -> None:
    assert rendering_flow_streamlit_nodes.overlay_nodes_for_domain_node is not None


def test_rendering_streamlit_route_node_helpers_live_in_owner_module() -> None:
    assert rendering_flow_streamlit_nodes.route_anchor_nodes_for_route is not None
    assert rendering_flow_streamlit_nodes.route_label_node_for_route is not None


def test_rendering_streamlit_node_owner_stays_out_of_component_runtime() -> None:
    assert rendering_flow_streamlit_nodes.build_streamlit_nodes_from_snapshot is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_streamlit_nodes.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_canvas_payload",
            "pydiag.rendering.flow_streamlit_edges",
        },
    )


def test_rendering_canvas_adapter_can_use_node_helpers_without_component_runtime() -> None:
    assert rendering_flow_adapter.KIND_LABELS is rendering_flow_node_rendering.KIND_LABELS
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_canvas_adapter.py")],
        {
            "pydiag.rendering.flow_canvas_component",
        },
    )


def test_rendering_canvas_state_helpers_stay_framework_free() -> None:
    assert rendering_flow_canvas_state.component_selected_id_from_state is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_canvas_state.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_canvas_payload",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
        },
    )


def test_rendering_canvas_bounds_helpers_stay_low_level() -> None:
    assert rendering_flow_canvas_bounds.flow_canvas_bounds is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_canvas_bounds.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_canvas_payload",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
        },
    )


def test_rendering_canvas_payload_exposes_node_helpers() -> None:
    assert rendering_flow_canvas_payload.build_flow_canvas_nodes_from_snapshot is not None


def test_rendering_canvas_payload_exposes_edge_helpers() -> None:
    assert rendering_flow_canvas_payload.build_flow_canvas_edges_from_snapshot is not None


def test_rendering_canvas_payload_owner_stays_component_free() -> None:
    assert rendering_flow_canvas_payload.build_flow_canvas_payload is not None
    assert_no_forbidden_imports_in_files(
        [rendering_file("flow_canvas_payload.py")],
        {
            "pydiag.rendering.flow_adapter",
            "pydiag.rendering.flow_canvas_adapter",
            "pydiag.rendering.flow_canvas_component",
            "pydiag.rendering.flow_streamlit_edges",
            "pydiag.rendering.flow_streamlit_nodes",
            "pydiag.rendering.flow_streamlit_primitives",
        },
    )


def test_rendering_canvas_adapter_facade_stays_thin() -> None:
    assert (
        rendering_flow_canvas_adapter.build_flow_canvas_payload
        is rendering_flow_canvas_payload.build_flow_canvas_payload
    )
    assert (
        rendering_flow_canvas_adapter.component_positions_from_state
        is rendering_flow_canvas_state.component_positions_from_state
    )
    assert (
        rendering_flow_canvas_adapter.component_selected_id_from_state
        is rendering_flow_canvas_state.component_selected_id_from_state
    )
    imports = file_imports(rendering_file("flow_canvas_adapter.py"))
    assert imports == {
        "pydiag.rendering.flow_canvas_payload",
        "pydiag.rendering.flow_canvas_state",
    }


def test_presentation_view_model_modules_stay_pure() -> None:
    assert_no_forbidden_imports_in_files(
        [
            presentation_file("admin_models.py"),
            presentation_file("html_utils.py"),
            presentation_file("inspector_models.py"),
        ],
        {
            "streamlit",
            "pydiag.infrastructure",
            "pydiag.presentation.admin",
            "pydiag.presentation.chrome",
            "pydiag.presentation.inspector",
            "pydiag.presentation.runtime",
            "pydiag.presentation.runtime_session",
            "pydiag.presentation.sidebar",
            "pydiag.presentation.streamlit_app",
        },
    )


def test_presentation_chrome_module_stays_out_of_runtime_and_infrastructure() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("chrome.py")],
        {
            "streamlit",
            "pydiag.infrastructure",
            "pydiag.presentation.runtime",
            "pydiag.presentation.runtime_session",
            "pydiag.presentation.sidebar",
            "pydiag.presentation.streamlit_app",
        },
    )


def test_presentation_auth_models_stay_pure() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("auth_models.py")],
        {
            "streamlit",
            "pydiag.infrastructure",
            "pydiag.presentation.auth",
            "pydiag.presentation.auth_config",
            "pydiag.presentation.auth_policy",
            "pydiag.presentation.auth_session",
            "pydiag.presentation.auth_sources",
            "pydiag.presentation.runtime",
            "pydiag.presentation.sidebar",
        },
    )


def test_presentation_auth_sources_stay_out_of_runtime_ui_and_session_helpers() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("auth_sources.py")],
        {
            "streamlit",
            "pydiag.infrastructure",
            "pydiag.presentation.auth",
            "pydiag.presentation.auth_config",
            "pydiag.presentation.auth_policy",
            "pydiag.presentation.auth_session",
            "pydiag.presentation.runtime",
            "pydiag.presentation.sidebar",
            "pydiag.presentation.streamlit_app",
        },
    )


def test_presentation_auth_policy_stays_out_of_runtime_ui_and_session_helpers() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("auth_policy.py")],
        {
            "streamlit",
            "pydiag.infrastructure",
            "pydiag.presentation.auth",
            "pydiag.presentation.auth_config",
            "pydiag.presentation.auth_session",
            "pydiag.presentation.runtime",
            "pydiag.presentation.sidebar",
            "pydiag.presentation.streamlit_app",
        },
    )
    assert presentation_auth_policy.admin_password is not None


def test_presentation_auth_session_stays_state_focused() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("auth_session.py")],
        {
            "streamlit",
            "pydiag.infrastructure",
            "pydiag.presentation.auth",
            "pydiag.presentation.auth_config",
            "pydiag.presentation.runtime",
            "pydiag.presentation.sidebar",
            "pydiag.presentation.streamlit_app",
        },
    )
    assert presentation_auth_session.current_user_is_admin is not None


def test_presentation_auth_facade_stays_thin() -> None:
    imports = file_imports(presentation_file("auth.py"))
    assert presentation_auth.admin_password is presentation_auth_config.admin_password
    assert imports == {
        "collections.abc",
        "dataclasses",
        "typing",
        "pydiag.presentation.auth_config",
        "pydiag.presentation.auth_models",
        "pydiag.presentation.auth_session",
    }


def test_presentation_auth_config_facade_stays_thin() -> None:
    assert presentation_auth_config.AUTH_USERS_ENV == presentation_auth_sources.AUTH_USERS_ENV
    assert (
        presentation_auth_config.LEGACY_ADMIN_USERNAME
        == presentation_auth_sources.LEGACY_ADMIN_USERNAME
    )
    assert (
        presentation_auth_config.auth_users_from_env_json
        is presentation_auth_sources.auth_users_from_env_json
    )
    assert (
        presentation_auth_config.configured_admin_password
        is presentation_auth_sources.configured_admin_password
    )
    assert presentation_auth_config.admin_password is presentation_auth_policy.admin_password
    assert presentation_auth_config.authenticate_user is presentation_auth_policy.authenticate_user
    imports = file_imports(presentation_file("auth_config.py"))
    assert imports == {
        "pydiag.presentation.auth_policy",
        "pydiag.presentation.auth_sources",
    }


def test_presentation_sidebar_module_stays_out_of_runtime_and_infrastructure() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("sidebar.py")],
        {
            "pydiag.infrastructure",
            "pydiag.presentation.runtime",
            "pydiag.presentation.runtime_session",
            "pydiag.presentation.streamlit_app",
        },
    )
    assert presentation_sidebar.render_sidebar is not None


def test_presentation_sidebar_renderer_stays_thin() -> None:
    imports = file_imports(presentation_file("sidebar.py"))
    assert imports == {
        "collections.abc",
        "dataclasses",
        "typing",
        "pydiag.common.graph_versions",
        "pydiag.domain.models",
        "pydiag.rendering.flow_node_rendering",
    }


def test_presentation_admin_renderer_routes_well_mutations_through_application() -> None:
    imports = file_imports(presentation_file("admin.py"))
    assert imports == {
        "collections.abc",
        "dataclasses",
        "pydiag.application",
        "pydiag.domain.models",
        "pydiag.presentation.admin_models",
    }


def test_streamlit_app_entrypoint_stays_minimal() -> None:
    imports = file_imports(presentation_file("streamlit_app.py"))
    assert imports == {
        "pydiag.infrastructure",
        "streamlit",
        "pydiag.presentation.runtime",
        "pydiag.rendering.flow_canvas_component",
    }


def test_runtime_coordinator_avoids_direct_streamlit_and_infrastructure_imports() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("runtime.py")],
        {
            "streamlit",
            "pydiag.infrastructure",
        },
    )


def test_chrome_renderer_stays_thin_and_uses_support_modules() -> None:
    assert presentation_chrome.build_header_model is not None
    assert presentation_chrome.APP_CSS.startswith("<style>")
    imports = file_imports(presentation_file("chrome.py"))
    assert imports == {
        "dataclasses",
        "pydiag.domain.models",
        "pydiag.presentation.html_utils",
    }


def test_runtime_session_stays_out_of_ui_rendering_modules() -> None:
    assert_no_forbidden_imports_in_files(
        [presentation_file("runtime_session.py")],
        {
            "streamlit",
            "pydiag.infrastructure",
            "pydiag.presentation.admin",
            "pydiag.presentation.chrome",
            "pydiag.presentation.inspector",
            "pydiag.presentation.sidebar",
            "pydiag.presentation.streamlit_app",
        },
    )


def test_streamlit_renderer_modules_do_not_talk_to_infrastructure_directly() -> None:
    assert_no_forbidden_imports_in_files(
        [
            presentation_file("admin.py"),
            presentation_file("chrome.py"),
            presentation_file("inspector.py"),
            presentation_file("sidebar.py"),
        ],
        {"pydiag.infrastructure"},
    )


def test_root_app_py_stays_minimal() -> None:
    app_path = ROOT / "app.py"
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_path))

    function_defs = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert function_defs == []
    assert "pydiag.presentation.streamlit_app" in source
