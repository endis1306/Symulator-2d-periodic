from typing import Dict, Any

from sim.systems.logic.logic import Logic
from sim.systems.logic.logic_functions import static_logic, build_seek_control_logic, build_custom_logic


def build_logic(obj_def: Dict[str, Any]) -> Logic:


    logic_def = obj_def.get("logic") or {}
    if not isinstance(logic_def, dict):
        raise TypeError("Sekcja 'logic' musi być dict")

    logic_type = str(logic_def.get("type", "static")).lower().strip()
    params = logic_def.get("params") or {}
    if not isinstance(params, dict):
        raise TypeError("logic.params musi być dict")

    logic = Logic(type=logic_type, params=params)

    if logic_type == "static":
        logic._bind = lambda simobj: static_logic
    elif logic_type == "seek_control":
        logic._bind = lambda simobj: build_seek_control_logic(params, simobj)
    elif logic_type == "custom":
        logic._bind = lambda simobj: build_custom_logic(params, simobj)
    else:
        raise ValueError(f"Nieznany typ logiki: {logic_type}")

    return logic
