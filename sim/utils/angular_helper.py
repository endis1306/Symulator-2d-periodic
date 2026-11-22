import math

TAU = 2 * math.pi

def norm_pm_pi(a: float) -> float:
    """Normalize angle to (-pi, pi]."""
    x = (a + math.pi) % TAU - math.pi
    if abs(x + math.pi) < 1e-12:
        return math.pi
    return x

def norm_0_2pi(a: float) -> float:
    """Normalize angle to [0, 2*pi)."""
    return a % TAU

def angle_diff(a: float, b: float) -> float:
    """Shortest signed angular difference a-b in (-pi, pi]."""
    return norm_pm_pi(a - b)

def almost_equal(a: float, b: float, eps=1e-12) -> bool:
    return abs(norm_pm_pi(a - b)) <= eps
