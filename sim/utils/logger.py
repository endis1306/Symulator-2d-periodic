import json
import sys
from dataclasses import dataclass, field
from typing import Callable, Any, TextIO, Optional, Dict
import io


@dataclass
class Logger:
    file: TextIO
    get_serialize_init: Callable[[], Dict[str, Any]]
    get_state: Callable[[], Dict[str, Any]]

    filename: Optional[str] = None
    _own_file: bool = field(default=False, repr=False)

    def __post_init__(self):
        if not callable(self.get_serialize_init):
            raise TypeError("serialize_init musi być callable.")

        if not callable(self.get_state):
            raise TypeError("get_state musi być callable.")

        if not hasattr(self.file, "write") or not callable(self.file.write):
            raise TypeError("Podany obiekt 'file' nie jest zapisywalnym strumieniem (brak write).")

        if isinstance(self.file, io.TextIOBase):
            mode = getattr(self.file, "mode", "")
            if mode and not any(ch in mode for ch in ("w", "a", "+")):
                raise ValueError(f"Plik '{self.filename or ''}' nie wydaje się być w trybie zapisu (mode={mode}).")


    def log_init(self) -> None:
        data = self.get_serialize_init()
        try:
            self.file.write(json.dumps(data) + "\n")
            self.file.flush()
        except Exception as e:
            print(f"[Logger] Błąd logowania eventu: {e}", file=sys.stderr)


    def next_log(self) -> None:
        state = self.get_state()
        try:
            self.file.write(json.dumps(state) + "\n")
            self.file.flush()
        except Exception as e:
            print(f"[Logger] Błąd podczas zapisu logu: {type(e).__name__}: {e}", file=sys.stderr)

    def close(self) -> None:
        if self._own_file and hasattr(self.file, "close") and not self.file.closed:
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
