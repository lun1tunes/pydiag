from __future__ import annotations

from pydiag.presentation.sidebar import (
    KIND_FILTER_LABELS,
    LAYOUT_MODE_LABELS,
    build_authenticated_user_state,
    build_login_state,
    build_position_edit_state,
)


def test_authenticated_user_state_hides_duplicate_username_caption() -> None:
    user_state = build_authenticated_user_state(
        {"display_name": "Иван", "username": "ivan"},
        is_admin=True,
        is_super_admin=False,
    )
    same_name_state = build_authenticated_user_state(
        {"display_name": "planner", "username": "planner"},
        is_admin=False,
        is_super_admin=True,
    )

    assert user_state.display_name == "Иван"
    assert user_state.username_caption == "Логин: ivan"
    assert user_state.show_admin_caption is True
    assert user_state.show_super_admin_caption is False
    assert same_name_state.username_caption is None
    assert same_name_state.show_super_admin_caption is True


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
        layout_mode="manual",
        save_positions_enabled=True,
        block_reason=None,
    )
    visible = build_position_edit_state(
        is_admin=True,
        enabled=True,
        editable=True,
        layout_mode="custom",
        save_positions_enabled=False,
        block_reason=None,
    )
    snake = build_position_edit_state(
        is_admin=True,
        enabled=True,
        editable=True,
        layout_mode="snake",
        save_positions_enabled=True,
        block_reason=None,
    )

    assert hidden.visible is False
    assert hidden.enabled is False
    assert hidden.helper_caption is None
    assert visible.visible is True
    assert visible.enabled is True
    assert "Фишки скважин" in str(visible.helper_caption)
    assert visible.save_disabled is True
    assert snake.enabled is False
    assert "custom" in str(snake.helper_caption)


def test_sidebar_labels_expose_expected_public_values() -> None:
    labels = list(KIND_FILTER_LABELS.values())

    assert len(labels) == len(set(labels))
    assert KIND_FILTER_LABELS["decision_diamond"] == "Решение (ромб)"
    assert KIND_FILTER_LABELS["decision_card"] == "Решение (карточка)"
    assert KIND_FILTER_LABELS["event"] == "Событие"
    assert KIND_FILTER_LABELS["figma_text"] == "Текст Figma"
    assert LAYOUT_MODE_LABELS == {
        "snake": "Змейка",
        "manual": "Координаты из source",
        "custom": "Кастомный layout",
    }
