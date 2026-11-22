# --------------------------
# Collision helpers
# --------------------------
from typing import List, Optional, Union

from sim.geometry.box import Box
from sim.vectors.vec2d import *

Edge = Tuple[Vec, Vec]

def ray_intersect_aabb(ray_origin, ray_dir, box, eps: float = 1e-9) -> Optional[float]:
    """
    Zoptymalizowana wersja Ray vs AABB.
    - Używa metody "Slab".
    - Obsługuje dzielenie przez zero (nieskończoność).
    - eps: tolerancja numeryczna
    """
    ox, oy = ray_origin
    dx, dy = ray_dir

    inv_dx = 1.0 / dx if abs(dx) > eps else float('inf')
    inv_dy = 1.0 / dy if abs(dy) > eps else float('inf')

    t1 = (box.minx - ox) * inv_dx
    t2 = (box.maxx - ox) * inv_dx
    t3 = (box.miny - oy) * inv_dy
    t4 = (box.maxy - oy) * inv_dy

    tmin = max(min(t1, t2), min(t3, t4))
    tmax = min(max(t1, t2), max(t3, t4))

    if tmax < 0 or tmin > tmax:
        return None

    return tmax if tmin < 0 else tmin


"""
dx, dy = ray_dir

    dlen = math.hypot(dx, dy)
    if dlen < eps:
        raise ValueError("ray_dir zero")
"""


def ray_intersect_moved_object(
    ray_origin: Vec,
    ray_dir: Vec,
    moved_object: Union[Tuple[str, Box], Tuple[str, Vec, float], Tuple[str, List[Vec], List[Edge]]],
    eps: float = 1e-9
) -> Optional[float]:

    """
    Oblicza przecięcie promienia z moved obiektem (Circle lub Polygon).
    moved_object: wynik moved() bez ostatniego Boxa
        - Circle: ("circle", center: Vec, radius: float)
        - Polygon: ("poly", points: List[Vec], edges: List[Edge])
    Zwraca najbliższą odległość t od ray_origin lub None jeśli brak trafienia.
    """

    obj_type = moved_object[0]

    if obj_type == "circle":
        _, center, radius = moved_object
        return ray_intersect_circle(ray_origin, ray_dir, center, radius, eps=eps)
    elif obj_type == "polygon":
        _, points, edges = moved_object
        return ray_intersect_polygon(ray_origin, ray_dir, points, edges, eps=eps)
    else:
        raise TypeError(f"Nieobsługiwany typ obiektu moved: {obj_type}")


def ray_intersect_circle(
    ray_origin: Vec,
    ray_dir: Vec,
    center: Vec,
    radius: float,
    eps: float = 1e-9
) -> Optional[float]:
    if radius <= 0:
        raise ValueError("radius musi być dodatni")

    Lx, Ly = center[0] - ray_origin[0], center[1] - ray_origin[1]
    dx, dy = ray_dir

    tca = Lx * dx + Ly * dy
    if tca <= eps:
        return None
    d2 = Lx*Lx + Ly*Ly - tca*tca
    if d2 > radius*radius:
        return None
    t0 = tca - math.sqrt(max(0.0, radius*radius - d2))
    return t0 if t0 > eps else None

"""
dlen = vec_len(ray_dir)
    if dlen <= eps:
        raise ValueError("ray_dir nie może być zerowy")
"""

def ray_intersect_polygon(
    ray_origin: Vec,
    ray_dir: Vec,
    poly_points: List[Vec],
    poly_edges: List[Edge],
    eps: float = 1e-9
) -> Optional[float]:
    dx, dy = ray_dir
    rx, ry = ray_origin

    # jeśli początek wewnątrz -> brak "zewnętrznego" trafienia
    if point_in_poly((rx, ry), poly_points):
        return None

    closest = float("inf")
    hit = False
    for (x1, y1), (x2, y2) in poly_edges:
        sx, sy = x2 - x1, y2 - y1
        det = dx * sy - dy * sx
        if abs(det) <= eps:
            continue
        qx, qy = x1 - rx, y1 - ry
        t = (qx * sy - qy * sx) / det
        u = (qx * dy - qy * dx) / det
        if eps < t < closest and -eps <= u <= 1.0 + eps:
            closest = t; hit = True

    return closest if hit else None


