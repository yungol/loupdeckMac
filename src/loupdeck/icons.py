"""Material Icons: nombre legible -> codepoint en la fuente.

Todos verificados contra assets/MaterialIcons-Regular.ttf (renderizan glifo).
El layout.json referencia iconos por nombre; aca se resuelven a codepoint.
"""

from __future__ import annotations

from typing import Optional

ICONS = {
    "terminal": 0xEB8E, "folder": 0xE2C7, "code": 0xE86F,
    "volume_up": 0xE050, "volume_off": 0xE04F, "volume_down": 0xE04D,
    "photo_library": 0xE413, "mic": 0xE029, "mic_off": 0xE02B,
    "language": 0xE894, "queue_music": 0xE03D, "home": 0xE88A,
    "settings": 0xE8B8, "search": 0xE8B6, "mail": 0xE158,
    "web": 0xE051, "videocam": 0xE04B, "photo_camera": 0xE412,
    "music_note": 0xE405, "play_arrow": 0xE037, "pause": 0xE034,
    "skip_next": 0xE044, "skip_previous": 0xE045, "lock": 0xE897,
    "brightness_high": 0xE1AC, "refresh": 0xE5D5, "close": 0xE5CD,
    "check": 0xE5CA, "star": 0xE838, "favorite": 0xE87D,
    "delete": 0xE872, "edit": 0xE3C9, "save": 0xE161,
    "content_copy": 0xE14D, "content_paste": 0xE14F, "desktop_windows": 0xE30C,
    "computer": 0xE30A, "keyboard": 0xE312, "power": 0xE8AC,
    "add": 0xE145, "chat": 0xE0B7, "call": 0xE0B0,
    "camera": 0xE3AF, "map": 0xE55B, "event": 0xE878,
    "headphones": 0xF01F, "dns": 0xE875, "extension": 0xE87B,
    "apps": 0xE5C3, "menu": 0xE5D2,
    "auto_awesome": 0xE65F,
}


def codepoint(name: Optional[str]) -> Optional[int]:
    """Devuelve el codepoint del icono, o None si el nombre es None/desconocido."""
    if name is None:
        return None
    return ICONS.get(name)
