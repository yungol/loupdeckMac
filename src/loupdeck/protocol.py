"""Protocolo Loupedeck: dominio puro, SIN entrada/salida.

Tres niveles de encapsulamiento (de afuera hacia adentro):

    1. Serie (USB CDC) ........ bytes crudos por el puerto
    2. Frame WebSocket ........ [0x82, len, <payload>]   (mutante, no RFC 6455)
    3. Mensaje Loupedeck ...... [length, command, txId, <data>]

Este modulo solo sabe codificar/decodificar bytes de los niveles 2 y 3.
No abre puertos ni toca hardware: eso vive en transport.py.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Handshake (se envia CRUDO, sin frame WebSocket) ------------------------
# OJO: el firmware es permisivo y espera estos bytes EXACTOS, con saltos de
# linea '\n' (no '\r\n') y la linea de request partida en dos. Replicamos tal
# cual lo hace la implementacion de referencia (foxxyz/loupedeck).
WS_UPGRADE_HEADER = (
    b"GET /index.html\n"
    b"HTTP/1.1\n"
    b"Connection: Upgrade\n"
    b"Upgrade: websocket\n"
    b"Sec-WebSocket-Key: 123abc\n"
    b"\n"
)
WS_UPGRADE_RESPONSE_PREFIX = b"HTTP/1.1"
WS_CLOSE_FRAME = bytes([0x88, 0x80, 0x00, 0x00, 0x00, 0x00])

WS_MAGIC_BYTE = 0x82  # FIN + opcode binario (0x2)

# --- Identificacion del hardware --------------------------------------------
VENDOR_IDS = (0x2EC2, 0x1532)        # Loupedeck, Razer
MANUFACTURERS = ("Loupedeck", "Razer")

MAX_BRIGHTNESS = 10

# --- Pantalla ---------------------------------------------------------------
# El Loupedeck Live / Razer Stream Controller tiene UNA sola pantalla tactil de
# 480x270. Las "tres pantallas" (izq / centro / der) son la misma, direccionadas
# con offset de X. El id de pantalla es 0x00 0x4D ('M').
DISPLAY_ID = b"\x00M"

# Grilla de teclas (solo en la zona central): 4 columnas x 3 filas, 90x90 px.
KEY_SIZE = 90
KEY_COLUMNS = 4
KEY_ROWS = 3


@dataclass(frozen=True)
class Region:
    """Una zona rectangular de la pantalla, en coordenadas ABSOLUTAS (480x270)."""

    x: int
    y: int
    width: int
    height: int


DISPLAYS = {
    "left": Region(0, 0, 60, 270),
    "center": Region(60, 0, 360, 270),
    "right": Region(420, 0, 60, 270),
    "full": Region(0, 0, 480, 270),
}


# Mapa: byte de id fisico -> nombre amigable. Las perillas son strings; los
# botones redondos del Loupedeck Live son enteros 0..7. Los nombres extra
# (home, undo, a..e) son del Loupedeck CT y no aplican a este device, pero no
# molesta tenerlos.
BUTTONS = {
    0x00: "knobCT", 0x01: "knobTL", 0x02: "knobCL", 0x03: "knobBL",
    0x04: "knobTR", 0x05: "knobCR", 0x06: "knobBR",
    0x07: 0, 0x08: 1, 0x09: 2, 0x0A: 3, 0x0B: 4, 0x0C: 5, 0x0D: 6, 0x0E: 7,
    0x0F: "home", 0x10: "undo", 0x11: "keyboard", 0x12: "enter", 0x13: "save",
    0x14: "fnL", 0x15: "a", 0x16: "c", 0x17: "fnR", 0x18: "b", 0x19: "d", 0x1A: "e",
}


class Command:
    """Opcodes del protocolo Loupedeck (byte 1 del mensaje)."""

    BUTTON_PRESS = 0x00
    KNOB_ROTATE = 0x01
    SET_COLOR = 0x02
    SERIAL = 0x03
    RESET = 0x06
    VERSION = 0x07
    SET_BRIGHTNESS = 0x09
    MCU = 0x0D
    DRAW = 0x0F
    FRAMEBUFF = 0x10
    SET_VIBRATION = 0x1B
    TOUCH = 0x4D
    TOUCH_CT = 0x52
    TOUCH_END = 0x6D
    TOUCH_END_CT = 0x72


def encode_ws_frame(payload: bytes) -> bytes:
    """Envuelve un payload en un frame WebSocket 'mutante' (cliente -> device).

    Replica EXACTAMENTE el firmware (no es RFC 6455 valido): activa el bit de
    mascara (0x80) pero deja la clave de mascara en cero y NO aplica XOR. Por
    eso una libreria WebSocket estandar no sirve y lo armamos a mano.
    """
    n = len(payload)
    if n > 0xFF:
        # Mensaje grande: header de 14 bytes, longitud de 64 bits.
        header = bytearray(14)
        header[0] = WS_MAGIC_BYTE
        header[1] = 0xFF  # 0x80 (mascara) | 0x7F (indicador de longitud 64-bit)
        header[6:10] = n.to_bytes(4, "big")  # 32 bits bajos; los altos quedan en 0
    else:
        # Mensaje chico: header de 6 bytes (los 4 ultimos = clave de mascara en 0).
        header = bytearray(6)
        header[0] = WS_MAGIC_BYTE
        header[1] = 0x80 + n
    return bytes(header) + payload


def encode_message(command: int, transaction_id: int, data: bytes = b"") -> bytes:
    """Arma un mensaje Loupedeck: [length, command, transactionId, data...].

    `length` es la longitud total del mensaje (cabecera incluida), tope 0xFF.
    """
    length = min(3 + len(data), 0xFF)
    return bytes([length, command, transaction_id]) + data


class FrameParser:
    """Reensambla frames WebSocket entrantes (device -> cliente).

    El device envia: [0x82, length, <payload de 'length' bytes>]. A diferencia
    del envio, aca la longitud viene 'limpia' (sin bit de mascara).

    Es incremental: se le pasan chunks de bytes con feed() y devuelve la lista
    de payloads completos que pudo extraer. Lo que queda a medias se guarda para
    el proximo chunk.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        self._buf.extend(chunk)
        out: list[bytes] = []
        while True:
            # Descarto basura hasta alinear con el magic byte.
            magic = self._buf.find(WS_MAGIC_BYTE)
            if magic == -1:
                self._buf.clear()
                break
            if magic > 0:
                del self._buf[:magic]
            if len(self._buf) < 2:
                break  # falta el byte de longitud
            length = self._buf[1] & 0x7F
            end = 2 + length
            if len(self._buf) < end:
                break  # frame incompleto: espero mas bytes
            out.append(bytes(self._buf[2:end]))
            del self._buf[:end]
        return out
