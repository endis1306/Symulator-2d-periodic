from __future__ import annotations
from typing import List, TYPE_CHECKING, Dict, Any

from sim.builders.sim_object_builder import build_simobject

if TYPE_CHECKING:
    from sim.core.sim_object import SimObject

def build_simobjects(objs_cfg: List[Dict[str, Any]]) -> List[SimObject]:
    if not isinstance(objs_cfg, list):
        raise TypeError("Pole 'objects' w konfiguracji musi być listą.")
    if len(objs_cfg) == 0:
        raise ValueError("Lista 'objects' nie może być pusta — musi zawierać co najmniej jeden obiekt.")

    objs: List[SimObject] = []
    ids_seen: set = set()
    for idx, o in enumerate(objs_cfg):
        try:
            simobj = build_simobject(o)
        except Exception as e:
            id_here = o.get("id") if isinstance(o, dict) else None
            ctx = f"index={idx}"
            if id_here:
                ctx += f", id='{id_here}'"
            raise ValueError(f"Błąd podczas budowy obiektu ({ctx}): {e}") from e

        if simobj.id in ids_seen:
            raise ValueError(f"Zduplikowane id obiektu: '{simobj.id}'. Id musi być unikalne.")
        ids_seen.add(simobj.id)

        objs.append(simobj)

    return objs
