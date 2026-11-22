from typing import Dict, Any
from sim.systems.sensors.sensor import Sensor
from sim.geometry.shape import RadialSector

def build_sensor(sensor_def: Dict[str, Any]) -> Sensor:
    if not isinstance(sensor_def, dict):
        raise TypeError("Definicja sensora musi być słownikiem (dict).")

    # --- id sensora ---
    id_val = sensor_def.get("id", "Sensor")
    if not isinstance(id_val, str):
        raise TypeError(f"Pole 'id' musi być stringiem, otrzymano: {type(id_val)}")
    id_val = id_val.strip()
    if not id_val:
        raise ValueError("Pole 'id' nie może być puste.")

    # --- category i enabled ---
    category = sensor_def.get("category")
    enabled = sensor_def.get("enabled", True)
    if not isinstance(enabled, bool):
        raise TypeError(f"Pole 'enabled' musi być bool, otrzymano: {type(enabled)}")
    if category is not None and not isinstance(category, str):
        raise TypeError(f"Pole 'category' musi być stringiem lub None, otrzymano: {type(category)}")

    try:
        rays_count = sensor_def["rays_count"]
        max_range = sensor_def["max_range"]
        fov = sensor_def["fov"]
        offset_theta = sensor_def.get("offset_theta", 0.0)
    except KeyError as e:
        raise ValueError(f"Brak wymaganego pola dla RadialSector: {e.args[0]} w definicji sensora '{id_val}'")

    try:
        if not isinstance(rays_count, int):
            raise TypeError(f"rays_count musi być int, otrzymano: {type(rays_count)}")
        if not isinstance(max_range, (int, float)):
            raise TypeError(f"max_range musi być int lub float, otrzymano: {type(max_range)}")
        if not isinstance(fov, (int, float)):
            raise TypeError(f"fov musi być int lub float, otrzymano: {type(fov)}")
        if not isinstance(offset_theta, (int, float)):
            raise TypeError(f"offset_theta musi być int lub float, otrzymano: {type(offset_theta)}")

        detection_shape = RadialSector(
            rays_count=rays_count,
            max_range=float(max_range),
            fov=float(fov),
            offset_theta=float(offset_theta)
        )
    except (ValueError, TypeError) as e:
        raise ValueError(f"Błąd przetwarzania danych dla RadialSector w sensorze '{id_val}': {e}") from e

    try:
        sensor = Sensor(
            id=id_val,
            detection_shape=detection_shape,
            category=category,
            enabled=enabled
        )
        return sensor
    except Exception as e:
        raise ValueError(f"Nie można utworzyć Sensor '{id_val}': {e}") from e
