from __future__ import annotations

from sim.vectors.vec2d import Vec, to_vec2
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from sim.core.sim_object import SimObject

LogicFunc = Callable[[list], Vec]  # simobjs -> Vec

@dataclass
class Logic:
    type: str = "static"
    params: Dict[str, Any] = field(default_factory=dict)


    func: LogicFunc = field(init=False)
    simobj: SimObject = field(init=False, default=None, repr=False)
    _bind: Callable[[SimObject], LogicFunc] = field(init=False, default=None, repr=False)

    def __post_init__(self):
        self._state = {
            "mode": "idle",
            "intention_vector": to_vec2(0, 0)
        }

    def sync(self, simobj: SimObject):
        self.simobj = simobj
        if self._bind:
            try:
                self.func = self._bind(simobj)
            except Exception as e:
                raise RuntimeError(
                    f"Błąd bindowania logiki {type(self).__name__}"
                ) from e

    def step(self, simobjs) -> Vec:
        if not hasattr(self, "func") or self.func is None:
            raise RuntimeError("Logic.func nie jest ustawiona. Wywołaj .sync(simobj) jeśli to logika dynamiczna.")

        v = to_vec2(self.func(simobjs))
        self._state["intention_vector"] = v
        return v

    def get_logic_state(self) -> Dict[str, Any]:

        return {
            "_format": 1,
            "mode": self._state.get("mode"),
            "intention_vector": self._state.get("intention_vector")
        }

    def drop(self):
        self.simobj = None
        self.func = None
        self._bind = None
