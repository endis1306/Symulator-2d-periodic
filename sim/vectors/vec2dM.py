import math
from typing import List, Any

# Vec semantics: [x, y] — mutowalna lista dwóch wartości float
VecM = List[float]  # mutowalny wektor 2D

def is_vecM(v: Any) -> bool:
    """
    Sprawdza, czy v jest poprawnym VecM (lista 2-elementowa z liczbami).
    """
    return (
        isinstance(v, list) and
        len(v) == 2 and
        all(isinstance(x, (int, float)) for x in v)
    )

def to_vec2M(*args) -> VecM:

    if len(args) == 0:
        return [0.0, 0.0]

    if len(args) == 1:
        data = args[0]
        if isinstance(data, (list, tuple)):
            if len(data) == 2:
                return [float(data[0]), float(data[1])]
            else:
                raise ValueError("Lista/tuple musi mieć 2 elementy.")
        raise TypeError(f"Nieobsługiwany typ wejścia: {type(data).__name__}")

    if len(args) == 2:
        return [float(args[0]), float(args[1])]

    raise TypeError("to_vec2M() przyjmuje maksymalnie 2 argumenty.")


def vec_addM(a: VecM, b: VecM) -> VecM:
    return [a[0] + b[0], a[1] + b[1]]


def vec_subM(a: VecM, b: VecM) -> VecM:
    return [a[0] - b[0], a[1] - b[1]]


def vec_mulM(a: VecM, s: float) -> VecM:
    return [a[0] * s, a[1] * s]


def vec_lenM(a: VecM) -> float:
    return math.hypot(a[0], a[1])


def vec_normM(a: VecM) -> VecM:
    l = vec_lenM(a)
    if l == 0:
        return [0.0, 0.0]
    return [a[0] / l, a[1] / l]


def vec_dotM(a: VecM, b: VecM) -> float:
    return a[0] * b[0] + a[1] * b[1]


def vec_crossM(a: VecM, b: VecM) -> float:
    # 2D cross product scalar (x1*y2 - y1*x2)
    return a[0] * b[1] - a[1] * b[0]


# rotation utilities: angle in radians, rotates in x-y plane
def rotate_vecM(v: VecM, angle: float) -> VecM:
    c = math.cos(angle)
    s = math.sin(angle)
    return [v[0] * c - v[1] * s, v[0] * s + v[1] * c]


def world_to_localM(v: VecM, angle: float) -> VecM:
    return rotate_vecM(v, -angle)


def local_to_worldM(v: VecM, angle: float) -> VecM:
    return rotate_vecM(v, angle)

def clamp_vec(v: VecM, max_norm: float = 1.0) -> VecM:
    n = math.hypot(v[0], v[1])
    if n == 0.0:
        return v
    if n <= max_norm:
        return v
    s = max_norm / n
    return [v[0] * s, v[1] * s]
