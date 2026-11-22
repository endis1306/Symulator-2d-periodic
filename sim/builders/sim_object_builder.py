from typing import Any, Dict
from sim.builders.shape_builder import build_shape, Shape
from sim.builders.engines_control_builder import build_engines_control, EnginesControl
from sim.builders.sensors_control_builder import build_sensors_control, SensorsControl
from sim.builders.body_params_builder import build_body_params, BodyParams
from sim.builders.build_logic import build_logic, Logic
from sim.vectors.vec2dM import to_vec2M
from sim.core.sim_object import SimObject


def build_simobject(obj_def: Dict[str, Any]) -> SimObject:

    if not isinstance(obj_def, dict):
        raise TypeError("Definicja obiektu musi być słownikiem (dict).")

    id_val = obj_def.get("id", "Obj").strip()
    if not id_val:
        raise ValueError("Pole 'id' w obiekcie nie może być puste.")

    if id_val == "WORLD_BOUNDARY":
        raise ValueError("Pole 'id' w obiekcie nie może mieć nazwy 'WORLD_BOUNDARY'.")

    if "shape" not in obj_def:
        raise ValueError(f"Brak sekcji 'shape' w definicji obiektu '{id_val}'.")

    try:
        shape: Shape = build_shape(obj_def)
        bodyParams: BodyParams = build_body_params(obj_def)
        enginesControl: EnginesControl = build_engines_control(obj_def)
        sensorsControl: SensorsControl = build_sensors_control(obj_def)
        logic: Logic = build_logic(obj_def)

        static = bool(obj_def.get("static", False))
        position_xy = to_vec2M(obj_def.get("positionXY", (0.0, 0.0)))

        velocity_xy = to_vec2M(obj_def.get("velocityXY", (0.0, 0.0)))

        theta = float(obj_def.get("theta", 0.0))
        omega = float(obj_def.get("omega", 0.0))

    except (ValueError, TypeError) as e:
        raise ValueError(f"Błąd przetwarzania danych dla obiektu '{id_val}': {e}") from e

    try:
        simobj = SimObject(
            id=id_val,
            shape=shape,
            positionXY=position_xy,
            velocityXY=velocity_xy,
            theta=theta,
            omega=omega,
            bodyParams=bodyParams,
            enginesControl=enginesControl,
            sensorsControl=sensorsControl,
            logic=logic,
            static=static,
        )
    except Exception as e:
        raise ValueError(f"Nie można utworzyć SimObject '{id_val}': {e}") from e

    return simobj
