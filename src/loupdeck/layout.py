"""Modelo del layout + carga desde layout.json.

El layout es DATOS puros: paginas con teclas, perillas y botones, cada uno con
una accion. Cargar = parsear el JSON a estos dataclasses; nada de I/O de device.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .actions import Action

Color = Tuple[int, int, int]

DEFAULT_BG: Color = (24, 24, 28)
DEFAULT_KEY_COLOR: Color = (40, 40, 46)


def _color(value, default: Color) -> Color:
    """Acepta '#RRGGBB' o [r, g, b]; devuelve tupla (r, g, b)."""
    if value is None:
        return default
    if isinstance(value, str):
        s = value.lstrip("#")
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    return default


@dataclass
class KeyDef:
    index: int
    label: str = ""
    icon: Optional[str] = None
    color: Color = DEFAULT_KEY_COLOR
    action: Optional[Action] = None


@dataclass
class KnobDef:
    rotate: Optional[Action] = None
    press: Optional[Action] = None
    icon: Optional[str] = None       # icono a mostrar en la franja lateral
    label: str = ""                  # texto corto debajo del icono
    color: Optional[Color] = None    # color del icono/texto


@dataclass
class ButtonDef:
    action: Optional[Action] = None
    color: Optional[Color] = None  # color del LED; None = usa el default del controller


@dataclass
class SideDef:
    text: str
    color: Color = DEFAULT_BG


@dataclass
class Page:
    name: str
    background: Color = DEFAULT_BG
    keys: List[KeyDef] = field(default_factory=list)
    knobs: Dict[str, KnobDef] = field(default_factory=dict)
    buttons: Dict[int, ButtonDef] = field(default_factory=dict)
    left: Optional[SideDef] = None
    right: Optional[SideDef] = None


@dataclass
class Layout:
    brightness: float = 1.0
    pages: List[Page] = field(default_factory=list)

    def page_by_name(self, name: str) -> Optional[Page]:
        return next((p for p in self.pages if p.name == name), None)


def _parse_page(obj: dict) -> Page:
    bg = _color(obj.get("background"), DEFAULT_BG)

    keys = [
        KeyDef(
            index=int(k["index"]),
            label=k.get("label", ""),
            icon=k.get("icon"),
            color=_color(k.get("color"), DEFAULT_KEY_COLOR),
            action=Action.from_json(k.get("action")),
        )
        for k in obj.get("keys", [])
    ]

    knobs = {
        name: KnobDef(
            rotate=Action.from_json(cfg.get("rotate")),
            press=Action.from_json(cfg.get("press")),
            icon=cfg.get("icon"),
            label=cfg.get("label", ""),
            color=_color(cfg["color"], DEFAULT_KEY_COLOR) if cfg.get("color") else None,
        )
        for name, cfg in obj.get("knobs", {}).items()
    }

    def _button(cfg) -> Optional[ButtonDef]:
        if not cfg:
            return None
        # Forma rica: {"color": "#..", "action": {...}}.
        if "action" in cfg or ("color" in cfg and "type" not in cfg):
            color = _color(cfg["color"], DEFAULT_KEY_COLOR) if cfg.get("color") else None
            return ButtonDef(action=Action.from_json(cfg.get("action")), color=color)
        # Forma simple (legacy): el cfg ES la accion.
        return ButtonDef(action=Action.from_json(cfg), color=None)

    buttons = {}
    for idx, cfg in obj.get("buttons", {}).items():
        bd = _button(cfg)
        if bd is not None:
            buttons[int(idx)] = bd

    def _side(cfg) -> Optional[SideDef]:
        if not cfg:
            return None
        return SideDef(text=cfg.get("text", ""), color=_color(cfg.get("color"), bg))

    return Page(
        name=obj["name"],
        background=bg,
        keys=keys,
        knobs=knobs,
        buttons=buttons,
        left=_side(obj.get("left")),
        right=_side(obj.get("right")),
    )


def load_layout(path: "str | Path") -> Layout:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Layout(
        brightness=float(data.get("brightness", 1.0)),
        pages=[_parse_page(p) for p in data.get("pages", [])],
    )
