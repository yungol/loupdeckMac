# loupdeckMac

Driver en **Python desde cero** para controlar un **Loupedeck Live / Razer Stream Controller** en **macOS**, sin el software oficial. Pensado para revivir un equipo que perdió soporte: lo detecta por USB, dibuja en su pantalla, escucha botones/perillas/touch y dispara acciones del Mac (abrir apps, volumen, etc.) — todo configurable por un `layout.json` y corriendo 24/7 como servicio.

> Probado contra un **Razer Stream Controller** (`VID 0x1532 / PID 0x0D06`, firmware `0.2.14`) en macOS. El Razer es un Loupedeck Live rebrandeado: mismo protocolo.

## Inicio rápido

```bash
# 1. Entorno
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Probar que el device responde (detecta + conecta + brillo + vibración)
.venv/bin/python scripts/smoke.py

# 3. Correr el controlador (usa config/layout.json)
.venv/bin/python scripts/run.py

# 4. Instalar como servicio (arranca solo al iniciar sesión, reconecta solo)
deploy/install.sh
```

Para detener el servicio: `deploy/uninstall.sh`. Si algo falla, mirá `logs/daemon.err`.

## Qué funciona

| Capacidad | Detalle |
|-----------|---------|
| Detección | Encuentra el puerto serie por VID/PID, sin hardcodear |
| Pantalla | Dibujo RGB565 con iconos Material Icons, sin parpadeo |
| Entrada | Botones, perillas (giro con signo + click) y touch → tecla |
| Acciones | Abrir app, URL, shell, volumen, mute, control de Music |
| Páginas | Múltiples grillas conmutables desde los botones físicos |
| Persistencia | Daemon con reconexión automática + arranque vía `launchd` |

## Arquitectura

Por capas, de afuera (hardware) hacia adentro (aplicación). El **dominio puro** (sin I/O) está separado de la **infraestructura**, por eso cada capa se probó y evolucionó sin reescrituras.

```
USB serie (256000) → WebSocket "mutante" → Mensaje Loupedeck → Eventos/Dibujo → Layout JSON → Daemon
```

| Módulo (`src/loupdeck/`) | Responsabilidad |
|--------------------------|-----------------|
| `discovery.py` | Encontrar el puerto del device |
| `protocol.py` | Frames WebSocket + mensajes + regiones + botones (dominio puro) |
| `transport.py` | Serie + handshake + hilo lector + detección de desconexión |
| `graphics.py` | Conversión a RGB565 (numpy) |
| `events.py` | Decodificar botones/perillas/touch |
| `device.py` | API de alto nivel (dibujo, brillo, vibración, callbacks) |
| `render.py` · `icons.py` | Render de teclas con Material Icons |
| `actions.py` | `Action` (dato) + `ActionRunner` (interfaz) + `ActionExecutor` (hilo) |
| `macos_actions.py` | Implementación macOS de las acciones |
| `layout.py` | Carga/valida `layout.json` |
| `controller.py` | Une device + layout + runner; rutea eventos → acciones |
| `daemon.py` | Supervisor con reconexión |

## El protocolo (notas de reverse-engineering)

Lo no obvio, que es justo lo que hace fallar a la mayoría:

- **No es HID.** Es un **puerto serie virtual** (USB CDC). En macOS aparece como `/dev/cu.usbmodem*`.
- **WebSocket "mutante" sobre serie**, a **baud 256000**. El handshake va crudo con saltos `\n` (no `\r\n`) y la línea de request partida:
  ```
  GET /index.html\nHTTP/1.1\nConnection: Upgrade\nUpgrade: websocket\nSec-WebSocket-Key: 123abc\n\n
  ```
  El device responde `HTTP/1.1 101 Switching Protocols`.
- **Frames asimétricos** (no es RFC 6455 válido): el cliente activa el bit de máscara pero con clave en cero y sin XOR → **una librería WebSocket estándar no sirve**. Por eso se arman a mano.
- **Mensaje Loupedeck** dentro del frame: `[length, command, transactionId, data]`.
- **Gotcha de arranque:** tras el `101`, el firmware re-emite ("echo") el handshake como frames basura → hay que drenar la entrada ~200 ms.
- **La pantalla se apaga** al cerrar la conexión (timeout ~3 s) → requiere un proceso persistente.

Referencias que ayudaron: [`foxxyz/loupedeck`](https://github.com/foxxyz/loupedeck) (Node) y [`devleaks/python-loupedeck-live`](https://github.com/devleaks/python-loupedeck-live).

## Configurar tu setup

Editá **`config/layout.json`** — es solo datos, no toca código. Tras editar, reenchufá el device o reiniciá el daemon.

```jsonc
{
  "brightness": 1.0,
  "pages": [
    {
      "name": "apps",
      "buttons": { "1": { "type": "page", "name": "media" } },
      "knobs": {
        "knobTL": { "rotate": { "type": "volume", "step": 5 },
                    "press":  { "type": "mute" } }
      },
      "keys": [
        { "index": 0, "label": "Finder", "icon": "folder",
          "color": "#0078d7", "action": { "type": "open", "app": "Finder" } }
      ]
    }
  ]
}
```

Tipos de acción disponibles:

| `type` | Parámetros | Hace |
|--------|------------|------|
| `open` | `app` | Abre una aplicación |
| `url` | `url` | Abre una URL |
| `shell` | `command` | Ejecuta un comando |
| `volume` | `step` | Sube/baja volumen (la perilla usa el delta) |
| `mute` | — | Alterna silencio |
| `music` | `command`: `playpause`/`next`/`previous` | Controla Music |
| `page` | `name` | Cambia de página |

Iconos: nombres de Material Icons (ver `src/loupdeck/icons.py`). IDs de perilla: `knobTL`, `knobCL`, `knobBL`, `knobTR`, `knobCR`, `knobBR`. Botones físicos: `0`–`7`.

## Lección de diseño: el hilo lector es sagrado

Los tres bugs de rendimiento que surgieron eran el **mismo error**: hacer trabajo lento o bloqueante dentro del hilo que lee los eventos del device.

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Lag y eventos atrasados | Esperar el ACK de un dibujo desde un callback (deadlock contra el propio hilo lector) | Dibujar es "disparar y olvidar" (`wait=False`) |
| Parpadeo al cambiar de página | 15 dibujos sueltos; el firmware muestra cada uno al llegar | Componer la pantalla entera y enviar **un** solo dibujo |
| Volumen lentísimo | `osascript` bloqueante en el hilo lector, uno por click | Hilo ejecutor aparte + *coalescing* de giros |

**Regla:** los callbacks `on_button`/`on_rotate`/`on_touch` corren en el hilo lector; solo deben encolar u operaciones rápidas. Todo lo lento va a otro hilo.

## Scripts

| Script | Para qué |
|--------|----------|
| `smoke.py` | Detectar + conectar + identidad + brillo/vibración |
| `draw_demo.py` | Pintar la pantalla con iconos |
| `events_demo.py` | Ver botones/perillas/touch en consola |
| `one_button.py` · `one_knob.py` | Pruebas mínimas aisladas |
| `run.py` | Controlador completo (foreground) |
| `daemon.py` | Controlador con reconexión (servicio) |

## Requisitos

- macOS · Python 3.9+
- `pyserial`, `pillow`, `numpy` (ver `requirements.txt`)
- La primera vez, macOS puede pedir permiso de **Automatización** (para volumen/Music): aceptarlo.

## Licencia

Uso personal. El protocolo Loupedeck es propiedad de sus respectivos dueños; este proyecto es interoperabilidad por reverse-engineering para hardware sin soporte.
