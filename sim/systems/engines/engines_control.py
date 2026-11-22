from dataclasses import dataclass, field
from typing import List, Tuple, Any, Optional, Callable

from sim.systems.engines.rotor import Rotor
from sim.utils.collision_helpers import point_in_local_shape
from sim.utils.angular_helper import norm_pm_pi

from sim.utils.views import make_engines_control_views
from sim.systems.engines.midle_lewel_control import midle_lewel_control12
from sim.systems.engines.low_level_control import low_level_control
from sim.vectors.vec2d import Vec, to_vec2, vec_len, vec_norm

from sim.vectors.vec2dM import VecM, to_vec2M


# from sim.vectors.vec2dM import VecM, to_vec
@dataclass
class EnginesControl:

    engines: List[Rotor] = field(default_factory=list)

    # --- sync z obiektem ---
    get_object_positionXY: Optional[Callable[[], VecM]] = field(
        init=False, default=None, repr=False
    )

    get_object_velocityXY: Optional[Callable[[], Vec]] = field(
        init=False, default=None, repr=False
    )

    get_object_theta: Optional[Callable[[], float]] = field(
        init=False, default=None, repr=False
    )
    get_object_omega: Optional[Callable[[], float]] = field(
        init=False, default=None, repr=False
    )
    # ----------------------------
    # Walidacja
    # ----------------------------
    def __post_init__(self):
        if not isinstance(self.engines, list):
            raise TypeError("engines musi być listą")

        if len(self.engines) == 1:
            raise ValueError("wymagane 0 lub >= 2 silniki")

        ids = set()
        for i, e in enumerate(self.engines):
            if not isinstance(e, Rotor):
                raise TypeError(f"engines[{i}] nie jest typu Rotor")
            if e.id in ids:
                raise ValueError(f"Duplikat id silnika: '{e.id}'")
            ids.add(e.id)

        self._ml_state = {
            # ==================================================
            # FSM
            # ==================================================
            "mode": "idle",  # aktualny tryb

            # ==================================================
            # OSTATNIE WYJŚCIA (rate limit)
            # ==================================================
            "u_thrust": 0.0,
            "u_yaw": 0.0,

            # ==================================================
            # FILTRY
            # ==================================================
            "u_yaw_filtered": 0.0,  # LPF yaw
            "vel_side_filtered": 0.0,  # LPF prędkości bocznej

            # ==================================================
            # REGULATOR PRĘDKOŚCI
            # ==================================================
            "prev_vel_err": 0.0,  # do członu D

            "prev_omega": 0.0,
        }

    # ----------------------------
    # Synchronizacja
    # ----------------------------
    def sync(self, simobj):

        if not callable(getattr(simobj, "get_positionXY", None)):
            raise AttributeError("SimObject musi mieć metodę get_positionXY")

        if not callable(getattr(simobj, "get_velocityXY", None)):
            raise AttributeError("SimObject musi mieć metodę get_velocityXY")

        if not callable(getattr(simobj, "get_theta", None)):
            raise AttributeError("SimObject musi mieć metodę get_theta")

        if not callable(getattr(simobj, "get_omega", None)):
            raise AttributeError("SimObject musi mieć metodę get_omega")

        self.get_object_positionXY = simobj.get_positionXY
        self.get_object_velocityXY = simobj.get_velocityXY
        self.get_object_theta = simobj.get_theta
        self.get_object_omega = simobj.get_omega

        simobj_local_shape: Any = simobj.local_shape
        try:
            for e in self.engines:
                pos = e.local_position
                if not point_in_local_shape(pos, simobj_local_shape):
                    raise ValueError(
                        f"Engine {e.id} poza lokalną bryłą obiektu "
                        f"(pos={pos}, shape={simobj_local_shape})"
                    )
                e.sync(simobj)
        except Exception as e:
            raise RuntimeError(
                f"Błąd synchronizacji silników w obiekcie {simobj.id}"
            ) from e

    def clear(self):
        for e in self.engines:
            e.clear()
    def drop(self):
        self.get_object_positionXY = None
        self.get_object_velocityXY = None
        self.get_object_theta = None
        self.get_object_omega = None

    def _midle_lewel_control(
            self,
            v_dir: Vec,
            distance_to_target: float,
            dt: float
    ) -> Tuple[float, float]:

        object_theta = self.get_object_theta()
        object_omega = self.get_object_omega()
        object_velocityXY = to_vec2(self.get_object_velocityXY())

        return midle_lewel_control12(
            object_theta=object_theta,
            object_omega=object_omega,
            object_velocityXY=object_velocityXY,
            v_dir=v_dir,
            distance_to_target=distance_to_target,
            dt=dt,
            state=self._ml_state
        )

    #mixer
    def _low_lewel_control(self, u_thrust: float, u_yaw: float) -> List[float]:
        object_position = self.get_object_positionXY()
        engines_views = make_engines_control_views(self.engines)
        return low_level_control(
            object_position=object_position,
            engines=engines_views,
            u_thrust=u_thrust,
            u_yaw=u_yaw
        )

    # ----------------------------
    # Update
    # ----------------------------
    def update(self, v: Vec, dt=0.01):

        distance_to_target = vec_len(v) # dystans do celu
        v_dir = vec_norm(v) # znormalizowany wektor intencji

        u_thrust, u_yaw = self._midle_lewel_control(v_dir, distance_to_target, dt)

        omegas = self._low_lewel_control(u_thrust, u_yaw)

        for e, w in zip(self.engines, omegas):
            e.update(w, dt)


    # ----------------------------
    # Agregacja sił
    # ----------------------------
    def get_thrust_and_torque(self) -> Tuple[VecM, float]:
        Fx = 0.0
        Fy = 0.0
        tau_geom = 0.0

        for e in self.engines:
            F = e.get_force_vector()
            Fx += F[0]
            Fy += F[1]

            tau_geom += e.get_torque()

        tau = tau_geom
        return to_vec2M(Fx, Fy), tau

    def get_engines_spec(self) -> list[dict]:
        return [
            {
                "id": e.id,
                "type": e.__class__.__name__,
                "positionXY_local": e.local_position,
                "angle_local": e.local_angle,
                "max_thrust": e.max_thrust,
                "thrust_direction_local": e.thrust_direction_local,
            }
            for e in self.engines
        ]

    def get_middle_level_control_state(self) -> dict:
        """
        Diagnostyka middle-level control.
        """
        return {
            "_format": 1,
            "mode": self._ml_state.get("mode"),
            "u_yaw_filtered": self._ml_state.get("u_yaw_filtered"),
            "vel_side_filtered": self._ml_state.get("vel_side_filtered"),
            "prev_vel_err": self._ml_state.get("prev_vel_err"),
            "u_thrust": self._ml_state.get("u_thrust"),
            "u_yaw": self._ml_state.get("u_yaw"),
        }
    def get_engines_state(self) -> List[dict]:
        """
        Zwraca dane diagnostyczne silników (do debugowania / wizualizacji).
        Model thrust-only (bez momentu reakcyjnego).
        """
        engines_state = []

        for e in self.engines:
            # --- podstawowe
            engine_id = e.id

            omega = e.rotor_omega
            omega2 = e.omega2

            # --- thrust
            thrust = e.thrust()
            thrust_dir = e.get_thrust_direction()
            thrust_vec = e.get_force_vector()

            # --- moment geometryczny (r × F)
            torque_geom = e.get_torque()

            engines_state.append({
                "_format": 2,

                # identyfikacja
                "id": engine_id,

                # stan silnika
                "rotor_omega": omega,
                "rotor_omega_sq": omega2,

                # thrust
                "thrust": thrust,
                "thrust_vector": thrust_vec,
                "thrust_direction": (
                    thrust_dir[0],
                    thrust_dir[1]
                ),

                # momenty
                "torque": torque_geom,
            })

        return engines_state

    def get_engines_data(self) -> List[dict]:
        """
        Zwraca dane diagnostyczne silników (do debugowania / wizualizacji).
        Model thrust-only (bez momentu reakcyjnego).
        """
        engines_data = []

        for e in self.engines:
            # --- podstawowe
            engine_id = e.id
            engine_type = e.__class__.__name__

            pos = e.get_global_position()
            angle = norm_pm_pi(e.get_global_angle())


            omega = e.rotor_omega
            omega2 = e.omega2

            # --- thrust
            thrust = e.thrust()
            thrust_dir = e.get_thrust_direction()
            thrust_vec = e.get_force_vector()

            max_thrust = e.max_thrust

            # --- moment geometryczny (r × F)
            torque_geom = e.get_torque()

            engines_data.append({
                "_format": 2,

                # identyfikacja
                "id": engine_id,
                "type": engine_type,

                # geometria
                "positionXY": (pos[0], pos[1]),
                "angle_global": angle,

                # stan silnika
                "rotor_omega": omega,
                "rotor_omega_sq": omega2,

                # thrust
                "thrust": thrust,
                "thrust_vector": thrust_vec,
                "thrust_direction": (
                    thrust_dir[0],
                    thrust_dir[1]
                ),
                "max_thrust": max_thrust,

                # momenty
                "torque": torque_geom,
            })

        return engines_data
