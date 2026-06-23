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
    "zoom_in": 0xE8FF, "zoom_out": 0xE901,
    # Window positioning / layout icons
    "arrow_back": 0xE5C4, "arrow_forward": 0xE5C8,
    "arrow_upward": 0xE5D8, "arrow_downward": 0xE5DB,
    "north_west": 0xF0C5, "north_east": 0xE202,
    "south_west": 0xEB70, "south_east": 0xEB71,
    "crop_free": 0xE3C6, "crop_square": 0xE3C8,
    "center_focus_strong": 0xE3B4, "center_focus_weak": 0xE3B5,
    "fullscreen": 0xE5D0, "open_in_full": 0xE8E1,
    "open_with": 0xE89F, "grid_view": 0xE9B0,
    "dock_to_left": 0xEF3B, "dock_to_right": 0xEF3A,
    "window": 0xF088, "vertical_split": 0xE949,
    "horizontal_split": 0xE950,
}


def codepoint(name: Optional[str]) -> Optional[int]:
    """Devuelve el codepoint del icono, o None si el nombre es None/desconocido."""
    if name is None:
        return None
    return ICONS.get(name)
