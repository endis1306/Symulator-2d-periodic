from typing import TextIO
from sim.utils.logger import Logger
from sim.core.world import World


def build_logger(filename: str, world: World, mode: str = "w", encoding: str = "utf-8") -> Logger:

    if not hasattr(world, "serialize_init") or not callable(getattr(world, "serialize_init")):
        raise AttributeError(f"World musi mieć callable 'serialize_init' wymagany przez Logger.")

    if not hasattr(world, "serialize") or not callable(getattr(world, "serialize")):
        raise AttributeError(f"World musi mieć callable 'serialize' wymagany przez Logger.")

    f: TextIO = open(filename, mode, encoding=encoding, buffering=1) # type: ignore
    try:
        get_serialize_init = getattr(world, "serialize_init")
        get_state = getattr(world, "serialize")

        logger = Logger(
            file=f,
            get_serialize_init = get_serialize_init,
            get_state=get_state,
            filename=filename,
            _own_file=True,
        )
    except Exception as e:
        try:
            f.close()
        except Exception:
            pass
        raise RuntimeError(f"Błąd podczas tworzenia Loggera: {e}") from e

    return logger
