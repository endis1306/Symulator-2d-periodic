from sim.systems.engines.engines_control import EnginesControl
from sim.builders.rotor_builder import Rotor, build_rotor

def build_engines_control(obj_def: dict) -> EnginesControl:
    try:
        engines_def = obj_def.get("engines")

        if engines_def is None:
            return EnginesControl()

        if not isinstance(engines_def, list):
            raise TypeError("Sekcja 'engines' musi być listą")


        if len(engines_def) == 0:
            return EnginesControl()

        if len(engines_def) == 1:
            raise ValueError("Wymagane 0 lub >= 2 silniki")

        engines: list[Rotor] = []
        ids_seen: set[str] = set()

        for idx, r_def in enumerate(engines_def):
            if not isinstance(r_def, dict):
                raise TypeError(f"engines[{idx}] musi być dict")

            try:
                engine = build_rotor(r_def, idx)
            except Exception as e:
                sid = r_def.get("id")
                ctx = f"index={idx}"
                if isinstance(sid, str) and sid:
                    ctx += f", id='{sid}'"
                raise ValueError(f"Błąd podczas budowy silnika ({ctx}): {e}") from e

            if engine.id in ids_seen:
                raise ValueError(f"Zduplikowane id silnika: '{engine.id}'")
            ids_seen.add(engine.id)

            engines.append(engine)

        return EnginesControl(engines=engines)

    except Exception as e:
        raise RuntimeError(f"Nie udało się zbudować EnginesControl: {e}") from e
