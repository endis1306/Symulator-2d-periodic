import json
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from tqdm import tqdm

from sim.builders.build_world import build_world
from sim.core.world import World
from sim.builders.logger_builder import build_logger

# --------------------------
# Simulation runner
# --------------------------

def choose_config_file() -> Optional[str]:
    # tkinter importowany dopiero tutaj, aby symulacja działała też bez GUI (headless)
    import tkinter as tk
    from tkinter import filedialog
    try:
        root = tk.Tk()
        root.withdraw()
        path: str = filedialog.askopenfilename(
            title="Wybierz plik konfiguracyjny (JSON)",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        if not path:
            return None
        return path
    except tk.TclError as e:
        raise RuntimeError(f"Błąd przy otwieraniu dialogu pliku: {e}")
    except Exception as e:
        raise RuntimeError(f"Nieoczekiwany błąd przy wyborze pliku: {e}")

def load_config(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg: Dict[str, Any] = json.load(f)
        return cfg
    except FileNotFoundError:
        raise RuntimeError(f"Plik konfiguracyjny '{path}' nie istnieje.")
    except PermissionError:
        raise RuntimeError(f"Brak uprawnień do odczytu pliku '{path}'.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Błąd parsowania JSON w pliku '{path}': {e}")
    except Exception as e:
        raise RuntimeError(f"Nieoczekiwany błąd przy wczytywaniu pliku '{path}': {e}")

def get_simulation_parameters(cfg: Dict[str, Any]) -> Tuple[str, int]:

    if "log_file" not in cfg:
        raise ValueError("Brak parametru 'log_file' w konfiguracji.")

    log_file = cfg["log_file"]

    if not isinstance(log_file, str):
        raise TypeError(f"Parametr 'log_file' musi być typu str, a jest {type(log_file).__name__}.")
    if not log_file.strip():
        raise ValueError("Parametr 'log_file' nie może być pustym stringiem.")

    if "iterations" not in cfg:
        raise ValueError("Brak parametru 'iterations' w konfiguracji.")

    iterations_raw = cfg["iterations"]

    if not isinstance(iterations_raw, (int, float)):
        raise TypeError(f"Parametr 'iterations' musi być typu int (lub konwertowalny), a jest {type(iterations_raw).__name__}.")
    try:
        iterations = int(iterations_raw)
    except Exception:
        raise ValueError(f"Nie można przekonwertować parametru 'iterations' na int: {iterations_raw}")
    if iterations <= 0:
        raise ValueError(f"Parametr 'iterations' musi być dodatni, a jest {iterations}")

    return log_file, iterations

def run_simulation(cfg_path: str) -> None:
    cfg: Dict[str, Any] = load_config(cfg_path)
    log_file, iterations = get_simulation_parameters(cfg)
    world: World = build_world(cfg)
    world.sync()
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)


    with build_logger(log_file, world) as logger:


        world.check_and_destroy_initial_collisions()
        world.compute_perception()

        logger.log_init()
        logger.next_log()

        for _ in tqdm(range(iterations), desc="Symulacja"):
            finished = world.next_state()
            logger.next_log()
            if finished:
                break

if __name__ == "__main__":
    # Użycie: python simulator.py [plik_konfiguracji.json]
    # Bez argumentu otwiera okno wyboru pliku (wymaga tkinter).
    cfgpath = sys.argv[1] if len(sys.argv) > 1 else choose_config_file()
    if not cfgpath:
        print("Nie wybrano pliku konfiguracyjnego. Koniec.")
    else:
        run_simulation(cfgpath)
