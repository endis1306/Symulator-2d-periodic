from typing import Dict, Any, Optional
from sim.geometry.shape import Shape, Circle, Polygon


def build_shape(obj_def: Dict[str, Any]) -> Shape:
    shape_data: Dict[str, Any] = obj_def.get("shape")
    if not isinstance(shape_data, dict):
        raise ValueError("Sekcja 'shape' musi być słownikiem.")

    shape_type: Optional[str] = shape_data.get("type")
    if not isinstance(shape_type, str):
        raise ValueError("Typ kształtu ('type') musi być ciągiem znaków (str).")

    shape_type = shape_type.lower().strip()

    try:
        if shape_type == "circle":
            if "r" not in shape_data:
                raise ValueError("Brak klucza 'r' (promień) dla kształtu 'circle'.")

            raw_radius = shape_data.get("r")
            try:
                radius = float(raw_radius)
            except (ValueError, TypeError):
                raise TypeError(f"Nie można przekonwertować promienia '{raw_radius}' na liczbę.")

            return Circle(r=radius)

        elif shape_type in ("polygon", "poly"):
            if "points" not in shape_data:
                raise ValueError("Brak klucza 'points' dla kształtu 'polygon'.")


            raw_points = shape_data.get("points")
            if not isinstance(raw_points, list):
                raise TypeError(f"Pole 'points' musi być listą, a nie {type(raw_points).__name__}.")

            return Polygon(points=raw_points)

        else:
            raise ValueError(f"Nieznany typ kształtu: '{shape_type}'")

    except (ValueError, TypeError) as e:
        raise ValueError(f"Błąd podczas tworzenia kształtu typu '{shape_type}': {e}") from e
