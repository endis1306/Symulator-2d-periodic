from dataclasses import dataclass, field
from typing import List, Optional, Callable

from sim.systems.sensors.sensor import Sensor
from sim.vectors.vec2dM import VecM


@dataclass
class SensorsControl:
    sensors: List[Sensor] = field(default_factory=list)

    get_object_id: Optional[Callable[[], str]] = field(init=False, default=None, repr=False)
    get_object_positionXY: Optional[Callable[[], VecM]] = field(init=False, default=None, repr=False)
    get_object_theta: Optional[Callable[[], float]] = field(init=False, default=None, repr=False)


    def __post_init__(self):
        # --- sensors musi być listą ---
        if not isinstance(self.sensors, list):
            raise TypeError(
                f"SensorsControl.sensors musi być listą, "
                f"a nie {type(self.sensors).__name__}."
            )

        ids_seen = set()

        for i, s in enumerate(self.sensors):
            # --- typ sensora ---
            if not isinstance(s, Sensor):
                raise TypeError(
                    f"Element sensors[{i}] musi być typu Sensor, "
                    f"a nie {type(s).__name__}."
                )

            # --- unikalność id ---
            if s.id in ids_seen:
                raise ValueError(
                    f"Zduplikowane id sensora w SensorsControl: '{s.id}'."
                )
            ids_seen.add(s.id)

    def sync(self, simobj):
        if not callable(getattr(simobj, "get_id", None)):
            raise AttributeError("SimObject musi mieć metodę get_id")

        if not callable(getattr(simobj, "get_positionXY", None)):
            raise AttributeError("SimObject musi mieć metodę get_positionXY")

        if not callable(getattr(simobj, "get_theta", None)):
            raise AttributeError("SimObject musi mieć metodę get_theta")

        self.get_object_id = simobj.get_id
        self.get_object_positionXY = simobj.get_positionXY
        self.get_object_theta = simobj.get_theta

        for s in self.sensors:
            s.sync(self)

    def scan_all(self, simobjs, border_box=None):
        for s in self.sensors:
            s.scan(simobjs, border_box)

    def get_enabled(self):
        return [s for s in self.sensors if s.enabled]

    def get_sensors_spec(self) -> list[dict]:
        specs = []

        for s in self.sensors:
            _, max_range, angle_start, angle_end = s.detection_shape.local_shape

            specs.append({
                "id": s.id,
                "type": s.__class__.__name__,
                "category": s.category,

                "vision": {
                    "max_range": max_range,
                    "angle_start": angle_start,
                    "angle_end": angle_end,
                },

                "default_enabled": s.enabled,
            })

        return specs

    def get_sensors_state(self) -> list[dict]:
        """
        Zwraca aktualny stan sensorów:
        - włączony/wyłączony
        - ostatni skan
        """
        sensors_state = []

        for s in self.sensors:
            sensors_state.append({
                "id": s.id,  # przydatne do mapowania wyników, można traktować jako metadane
                "enabled": s.enabled,
                "scan": s.last_scans[0] if s.last_scans else None,
            })

        return sensors_state

    def get_sensors_data(self) -> List[dict]:
        sensors_data = []
        for s in self.sensors:
            _format = 1
            sensor_id = s.id
            type = s.__class__.__name__
            positionXY = tuple(s.get_positionXY())
            enabled = s.enabled
            category = s.category
            last_scans = s.last_scans

            max_range = s.detection_shape.max_range
            angle_start, angle_end = s.detection_shape.get_global_angle_span()

            vision = {"max_range": max_range, "angle_start": angle_start, "angle_end": angle_end}

            sensors_data.append({
                "_format": _format,
                "id": sensor_id,
                "type": type,
                "positionXY": positionXY,
                "vision": vision,
                "enabled": enabled,
                "category": category,
                "scans": last_scans,
            })


        return sensors_data

    def drop(self):
        self.sensors.clear()

    def clear(self):
        for s in self.sensors:
            s.clear()
