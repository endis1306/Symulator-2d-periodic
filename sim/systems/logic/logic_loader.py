import importlib
import inspect
from types import ModuleType
from typing import Callable, Any, Mapping


LogicFn = Callable[[Any, Any], Any]


def load_logic_function(params: Mapping[str, Any]) -> LogicFn:
    """
    Ładuje funkcję logiki sensora z przestrzeni projektu.

    Wymagany kontrakt funkcji:
        fn(arg1, arg2)

    - dokładnie 2 argumenty pozycyjne
    - brak *args i **kwargs
    """

    module_name = params.get("logic_module")
    func_name = params.get("logic_function")

    # --- walidacja parametrów ---
    if not isinstance(module_name, str) or not module_name:
        raise RuntimeError("Parametr 'logic_module' musi być niepustym stringiem")

    if not isinstance(func_name, str) or not func_name:
        raise RuntimeError("Parametr 'logic_function' musi być niepustym stringiem")

    # --- import modułu ---
    try:
        module: ModuleType = importlib.import_module(module_name)
    except ImportError as e:
        raise RuntimeError(
            f"Nie można zaimportować modułu '{module_name}'"
        ) from e

    # --- pobranie funkcji ---
    try:
        func = getattr(module, func_name)
    except AttributeError as e:
        raise RuntimeError(
            f"Moduł '{module_name}' nie zawiera symbolu '{func_name}'"
        ) from e

    # --- callable ---
    if not callable(func):
        raise RuntimeError(
            f"'{func_name}' z modułu '{module_name}' nie jest wywoływalny"
        )

    # --- WALIDACJA KONTRAKTU ---
    sig = inspect.signature(func)
    params = sig.parameters.values()

    positional = [
        p for p in params
        if p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]

    forbidden = [
        p for p in params
        if p.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    ]

    if forbidden:
        names = ", ".join(p.name for p in forbidden)
        raise RuntimeError(
            f"Funkcja '{func_name}' nie może używać *args/**kwargs (znaleziono: {names})"
        )

    if len(positional) != 3:
        raise RuntimeError(
            f"Funkcja '{func_name}' musi przyjmować dokładnie 2 argumenty pozycyjne "
            f"(znaleziono {len(positional)})"
        )

    return func
