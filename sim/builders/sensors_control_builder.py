from __future__ import annotations
from typing import Dict, Any, TYPE_CHECKING
from sim.systems.sensors.sensors_control import SensorsControl
from sim.builders.sensor_builder import build_sensor

if TYPE_CHECKING:
    from sim.systems.sensors.sensor import Sensor

def build_sensors_control(obj_def: Dict[str, Any]) -> SensorsControl:
    try:
        if not isinstance(obj_def, dict):
            raise TypeError("obj_def musi być dict")

        sensors_cfg = obj_def.get("sensors")

        # brak sekcji sensors → brak sensorów (OK)
        if sensors_cfg is None:
            return SensorsControl()

        if not isinstance(sensors_cfg, list):
            raise TypeError("Sekcja 'sensors' musi być listą")

        sensors: list[Sensor] = []
        ids_seen: set[str] = set()

        for idx, s_def in enumerate(sensors_cfg):
            if not isinstance(s_def, dict):
                raise TypeError(f"sensors[{idx}] musi być dict")

            try:
                sensor = build_sensor(s_def)
            except Exception as e:
                sid = s_def.get("id")
                ctx = f"index={idx}"
                if isinstance(sid, str) and sid:
                    ctx += f", id='{sid}'"
                raise ValueError(f"Błąd podczas budowy sensora ({ctx}): {e}") from e

            if sensor.id in ids_seen:
                raise ValueError(f"Zduplikowane id sensora: '{sensor.id}'")
            ids_seen.add(sensor.id)

            sensors.append(sensor)

        return SensorsControl(sensors=sensors)

    except Exception as e:
        raise RuntimeError(f"Nie udało się zbudować SensorsControl: {e}") from e
