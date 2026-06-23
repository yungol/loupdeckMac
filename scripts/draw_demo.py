#!/usr/bin/env python3
"""Demo de dibujo: pinta la pantalla del Loupedeck de punta a punta.

Ejercita todo el camino grafico: PIL -> RGB565 -> FRAMEBUFF -> DRAW.
Dibuja un fondo, las dos pantallas laterales y una grilla de teclas con
iconos Material Icons + etiquetas.

Uso:
    .venv/bin/python scripts/draw_demo.py
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from loupdeck.device import LoupedeckDevice  # noqa: E402
from loupdeck.discovery import discover  # noqa: E402
from loupdeck.protocol import KEY_SIZE  # noqa: E402

APP_DIR = Path(__file__).resolve().parent.parent
ICON_FONT_PATH = APP_DIR / "assets" / "MaterialIcons-Regular.ttf"

# (label, codepoint) de Material Icons, verificados contra la fuente que ya usabas.
ICONS = [
    ("Terminal", 0xEB8E),  # terminal
    ("Archivos", 0xE2C7),  # folder
    ("Codigo", 0xE86F),    # code
    ("Volumen", 0xE050),   # volume_up
    ("Fotos", 0xE413),     # photo_library
    ("Mic", 0xE029),       # mic
    ("Web", 0xE894),       # language
    ("Musica", 0xE03D),    # queue_music
]

KEY_COLORS = [
    (0, 200, 120), (255, 170, 0), (90, 130, 220), (0, 150, 215),
    (255, 60, 120), (180, 90, 220), (0, 190, 200), (40, 200, 90),
]


def load_text_font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_key(label: str, codepoint: int, bg, fg=(255, 255, 255)) -> Image.Image:
    img = Image.new("RGB", (KEY_SIZE, KEY_SIZE), bg)
    draw = ImageDraw.Draw(img)
    icon_font = ImageFont.truetype(str(ICON_FONT_PATH), 40)
    text_font = load_text_font(13)
    draw.text((KEY_SIZE // 2, 33), chr(codepoint), font=icon_font, anchor="mm", fill=fg)
    draw.text((KEY_SIZE // 2, 74), label, font=text_font, anchor="mm", fill=fg)
    return img


def render_side(text: str, bg) -> Image.Image:
    img = Image.new("RGB", (60, 270), bg)
    draw = ImageDraw.Draw(img)
    font = load_text_font(15)
    # Texto vertical simple: una letra por linea, centrado.
    total = len(text) * 18
    y = (270 - total) // 2
    for char in text:
        draw.text((30, y + 9), char, font=font, anchor="mm", fill=(255, 255, 255))
        y += 18
    return img


def main() -> int:
    devices = discover()
    if not devices:
        print("X No se encontro el dispositivo.")
        return 1

    dev = LoupedeckDevice(devices[0].path)
    dev.connect()
    print(f"Conectado a {devices[0].description}. Dibujando...")

    dev.set_brightness(1.0)

    # Fondo general oscuro (toda la pantalla), sin refrescar todavia.
    dev.fill_region("full", (18, 18, 22), refresh=False)

    # Pantallas laterales.
    dev.draw_image("left", render_side("VOL", (0, 120, 80)), refresh=False)
    dev.draw_image("right", render_side("MIC", (140, 40, 60)), refresh=False)

    # Grilla central: 8 teclas con icono, el resto en gris oscuro.
    for index in range(12):
        if index < len(ICONS):
            label, codepoint = ICONS[index]
            img = render_key(label, codepoint, KEY_COLORS[index])
        else:
            img = Image.new("RGB", (KEY_SIZE, KEY_SIZE), (30, 30, 34))
        dev.draw_key(index, img, refresh=False)

    # Un unico refresh final: todo aparece de golpe.
    dev.refresh()
    print("Listo. Mira la pantalla del device. (10s y cierro)")

    try:
        time.sleep(10)
    except KeyboardInterrupt:
        pass
    dev.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
