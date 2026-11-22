from sim.systems.engines.rotor import Rotor
from sim.vectors.vec2d import to_vec2


def build_rotor(defn: dict, idx: int = 0) -> Rotor:
    if not isinstance(defn, dict):
        raise TypeError(f"Rotor {idx}: definicja musi być dict")

    try:
        return Rotor(
            id=str(defn.get("id", "Rot")).strip(),
            rotor_omega_max=float(defn.get("rotor_omega_max", 0.0)),
            tau_motor=float(defn.get("tau_motor", 0.1)),
            k_thrust=float(defn.get("k_thrust", 0.0)),
            angle_offset=float(defn.get("angle_offset", 0.0)),
            position_local=to_vec2(defn.get("position_local", to_vec2())),
        )
    except Exception as e:
        raise ValueError(f"Błąd w definicji Rotor {idx}: {e}") from e
