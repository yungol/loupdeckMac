"""Conversion de imagenes a buffers que entiende la pantalla (dominio puro).

La pantalla espera color en formato RGB565 little-endian: cada pixel son 2 bytes
donde se empaquetan 5 bits de rojo, 6 de verde y 5 de azul. Convertir pixel a
pixel en Python puro seria lento (130k pixeles en pantalla completa), asi que se
hace vectorizado con numpy.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def image_to_rgb565_le(img: Image.Image) -> bytes:
    """Convierte una imagen PIL a bytes RGB565 little-endian.

    RGB888 -> RGB565: se descartan los bits menos significativos de cada canal
    (rojo y azul a 5 bits, verde a 6) y se empaquetan en un entero de 16 bits.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    arr = np.asarray(img, dtype=np.uint16)  # forma (alto, ancho, 3)
    r = (arr[:, :, 0] >> 3) & 0x1F
    g = (arr[:, :, 1] >> 2) & 0x3F
    b = (arr[:, :, 2] >> 3) & 0x1F
    rgb565 = (r << 11) | (g << 5) | b

    # astype('<u2') fuerza little-endian (byte bajo primero), como espera el device.
    return rgb565.astype("<u2").tobytes()
