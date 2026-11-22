from typing import Dict, Any, List
from sim.core.world import World
from sim.core.sim_object import SimObject
from sim.builders.sim_objects_builder import build_simobjects
from sim.vectors.vec2d import Vec, to_vec2
from sim.geometry.box import Box

def build_world(cfg: Dict[str, Any]) -> World:
    if not isinstance(cfg, dict):
        raise TypeError("Konfiguracja świata (cfg) musi być słownikiem (dict).")

    raw_boundary_point = cfg.get("boundary_point")
    if raw_boundary_point is None:
        raise ValueError("Brakuje wymaganego pola 'boundary_point' w konfiguracji świata.")
    try:
        boundary_point: Vec = to_vec2(raw_boundary_point)
    except (ValueError, TypeError):
        raise TypeError(f"Pole 'boundary_point' musi być konwertowalne na Vec (otrzymano '{raw_boundary_point}').")

    try:
        bx, by = boundary_point
        world_box: Box = Box(0,0,bx,by)
    except Exception as e:
        raise type(e)(f"Błąd podczas budowania przestrzeni świata: {e}") from e

    raw_delta_t = cfg.get("delta_t")
    if raw_delta_t is None:
        raise ValueError("Brakuje wymaganego pola 'delta_t' w konfiguracji świata.")
    try:
        delta_t: float = float(raw_delta_t)
    except (ValueError, TypeError):
        raise TypeError(f"Pole 'delta_t' musi być konwertowalne na liczbę (otrzymano '{raw_delta_t}').")

    objects_cfg = cfg.get("objects", [])
    if not isinstance(objects_cfg, list):
        raise TypeError("Pole 'objects' w konfiguracji musi być listą.")

    try:
        simobjs: List[SimObject] = build_simobjects(objects_cfg)
    except Exception as e:
        raise ValueError(f"Błąd podczas budowania listy obiektów symulacji: {e}") from e

    try:
        world = World(world_box=world_box, delta_t=delta_t, simobjs=simobjs)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Błąd podczas budowy świata: {e}") from e

    return world
