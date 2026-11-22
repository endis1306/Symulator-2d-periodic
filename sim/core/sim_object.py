from __future__ import annotations
from dataclasses import field, dataclass
from typing import Tuple, TYPE_CHECKING
from sim.geometry.shape import Shape, moved_shape_to_dict
from sim.systems.engines.engines_control import EnginesControl
from sim.systems.sensors.sensors_control import SensorsControl
from sim.core.body_params import BodyParams
from sim.systems.logic.logic import Logic
from sim.systems.physics.physics import Physics
from sim.vectors.vec2dM import *
from sim.vectors.vec2d import Vec, to_vec2
from sim.utils.validation_helper import ensure_has_interface


if TYPE_CHECKING:
    from sim.geometry.box import Box

@dataclass
class SimObject:
    id: str
    shape: Shape

    positionXY: VecM = field(default_factory=lambda: to_vec2M(0, 0))
    velocityXY: VecM = field(default_factory=lambda: to_vec2M(0, 0))
    accelerationXY: VecM = field(default_factory=lambda: to_vec2M(0, 0))

    theta: float = 0 #radiany
    omega: float = 0 #radiany
    alpha: float = 0 #radiany

    bodyParams: BodyParams = field(default_factory=BodyParams)
    enginesControl: EnginesControl = field(default_factory=EnginesControl)
    sensorsControl: SensorsControl = field(default_factory=SensorsControl)
    logic: Logic = field(default_factory=Logic)

    physics: Physics = field(default_factory=Physics)

    static: bool = False

    destroyed: bool = field(init=False, default=False)
    removed: bool = field(init=False, default=False)

    _cached_pos_theta: Tuple[Vec, float] = field(init=False, default=None)
    _cached_moved: Any = field(init=False, default=None)


    def sync(self):
        self.shape.sync(self)
        self.enginesControl.sync(self)
        self.physics.sync(self)
        self.sensorsControl.sync(self)
        self.logic.sync(self)


    def __post_init__(self):
        # --- podstawowe proste typy ---
        if not isinstance(self.id, str):
            raise TypeError("ID obiektu musi być typu str.")
        if not is_vecM(self.positionXY):
            raise TypeError("Pole 'positionXY' musi być typu VecM.")
        if not is_vecM(self.velocityXY):
            raise TypeError("Pole 'velocityXY' musi być typu VecM.")
        if not is_vecM(self.accelerationXY):
            raise TypeError("Pole 'accelerationXY' musi być typu VecM.")
        if not isinstance(self.theta, (int, float)):
            raise TypeError("Pole 'theta' musi być liczbą.")
        if not isinstance(self.omega, (int, float)):
            raise TypeError("Pole 'omega' musi być liczbą.")
        if not isinstance(self.alpha, (int, float)):
            raise TypeError("Pole 'alpha' musi być liczbą.")
        if not isinstance(self.static, bool):
            raise TypeError("Pole 'static' musi być typu bool.")

        shape_spec = {
            "sync": {"callable": True},
            "moved": {"callable": True},
        }
        try:
            ensure_has_interface(self.shape, shape_spec, "shape")
        except TypeError as e:
            raise TypeError(f"Pole 'shape' jest nieprawidłowe: {e}") from e

        engine_spec = {
            "sync": {"callable": True},
            "get_thrust_and_torque": {"callable": True},
            "update": {"callable": True},
            "get_engines_data": {"callable": True},
        }
        try:
            ensure_has_interface(self.enginesControl, engine_spec, "engineControl")
        except TypeError as e:
            raise TypeError(f"Pole 'engineControl' jest nieprawidłowe: {e}") from e

        logic_spec = {
            "sync": {"callable": True},
            "step": {"callable": True},
            "type": {"type_check": lambda v: isinstance(v, str)},
            "params": {"type_check": lambda v: isinstance(v, dict)},
        }
        try:
            ensure_has_interface(self.logic, logic_spec, "logic")
        except TypeError as e:
            raise TypeError(f"Pole 'logic' jest nieprawidłowe: {e}") from e

        bodyParams_spec = {
            "drag_lin_forward": {"type_check": lambda v: isinstance(v, (int, float))},
            "drag_lin_side": {"type_check": lambda v: isinstance(v, (int, float))},
            "drag_rot": {"type_check": lambda v: isinstance(v, (int, float))},
            "I": {"type_check": lambda v: isinstance(v, (int, float))},
            "mass": {"type_check": lambda v: isinstance(v, (int, float))},
        }
        try:
            ensure_has_interface(self.bodyParams, bodyParams_spec, "bodyParams")
        except TypeError as e:
            raise TypeError(f"Pole 'bodyParams' jest nieprawidłowe: {e}") from e

        sensors_spec = {
            "sync": {"callable": True},
            "scan_all": {"callable": True},
            "get_enabled": {"callable": True},
            "get_sensors_data": {"callable": True},
        }

        try:
            ensure_has_interface(self.sensorsControl, sensors_spec, "sensorsControl")
        except TypeError as e:
            raise TypeError(f"Pole 'sensorsControl' jest nieprawidłowe: {e}") from e

        physics_spec = {
            "step": {"callable": True},
        }

        try:
            ensure_has_interface(self.physics, physics_spec, "physics")
        except TypeError as e:
            raise TypeError(f"Pole 'physics' jest nieprawidłowe: {e}") from e


        if self.static:
            self.make_static()

        if self.destroyed:
            self.destroy()


    def to_spec_dict(self) -> dict:
        shape_spec = self.local_shape
        body_params = self.bodyParams.to_dict()
        engines_spec = self.enginesControl.get_engines_spec()
        sensors_spec = self.sensorsControl.get_sensors_spec()

        return {
            "id": self.id,
            "shape": shape_spec,
            "body_params": body_params,
            "engines": engines_spec,
            "sensors": sensors_spec,
        }

    def to_state_dict(self) -> dict:
        """
        Zwraca serializowalny snapshot stanu obiektu (stan dynamiczny).
        """
        state = {
            "id": self.get_id(),  # przydatne do mapowania
            "positionXY": tuple(self.get_positionXY()),
            "velocityXY": tuple(self.get_velocityXY()),
            "theta": float(self.get_theta()),
            "omega": float(self.get_omega()),
            "static": bool(self.static),
            "destroyed": bool(self.get_destroyed()),
            "removed": bool(self.get_removed()),
            "middle_level_control": self.enginesControl.get_middle_level_control_state(),
            "high_level_control": self.logic.get_logic_state(),
            "engines": self.enginesControl.get_engines_state(),
            "sensors": self.sensorsControl.get_sensors_state(),
        }
        return state

    def get_object_data(self) -> dict:
        """
        Zwraca wszystkie dane obiektu.
        Obejmuje podstawowe dane + dane silników/wirników.
        """
        _format = 1

        object_id = self.get_id()
        type = self.__class__.__name__
        positionXY = tuple(self.get_positionXY())
        shape = moved_shape_to_dict(self)
        velocityXY = tuple(self.get_velocityXY())
        theta = float(self.get_theta())
        omega = float(self.get_omega())
        is_static = bool(self.static)
        is_destroyed =  bool(self.get_destroyed())
        is_removed = bool(self.get_removed())
        engines = self.enginesControl.get_engines_data()
        sensors = self.sensorsControl.get_sensors_data()

        data = {
            "_format": _format,
            "id": object_id,
            "type": type,
            "shape": shape,
            "positionXY": positionXY,
            "velocityXY": velocityXY,
            "theta": theta,
            "omega": omega,
            "static": is_static,
            "destroyed": is_destroyed,
            "removed": is_removed,
            "engines": engines,
            "sensors": sensors,
        }

        return data

    def get_id(self):
        return self.id

    def get_positionXY(self):
        return self.positionXY

    def get_velocityXY(self):
        return self.velocityXY

    def get_accelerationXY(self):
        return self.accelerationXY

    def get_theta(self):
        return self.theta

    def get_omega(self):
        return self.omega

    def get_alpha(self):
        return self.alpha

    def get_static(self):
        return self.static

    def get_destroyed(self):
        return self.destroyed

    def get_removed(self):
        return self.removed


    def make_static(self):
        self.velocityXY = to_vec2M()
        self.accelerationXY = to_vec2M()
        self.omega = 0.0
        self.alpha = 0.0
        self.enginesControl.clear()
        self.sensorsControl.clear()
        self.static = True

    def destroy(self):
        self.velocityXY = to_vec2M()
        self.accelerationXY = to_vec2M()
        self.omega = 0.0
        self.alpha = 0.0
        self.enginesControl.clear()
        self.sensorsControl.clear()
        self.destroyed = True

    def remove(self):
        if self.destroyed:
            self.removed = True

    @property
    def local_shape(self) -> Any:
        return self.shape.local_shape

    def to_moved_shape(self) -> Any:
        key = (to_vec2(self.positionXY), self.theta)
        if self._cached_pos_theta == key and self._cached_moved is not None:
            return self._cached_moved
        moved = self.shape.moved()
        self._cached_moved = moved
        self._cached_pos_theta = key
        return moved


    def sensors_next_state(self, simobjs: List[SimObject], border_box: Box) -> bool:
        if self.destroyed:
            return False
        self.sensorsControl.scan_all(simobjs, border_box)
        return True


    def compute_control(self, simobjs: List[SimObject]) -> Vec:
        return self.logic.step(simobjs)

    def apply_control(self, v: Vec, dt: float) -> None:
        self.enginesControl.update(v, dt)

    def update_control(self, simobjs: List[SimObject], dt: float) -> None:
        v: Vec = self.compute_control(simobjs)
        self.apply_control(v, dt)

    def logic_next_state(self, simobjs: List[SimObject], deltaT: float) -> bool:
        if self.static or self.destroyed:
            return False
        self.update_control(simobjs, deltaT)
        return True

    def physics_next_state(self, deltaT: float) -> bool:
        if self.static or self.destroyed:
            return not self.destroyed
        self.physics.step(deltaT)
        return True

    def on_collision(self, other):
        self.destroy()

    def on_removed(self):
        self.remove()
