"""Implementacion macOS del ActionRunner.

Cada tipo de accion se resuelve por convencion: un metodo `_do_<type>`. Asi
agregar una accion nueva es agregar un metodo, sin tocar el ruteo.

Tipos soportados:
  open    {"app": "Safari", "new": false}         -> abre una app ("new": ventana nueva)
  url     {"url": "https://..."}                  -> abre una URL en el navegador
  shell   {"command": "..."}                      -> ejecuta un comando de shell
  volume  {"step": 5}                             -> sube/baja volumen (usa delta de perilla)
  mute    {}                                      -> alterna silencio
  music   {"command": "playpause|next|previous"}  -> controla la app Music
"""

from __future__ import annotations

import logging
import subprocess

from .actions import Action, ActionRunner

log = logging.getLogger("loupdeck.macos")

# Apps single-instance donde 'open -n -a' NO crea ventana: necesitan AppleScript
# propio. Verificado en macOS via 'get id of every window' antes/despues.
_NEW_WINDOW_SCRIPTS = {
    "Terminal": 'tell application "Terminal" to do script ""',
    "Finder": 'tell application "Finder" to make new Finder window',
}


def _osascript(script: str) -> str:
    out = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        log.warning("osascript fallo: %s", out.stderr.strip())
    return out.stdout.strip()


class MacActionRunner(ActionRunner):
    def run(self, action: Action, delta: int = 0) -> None:
        handler = getattr(self, f"_do_{action.type}", None)
        if handler is None:
            log.warning("Accion desconocida: %s", action.type)
            return
        try:
            handler(action.params, delta)
        except Exception as exc:  # no queremos que una accion tumbe el proceso
            log.exception("Error ejecutando %s: %s", action.type, exc)

    # --- handlers -----------------------------------------------------------
    def _do_open(self, params: dict, delta: int) -> None:
        app = params["app"]
        if not params.get("new"):
            subprocess.Popen(["open", "-a", app])
            return
        # Ventana NUEVA en cada press. Ojo: 'open -n' NO sirve para apps
        # single-instance (verificado: con Terminal no abre nada, con Finder
        # falla con 'Launch failed'). Cada una expone su propia sintaxis
        # AppleScript para crear ventana; el resto de apps usan 'open -n -a'.
        script = _NEW_WINDOW_SCRIPTS.get(app)
        if script:
            subprocess.Popen(["osascript", "-e", script])
        else:
            subprocess.Popen(["open", "-n", "-a", app])

    def _do_url(self, params: dict, delta: int) -> None:
        subprocess.Popen(["open", params["url"]])

    def _do_shell(self, params: dict, delta: int) -> None:
        subprocess.Popen(params["command"], shell=True)

    def _do_volume(self, params: dict, delta: int) -> None:
        step = int(params.get("step", 5))
        # En perilla, delta marca direccion y cantidad de clicks; en boton, 1 paso.
        amount = step * delta if delta else step
        # Un solo osascript: lee + suma + clamp + setea. Mas rapido que dos llamadas.
        subprocess.run(
            [
                "osascript",
                "-e", f"set v to (output volume of (get volume settings)) + ({amount})",
                "-e", "if v > 100 then set v to 100",
                "-e", "if v < 0 then set v to 0",
                "-e", "set volume output volume v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def _do_mute(self, params: dict, delta: int) -> None:
        _osascript(
            "set volume output muted not (output muted of (get volume settings))"
        )

    def _do_music(self, params: dict, delta: int) -> None:
        cmd = params.get("command", "playpause")
        mapping = {
            "playpause": "playpause",
            "next": "next track",
            "previous": "previous track",
        }
        verb = mapping.get(cmd)
        if verb:
            _osascript(f'tell application "Music" to {verb}')
