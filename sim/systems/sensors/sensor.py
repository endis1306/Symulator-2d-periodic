from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable, TYPE_CHECKING, Tuple
from sim.geometry.box import Box
from sim.geometry.shape import RadialSector
from sim.utils.collision_helpers import ray_intersect_moved_object, ray_intersect_aabb
from sim.utils.angular_helper import norm_pm_pi
from sim.vectors.vec2dM import VecM
from sim.vectors.vec2d import Vec, to_vec2


if TYPE_CHECKING:
    from sim.core.sim_object import SimObject


@dataclass
class Sensor:
    id: str
    detection_shape: RadialSector

    get_object_id: Optional[Callable[[], str]] = field(init=False, default=None, repr=False)
    get_positionXY: Optional[Callable[[], VecM]] = field(init=False, default=None, repr=False)
    get_theta: Optional[Callable[[], float]] = field(init=False, default=None, repr=False)


    enabled: bool = True
    category: Optional[str] = None  # np. "lidar", "vision", "ultrasonic"

    last_scans: Optional[List[Tuple[float, float, str]]] = None

    _cached_moved: Any = field(init=False, default=None, repr=False)
    _cached_pos_theta: Optional[Tuple[Vec, float]] = field(init=False, default=None, repr=False)

    def __post_init__(self):
        # --- id ---
        if not isinstance(self.id, str):
            raise TypeError(f"Sensor.id musi być stringiem, otrzymano: {type(self.id)}")

        if self.id.strip() == "":
            raise ValueError("Sensor.id nie może być pustym stringiem.")

        # --- shape ---
        if not isinstance(self.detection_shape, RadialSector):
            raise TypeError(
                f"Sensor.shape musi być instancją Shape lub klasy dziedziczącej, "
                f"otrzymano: {type(self.detection_shape)}"
            )

        # --- enabled ---
        if not isinstance(self.enabled, bool):
            raise TypeError(f"Sensor.enabled musi być typu bool, otrzymano: {type(self.enabled)}")

        # --- category ---
        if self.category is not None and not isinstance(self.category, str):
            raise TypeError(
                f"Sensor.category musi być stringiem lub None, otrzymano: {type(self.category)}"
            )

    def sync(self, sensors_control):
        """
        Sensor synchronizuje się poprzez swój kształt.
        """
        if not callable(getattr(sensors_control, "get_object_id", None)):
            raise AttributeError("sensors_control musi mieć metodę get_object_id")

        if not callable(getattr(sensors_control, "get_object_id", None)):
            raise AttributeError("sensors_control musi mieć metodę get_object_positionXY")

        if not callable(getattr(sensors_control, "get_object_theta", None)):
            raise AttributeError("sensors_control musi mieć metodę get_object_theta")

        self.get_object_id = sensors_control.get_object_id
        self.get_positionXY = sensors_control.get_object_positionXY
        self.get_theta = sensors_control.get_object_theta

        self.detection_shape.sync(self)

    def get_id(self):
        return self.id

    @property
    def local_detection_shape(self) -> Any:
        return self.detection_shape.local_shape

    def to_moved_shape(self) -> Any:
        """
        Zwraca globalny obraz kształtu sensora.
        Jeśli pozycja i kąt się nie zmieniły, zwraca zapisany wynik (_cached_moved).
        """
        if self.get_positionXY is None or self.get_theta is None:
            raise RuntimeError("Sensor nie jest zsynchronizowany. Wywołaj .sync(self)")

        pos = to_vec2(self.get_positionXY())
        theta = self.get_theta()
        key = (pos, theta)

        if self._cached_pos_theta == key and self._cached_moved is not None:
            return self._cached_moved

        moved = self.detection_shape.moved()
        self._cached_moved = moved
        self._cached_pos_theta = key
        return moved

    def scan(self, simobjs: List[SimObject], border_box: Optional[Box] = None, eps: float = 1e-9
            ) -> Optional[List[Tuple[float, float, str]]]:
        """
        Główna metoda skanowania (bez przenikania):
          - Każdy promień (ray) może wykryć maksymalnie jedno trafienie (najbliższe).
          - Zwraca listę trafień posortowaną rosnąco po odległości: [(angle, distance, obj_id_or_None), ...]
            gdzie obj_id_or_None == None oznacza trafienie granicy (border_box).
          - Jeżeli brak trafień zwraca None.
        """
        if not self.enabled:
            self.last_scans = None
            return None

        # Pobierz informacje sensora
        moved_sensor = self.to_moved_shape()
        try:
            tag, center, max_range, global_rays, sector_box = moved_sensor
        except (ValueError, TypeError):
            raise NotImplementedError("scan() obsługuje tylko RadialSector (format zwracany przez moved).")

        if tag != "radial_sector":
            raise NotImplementedError("scan() obsługuje tylko RadialSector (tag 'radial_sector').")

        ray_origin = (center[0], center[1])

        # Przygotuj kandydatów obiektów (tak jak wcześniej): tylko te które nie są zniszczone/removed,
        # nie są parentem sensora, mają moved shape i ich box przecina sector_box.
        candidates: List[Tuple[Any, SimObject]] = []
        for obj in simobjs:
            if obj.get_destroyed() or obj.get_removed():
                continue
            if obj.get_id() == self.get_object_id():
                continue
            moved_obj = obj.to_moved_shape()
            if not moved_obj:
                continue
            obj_box = moved_obj[-1]
            if sector_box.intersects(obj_box):
                # przechowujemy geom bez boxa oraz referencję do obiektu
                candidates.append((moved_obj[:-1], obj))

        hits: List[Tuple[float, float, Optional[str]]] = []

        # Dla każdego promienia: znajdź najbliższe trafienie (obiekt lub granica)
        for g_angle, ray_dir in global_rays:
            best_t: Optional[float] = None
            best_obj_id: Optional[str] = None  # None oznacza brak obiektu (może być border)

            # Sprawdź obiekty (najbliższy spośród kandydatów dla tego ray'a)
            for geom, obj in candidates:
                t_obj = ray_intersect_moved_object(ray_origin, ray_dir, geom, eps=eps)
                if t_obj is None:
                    continue
                # akceptujemy trafienia mieszczące się w zasięgu sensora
                if eps <= t_obj <= (max_range + eps):
                    if (best_t is None) or (t_obj < best_t - eps):
                        best_t = t_obj
                        best_obj_id = obj.get_id()
                    # jeżeli t_obj jest równe best_t w granicach eps -> pozostawiamy istniejący (border later ma priorytet)

            # Sprawdź granicę świata (jeżeli podana)
            if border_box is not None:
                t_border = ray_intersect_aabb(ray_origin, ray_dir, border_box, eps=eps)
                if t_border is not None and eps < t_border <= (max_range + eps):
                    # Priorytet granicy przy równości odległości:
                    if best_t is None or (t_border < best_t - eps) or (abs(t_border - best_t) <= eps):
                        best_t = t_border
                        best_obj_id = "WORLD_BOUNDARY"

            # Jeżeli znaleziono trafienie dla tego promienia, dodaj do listy
            if best_t is not None:
                hits.append((norm_pm_pi(g_angle), float(best_t), best_obj_id))

        if not hits:
            self.last_scans = None
            return None

        hits.sort(key=lambda x: x[1])
        self.last_scans = hits
        return hits

    def clear(self):
        self.last_scans = None
        self._cached_moved = None
        self._cached_pos_theta = None
