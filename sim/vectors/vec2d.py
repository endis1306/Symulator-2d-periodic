import math
from typing import Tuple, Any


Vec = Tuple[float, float]
DEFAULT_VEC: Vec = (0.0, 0.0)

def is_vec(v: Any) -> bool:
    """
    Sprawdza, czy v jest poprawnym Vec (tuple 2-elementowa z liczbami).
    """
    return (
        isinstance(v, tuple) and
        len(v) == 2 and
        all(isinstance(x, (int, float)) for x in v)
    )

def to_vec2(*args: Any, default: Vec = DEFAULT_VEC) -> Vec:
    if len(args) == 0:
        return default

    if len(args) == 2:
        try:
            x = float(args[0])
            y = float(args[1])
            return x, y
        except (TypeError, ValueError):
            raise ValueError(f"Nie można przekonwertować argumentów {args} na float")

    if len(args) == 1:
        data = args[0]
        if isinstance(data, (list, tuple)):
            if len(data) == 2:
                try:
                    x = float(data[0])
                    y = float(data[1])
                    return x, y
                except (TypeError, ValueError):
                    raise ValueError(f"Nie można przekonwertować {data} na wektor floatów")
            else:
                raise ValueError(f"Lista/tuple musi mieć dokładnie 2 elementy, a ma {len(data)}: {data}")
        else:
            raise TypeError(f"Nieobsługiwany typ wejścia: {type(data).__name__}")

    raise TypeError(f"to_vec2() przyjmuje maksymalnie 2 argumenty (otrzymano {len(args)})")


def vec_add(a: Vec, b: Vec) -> Vec:
    return a[0] + b[0], a[1] + b[1]


def vec_sub(a: Vec, b: Vec) -> Vec:
    return a[0] - b[0], a[1] - b[1]


def vec_mul(a: Vec, s: float) -> Vec:
    return a[0] * s, a[1] * s


def vec_len(a: Vec) -> float:
    return math.hypot(a[0], a[1])


def vec_norm(a: Vec) -> Vec:
    l = vec_len(a)
    if l == 0:
        return 0.0, 0.0
    return a[0] / l, a[1] / l

def vec_dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]

def vec_cross(a: Vec, b: Vec) -> float:
    # 2D cross product scalar (x1*y2 - y1*x2)
    return a[0]*b[1] - a[1]*b[0]

# rotation utilities: angle in radians, rotates in x-y plane
def rotate_vec(v: Vec, angle: float) -> Vec:
    c = math.cos(angle)
    s = math.sin(angle)
    return v[0]*c - v[1]*s, v[0]*s + v[1]*c
def world_to_local(v: Vec, angle: float) -> Vec:
    return rotate_vec(v, -angle)

def local_to_world(v: Vec, angle: float) -> Vec:
    return rotate_vec(v, angle)

def clamp_vec(v: Vec, max_norm: float = 1.0) -> Vec:
    n = math.hypot(v[0], v[1])
    if n == 0.0:
        return v
    if n <= max_norm:
        return v
    s = max_norm / n
    return v[0] * s, v[1] * s
