from dataclasses import dataclass, field
from typing import Optional, Callable
from sim.vectors.vec2dM import *
from sim.vectors.vec2d import *
from sim.geometry.box import Box
from sim.utils.collision_helpers import segments_intersect, point_in_poly
from sim.utils.angular_helper import norm_pm_pi
# --------------------------
# SHAPES
# --------------------------

# "radial_sector", center, self.max_range, global_rays, sector_box

def moved_shape_to_dict(obj) -> dict:
    moved_shape = obj.to_moved_shape()

    t = moved_shape[0]

    if t == "circle":
        r = moved_shape[2]
        return {"type": "circle", "r": r}

    if t == "polygon":
        points = moved_shape[1]
        return {"type": "polygon", "points": points}

    if t == "radial_sector":
        max_range = moved_shape[2]
        global_rays = moved_shape[3]
        return {"type": "radial_sector", "max_range": max_range, "global_rays": global_rays}

    # [list(p) for p in points]
    return {"type": t}


@dataclass
class Shape:
    get_sync_object_positionXY: Optional[Callable[[], VecM]] = field(init=False, default=None, repr=False)
    get_sync_object_theta: Optional[Callable[[], float]] = field(init=False, default=None, repr=False)

    def sync(self, obj):
        if not callable(getattr(obj, "get_positionXY", None)):
            raise AttributeError("Object musi mieć callable get_positionXY()")

        if not callable(getattr(obj, "get_theta", None)):
            raise AttributeError("Object musi mieć callable get_theta()")

        self.get_sync_object_positionXY = obj.get_positionXY
        self.get_sync_object_theta = obj.get_theta

    @property
    def local_shape(self):
        raise NotImplementedError
    def moved(self) -> Any:
        raise NotImplementedError


@dataclass
class Circle(Shape):
    r: float

    def __post_init__(self):
        if not isinstance(self.r, (float, int)):
            raise TypeError(f"Promień musi być liczbą a jest typu {type(self.r).__name__} (wartość: {self.r})")
        if self.r <= 0:
            raise ValueError(f"Promień musi być dodatni, a podano {self.r}.")

    @property
    def local_shape(self) -> Tuple[str, float]:
        return "circle", self.r

    def moved(self) -> Tuple[str, VecM, float, Box]:
        pos: VecM = self.get_sync_object_positionXY()
        box: Box = Box.from_circle(pos, self.r)
        return "circle", pos, self.r, box


@dataclass
class Polygon(Shape):
    points: List[Vec] = field(default_factory=list)
    points_quantity: int = field(init=False)

    def __post_init__(self):

        try:
            self.points = [to_vec2(point) for point in self.points]
        except (TypeError, ValueError) as e:
            raise TypeError(f"Nie można przekonwertować wszystkich punktów na wektory: {e}.") from e

        self.points_quantity = len(self.points)

        if self.points_quantity < 3:
            raise ValueError(f"Wielokąt musi mieć co najmniej 3 wierzchołki, a ma {self.points_quantity}.")


        self._validate_and_ensure_ccw()


    def _validate_and_ensure_ccw(self, eps: float = 1e-9):
        """
        Waliduje, czy punkty tworzą poprawny wielokąt prosty,
        zapewnia kolejność CCW i sprawdza, czy wielokąt zawiera (0,0).
        Uwzględnia:
        1. Samoprzecięcia segmentów.
        2. Sprawdzanie współliniowości sąsiednich wektorów.
        3. Punkt (0,0) w wielokącie.
        3. Orientację i CCW.
        """
        n = self.points_quantity
        points = self.points


        # --- Krok 1: samoprzecięcia ---
        for i in range(n):
            p1, q1 = points[i], points[(i + 1) % n]
            for j in range(i + 2, n):
                if j == n - 1 and i == 0:
                    continue
                p2, q2 = points[j], points[(j + 1) % n]
                if segments_intersect(p1, q1, p2, q2, eps):
                    raise ValueError(f"Samoprzecięcie: {p1}-{q1} przecina {p2}-{q2}")


        # --- Krok 2: Sprawdzanie współliniowości ---
        for i in range(n):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % n]
            p3 = self.points[(i + 2) % n]

            v1 = vec_sub(p2, p1)
            v2 = vec_sub(p3, p1)

            if abs(vec_cross(v1, v2)) < 1e-9:
                raise ValueError(f"Wielokąt zawiera współliniowe, kolejne punkty: {p1}, {p2}, {p3}.")

        # --- Krok 3: Sprawdzenie, czy punkt (0,0) jest wewnątrz ---
        origin = to_vec2(0.0, 0.0)
        if not point_in_poly(origin, points):
            raise ValueError("Zdefiniowany wielokąt musi zawierać punkt (0,0) w swojej przestrzeni lokalnej.")


        # --- Krok 4: Gwarancja porządku CCW (pierwszy trójkąt względem środka) ---
        p0 = to_vec2(points[0])
        p1 = to_vec2(points[1])
        first_cross = vec_cross(vec_sub(p0, origin), vec_sub(p1, origin))

        if first_cross < 0:
            self.points.reverse()

    @property
    def local_shape(self) -> Tuple[str, List[Vec]]:
        return "polygon", self.points

    def moved(self) -> Tuple[str, List[Vec], List[Tuple[Vec, Vec]], Box]:
        pos: VecM = self.get_sync_object_positionXY()
        theta: float = self.get_sync_object_theta()

        c = math.cos(theta)
        s = math.sin(theta)

        global_points: List[Vec] = []
        for lx, ly in self.points:
            rx = c * lx - s * ly
            ry = s * lx + c * ly
            gx = pos[0] + rx
            gy = pos[1] + ry
            global_points.append(to_vec2(gx, gy))

        # zrób segmenty z global_points (pojedyncze przejście)
        global_edges: List[Tuple[Vec, Vec]] = []
        n = len(global_points)
        for i in range(n):
            global_edges.append((global_points[i], global_points[(i + 1) % n]))

        box: Box = Box.from_points(global_points)
        return "polygon", global_points, global_edges, box


