"""Acciones: el 'que hace' como DATO + la interfaz que las ejecuta.

Una Action es solo datos (type + parametros), tal como viene del layout.json.
Quien la ejecuta es un ActionRunner, abstracto a proposito: hoy macOS, manana
otro SO, sin tocar el layout ni el controller.
"""

from __future__ import annotations

import logging
import queue
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

log = logging.getLogger("loupdeck.actions")


@dataclass
class Action:
    type: str
    params: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_json(obj: Optional[dict]) -> "Optional[Action]":
        if not obj:
            return None
        if "type" not in obj:
            raise ValueError(f"Accion sin 'type': {obj}")
        params = {k: v for k, v in obj.items() if k != "type"}
        return Action(type=obj["type"], params=params)


class ActionRunner(ABC):
    """Ejecuta acciones. `delta` lo usan las acciones relativas (giro de perilla)."""

    @abstractmethod
    def run(self, action: Action, delta: int = 0) -> None:  # pragma: no cover
        ...


class NullRunner(ActionRunner):
    """Runner de prueba: no toca el sistema, solo registra que llegaria a ejecutar."""

    def __init__(self) -> None:
        self.log: "list[tuple[str, dict, int]]" = []

    def run(self, action: Action, delta: int = 0) -> None:
        self.log.append((action.type, action.params, delta))
        print(f"[noop] {action.type} {action.params} delta={delta}")


class ActionExecutor:
    """Ejecuta acciones en su PROPIO hilo, para no bloquear el hilo lector.

    Quien recibe un evento solo encola (submit, no bloqueante). Un hilo aparte
    consume la cola y ejecuta. Ademas hace 'coalescing' del volumen: si se
    acumularon varios giros, los combina en uno solo (suma los deltas), asi un
    giro rapido no dispara N llamadas lentas a osascript.
    """

    def __init__(self, runner: ActionRunner) -> None:
        self._runner = runner
        self._queue: "queue.Queue[tuple[Action, int]]" = queue.Queue()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def submit(self, action: Action, delta: int = 0) -> None:
        self._queue.put((action, delta))

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            try:
                action, delta = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if action.type == "volume" and delta:
                    delta = self._coalesce_volume(action, delta)
                self._runner.run(action, delta)
            except Exception:  # una accion no debe tumbar el hilo
                log.exception("Accion fallo: %s", action.type)

    def _coalesce_volume(self, action: Action, delta: int) -> int:
        """Suma los giros de volumen consecutivos ya encolados en un solo delta."""
        total = delta
        while True:
            try:
                next_action, next_delta = self._queue.get_nowait()
            except queue.Empty:
                break
            if next_action.type == "volume" and next_action.params == action.params and next_delta:
                total += next_delta
            else:
                # No era volumen combinable: lo devolvemos a la cola para procesarlo luego.
                self._queue.put((next_action, next_delta))
                break
        return total
