from __future__ import annotations

import json
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

FigmaBlendMode = Literal[
    "PASS_THROUGH",
    "NORMAL",
    "DARKEN",
    "MULTIPLY",
    "LINEAR_BURN",
    "COLOR_BURN",
    "LIGHTEN",
    "SCREEN",
    "LINEAR_DODGE",
    "COLOR_DODGE",
    "OVERLAY",
    "SOFT_LIGHT",
    "HARD_LIGHT",
    "DIFFERENCE",
    "EXCLUSION",
    "HUE",
    "SATURATION",
    "COLOR",
    "LUMINOSITY",
]


class FigmaBaseModel(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore", populate_by_name=True)


class FigmaFontName(FigmaBaseModel):
    family: str | None = None
    style: str | None = None


class FigmaSpacing(FigmaBaseModel):
    unit: str | None = None
    value: float | None = None


class FigmaLineHeight(FigmaBaseModel):
    unit: str | None = None
    value: float | None = None


class FigmaConstraints(FigmaBaseModel):
    horizontal: str | None = None
    vertical: str | None = None


class FigmaSceneNode(FigmaBaseModel):
    id: str
    name: str = ""
    type: str
    parent: str | None = None
    visible: bool = True
    locked: bool = False
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    rotation: float = 0.0
    opacity: float = 1.0
    blend_mode: FigmaBlendMode | str | None = Field(
        default=None,
        validation_alias=AliasChoices("blendMode", "blenmode"),
        serialization_alias="blendMode",
    )


class FigmaTextNode(FigmaSceneNode):
    type: Literal["TEXT"]
    characters: str = ""
    font_size: float | None = Field(
        default=None,
        validation_alias=AliasChoices("fontSize", "fontsize"),
        serialization_alias="fontSize",
    )
    font_name: FigmaFontName | None = Field(
        default=None,
        validation_alias=AliasChoices("fontName", "fontname"),
        serialization_alias="fontName",
    )
    text_align_horizontal: str | None = Field(
        default=None,
        validation_alias=AliasChoices("textAlignHorizontal", "textalognhorizontal"),
        serialization_alias="textAlignHorizontal",
    )
    text_align_vertical: str | None = Field(
        default=None,
        validation_alias=AliasChoices("textAlignVertical", "textalignverrical"),
        serialization_alias="textAlignVertical",
    )
    letter_spacing: FigmaSpacing | None = Field(
        default=None,
        validation_alias=AliasChoices("letterSpacing", "letterspacing"),
        serialization_alias="letterSpacing",
    )
    line_height: FigmaLineHeight | None = Field(
        default=None,
        validation_alias=AliasChoices("lineHeight", "lineheight"),
        serialization_alias="lineHeight",
    )
    text_case: str | None = Field(
        default=None,
        validation_alias=AliasChoices("textCase", "textcase"),
        serialization_alias="textCase",
    )
    text_decoration: str | None = Field(
        default=None,
        validation_alias=AliasChoices("textDecoration", "textdexoration"),
        serialization_alias="textDecoration",
    )
    is_mask: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("isMask", "ismask"),
        serialization_alias="isMask",
    )
    effect_style_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("effectStyleId", "effectstyleid"),
        serialization_alias="effectStyleId",
    )
    constraints: FigmaConstraints | None = None
    layout_align: str | None = Field(
        default=None,
        validation_alias=AliasChoices("layoutAlign", "layoutalign"),
        serialization_alias="layoutAlign",
    )
    layout_grow: float | None = Field(
        default=None,
        validation_alias=AliasChoices("layoutGrow", "layoutgrow"),
        serialization_alias="layoutGrow",
    )
    layout_sizing_horizontal: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "layoutSizingHorizontal", "layoutsizinghorizontal"
        ),
        serialization_alias="layoutSizingHorizontal",
    )
    layout_sizing_vertical: str | None = Field(
        default=None,
        validation_alias=AliasChoices("layoutSizingVertical", "layoutsizingverrical"),
        serialization_alias="layoutSizingVertical",
    )


class FigmaConnectorNode(FigmaSceneNode):
    type: Literal["CONNECTOR"]


class FigmaOtherNode(FigmaSceneNode):
    pass


FigmaNode = FigmaTextNode | FigmaConnectorNode | FigmaOtherNode


def load_payload(raw: bytes) -> object:
    return json.loads(raw.decode("utf-8"))


def extract_typed_elements(
    payload: object,
) -> list[tuple[dict[str, object], FigmaNode]]:
    raw_elements = extract_elements_container(payload)
    nodes: list[tuple[dict[str, object], FigmaNode]] = []
    for item in raw_elements:
        if not isinstance(item, dict):
            continue
        node_type = str(item.get("type") or "").upper()
        if node_type in {"TEXT", "SHAPE_WITH_TEXT"}:
            nodes.append((item, FigmaTextNode.model_validate(text_like_payload(item))))
        elif node_type == "CONNECTOR":
            nodes.append((item, FigmaConnectorNode.model_validate(item)))
        else:
            nodes.append((item, FigmaOtherNode.model_validate(item)))
    if not nodes:
        raise ValueError("Figma skeleton payload does not contain any scene nodes")
    return nodes


def extract_raw_elements(payload: object) -> list[FigmaNode]:
    return [node for _, node in extract_typed_elements(payload)]


def payload_version(payload: object) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("version"), int):
        return int(payload["version"])
    return 1


def extract_elements_container(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("elements", "nodes", "components"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("Unsupported Figma skeleton payload shape")


def text_like_payload(item: dict[str, object]) -> dict[str, object]:
    if str(item.get("type") or "").upper() == "TEXT":
        return item
    normalized = dict(item)
    normalized["type"] = "TEXT"
    normalized["characters"] = str(
        item.get("characters") or item.get("name") or item.get("id") or ""
    )
    return normalized