# typ pomocniczy
RayData = Tuple[float, Vec]

@dataclass
class RadialSector(Shape):
    rays_count: int
    max_range: float
    fov: float
    offset_theta: float = 0.0

    local_rays: List[RayData] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):

        if not isinstance(self.rays_count, int):
            raise TypeError("rays_count musi być liczbą całkowitą")
        if self.rays_count < 1:
            raise ValueError("rays_count musi być >= 1")

        if not isinstance(self.max_range, (int, float)):
            raise TypeError("max_range musi być liczbą")
        if self.max_range <= 0:
            raise ValueError("max_range musi być dodatnie")

        if not isinstance(self.fov, (int, float)):
            raise TypeError("fov musi być liczbą (float)")

        if not (0.0 <= self.fov <= 2*math.pi):
            raise ValueError("fov musi być w zakresie [0, 2π]")

        if not isinstance(self.offset_theta, (int, float)):
            raise TypeError("offset_theta musi być liczbą (float)")

        if not (-math.pi <= self.offset_theta <= math.pi):
            raise ValueError("offset_theta musi być w zakresie [-π, π]")

        self._precompute_local()

    def _precompute_local(self):
        """Prekomputuje lokalne promienie (kąt i wektor jednostkowy)."""
        self.local_rays.clear()
        start = self.offset_theta - (self.fov / 2.0)
        step = self.fov / (self.rays_count - 1) if self.rays_count > 1 else 0.0

        for i in range(self.rays_count):
            angle = start + i * step
            dx = math.cos(angle)
            dy = math.sin(angle)
            self.local_rays.append((angle, (dx, dy)))

    @property
    def local_angle_span(self):
        angle_start = norm_pm_pi(self.offset_theta - self.fov / 2.0)
        angle_end = norm_pm_pi(self.offset_theta + self.fov / 2.0)
        return angle_start, angle_end

    @property
    def local_shape(self) -> Tuple[str, float, float, float]:
        angle_start, angle_end = self.local_angle_span
        return "radial_sector", self.max_range, angle_start, angle_end


    def get_global_angle_span(self) -> Tuple[float, float]:
        """
        Zwraca (angle_start, angle_end) sektora w układzie globalnym.

        Uwzględnia:
        - orientację obiektu (parent theta)
        - offset sensora
        - FOV

        Renderer powinien korzystać z tej funkcji zamiast global_rays.
        """
        if self.get_sync_object_theta is None:
            raise RuntimeError("RadialSector nie jest zsynchronizowany. Wywołaj .sync(simobj).")

        parent_theta = self.get_sync_object_theta()

        angle_start = norm_pm_pi(parent_theta + self.offset_theta - (self.fov / 2.0))
        angle_end = norm_pm_pi(parent_theta + self.offset_theta + (self.fov / 2.0))

        return angle_start, angle_end


    def moved(self) -> Tuple[ str, 'VecM', float, List[RayData], 'Box' ]:
        """
        Zwraca (global_center, global_rays, sector_box).
        global_rays: lista (global_angle, (rx,ry)) gdzie (rx,ry) to zrotowany wektor jednostkowy.
        """
        # korzystamy z pól ustawionych przez Shape.sync(...)
        if self.get_sync_object_positionXY is None or self.get_sync_object_theta is None:
            raise RuntimeError("RadialSector nie jest zsynchronizowany. Wywołaj .sync(simobj) na instancji.")

        center = self.get_sync_object_positionXY()  # VecM
        parent_theta = self.get_sync_object_theta()

        c = math.cos(parent_theta)
        s = math.sin(parent_theta)

        global_rays: List[RayData] = []
        for local_angle, (lx, ly) in self.local_rays:
            g_angle = local_angle + parent_theta
            # rotacja wektora kierunkowego do układu globalnego
            rx = lx * c - ly * s
            ry = lx * s + ly * c
            global_rays.append((g_angle, (rx, ry)))

        global_start, global_end = self.get_global_angle_span()
        sector_box = Box.from_radial_sector(center, self.max_range, global_start, global_end)

        return "radial_sector",center, self.max_range, global_rays, sector_box
