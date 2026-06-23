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
NUM_BUTTONS = 8  # botones redondos fisicos (0..7)
DEFAULT_BUTTON_COLOR = (120, 120, 140)  # LED si el boton tiene accion pero no color
LED_OFF = (0, 0, 0)
DIM_FACTOR = 0.22  # cuanto se atenua el LED de una grilla disponible pero no activa

# Posicion (x, y) de la celda de cada perilla en la pantalla (3 izquierda, 3 derecha).
KNOB_SLOTS = {
    "knobTL": (0, 0), "knobCL": (0, 90), "knobBL": (0, 180),
    "knobTR": (420, 0), "knobCR": (420, 90), "knobBR": (420, 180),
}


def _dim(color, factor: float = DIM_FACTOR):
    return tuple(int(c * factor) for c in color)


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
        self.brightness = layout.brightness
        self.button_brightness = 1.0  # factor 0..1 que escala el color de los LEDs 0..7

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

        # Una celda por perilla configurada (con icono/label); el resto, vacio.
        for knob_id, (x, y) in KNOB_SLOTS.items():
            knob = page.knobs.get(knob_id)
            if knob is None or (knob.icon is None and not knob.label):
                continue
            cell = self.renderer.knob_cell(
                icons.codepoint(knob.icon),
                knob.label,
                knob.color or DEFAULT_BUTTON_COLOR,
                page.background,
            )
            canvas.paste(cell, (x, y))

        keymap: Dict[int, KeyDef] = {k.index: k for k in page.keys}
        for index in range(KEYS_PER_PAGE):
            key = keymap.get(index)
            if key is None:
                continue
            col = index % KEY_COLUMNS
            row = index // KEY_COLUMNS
            # Fondo oscuro (el de la pagina) + icono/texto en el color de la tecla.
            img = self.renderer.key(
                key.label, icons.codepoint(key.icon), page.background, fg=key.color
            )
            canvas.paste(img, (60 + col * KEY_SIZE, row * KEY_SIZE))

        self.device.draw_image("full", canvas, refresh=True)
        self._refresh_button_leds()
        log.info("Pagina '%s' dibujada en %.0f ms", page.name, (time.time() - t0) * 1000)

    def _refresh_button_leds(self) -> None:
        """Enciende los LEDs de los botones: pleno si su grilla es la activa,
        tenue si tiene grilla pero no es la actual, apagado si no tiene nada."""
        page = self.page
        for i in range(NUM_BUTTONS):
            binding = page.buttons.get(i)
            if binding is None or binding.action is None:
                self.device.set_button_color(i, LED_OFF)
                continue
            base = binding.color or DEFAULT_BUTTON_COLOR
            action = binding.action
            is_active = action.type == "page" and action.params.get("name") == page.name
            color = base if is_active else _dim(base)
            # Escalamos por el factor global de intensidad de los LEDs.
            self.device.set_button_color(i, _dim(color, self.button_brightness))

    # --- ruteo de acciones --------------------------------------------------
    def _run(self, action: Optional[Action], delta: int = 0) -> None:
        if action is None:
            return
        log.info("Accion: %s %s%s", action.type, action.params, f" delta={delta}" if delta else "")
        # Accion especial manejada por el controller (rapida, sin bloquear).
        if action.type == "page":
            self._goto(action.params.get("name"))
            return
        # Brillo del LCD: lo maneja el controller (toca el device, no el SO) y
        # es no bloqueante (SET_BRIGHTNESS va con wait=False), igual que 'page'.
        if action.type == "brightness":
            self._adjust_brightness(action, delta)
            return
        if action.type == "button_brightness":
            self._adjust_button_brightness(action, delta)
            return
        # El resto va al ejecutor: el hilo lector encola y sigue libre.
        self.executor.submit(action, delta)

    def _adjust_brightness(self, action: Action, delta: int) -> None:
        """Ajusta el brillo del LCD (grilla 4x3, celdas de perilla y laterales,
        todo es UN solo panel). Cada click de perilla mueve un 'step'. El minimo
        se limita a 0.1 a proposito: en 0 el panel se apaga y el usuario no veria
        para volver a subirlo."""
        step = float(action.params.get("step", 0.1))
        amount = step * delta if delta else step
        self.brightness = max(0.1, min(1.0, self.brightness + amount))
        self.device.set_brightness(self.brightness)
        log.info("Brillo: %.0f%%", self.brightness * 100)

    def _adjust_button_brightness(self, action: Action, delta: int) -> None:
        """Ajusta la intensidad de los LEDs de los botones redondos (0..7).
        A diferencia del LCD, los LEDs no tienen brillo de hardware: se escala el
        color RGB antes de enviarlo (via _refresh_button_leds). El minimo es 0
        (apagarlos del todo es valido y no deja al usuario trabado: la perilla y
        el LCD siguen visibles)."""
        step = float(action.params.get("step", 0.1))
        amount = step * delta if delta else step
        self.button_brightness = max(0.0, min(1.0, self.button_brightness + amount))
        self._refresh_button_leds()
        log.info("Brillo botones: %.0f%%", self.button_brightness * 100)

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
            binding = self.page.buttons.get(event.id)
            if binding is not None:
                self._run(binding.action)

    def _on_rotate(self, event: RotateEvent) -> None:
        knob = self.page.knobs.get(event.id) if isinstance(event.id, str) else None
        if knob is not None:
            self._run(knob.rotate, delta=event.delta)
