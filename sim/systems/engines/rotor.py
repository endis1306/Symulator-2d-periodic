# rotor.py
import math
from dataclasses import dataclass, field
from typing import Optional, Callable

from sim.vectors.vec2d import Vec, to_vec2, is_vec
from sim.vectors.vec2dM import VecM


@dataclass
class Rotor:
    """
    Model pojedynczego wirnika (pełny element fizyczny).
    """
    id: str

    rotor_omega_max: float
    tau_motor: float
    k_thrust: float
    angle_offset: float              # [rad] względem osi kadłuba
    position_local: Vec

    # --- sync z obiektem ---
    get_object_positionXY: Optional[Callable[[], VecM]] = field(
        init=False, default=None, repr=False
    )
    get_object_theta: Optional[Callable[[], float]] = field(
        init=False, default=None, repr=False
    )

    # --- stan ---
    rotor_omega: float = field(default=0.0, init=False)

    # ----------------------------
    # Walidacja
    # ----------------------------
    def __post_init__(self):
        if not isinstance(self.id, str):
            raise TypeError("Rotor.id musi być typu str")

        if not is_vec(self.position_local):
            raise ValueError("rotor.position_local musi być typu Vec")
        if self.rotor_omega_max < 0:
            raise ValueError("rotor_omega_max >= 0")
        if self.tau_motor < 0:
            raise ValueError("tau_motor >= 0")
        if self.k_thrust < 0:
            raise ValueError("k_thrust >= 0")
        if not (-math.pi <= self.angle_offset <= math.pi):
            raise ValueError("angle_offset ∈ [-π, π]")
    # ----------------------------
    # Synchronizacja
    # ----------------------------
    def sync(self, simobj):

        if not callable(getattr(simobj, "get_positionXY", None)):
            raise AttributeError("SimObject musi mieć metodę get_positionXY")

        if not callable(getattr(simobj, "get_theta", None)):
            raise AttributeError("SimObject musi mieć metodę get_theta")

        self.get_object_positionXY = simobj.get_positionXY
        self.get_object_theta = simobj.get_theta


    def clear(self):
        self.rotor_omega = 0.0

    def drop(self):
        self.get_object_positionXY = None
        self.get_object_theta = None


    # ----------------------------
    # Dynamika silnika
    # ----------------------------


    def update(self, omega_cmd: float, dt: float):
        omega_cmd = max(0.0, min(self.rotor_omega_max, omega_cmd))

        if self.tau_motor > 0:
            k = math.exp(-dt / self.tau_motor)
            self.rotor_omega = omega_cmd + (self.rotor_omega - omega_cmd) * k
        else:
            self.rotor_omega = omega_cmd

    # ----------------------------
    # Fizyka
    # ----------------------------
    @property
    def omega2(self) -> float:
        return self.rotor_omega ** 2

    @property
    def max_thrust(self) -> float:
        return self.k_thrust * (self.rotor_omega_max ** 2)

    def thrust(self) -> float:
        return self.k_thrust * self.omega2

    @property
    def local_position(self) -> Vec:
        return self.position_local

    def get_global_position(self) -> Vec:
        if self.get_object_positionXY is None or self.get_object_theta is None:
            raise RuntimeError("Rotor nie jest zsynchronizowany")

        obj_pos = self.get_object_positionXY()
        theta = self.get_object_theta()

        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        return to_vec2(
      obj_pos[0] + cos_t * self.position_local[0] - sin_t * self.position_local[1],
            obj_pos[1] + sin_t * self.position_local[0] + cos_t * self.position_local[1],
        )
    @property
    def local_angle(self) -> float:
        return self.angle_offset

    def get_global_angle(self) -> float:
        if self.get_object_theta is None:
            raise RuntimeError("Rotor nie jest zsynchronizowany")
        return self.get_object_theta() + self.angle_offset

    @property
    def thrust_direction_local(self) -> Vec:
        ang = self.local_angle
        return to_vec2(math.cos(ang), math.sin(ang))


    def get_thrust_direction(self) -> Vec:
        ang = self.get_global_angle()
        return to_vec2(math.cos(ang), math.sin(ang))


    def get_force_vector(self) -> Vec:
        d = self.get_thrust_direction()
        T = self.thrust()
        return to_vec2(d[0] * T, d[1] * T)

    def get_torque(self) -> float:
        """
        Moment geometryczny od thrustu (r × F).
        Brak momentu reakcyjnego.
        """
        return self.torque_from_force()


    def torque_from_force(self) -> float:
        pos = self.get_global_position()
        obj_pos = self.get_object_positionXY()
        F = self.get_force_vector()

        rx = pos[0] - obj_pos[0]
        ry = pos[1] - obj_pos[1]

        return rx * F[1] - ry * F[0]
