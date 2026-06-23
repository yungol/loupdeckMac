"""Dispositivo Loupedeck: API de alto nivel sobre el transporte.

Maneja transaction IDs (cada peticion espera su respuesta) y traduce los
mensajes crudos en algo usable: version, serial, brillo, vibracion y eventos
(botones / perillas / toques).
"""

from __future__ import annotations

import queue
import struct
import threading
from typing import Callable, Optional, Tuple

from PIL import Image

from .events import ButtonEvent, RotateEvent, TouchEvent, decode_event
from .graphics import image_to_rgb565_le
from .protocol import (
    BUTTONS,
    Command,
    DISPLAY_ID,
    DISPLAYS,
    KEY_COLUMNS,
    KEY_ROWS,
    KEY_SIZE,
    MAX_BRIGHTNESS,
    encode_message,
)
from .transport import SerialTransport

# Mapa inverso id-amigable -> byte fisico (ej. boton 0 -> 0x07, knobTL -> 0x01).
_BUTTON_ID_TO_BYTE = {name: byte for byte, name in BUTTONS.items()}

# Un evento entrante decodificado a nivel protocolo: (command, data).
Message = Tuple[int, bytes]


class LoupedeckDevice:
    def __init__(self, path: str) -> None:
        self.transport = SerialTransport(path)
        self._transaction_id = 0
        self._tx_lock = threading.Lock()
        self._pending: "dict[int, queue.Queue]" = {}
        # Callbacks tipados para eventos del usuario. Asignalos si te interesan.
        self.on_button: Optional[Callable[[ButtonEvent], None]] = None
        self.on_rotate: Optional[Callable[[RotateEvent], None]] = None
        self.on_touch: Optional[Callable[[TouchEvent], None]] = None
        # Fallback crudo para cualquier mensaje no solicitado que no sea evento conocido.
        self.on_event: Optional[Callable[[int, bytes], None]] = None
        # Toques activos, para distinguir 'start' (primer contacto) de 'move'.
        self._active_touches: "set[int]" = set()

    # --- ciclo de vida ------------------------------------------------------
    def connect(self, on_disconnect=None) -> bytes:
        return self.transport.connect(self._on_message, on_disconnect=on_disconnect)

    def close(self) -> None:
        self.transport.close()

    def is_ready(self) -> bool:
        return self.transport.is_ready()

    # --- nucleo de mensajeria ----------------------------------------------
    def _next_transaction(self) -> int:
        with self._tx_lock:
            self._transaction_id = (self._transaction_id + 1) % 256
            if self._transaction_id == 0:  # el device ignora el txId 0
                self._transaction_id = 1
            return self._transaction_id

    def _on_message(self, payload: bytes) -> None:
        if len(payload) < 3:
            return
        length = payload[0]
        command = payload[1]
        transaction_id = payload[2]
        data = payload[3:length] if 3 <= length <= len(payload) else payload[3:]

        waiter = self._pending.pop(transaction_id, None)
        if waiter is not None:
            waiter.put((command, data))
        else:
            self._dispatch_event(command, data)

    def _dispatch_event(self, command: int, data: bytes) -> None:
        event = decode_event(command, data)

        if isinstance(event, ButtonEvent):
            if self.on_button:
                self.on_button(event)
                return
        elif isinstance(event, RotateEvent):
            if self.on_rotate:
                self.on_rotate(event)
                return
        elif isinstance(event, TouchEvent):
            # Primer contacto de un touch_id => 'start'; al soltar => 'end'.
            if event.type == "move":
                if event.touch_id not in self._active_touches:
                    self._active_touches.add(event.touch_id)
                    event.type = "start"
            elif event.type == "end":
                self._active_touches.discard(event.touch_id)
            if self.on_touch:
                self.on_touch(event)
                return

        # Nada lo manejo arriba: cae al fallback crudo (acks de brillo/draw, etc.).
        if self.on_event is not None:
            self.on_event(command, data)

    def send(
        self,
        command: int,
        data: bytes = b"",
        wait: bool = True,
        timeout: float = 1.0,
    ) -> Optional[Message]:
        """Envia un comando. Si wait=True espera la respuesta del mismo txId."""
        tid = self._next_transaction()
        waiter: "Optional[queue.Queue]" = None
        if wait:
            waiter = queue.Queue(maxsize=1)
            self._pending[tid] = waiter  # registrar ANTES de enviar (evita carrera)

        self.transport.send(encode_message(command, tid, data))

        if waiter is None:
            return None
        try:
            return waiter.get(timeout=timeout)
        except queue.Empty:
            self._pending.pop(tid, None)
            return None

    # --- API de alto nivel --------------------------------------------------
    def get_version(self, timeout: float = 1.0) -> Optional[str]:
        res = self.send(Command.VERSION, timeout=timeout)
        if not res:
            return None
        _, data = res
        if len(data) >= 3:
            return f"{data[0]}.{data[1]}.{data[2]}"
        return None

    def get_serial(self, timeout: float = 1.0) -> Optional[str]:
        res = self.send(Command.SERIAL, timeout=timeout)
        if not res:
            return None
        _, data = res
        return data.decode(errors="replace").strip()

    def set_brightness(self, value: float) -> None:
        """value en [0.0, 1.0]."""
        level = max(0, min(MAX_BRIGHTNESS, round(value * MAX_BRIGHTNESS)))
        self.send(Command.SET_BRIGHTNESS, bytes([level]), wait=False)

    def vibrate(self, pattern: int = 0x01) -> None:
        self.send(Command.SET_VIBRATION, bytes([pattern]), wait=False)

    def set_button_color(self, button_id, color: "Tuple[int, int, int]") -> None:
        """Enciende el LED de un boton fisico redondo (id 0..7). (0,0,0) = apagado.

        El protocolo usa el byte fisico del boton, no el id amigable (el boton 0
        es el byte 0x07). SET_COLOR lleva [byte, r, g, b].
        """
        byte = _BUTTON_ID_TO_BYTE.get(button_id)
        if byte is None:
            return
        r, g, b = color
        self.send(Command.SET_COLOR, bytes([byte, int(r), int(g), int(b)]), wait=False)

    # --- pantalla -----------------------------------------------------------
    def refresh(self) -> None:
        """Vuelca el framebuffer a la pantalla fisica.

        wait=False: dibujar es 'disparar y olvidar'. NUNCA esperar ACK aca, porque
        estos metodos pueden llamarse desde el hilo lector (dentro de un callback
        on_touch/on_button) y esperar el ACK alli mismo lo congelaria (deadlock).
        """
        self.send(Command.DRAW, DISPLAY_ID, wait=False)

    def draw_buffer(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        rgb565: bytes,
        refresh: bool = True,
    ) -> None:
        """Escribe un rectangulo crudo (RGB565 LE) en coordenadas absolutas.

        El mensaje FRAMEBUFF lleva: id de pantalla + [x, y, w, h] (uint16 BE) +
        los pixeles. Si refresh=True, refresca la pantalla al terminar.
        """
        expected = width * height * 2
        if len(rgb565) != expected:
            raise ValueError(
                f"Buffer de {len(rgb565)} bytes; se esperaban {expected} "
                f"({width}x{height} px RGB565)"
            )
        header = struct.pack(">HHHH", x, y, width, height)
        self.send(Command.FRAMEBUFF, DISPLAY_ID + header + rgb565, wait=False)
        if refresh:
            self.refresh()

    def draw_image(self, region: str, img: Image.Image, refresh: bool = True) -> None:
        """Dibuja una imagen PIL que llena una region nombrada (left/center/right/full)."""
        area = DISPLAYS[region]
        if img.size != (area.width, area.height):
            img = img.resize((area.width, area.height))
        self.draw_buffer(
            area.x, area.y, area.width, area.height, image_to_rgb565_le(img), refresh
        )

    def fill_region(
        self, region: str, color: "Tuple[int, int, int]", refresh: bool = True
    ) -> None:
        """Pinta una region entera de un color solido."""
        area = DISPLAYS[region]
        img = Image.new("RGB", (area.width, area.height), color)
        self.draw_image(region, img, refresh)

    def draw_key(self, index: int, img: Image.Image, refresh: bool = True) -> None:
        """Dibuja una imagen 90x90 en la tecla `index` (0..11) de la grilla central."""
        if not 0 <= index < KEY_COLUMNS * KEY_ROWS:
            raise ValueError(f"Tecla {index} fuera de rango (0..{KEY_COLUMNS * KEY_ROWS - 1})")
        center = DISPLAYS["center"]
        x = center.x + (index % KEY_COLUMNS) * KEY_SIZE
        y = center.y + (index // KEY_COLUMNS) * KEY_SIZE
        if img.size != (KEY_SIZE, KEY_SIZE):
            img = img.resize((KEY_SIZE, KEY_SIZE))
        self.draw_buffer(x, y, KEY_SIZE, KEY_SIZE, image_to_rgb565_le(img), refresh)
