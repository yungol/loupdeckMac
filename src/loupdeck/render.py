"""Renderizado de la UI: convierte (label, icono, color) en imagenes PIL.

Separa el 'como se ve' del 'que hace'. El controller pide imagenes; este modulo
no sabe nada del device ni de las acciones.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .protocol import KEY_SIZE

Color = Tuple[int, int, int]

_TEXT_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def _load_text_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _TEXT_FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class Renderer:
    def __init__(self, icon_font_path: str, icon_size: int = 40, label_size: int = 13) -> None:
        self.icon_font = ImageFont.truetype(str(icon_font_path), icon_size)
        self.text_font = _load_text_font(label_size)
        self.side_font = _load_text_font(16)

    def key(
        self,
        label: str,
        codepoint: Optional[int],
        color: Color,
        fg: Color = (255, 255, 255),
    ) -> Image.Image:
        img = Image.new("RGB", (KEY_SIZE, KEY_SIZE), color)
        draw = ImageDraw.Draw(img)
        if codepoint is not None:
            draw.text((KEY_SIZE // 2, 33), chr(codepoint), font=self.icon_font, anchor="mm", fill=fg)
            if label:
                draw.text((KEY_SIZE // 2, 74), label, font=self.text_font, anchor="mm", fill=fg)
        elif label:
            draw.text((KEY_SIZE // 2, KEY_SIZE // 2), label, font=self.text_font, anchor="mm", fill=fg)
        return img

    def side(self, text: str, color: Color, fg: Color = (255, 255, 255)) -> Image.Image:
        img = Image.new("RGB", (60, 270), color)
        draw = ImageDraw.Draw(img)
        total = len(text) * 20
        y = (270 - total) // 2
        for char in text:
            draw.text((30, y + 10), char, font=self.side_font, anchor="mm", fill=fg)
            y += 20
        return img