"""
dlen = vec_len(ray_dir)
    if dlen <= eps:
        raise ValueError("ray_dir nie może być zerowy")
    dx, dy = ray_dir[0] / dlen, ray_dir[1] / dlen
"""

'''
def aabb_aabb_collision(a_minx: float, a_minz: float, a_maxx: float, a_maxz: float,
                        b_minx: float, b_minz: float, b_maxx: float, b_maxz: float) -> bool:
    return not (a_maxx < b_minx or b_maxx < a_minx or a_maxz < b_minz or b_maxz < a_minz)
'''
def circle_circle_collision(c1_pos: Vec, c1_r: float, c2_pos: Vec, c2_r: float, eps: float = 1e-9) -> bool:
    return vec_len(vec_sub(c1_pos, c2_pos)) <= (c1_r + c2_r + eps)


# SAT for convex polygons (and polygon vs polygon or polygon vs aabb by converting aabb to poly)
def project_polygon(axis: Vec, points: List[Vec]) -> Tuple[float, float]:
    dots: List[float] = [axis[0] * p[0] + axis[1] * p[1] for p in points]
    return min(dots), max(dots)


def axis_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    return not (a_max < b_min or b_max < a_min)


# generic collision between two moved shape descriptions:
def shapes_collide(s1: Tuple[Any, ...], s2: Tuple[Any, ...]) -> bool:
    t1: str = s1[0]
    t2: str = s2[0]

    box1: Box = s1[-1]
    box2: Box = s2[-1]

    if t1 == "circle" and t2 == "circle":
        return circle_circle_collision(s1[1], s1[2], s2[1], s2[2])
    if t1 == "polygon" and t2 == "polygon":
        if not box1.intersects(box2):
            return False
        return polygon_polygon_collision(s1[1], s1[2], s2[1], s2[2])
    if t1 == "circle" and t2 == "polygon":
        if not box1.intersects(box2):
            return False
        return circle_polygon_collision(s1[1], s1[2], s2[1], s2[2])
    if t2 == "circle" and t1 == "polygon":
        if not box1.intersects(box2):
            return False
        return circle_polygon_collision(s2[1], s2[2], s1[1], s1[2])
    return False

def check_vertices_on_nonadjacent_edges(points: List[Vec], eps: float = 1e-9):
    n = len(points)
    for i in range(n):
        v = points[i]
        for j in range(n):
            # nie sprawdzamy sąsiadów i samego segmentu
            if j in [(i - 1) % n, i, (i + 1) % n]:
                continue
            a = points[j]
            b = points[(j + 1) % n]
            if _point_on_segment(v, a, b, eps):
                raise ValueError(f"Wierzchołek {v} leży na nie-sąsiedniej krawędzi {a}-{b}.")


def _point_on_segment(p: Vec, a: Vec, b: Vec, eps: float = 1e-9) -> bool:
    px, py = p
    ax, ay = a
    bx, by = b

    # sprawdzanie kolinearności
    if abs(vec_cross(vec_sub(b, a), vec_sub(p, a))) > eps:
        return False

    # test bounding-box
    if (min(ax, bx) - eps <= px <= max(ax, bx) + eps and
        min(ay, by) - eps <= py <= max(ay, by) + eps):
        return True

    return False

def point_in_local_shape(pt: Vec, local_shape, eps: float = 1e-9) -> bool:
    t = local_shape[0]

    if t == "circle":
        _, radius = local_shape
        return point_in_circle(pt, to_vec2(), radius, eps)

    if t == "polygon":
        _, points = local_shape
        return point_in_poly(pt, points)

    raise TypeError(f"Nieobsługiwany typ kształtu: {t}")

