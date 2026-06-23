#!/usr/bin/env python3
"""Paso minimo: detectar UNA perilla (giro + click), nada mas.

- Limpia la pantalla a negro UNA vez (de paso: probamos si el dibujo grande
  ya es rapido despues del fix del deadlock).
- Gira cualquier perilla -> imprime id y delta al instante, y muestra un
  contador en pantalla.
- Pulsa la perilla (click) -> imprime y muestra CLICK.
- Conexion abierta hasta Ctrl+C (la pantalla no se apaga).

Uso:
    .venv/bin/python scripts/one_knob.py
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from loupdeck.device import LoupedeckDevice  # noqa: E402
from loupdeck.discovery import discover  # noqa: E402
from loupdeck.events import ButtonEvent, RotateEvent  # noqa: E402

KEY_INDEX = 6


def _font(size: int):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_key(text: str, color) -> Image.Image:
    img = Image.new("RGB", (90, 90), color)
    draw = ImageDraw.Draw(img)
    draw.text((45, 45), text, font=_font(24), anchor="mm", fill=(255, 255, 255))
    return img


def now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def main() -> int:
    devices = discover()
    if not devices:
        print("X No se encontro el dispositivo.")
        return 1

    dev = LoupedeckDevice(devices[0].path)
    counter = {"value": 0}

    def on_rotate(e: RotateEvent) -> None:
        counter["value"] += e.delta
        sign = "+" if e.delta >= 0 else ""
        print(f"[{now()}] GIRO   {e.id!r:>8}  {sign}{e.delta}   total={counter['value']}")
        dev.draw_key(KEY_INDEX, make_key(str(counter["value"]), (40, 40, 120)), refresh=True)

    def on_button(e: ButtonEvent) -> None:
        # Solo nos interesan las perillas (ids string como 'knobTL').
        if not isinstance(e.id, str):
            return
        print(f"[{now()}] CLICK  {e.id!r:>8}  {'down' if e.pressed else 'up'}")
        if e.pressed:
            dev.draw_key(KEY_INDEX, make_key("CLICK", (0, 160, 80)), refresh=True)
        else:
            dev.draw_key(KEY_INDEX, make_key(str(counter["value"]), (40, 40, 120)), refresh=True)

    dev.on_rotate = on_rotate
    dev.on_button = on_button

    t0 = time.time()
    dev.connect()
    dev.set_brightness(1.0)
    dev.fill_region("full", (0, 0, 0), refresh=True)  # limpiar a negro (dibujo grande)
    dev.draw_key(KEY_INDEX, make_key("0", (40, 40, 120)), refresh=True)
    print(f"Pantalla lista en {time.time() - t0:.2f}s tras conectar.")

    print("Gira cualquier perilla y pulsala (click). Ctrl+C para salir.")
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
