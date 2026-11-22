import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Optional, Tuple
from sim.vectors.vec2d import Vec, to_vec2


@dataclass(frozen=True)
class SimObjectView:
    """
    Read-only snapshot (view) obiektu symulacji. To powinno być bezpieczne
    do przekazywania użytkownikom/plug-inom — nie pozwala na zmianę stanu.
    """
    id: str
    positionXY: Vec
    velocityXY: Vec
    accelerationXY: Vec

    theta: float
    omega: float
    alpha: float

    # uproszczone/serializowalne informacje o ciele
    body_params: Dict[str, Any]

    # zastępujemy expose kontroli silników i sensorów ich snapshotami
    engines: Any
    sensors: Any

    # shape po translacji/rotacji (to co zwraca simobj.to_moved_shape() lub moved_shape_to_dict)
    moved_shape: Optional[Any] = None

    static: bool = False
    destroyed: bool = False
    removed: bool = False

    # dodatkowe pole — surowy snapshot wygenerowany przez to_state_dict (opcjonalne)
    state_dict: Optional[Dict[str, Any]] = field(default=None, repr=False)


def make_simobject_view(simobj) -> SimObjectView:
    """
    Stworzy SimObjectView z istniejącego SimObject.
    Używa metod get_* i to_state_dict, to_moved_shape tam gdzie sensowne.
    """
    # pozycje/wektory -> proste tupl'e
    pos = to_vec2(simobj.get_positionXY())
    vel = to_vec2(simobj.get_velocityXY())
    # acceleration może nie mieć get_accelerationXY, korzystamy z atrybutu jeśli brak getter
    acc = to_vec2(getattr(simobj, "accelerationXY", (0.0, 0.0)))

    # body params: bierzemy najważniejsze pola (jeśli istnieją)
    bp = {}
    try:
        bp["mass"] = getattr(simobj.bodyParams, "mass", None)
        bp["I"] = getattr(simobj.bodyParams, "I", None)
        bp["drag_lin"] = getattr(simobj.bodyParams, "drag_lin", None)
        bp["drag_rot"] = getattr(simobj.bodyParams, "drag_rot", None)
    except Exception:
        bp = {}

    # engines / sensors snapshots korzystają z istniejących metod
    engines = None
    sensors = None
    try:
        engines = simobj.enginesControl.get_engines_data()
    except Exception:
        engines = None
    try:
        sensors = simobj.sensorsControl.get_sensors_data()
    except Exception:
        sensors = None

    # moved_shape — próbujemy użyć to_moved_shape (może zwracać obiekt)
    moved_shape = None
    try:
        moved_shape = simobj.to_moved_shape()
    except Exception:
        moved_shape = None

    # opcjonalny state_dict (ułatwia debug/replay)
    state = None
    try:
        state = simobj.to_state_dict()
    except Exception:
        state = None

    return SimObjectView(
        id=simobj.get_id(),
        positionXY=pos,
        velocityXY=vel,
        accelerationXY=acc,
        theta=float(simobj.get_theta()),
        omega=float(simobj.get_omega()),
        alpha=float(getattr(simobj, "alpha", 0.0)),
        body_params=bp,
        engines=engines,
        sensors=sensors,
        moved_shape=moved_shape,
        static=bool(getattr(simobj, "static", False)),
        destroyed=bool(simobj.get_destroyed()),
        removed=bool(simobj.get_removed()),
        state_dict=state,
    )


def make_simobjs_views(simobjs: Sequence) -> List[SimObjectView]:
    """
    Wygeneruj listę SimObjectView z listy SimObject.
    """
    views: List[SimObjectView] = []
    for so in simobjs:
        try:
            views.append(make_simobject_view(so))
        except Exception:
            # nie przerywaj — jeżeli jakiś obiekt ma błąd, daj pusty placeholder
            views.append(SimObjectView(
                id=str(getattr(so, "id", "unknown")),
                positionXY=(0.0, 0.0),
                velocityXY=(0.0, 0.0),
                accelerationXY=(0.0, 0.0),
                theta=0.0,
                omega=0.0,
                alpha=0.0,
                body_params={},
                engines=None,
                sensors=None,
                moved_shape=None,
                static=False,
                destroyed=False,
                removed=False,
                state_dict=None,
            ))
    return views


@dataclass(frozen=True)
class EngineControlView:
    position: Vec
    thrust_dir: Vec

    k_thrust: float
    omega_max: float


    #force_vector: Vec
    #torque: float
    #max_thrust: float


def make_engine_control_view(engine) -> EngineControlView:
    try:
        pos = to_vec2(engine.get_global_position())      # globalna pozycja silnika
        thrust_dir = to_vec2(engine.get_thrust_direction())  # globalny kierunek thrustu (unit vector)
        k_thrust = float(engine.k_thrust)
        omega_max = float(engine.rotor_omega_max)

        # obliczenie aktualnej siły i momentu
        #force_vec = to_vec2(engine.get_force_vector())
        #torque = float(engine.get_torque())
        #max_thrust = float(engine.max_thrust)
    except AttributeError as e:
        raise TypeError(
            "Engine nie spełnia minimalnego kontraktu sterowania"
        ) from e

    return EngineControlView(
        position=pos,
        thrust_dir=thrust_dir,
        k_thrust=k_thrust,
        omega_max=omega_max,
    )

def make_engines_control_views(engines: Sequence) -> List[EngineControlView]:
    return [
        make_engine_control_view(e)
        for e in engines
    ]

@dataclass(frozen=True)
class SimObjectLogicView:
    id: str
    positionXY: Tuple[float, float]
    velocityXY: Tuple[float, float]
    accelerationXY: Tuple[float, float]
    theta: float
    sensors: List[dict] = field(default_factory=list)
    static: bool = False


def process_sensor_scans_for_logic(simobj) -> List[dict]:
    """
    Przetwarza skany sensora na dane przydatne dla logiki.
    Zwraca listę słowników: {"obj_id", "vector_global", "distance"}.
    """
    processed = []
    sensors_data: List[dict] = simobj.sensorsControl.get_sensors_data()

    for s in sensors_data:
        scans: Optional[List[Tuple[float, float, str]]] = s.get("scans")
        if not scans:
            continue

        for g_angle, dist, obj_id in scans:
            if obj_id is None:
                continue

            dx = dist * math.cos(g_angle)
            dy = dist * math.sin(g_angle)
            processed.append({
                "obj_id": obj_id,
                "vector_global": to_vec2(dx, dy),
                "distance": dist
            })
    return processed


def make_simobject_logic_view(simobj) -> SimObjectLogicView:
    id = str(simobj.get_id())
    pos = to_vec2(simobj.get_positionXY())
    vel = to_vec2(simobj.get_velocityXY())
    acc = to_vec2(simobj.get_accelerationXY())
    theta = float(simobj.get_theta())
    sensors = process_sensor_scans_for_logic(simobj)
    static = bool(simobj.get_static())
    return SimObjectLogicView(
        id=id,
        positionXY=pos,
        velocityXY=vel,
        accelerationXY=acc,
        theta=theta,
        sensors=sensors,
        static=static,
    )


def make_simobjs_logic_views(simobjs: Sequence) -> List[SimObjectLogicView]:
    return [
        make_simobject_logic_view(so)
        for so in simobjs
    ]
