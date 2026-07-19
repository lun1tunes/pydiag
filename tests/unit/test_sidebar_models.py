from __future__ import annotations

from pydiag.presentation.sidebar import (
    KIND_FILTER_LABELS,
    build_authenticated_user_state,
    build_login_state,
    build_position_edit_state,
)


def test_authenticated_user_state_exposes_rights_caption() -> None:
    admin_state = build_authenticated_user_state(
        {"display_name": "Иван", "username": "ivan"},
        is_admin=True,
        is_super_admin=False,
    )
    super_admin_state = build_authenticated_user_state(
        {"display_name": "planner", "username": "planner"},
        is_admin=True,
        is_super_admin=True,
    )
    user_state = build_authenticated_user_state(
        {"display_name": "Гость", "username": "guest"},
        is_admin=False,
        is_super_admin=False,
    )

    assert admin_state.display_name == "Иван"
    assert admin_state.rights_caption == "Права: Админ"
    assert super_admin_state.rights_caption == "Права: Super Admin"
    assert user_state.rights_caption == "Права: Пользователь"


def test_login_state_reflects_user_configuration_and_insecure_mode() -> None:
    configured = build_login_state(
        users_configured=True,
        warning_message="warn",
        insecure_admin_mode_enabled=False,
    )
    unconfigured = build_login_state(
        users_configured=False,
        warning_message="warn",
        insecure_admin_mode_enabled=True,
    )

    assert configured.warning_message is None
    assert configured.insecure_caption is None
    assert unconfigured.warning_message == "warn"
    assert "admin" in str(unconfigured.insecure_caption)


def test_position_edit_state_controls_visibility_caption_and_save_button() -> None:
    hidden = build_position_edit_state(
        is_admin=False,
        enabled=True,
        editable=True,
        save_positions_enabled=True,
    )
    visible = build_position_edit_state(
        is_admin=True,
        enabled=True,
        editable=True,
        save_positions_enabled=False,
    )
    blocked = build_position_edit_state(
        is_admin=True,
        enabled=False,
        editable=False,
        save_positions_enabled=True,
    )

    assert hidden.visible is False
    assert hidden.enabled is False
    assert visible.visible is True
    assert visible.enabled is True
    assert visible.save_disabled is True
    assert blocked.enabled is False
    assert blocked.editable is False


def test_sidebar_labels_expose_expected_public_values() -> None:
    labels = list(KIND_FILTER_LABELS.values())

    assert len(labels) == len(set(labels))
    assert KIND_FILTER_LABELS["decision_diamond"] == "Решение (ромб)"
    assert KIND_FILTER_LABELS["decision_card"] == "Решение (карточка)"
    assert KIND_FILTER_LABELS["event"] == "Событие"
    assert KIND_FILTER_LABELS["figma_text"] == "Текст Figma"
