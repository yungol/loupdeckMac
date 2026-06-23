#!/usr/bin/env python3
"""Demo de captura de eventos: el device te 'escucha'.

Imprime en consola cada boton, giro de perilla y toque de pantalla.

Uso:
    .venv/bin/python scripts/events_demo.py [segundos]
Sin argumento corre hasta Ctrl+C; con un numero, corre esos segundos.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from loupdeck.device import LoupedeckDevice  # noqa: E402
from loupdeck.discovery import discover  # noqa: E402
from loupdeck.events import ButtonEvent, RotateEvent, TouchEvent  # noqa: E402


def draw_hint(dev: LoupedeckDevice) -> None:
    dev.set_brightness(1.0)
    dev.fill_region("full", (15, 15, 20), refresh=False)
    img = Image.new("RGB", (360, 270), (15, 15, 20))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((180, 110), "Toca / gira / pulsa", font=font, anchor="mm", fill=(255, 255, 255))
    draw.text((180, 150), "(mira la consola)", font=font, anchor="mm", fill=(120, 120, 130))
    dev.draw_image("center", img, refresh=True)


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else None

    devices = discover()
    if not devices:
        print("X No se encontro el dispositivo.")
        return 1

    dev = LoupedeckDevice(devices[0].path)

    def on_button(e: ButtonEvent) -> None:
        print(f"  BOTON   {e.id!r:>8}  {'DOWN' if e.pressed else 'up'}")

    def on_rotate(e: RotateEvent) -> None:
        sign = "+" if e.delta >= 0 else ""
        print(f"  PERILLA {e.id!r:>8}  {sign}{e.delta}")

    def on_touch(e: TouchEvent) -> None:
        donde = f"tecla {e.key}" if e.key is not None else f"pantalla {e.screen}"
        print(f"  TOUCH   {e.type:>5}  ({e.x:>3},{e.y:>3})  {donde}")

    dev.on_button = on_button
    dev.on_rotate = on_rotate
    dev.on_touch = on_touch

    dev.connect()
    draw_hint(dev)
    print(f"Conectado a {devices[0].description}.")
    print("Interactua con el device. " + (f"({duration:.0f}s)" if duration else "Ctrl+C para salir."))

    try:
        if duration:
            time.sleep(duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass

    dev.close()
    print("\nFin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
