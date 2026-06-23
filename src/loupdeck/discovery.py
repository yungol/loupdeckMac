"""Deteccion del dispositivo (infraestructura).

Escanea los puertos serie del sistema y se queda con los que pertenecen a un
fabricante Loupedeck/Razer. Devuelve datos planos; no abre ninguna conexion.
"""

from __future__ import annotations

from dataclasses import dataclass

from serial.tools import list_ports

from .protocol import MANUFACTURERS, VENDOR_IDS


@dataclass(frozen=True)
class DeviceInfo:
    path: str
    vendor_id: int
    product_id: int
    serial_number: "str | None"
    manufacturer: "str | None"
    description: str


def discover() -> "list[DeviceInfo]":
    """Devuelve todos los puertos que parecen un Loupedeck/Razer conectado."""
    found: "list[DeviceInfo]" = []
    for port in list_ports.comports():
        by_vendor = port.vid in VENDOR_IDS
        by_manufacturer = bool(port.manufacturer) and port.manufacturer in MANUFACTURERS
        if not (by_vendor or by_manufacturer):
            continue
        found.append(
            DeviceInfo(
                path=port.device,
                vendor_id=port.vid or 0,
                product_id=port.pid or 0,
                serial_number=port.serial_number,
                manufacturer=port.manufacturer,
                description=port.description or "",
            )
        )
    return found
