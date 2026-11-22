import math
from typing import List

from sim.systems.logic.logic_loader import load_logic_function
from sim.utils.views import make_simobject_logic_view, make_simobjs_logic_views
from sim.vectors.vec2d import to_vec2, Vec, vec_sub


def static_logic(simobjs):
    return to_vec2()

def seek_control_logic(
    simobjs: List,
    *,
    target_id: str,
    owner
) -> Vec:
    """
    High-level logic typu 'seek' dla obiektu owner.

    Zwraca:
    - Vec -> wektor intencji ruchu (kierunek + względna siła),
      interpretowany przez low_level_control.
    """

    # znajdź obiekt celu
    target = next((o for o in simobjs if o.id == target_id), None)
    if target is None:
        return to_vec2(0.0, 0.0)

    # czysty wektor intencji: od właściciela do celu
    return vec_sub(target.positionXY, owner.positionXY)

def build_seek_control_logic(params, owner):
    target_id = params.get("target_id")

    if target_id is None:
        raise ValueError("Brak wymaganego parametru 'target_id' dla seek_control")

    def wrapper(simobjs):
        so_view = make_simobject_logic_view(owner)
        sos_view = make_simobjs_logic_views(simobjs)
        return seek_control_logic(sos_view, target_id=target_id, owner=so_view)

    return wrapper


def build_custom_logic(params, owner):
    logic_fn = load_logic_function(params)

    def wrapper(simobjs):
        so_view = make_simobject_logic_view(owner)
        sos_view = make_simobjs_logic_views(simobjs)
        return to_vec2(logic_fn(so_view, sos_view, params))

    return wrapper


# output thrust, yaw
