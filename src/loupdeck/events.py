"""Decodificacion de eventos entrantes (device -> Mac), dominio puro.

Traduce un mensaje crudo (command + data) a un evento tipado y legible. No
mantiene estado ni sabe de hilos: solo interpreta bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .protocol import BUTTONS, Command, DISPLAYS, KEY_COLUMNS, KEY_SIZE

ButtonId = Union[int, str]


@dataclass
class ButtonEvent:
    id: ButtonId
    pressed: bool  # True = down, False = up


@dataclass
class RotateEvent:
    id: ButtonId
    delta: int  # con signo: + horario, - antihorario


@dataclass
class TouchEvent:
    type: str  # 'start' | 'move' | 'end'
    x: int
    y: int
    touch_id: int
    screen: Optional[str]  # 'left' | 'center' | 'right'
    key: Optional[int]     # indice de tecla (0..11) si toco la grilla central


Event = Union[ButtonEvent, RotateEvent, TouchEvent]


def touch_target(x: int, y: int) -> "tuple[Optional[str], Optional[int]]":
    """Dado un punto absoluto, devuelve (pantalla, indice_de_tecla)."""
    left_w = DISPLAYS["left"].width
    center_w = DISPLAYS["center"].width
    if x < left_w:
        return "left", None
    if x >= left_w + center_w:
        return "right", None
    column = (x - left_w) // KEY_SIZE
    row = y // KEY_SIZE
    return "center", row * KEY_COLUMNS + column


def decode_event(command: int, data: bytes) -> Optional[Event]:
    """Convierte (command, data) en un Event, o None si no es un evento conocido."""
    if command == Command.BUTTON_PRESS and len(data) >= 2:
        return ButtonEvent(id=BUTTONS.get(data[0], data[0]), pressed=data[1] == 0x00)

    if command == Command.KNOB_ROTATE and len(data) >= 2:
        delta = data[1] - 256 if data[1] > 127 else data[1]  # int8 con signo
        return RotateEvent(id=BUTTONS.get(data[0], data[0]), delta=delta)

    if command in (Command.TOUCH, Command.TOUCH_CT) and len(data) >= 6:
        x = (data[1] << 8) | data[2]
        y = (data[3] << 8) | data[4]
        screen, key = touch_target(x, y)
        return TouchEvent("move", x, y, data[5], screen, key)

    if command in (Command.TOUCH_END, Command.TOUCH_END_CT) and len(data) >= 6:
        x = (data[1] << 8) | data[2]
        y = (data[3] << 8) | data[4]
        screen, key = touch_target(x, y)
        return TouchEvent("end", x, y, data[5], screen, key)

    return None
