#!/usr/bin/env python3
"""Prueba de humo: detecta el Loupedeck, conecta y confirma que esta VIVO.

Uso (desde la raiz del proyecto, con el venv):
    .venv/bin/python scripts/smoke.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loupdeck.device import LoupedeckDevice  # noqa: E402
from loupdeck.discovery import discover  # noqa: E402
from loupdeck.protocol import Command  # noqa: E402


def main() -> int:
    print("1) Detectando dispositivos Loupedeck/Razer...")
    devices = discover()
    if not devices:
        print("   X No se encontro ningun dispositivo. Esta conectado por USB?")
        return 1
    for d in devices:
        print(
            f"   OK {d.description} en {d.path}  "
            f"VID:PID={d.vendor_id:#06x}:{d.product_id:#06x}  serial={d.serial_number}"
        )
    info = devices[0]

    print(f"\n2) Conectando a {info.path} (handshake WebSocket sobre serie)...")
    dev = LoupedeckDevice(info.path)

    def on_event(command: int, data: bytes) -> None:
        if command == Command.BUTTON_PRESS and len(data) >= 2:
            estado = "down" if data[1] == 0x00 else "up"
            print(f"   [evento] boton {data[0]:#04x} {estado}")
        elif command == Command.KNOB_ROTATE and len(data) >= 2:
            delta = int.from_bytes(bytes([data[1]]), "big", signed=True)
            print(f"   [evento] perilla {data[0]:#04x} delta={delta}")
        else:
            print(f"   [evento] cmd={command:#04x} data={data.hex()}")

    dev.on_event = on_event

    resp = dev.connect()
    primera_linea = resp.splitlines()[0] if resp else b""
    print(f"   OK handshake. Respuesta: {primera_linea!r}")

    print("\n3) Pidiendo identidad al firmware...")
    print(f"   firmware version: {dev.get_version()}")
    print(f"   serial:           {dev.get_serial()}")

    print("\n4) Prueba VISIBLE de que arranca: parpadeo de brillo + vibracion")
    for value in (1.0, 0.15, 1.0):
        dev.set_brightness(value)
        time.sleep(0.35)
    dev.vibrate()

    print("\n5) Escuchando eventos 8s (toca botones / gira perillas / toca la pantalla)...")
    try:
        time.sleep(8)
    except KeyboardInterrupt:
        pass

    dev.close()
    print("\nListo. La base funciona: deteccion + conexion + protocolo OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
