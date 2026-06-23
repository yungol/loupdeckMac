"""Supervisor: mantiene el controlador vivo y reconecta solo.

Bucle: buscar device -> conectar -> correr controller -> esperar. Si el device
se desconecta (desenchufado/error) o no aparece, espera y reintenta. Pensado
para correr de fondo (ver scripts/daemon.py) o bajo launchd.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from .controller import Controller
from .device import LoupedeckDevice
from .discovery import discover
from .layout import load_layout
from .macos_actions import MacActionRunner
from .render import Renderer

log = logging.getLogger("loupdeck.daemon")


class Supervisor:
    def __init__(
        self,
        layout_path: "str | Path",
        icon_font_path: "str | Path",
        reconnect_interval: float = 3.0,
    ) -> None:
        self.layout_path = str(layout_path)
        self.icon_font_path = str(icon_font_path)
        self.reconnect_interval = reconnect_interval
        self._stop = threading.Event()
        # Renderer y runner se reusan entre reconexiones (no dependen del device).
        self._renderer = Renderer(self.icon_font_path)
        self._runner = MacActionRunner()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        log.info("Supervisor iniciado. Ctrl+C para detener.")
        while not self._stop.is_set():
            if not self._run_once():
                self._wait(self.reconnect_interval)
        log.info("Supervisor detenido.")

    def _run_once(self) -> bool:
        """Una sesion completa de conexion. Devuelve False si no pudo conectar."""
        devices = discover()
        if not devices:
            log.info("Sin device. Reintento en %.0fs...", self.reconnect_interval)
            return False

        info = devices[0]
        device = LoupedeckDevice(info.path)
        # Recargamos el layout en cada conexion: editar layout.json y reenchufar
        # (o reiniciar) aplica los cambios sin tocar codigo.
        layout = load_layout(self.layout_path)
        controller = Controller(device, layout, self._runner, self._renderer)

        disconnected = threading.Event()
        try:
            device.connect(on_disconnect=disconnected.set)
            controller.start()
            log.info("Conectado a %s (%s)", info.description, info.path)
        except Exception as exc:
            log.warning("No se pudo conectar: %s", exc)
            controller.stop()
            device.close()
            return False

        # Esperamos hasta desconexion o pedido de stop.
        while not self._stop.is_set() and not disconnected.is_set():
            disconnected.wait(0.5)

        if disconnected.is_set():
            log.info("Device desconectado. Reconectando...")

        controller.stop()
        device.close()
        return True

    def _wait(self, seconds: float) -> None:
        # Espera interrumpible por stop().
        self._stop.wait(seconds)
