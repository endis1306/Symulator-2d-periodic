from typing import Dict, Any

from sim.core.body_params import BodyParams


def build_body_params(obj_def: Dict[str, Any]) -> BodyParams:
    c_def = obj_def.get("bodyParams", {})
    if not isinstance(c_def, dict):
        raise TypeError("Sekcja 'bodyParams' musi być słownikiem (dict).")

    kwargs = {}
    try:
        kwargs['drag_lin_forward'] = float(c_def.get("drag_lin_forward", 0.0))
        kwargs['drag_lin_side'] = float(c_def.get("drag_lin_side", 0.0))
        kwargs['drag_rot'] = float(c_def.get("drag_rot", 0.0))
        kwargs['I'] = float(c_def.get("I", 1.0))
        kwargs['mass'] = float(c_def.get("mass", 1.0))
    except (ValueError, TypeError) as e:
        raise TypeError(f"Błąd konwersji typu w sekcji 'bodyParams': {e}") from e

    try:
        return BodyParams(**kwargs)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Nie można utworzyć BodyParams: {e}") from e
