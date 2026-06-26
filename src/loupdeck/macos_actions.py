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
  zoom        {"step": 1}                         -> zoom de pantalla del sistema (usa delta)
   zoom_reset  {}                              -> vuelve el zoom de pantalla al 100% (toggle Cmd+Shift+8 x2)
  obs     {"command": "start_record|stop_record|toggle_record|set_scene", "scene": "..."}
                                                 -> controla OBS via WebSocket (no usa atajos de teclado)
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

# Zoom con Cmd (sin Shift ni Option). El usuario tiene estos atajos:
#   Cmd+= acerca, Cmd+- aleja, Cmd+0 resetea a 100%.
_ZOOM_IN_KEY = 24     # tecla "=" -> Cmd+= acerca
_ZOOM_OUT_KEY = 27    # tecla "-" -> Cmd+- aleja
_ZOOM_RESET_KEY = 82  # tecla "0" del teclado numerico -> Cmd+0 resetea a 100%


def _zoom_keys(key_code: int, times: int) -> str:
    """AppleScript que repite N veces el atajo de zoom (Cmd+<tecla>)."""
    return (
        'tell application "System Events"\n'
        f"  repeat {times} times\n"
        f"    key code {key_code} using {{command down}}\n"
        "  end repeat\n"
        "end tell"
    )


def _osascript(script: str) -> str:
    out = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        log.warning("osascript fallo: %s", out.stderr.strip())
    return out.stdout.strip()


class MacActionRunner(ActionRunner):
    _obs = None  # cliente WebSocket OBS perezoso; se reconecta si OBS reinicia

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

    def _do_zoom(self, params: dict, delta: int) -> None:
        # Sin delta no hay direccion (p.ej. si se atara a un boton): no hacemos nada.
        if not delta:
            return
        step = int(params.get("step", 1))
        key = _ZOOM_IN_KEY if delta > 0 else _ZOOM_OUT_KEY
        # |delta| clicks * step pulsaciones por click. Un solo osascript con el
        # repeat adentro: una llamada aunque el giro sea de varios clicks.
        _osascript(_zoom_keys(key, abs(delta) * step))

    def _do_zoom_reset(self, params: dict, delta: int) -> None:
        # Cmd+0 resetea el zoom a 100%.
        _osascript(_zoom_keys(_ZOOM_RESET_KEY, 1))

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

    # --- OBS via WebSocket --------------------------------------------------
    # En macOS los atajos de teclado de OBS solo se capturan si OBS tiene el
    # foco o permiso de Accesibilidad; el WebSocket (incorporado en OBS 28+) no
    # depende de eso y nunca colisiona con otros atajos del sistema.
    def _obs_client(self):
        if self._obs is not None:
            return self._obs
        import obsws_python as obsws

        self._obs = obsws.ReqClient(host="localhost", port=4455, timeout=5)
        return self._obs

    def _do_obs(self, params: dict, delta: int) -> None:
        cmd = params.get("command", "")
        # Dos intentos: si la conexion murio (OBS reiniciado), se reconecta.
        for attempt in (1, 2):
            try:
                cl = self._obs_client()
                if cmd == "start_record":
                    if not cl.get_record_status().output_active:
                        cl.start_record()
                elif cmd == "stop_record":
                    if cl.get_record_status().output_active:
                        cl.stop_record()
                elif cmd == "toggle_record":
                    cl.toggle_record()
                elif cmd == "set_scene":
                    cl.set_current_program_scene(params["scene"])
                else:
                    log.warning("Comando obs desconocido: %s", cmd)
                return
            except Exception as exc:
                log.warning("OBS '%s' fallo (intento %d): %s", cmd, attempt, exc)
                self._obs = None  # fuerza reconexion en el proximo intento