def point_in_shape(pt: Vec, shape, eps: float = 1e-9) -> bool:
    t = shape[0]

    if t == "circle":
        _, center, radius = shape[:3]
        return point_in_circle(pt, center, radius, eps)

    if t == "polygon":
        _, points, _ = shape[:3]
        return point_in_poly(pt, points)

    raise TypeError(f"Nieobsługiwany typ kształtu: {t}")


def point_in_circle(
    pt: Vec,
    center: Vec,
    radius: float,
    eps: float = 1e-9
) -> bool:

    if radius <= 0:
        raise ValueError("radius musi być dodatni")

    return vec_len(vec_sub(pt, center)) <= radius + eps

# Winding Number
def point_in_poly(pt: Vec, poly: List[Vec]) -> bool:

    x0, y0 = pt
    n = len(poly)


    for i in range(n):
        a = to_vec2(poly[i])
        b = to_vec2(poly[(i + 1) % n])
        if _point_on_segment(pt, a, b):
            return True

    wn = 0

    for i in range(n):
        a = to_vec2(poly[i])
        b = to_vec2(poly[(i + 1) % n])

        if a[-1] <= y0:
            if b[-1] > y0:
                if vec_cross(vec_sub(b, a), vec_sub(pt, a)) > 0:
                    wn += 1
        else:
            if b[-1] <= y0:
                if vec_cross(vec_sub(b, a), vec_sub(pt, a)) < 0:
                    wn -= 1

    return wn != 0


def circle_polygon_collision(center: Vec, r: float, points: List[Vec], segments: List[Tuple[Vec, Vec]], eps: float = 1e-9) -> bool:
    cx, cy = center

    if point_in_poly((cx, cy), points):
        return True

    for a, b in segments:
        if dist_point_segment((cx, cy), a, b) <= r + eps:
            return True

    return False


def dist_point_segment(p: Vec, a: Vec, b: Vec) -> float:
    pax, pay = p[0] - a[0], p[1] - a[1]
    bax, bay = b[0] - a[0], b[1] - a[1]
    denom = bax * bax + bay * bay
    if denom == 0:
        return vec_len(vec_sub(p, a))
    t = (pax * bax + pay * bay) / denom
    t = max(0.0, min(1.0, t))
    proj = (a[0] + bax * t, a[1] + bay * t)
    return vec_len(vec_sub(p, proj))

def segments_intersect(p1, q1, p2, q2, eps=1e-9):
    """
    Sprawdza, czy segmenty p1q1 i p2q2 się przecinają.
    """
    r = vec_sub(q1, p1)
    s = vec_sub(q2, p2)
    r_cross_s = vec_cross(r, s)
    q_minus_p = vec_sub(p2, p1)

    if abs(r_cross_s) < eps:
        if abs(vec_cross(q_minus_p, r)) > eps:
            return False

        r2 = vec_dot(r, r)
        if r2 == 0: return False

        t0 = vec_dot(q_minus_p, r) / r2
        t1 = t0 + vec_dot(s, r) / r2

        t_min = min(t0, t1)
        t_max = max(t0, t1)

        return t_max >= -eps and t_min <= 1 + eps

    # Przypadek nie-równoległy
    t = vec_cross(q_minus_p, s) / r_cross_s
    u = vec_cross(q_minus_p, r) / r_cross_s

    return (-eps <= t <= 1 + eps) and (-eps <= u <= 1 + eps)


def polygon_polygon_collision(
    poly1_points: List[Vec],
    poly1_segments: List[Tuple[Vec, Vec]],
    poly2_points: List[Vec],
    poly2_segments: List[Tuple[Vec, Vec]],
    eps: float = 1e-9
) -> bool:

    for a1, b1 in poly1_segments:
        for a2, b2 in poly2_segments:
            if segments_intersect(a1, b1, a2, b2, eps):
                return True

    if point_in_poly(poly1_points[0], poly2_points):
        return True

    if point_in_poly(poly2_points[0], poly1_points):
        return True

    return False
