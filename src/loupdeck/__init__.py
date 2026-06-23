"""Driver Python desde cero para el Loupedeck Live / Razer Stream Controller.

El dispositivo NO es un HID normal: habla un WebSocket "mutante" encapsulado
sobre un puerto serie virtual (USB CDC). La arquitectura sigue esa realidad en
capas:

    discovery  -> encontrar el puerto serie del dispositivo (infraestructura)
    protocol   -> codificar/decodificar bytes (dominio puro, sin I/O)
    transport  -> abrir el serie + handshake + leer frames (infraestructura)
    device     -> API de alto nivel: version, brillo, vibracion, eventos
"""

from .device import LoupedeckDevice
from .discovery import DeviceInfo, discover

__all__ = ["LoupedeckDevice", "DeviceInfo", "discover"]
