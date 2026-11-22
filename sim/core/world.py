from dataclasses import dataclass, field
from typing import List, Tuple, Any, Dict

from sim.utils.collision_helpers import shapes_collide
from sim.core.sim_object import SimObject
from sim.geometry.box import Box
from sim.vectors.vec2dM import to_vec2M


# world = build_world(cfg) -> { delta_t, simobjs: List[SimObject], next_iteration() }


@dataclass
class World:
    world_box: Box
    delta_t: float
    simobjs: List[SimObject]


    time: float = 0.0
    state_index: int = 0

    id_to_obj: Dict[str, SimObject] = field(init=False)
    pending_removal_ids: set[str] = field(init=False)

    alive_objects: List[SimObject] = field(init=False)

    def serialize_init(self) -> dict:
        return {
            "event": "world_init",
            "world": {
                "delta_t": self.delta_t,
                "world_box": {
                    "minx": self.world_box.minx,
                    "miny": self.world_box.miny,
                    "maxx": self.world_box.maxx,
                    "maxy": self.world_box.maxy,
                }
            },
            "objects": [
                obj.to_spec_dict() for obj in self.simobjs
            ]
        }


    def serialize(self) -> dict:
        return {
            "state_index": self.state_index,
            "time": self.time,
            "objects": [obj.to_state_dict() for obj in self.simobjs]
        }


    def sync(self):
        for obj in self.simobjs:
            try:
                obj.sync()
            except Exception as e:
                msg = f"Błąd synchronizacji obiektu o ID '{obj.id}'."
                raise RuntimeError(msg) from e

    def restore_from_state(self, data: dict) -> None:
        self.state_index = data["state_index"]
        self.time = data["time"]

        states_by_id = {o["id"]: o for o in data["objects"]}

        for obj in self.simobjs:
            state = states_by_id.get(obj.id)
            if state is None:
                continue

            obj.positionXY = to_vec2M(*state["positionXY"])
            obj.velocityXY = to_vec2M(*state["velocityXY"])
            obj.theta = state["theta"]
            obj.omega = state["omega"]

            obj.static = state["static"]
            obj.destroyed = state["destroyed"]
            obj.removed = state["removed"]

        self.normalize_destroyed_removed_flags()
        self.check_and_destroy_initial_collisions()
        self.rebuild_alive_objects()
        self.compute_perception()

    def __post_init__(self):

        if not isinstance(self.world_box, Box):
            raise TypeError(f"Pole 'world_box' musi być typu Box, a nie {type(self.world_box).__name__}.")

        if not isinstance(self.delta_t, (int, float)):
            raise TypeError(f"Krok czasowy (delta_t) musi być liczbą, a nie {type(self.delta_t).__name__}.")

        if not isinstance(self.simobjs, list):
            raise TypeError(f"Pole simobjs musi być listą, a nie {type(self.simobjs).__name__}.")

        if not all(isinstance(obj, SimObject) for obj in self.simobjs):
            raise TypeError("Wszystkie elementy na liście simobjs muszą być instancjami klasy SimObject.")

        if not isinstance(self.time, (int, float)):
            raise TypeError(f"Pole 'time' musi być liczbą, a nie {type(self.time).__name__}.")

        if not isinstance(self.state_index, int):
            raise TypeError(f"Pole 'iteration' musi być liczbą całkowitą, a nie {type(self.state_index).__name__}.")

        if not (self.world_box.minx == 0 and self.world_box.miny == 0):
            raise ValueError("Pole 'world_box' musi zaczynać się od punktu (0,0).")

        if not (self.world_box.maxx > 0 and self.world_box.maxy > 0):
            raise ValueError("Pole 'boundary_point' musi leżeć w prawej górnej części układu współrzędnych.")

        if self.delta_t <= 0:
            raise ValueError(f"Krok czasowy (delta_t) musi być dodatni, a jest {self.delta_t}.")

        ids = [obj.id for obj in self.simobjs]

        if len(ids) != len(set(ids)):
            raise ValueError("Wykryto zduplikowane ID obiektów w świecie symulacji.")

        if self.time < 0:
            raise ValueError("Pole 'time' nie może być ujemne.")

        if self.state_index < 0:
            raise ValueError("Pole 'iteration' nie może być ujemne.")


        self.normalize_destroyed_removed_flags()

        self.id_to_obj = { obj.id: obj for obj in self.simobjs }

        self.pending_removal_ids = set()

        self.rebuild_alive_objects()

    def normalize_destroyed_removed_flags(self) -> None:
        for obj in self.simobjs:
            if obj.get_destroyed() or obj.get_removed():
                obj.destroy()
                obj.remove()


    def rebuild_alive_objects(self) -> None:
        self.alive_objects = [
            obj for obj in self.simobjs
            if not obj.get_destroyed() and not obj.get_removed()
        ]

    def get_simobjs(self) -> List[SimObject]:
        return self.simobjs

    def get_time(self) -> float:
        return self.time

    def get_state_index(self) -> int:
        return self.state_index

    def check_and_destroy_initial_collisions(self) -> bool:
        simobjs: list = list(self.alive_objects)

        if not simobjs:
            return False

        self.id_to_obj = { obj.id: obj for obj in self.simobjs }

        collision_events: list[tuple[int, SimObject, SimObject | None]] = []
        n: int = len(simobjs)

        for i in range(n):
            obj1 = simobjs[i]
            s1 = obj1.to_moved_shape()

            if not self.world_box.intersects(s1[-1]):
                collision_events.append((1, obj1, None))

            for j in range(i + 1, n):
                obj2 = simobjs[j]
                s2 = obj2.to_moved_shape()

                if shapes_collide(s1, s2):
                    collision_events.append((2, obj1, obj2))

        collision_events.sort(key=lambda x: x[0], reverse=True)

        for _, obj1, obj2 in collision_events:
            if obj2 is None:
                obj1.on_collision(None)
            else:
                obj1.on_collision(obj2)
                obj2.on_collision(obj1)

        self.pending_removal_ids = {
            obj.id
            for obj in self.simobjs
            if obj.get_destroyed() and not obj.get_removed()
        }

        self.rebuild_alive_objects()

        return not self.pending_removal_ids


    def compute_perception(self):
        self.compute_next_sensors_state()

    def compute_next_sensors_state(self):
        for obj in self.alive_objects:
            obj.sensors_next_state(self.alive_objects, self.world_box)

    def compute_next_logic_state(self):
        for obj in self.alive_objects:
            obj.logic_next_state(self.alive_objects, self.delta_t)


    def next_state(self) -> bool:
        self.state_index += 1
        moved: List[Tuple[SimObject, Any]] = []
        for cid in self.pending_removal_ids:
            obj = self.id_to_obj.get(cid)
            if obj is None:
                continue
            try:
                obj.on_removed()
            except Exception as e:
                raise RuntimeError(f"Błąd podczas usuwania obiektu {cid}") from e
        self.compute_next_logic_state()
        for obj in self.alive_objects:
            if obj.physics_next_state(deltaT=self.delta_t):
                moved.append((obj, obj.to_moved_shape()))

        collision_events: list[tuple[int, SimObject, SimObject | None]] = []
        n: int = len(moved)

        for i in range(n):
            obj1, s1 = moved[i]

            if not self.world_box.intersects(s1[-1]):
                collision_events.append((1, obj1, None))

            for j in range(i + 1, n):
                obj2, s2 = moved[j]
                if shapes_collide(s1, s2):
                    collision_events.append((2, obj1, obj2))

        collision_events.sort(key=lambda x: x[0], reverse=True)

        for priority, obj1, obj2 in collision_events:
            if obj2 is None:
                obj1.on_collision(None)
            else:
                obj1.on_collision(obj2)
                obj2.on_collision(obj1)

        self.pending_removal_ids = {
            obj.id
            for obj in self.simobjs
            if obj.get_destroyed() and not obj.get_removed()
        }

        self.rebuild_alive_objects()

        self.compute_perception()
        self.time += self.delta_t

        return not (self.pending_removal_ids or moved)
