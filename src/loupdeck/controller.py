"""Controller: el pegamento entre device, layout y runner.

Responsabilidades:
  - Dibujar la pagina actual en la pantalla.
  - Rutear cada evento del device (touch / boton / perilla) a su accion.
  - Manejar el cambio de pagina (accion especial type='page').

No sabe COMO se ejecuta una accion (eso es del runner) ni COMO se dibuja una
tecla (eso es del renderer). Solo coordina.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from PIL import Image

from . import icons
from .actions import Action, ActionExecutor, ActionRunner
from .device import LoupedeckDevice
from .events import ButtonEvent, RotateEvent, TouchEvent
from .layout import KeyDef, Layout
from .protocol import KEY_COLUMNS, KEY_ROWS, KEY_SIZE
from .render import Renderer

log = logging.getLogger("loupdeck.controller")

KEYS_PER_PAGE = KEY_COLUMNS * KEY_ROWS


class Controller:
    def __init__(
        self,
        device: LoupedeckDevice,
        layout: Layout,
        runner: ActionRunner,
        renderer: Renderer,
    ) -> None:
        self.device = device
        self.layout = layout
        self.runner = runner
        self.renderer = renderer
        self.executor = ActionExecutor(runner)
        self.page_index = 0

    def stop(self) -> None:
        self.executor.stop()

    @property
    def page(self):
        return self.layout.pages[self.page_index]

    def start(self) -> None:
        self.device.on_touch = self._on_touch
        self.device.on_button = self._on_button
        self.device.on_rotate = self._on_rotate
        self.device.set_brightness(self.layout.brightness)
        self.render()

    # --- dibujo -------------------------------------------------------------
    def render(self) -> None:
        t0 = time.time()
        page = self.page

        # Componemos la pantalla ENTERA (480x270) en memoria y la enviamos en UN
        # solo dibujo. El cambio queda atomico: sin parpadeo y mas eficiente que
        # 15 dibujos sueltos (el firmware muestra cada uno apenas llega).
        canvas = Image.new("RGB", (480, 270), page.background)

        if page.left:
            canvas.paste(self.renderer.side(page.left.text, page.left.color), (0, 0))
        if page.right:
            canvas.paste(self.renderer.side(page.right.text, page.right.color), (420, 0))

        keymap: Dict[int, KeyDef] = {k.index: k for k in page.keys}
        for index in range(KEYS_PER_PAGE):
            key = keymap.get(index)
            if key is None:
                continue
            col = index % KEY_COLUMNS
            row = index // KEY_COLUMNS
            img = self.renderer.key(key.label, icons.codepoint(key.icon), key.color)
            canvas.paste(img, (60 + col * KEY_SIZE, row * KEY_SIZE))

        self.device.draw_image("full", canvas, refresh=True)
        log.info("Pagina '%s' dibujada en %.0f ms", page.name, (time.time() - t0) * 1000)

    # --- ruteo de acciones --------------------------------------------------
    def _run(self, action: Optional[Action], delta: int = 0) -> None:
        if action is None:
            return
        log.info("Accion: %s %s%s", action.type, action.params, f" delta={delta}" if delta else "")
        # Accion especial manejada por el controller (rapida, sin bloquear).
        if action.type == "page":
            self._goto(action.params.get("name"))
            return
        # El resto va al ejecutor: el hilo lector encola y sigue libre.
        self.executor.submit(action, delta)

    def _goto(self, name: Optional[str]) -> None:
        if name is None:
            return
        for i, page in enumerate(self.layout.pages):
            if page.name == name:
                self.page_index = i
                self.render()
                return
        log.warning("Pagina inexistente: %s", name)

    # --- eventos ------------------------------------------------------------
    def _on_touch(self, event: TouchEvent) -> None:
        # Solo actuamos al primer contacto sobre una tecla de la grilla central.
        if event.type != "start" or event.key is None:
            return
        key = next((k for k in self.page.keys if k.index == event.key), None)
        if key is not None:
            self._run(key.action)

    def _on_button(self, event: ButtonEvent) -> None:
        if not event.pressed:  # solo al presionar (down)
            return
        # Click de perilla: llega como boton con id de perilla (knobTL, etc.).
        knob = self.page.knobs.get(event.id) if isinstance(event.id, str) else None
        if knob is not None:
            self._run(knob.press)
            return
        # Boton redondo (0..7): accion definida en la pagina.
        if isinstance(event.id, int):
            self._run(self.page.buttons.get(event.id))

    def _on_rotate(self, event: RotateEvent) -> None:
        knob = self.page.knobs.get(event.id) if isinstance(event.id, str) else None
        if knob is not None:
            self._run(knob.rotate, delta=event.delta)
