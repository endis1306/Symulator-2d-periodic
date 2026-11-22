# tests/test_rotor.py
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest  # ✅ konieczne dla pytest.raises i pytest.approx
import math

from sim.systems.engines.rotor import Rotor
from sim.vectors.vec2d import to_vec2


def test_rotor_valid_creation():
    r = Rotor(
        id="r1",
        rotor_omega_max=10.0,
        tau_motor=0.5,
        k_thrust=2.0,
        angle_offset=0.0,
        position_local=to_vec2(1.0, 0.0),
    )
    assert r.id == "r1"
    assert r.rotor_omega == 0.0


def test_rotor_invalid_id():
    with pytest.raises(TypeError):
        Rotor(
            id=123,  # ❌
            rotor_omega_max=10,
            tau_motor=1,
            k_thrust=1,
            angle_offset=0,
            position_local=to_vec2(0, 0),
        )


def test_rotor_invalid_params():
    with pytest.raises(ValueError):
        Rotor(
            id="r",
            rotor_omega_max=-1,  # ❌
            tau_motor=1,
            k_thrust=1,
            angle_offset=0,
            position_local=to_vec2(0, 0),
        )


def test_rotor_update_dynamics():
    r = Rotor(
        id="r",
        rotor_omega_max=10,
        tau_motor=1.0,
        k_thrust=1.0,
        angle_offset=0,
        position_local=to_vec2(0, 0),
    )

    r.update(omega_cmd=10, dt=1.0)
    assert 0 < r.rotor_omega < 10  # dynamika I rzędu


def test_rotor_update_zero_dt():
    r = Rotor(id="r", rotor_omega_max=10, tau_motor=1.0, k_thrust=1.0, angle_offset=0, position_local=to_vec2(0,0))
    old_omega = r.rotor_omega
    r.update(omega_cmd=5.0, dt=0.0)
    assert r.rotor_omega == old_omega  # dt=0 nie zmienia stanu


def test_rotor_thrust():
    r = Rotor(
        id="r",
        rotor_omega_max=10,
        tau_motor=0,
        k_thrust=2.0,
        angle_offset=0,
        position_local=to_vec2(0, 0),
    )
    r.update(5.0, 0.1)
    assert r.thrust() == pytest.approx(2.0 * 25.0)


def test_rotor_thrust_with_offset():
    # Sprawdź, czy kąt offsetu nie psuje wartości siły
    r = Rotor(
        id="r",
        rotor_omega_max=10,
        tau_motor=0,
        k_thrust=1.0,
        angle_offset=math.pi/4,
        position_local=to_vec2(0, 0),
    )
    r.update(2.0, 0.1)
    expected = 1.0 * (2.0**2)
    assert r.thrust() == pytest.approx(expected)


def test_rotor_max_omega():
    # Przekroczenie omega_max nie może być możliwe
    r = Rotor(id="r", rotor_omega_max=5, tau_motor=0.1, k_thrust=1.0, angle_offset=0, position_local=to_vec2(0,0))
    r.update(10.0, dt=1.0)
    assert r.rotor_omega <= r.rotor_omega_max


def test_rotor_negative_tau_motor():
    # tau_motor < 0 powinno rzucić ValueError
    with pytest.raises(ValueError):
        Rotor(id="r", rotor_omega_max=5, tau_motor=-1.0, k_thrust=1.0, angle_offset=0, position_local=to_vec2(0,0))


# === Sekcja uruchamiania testów bezpośrednio ===
if __name__ == "__main__":
    # Wywołaj pytest na tym pliku
    import sys
    sys.exit(pytest.main([__file__]))
