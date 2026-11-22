from typing import Any


def ensure_has_interface(obj: Any, spec: dict, name: str) -> None:
    """
    spec: dict of attribute_name -> dict(callable: bool, type_check: callable|None)
    Raises TypeError/AttributeError when check fails. 'name' used in messages.
    """
    for attr, checks in spec.items():
        if not hasattr(obj, attr):
            raise TypeError(f"Pole '{name}' musi implementować '{attr}' (brak atrybutu).")
        val = getattr(obj, attr)
        if checks.get("callable", False) and not callable(val):
            raise TypeError(f"Pole '{name}': '{attr}' musi być callable.")
        type_check = checks.get("type_check")
        if type_check is not None and not type_check(val):
            raise TypeError(f"Pole '{name}': '{attr}' ma nieodpowiedni typ ({type(val).__name__}).")
