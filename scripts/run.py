#!/usr/bin/env python3
"""Entrypoint: carga el layout, conecta el device y corre el controller.

Uso:
    .venv/bin/python scripts/run.py [segundos]
Sin argumento corre hasta Ctrl+C; con un numero, corre esos segundos (util para
probar). El siguiente hito (daemon) envuelve esto con reconexion automatica.
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loupdeck.controller import Controller  # noqa: E402
from loupdeck.device import LoupedeckDevice  # noqa: E402
from loupdeck.discovery import discover  # noqa: E402
from loupdeck.layout import load_layout  # noqa: E402
from loupdeck.macos_actions import MacActionRunner  # noqa: E402
from loupdeck.render import Renderer  # noqa: E402

APP_DIR = Path(__file__).resolve().parent.parent
LAYOUT_PATH = APP_DIR / "config" / "layout.json"
ICON_FONT_PATH = APP_DIR / "assets" / "MaterialIcons-Regular.ttf"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else None

    layout = load_layout(LAYOUT_PATH)

    devices = discover()
    if not devices:
        print("X No se encontro el dispositivo.")
        return 1

    device = LoupedeckDevice(devices[0].path)
    renderer = Renderer(str(ICON_FONT_PATH))
    runner = MacActionRunner()
    controller = Controller(device, layout, runner, renderer)

    device.connect()
    controller.start()
    print(f"Corriendo en {devices[0].description}. " + (f"({duration:.0f}s)" if duration else "Ctrl+C para salir."))

    try:
        if duration:
            time.sleep(duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass

    controller.stop()
    device.close()
    print("\nFin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
