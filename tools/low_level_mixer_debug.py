# low_level_mixer_debug.py

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

# ============================================================
# AUTOMATYCZNE USTAWIENIE ROOT
# ============================================================
def _find_project_root(start: Path) -> Path:
    for p in (start, *start.parents):
        if (p / "pyproject.toml").exists():
            return p
    # fallback: katalog nadrzędny wobec tools/
    return start.parents[1]

PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
# IMPORT FUNKCJI DO TESTÓW
# ============================================================
from sim.systems.engines.low_level_control import debug_low_level_control

# ============================================================
# MOCK / VIEW
# ============================================================
VecM = Tuple[float, float]

@dataclass
class EngineMock:
    position: VecM          # (x, y)
    thrust_dir: VecM        # unit vector
    k_thrust: float
    omega_max: float

EngineControlView = EngineMock

# ============================================================
# TESTY (pytest)
# ============================================================
def _default_engines():
    return [
        EngineMock(position=(-1, 0), thrust_dir=(0, 1), k_thrust=1e-4, omega_max=500),
        EngineMock(position=(+1, 0), thrust_dir=(0, 1), k_thrust=1e-4, omega_max=500),
    ]

def test_pure_thrust():
    r = debug_low_level_control((0, 0), _default_engines(), 0.5, 0.0)
    assert abs(r["tau_actual"]) < 1e-6
    assert abs(r["T_actual"] - r["T_cmd"]) < 1e-6

def test_yaw_positive():
    r = debug_low_level_control((0, 0), _default_engines(), 0.2, 0.6)
    assert r["tau_actual"] > 0.0

def test_yaw_negative():
    r = debug_low_level_control((0, 0), _default_engines(), 0.2, -0.6)
    assert r["tau_actual"] < 0.0

def test_yaw_without_thrust():
    r = debug_low_level_control((0, 0), _default_engines(), 0.0, 1.0)
    assert abs(r["tau_actual"]) < 1e-9
    assert abs(r["T_actual"]) < 1e-9

# ============================================================
# URUCHOMIENIE TESTÓW
# ============================================================
if __name__ == "__main__":
    import pytest

    print(f"[DEBUG] PROJECT_ROOT = {PROJECT_ROOT}")

    # -q → cicho, -x → stop na pierwszym błędzie
    sys.exit(pytest.main([
        __file__,
        "-q"
    ]))
