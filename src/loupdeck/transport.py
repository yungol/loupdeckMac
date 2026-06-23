"""Transporte: puerto serie + handshake WebSocket + lectura de frames.

Es la unica capa que toca el hardware. Por arriba expone algo simple:
conectar (con handshake), enviar un payload, y entregar cada payload entrante
a un callback. El framing WebSocket vive en protocol.py.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import serial

from .protocol import (
    WS_UPGRADE_HEADER,
    WS_UPGRADE_RESPONSE_PREFIX,
    WS_CLOSE_FRAME,
    FrameParser,
    encode_ws_frame,
)

BAUD_RATE = 256000  # El firmware espera exactamente este baudrate.


class SerialTransport:
    def __init__(self, path: str) -> None:
        self.path = path
        self._serial: Optional[serial.Serial] = None
        self._write_lock = threading.Lock()  # evita que dos hilos mezclen un frame
        self._parser = FrameParser()
        self._reader: Optional[threading.Thread] = None
        self._running = False
        self._closing = False  # True solo en un close() intencional
        self._on_message: Optional[Callable[[bytes], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None

    def is_ready(self) -> bool:
        return self._serial is not None and self._serial.is_open and self._running

    def connect(
        self,
        on_message: Callable[[bytes], None],
        on_disconnect: Optional[Callable[[], None]] = None,
        handshake_timeout: float = 2.0,
    ) -> bytes:
        """Abre el puerto, hace el handshake WebSocket y arranca el hilo lector.

        Devuelve la respuesta cruda del handshake (empieza con 'HTTP/1.1').
        """
        self._on_message = on_message
        self._on_disconnect = on_disconnect
        self._closing = False
        self._serial = serial.Serial(self.path, BAUD_RATE, timeout=0.1)
        self._serial.reset_input_buffer()

        # Handshake: el header va CRUDO (sin frame). El device responde un
        # '101 Switching Protocols' cuya primera linea empieza con 'HTTP/1.1'.
        self._serial.write(WS_UPGRADE_HEADER)
        self._serial.flush()

        deadline = time.time() + handshake_timeout
        resp = bytearray()
        while time.time() < deadline:
            resp.extend(self._serial.read(64))
            if bytes(resp).startswith(WS_UPGRADE_RESPONSE_PREFIX):
                break

        if not bytes(resp).startswith(WS_UPGRADE_RESPONSE_PREFIX):
            self.close()
            raise ConnectionError(
                f"Handshake invalido en {self.path}. Recibido: {bytes(resp)!r}"
            )

        # Tras el '101', el firmware re-emite ('echo') nuestro propio handshake
        # como frames basura. Lo drenamos y descartamos cualquier estado parcial
        # del parser para arrancar limpios.
        drain_until = time.time() + 0.2
        while time.time() < drain_until:
            self._serial.read(256)
        self._serial.reset_input_buffer()
        self._parser = FrameParser()

        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        return bytes(resp)

    def send(self, payload: bytes) -> None:
        if not self.is_ready():
            raise ConnectionError("No conectado")
        assert self._serial is not None
        with self._write_lock:
            self._serial.write(encode_ws_frame(payload))
            self._serial.flush()

    def _dispatch(self, payload: bytes) -> None:
        if self._on_message:
            self._on_message(payload)

    def _read_loop(self) -> None:
        while self._running and self._serial is not None:
            try:
                chunk = self._serial.read(256)
            except (serial.SerialException, OSError):
                break  # el device se desconecto (desenchufado o error)
            if not chunk:
                continue
            for payload in self._parser.feed(chunk):
                self._dispatch(payload)

        # Salimos del loop. Si no fue un close() intencional, avisamos la caida.
        self._running = False
        if not self._closing and self._on_disconnect is not None:
            self._on_disconnect()

    def close(self) -> None:
        self._closing = True
        self._running = False
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.write(WS_CLOSE_FRAME)
                    self._serial.flush()
            except (serial.SerialException, OSError):
                pass
            try:
                self._serial.close()
            except (serial.SerialException, OSError):
                pass
            self._serial = None
