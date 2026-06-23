#!/usr/bin/env python3
"""Paso minimo: UN boton en pantalla y detectar su pulsacion, nada mas.

- Pinta una sola tecla (indice 6, zona central).
- Al tocarla: lo imprime al instante Y la tecla cambia de color en la pantalla.
- La conexion queda abierta (la pantalla NO se apaga) hasta Ctrl+C.

Uso:
    .venv/bin/python scripts/one_button.py
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from loupdeck.device import LoupedeckDevice  # noqa: E402
from loupdeck.discovery import discover  # noqa: E402
from loupdeck.events import TouchEvent  # noqa: E402

KEY_INDEX = 6  # una tecla del centro


def make_key(text: str, color) -> Image.Image:
    img = Image.new("RGB", (90, 90), color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    draw.text((45, 45), text, font=font, anchor="mm", fill=(255, 255, 255))
    return img


def main() -> int:
    devices = discover()
    if not devices:
        print("X No se encontro el dispositivo.")
        return 1

    dev = LoupedeckDevice(devices[0].path)

    def on_touch(e: TouchEvent) -> None:
        if e.key != KEY_INDEX:
            return
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if e.type == "start":
            print(f"[{ts}] >>> DETECTADO: tocaste el boton  (x={e.x}, y={e.y})")
            dev.draw_key(KEY_INDEX, make_key("OK!", (0, 200, 80)), refresh=True)
        elif e.type == "end":
            print(f"[{ts}]     soltaste")
            dev.draw_key(KEY_INDEX, make_key("TOCAME", (40, 40, 120)), refresh=True)

    dev.on_touch = on_touch

    dev.connect()
    dev.set_brightness(1.0)
    dev.draw_key(KEY_INDEX, make_key("TOCAME", (40, 40, 120)), refresh=True)

    print("Listo. Toca el boton azul en la pantalla. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    dev.close()
    print("\nFin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
