#!/usr/bin/env python3
"""Daemon: corre el controlador 24/7 con reconexion automatica.

Mantiene la pantalla viva, y si desenchufas/reenchufas el device se reconecta
solo. Editar config/layout.json y reenchufar (o reiniciar el daemon) aplica los
cambios.

Uso:
    .venv/bin/python scripts/daemon.py
Ctrl+C para detener.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loupdeck.daemon import Supervisor  # noqa: E402

APP_DIR = Path(__file__).resolve().parent.parent
LAYOUT_PATH = APP_DIR / "config" / "layout.json"
ICON_FONT_PATH = APP_DIR / "assets" / "MaterialIcons-Regular.ttf"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    supervisor = Supervisor(LAYOUT_PATH, ICON_FONT_PATH)
    try:
        supervisor.run()
    except KeyboardInterrupt:
        supervisor.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
