# drone-sim-2d

Własny, dwuwymiarowy symulator obiektów latających (drony z wirnikami) w Pythonie, bez zewnętrznego silnika fizyki. Powstaje jako podstawa pracy magisterskiej o wieloagentowym przechwytywaniu obiektu z użyciem PPO. Obecna wersja to symulator z logiką sterowania „goń cel” oraz odtwarzaczem zapisanych przebiegów.

## Co potrafi

- **Dynamika obiektu:** masa, moment bezwładności, anizotropowy opór liniowy (osobno wzdłuż i w poprzek kadłuba), opór obrotowy, całkowanie semi-implicit Euler (`sim/systems/physics`).
- **Napęd:** wirniki z dynamiką silnika (stała czasowa, `k_thrust`, położenie i kąt montażu), mikser sił i momentu (`sim/systems/engines`).
- **Sterowanie warstwowe:** logika (wektor zamiaru) → regulator średniego poziomu (ciąg i yaw) → mikser wirników.
- **Kształty:** okrąg i wielokąt, wykrywanie kolizji metodą SAT (`sim/geometry`, `sim/utils/collision_helpers.py`).
- **Sensory:** wiązka promieni (`RadialSector`) z raycastem do obiektów i granic świata (`sim/systems/sensors`).
- **Logika obiektów:** `static`, `seek_control` oraz `custom` (własna funkcja Pythona wskazana w konfiguracji; to miejsce na podłączenie polityki uczonej).
- **Konfiguracja:** własny język `.simdsl` konwertowany do walidowanego JSON (`DSL/`).
- **Logi:** zapis przebiegu do pliku JSON Lines (`.log.jsonl`).
- **Odtwarzacz:** `replay.py` (matplotlib + tkinter) pokazuje zapisany przebieg wraz z inspektorem obiektów.

## Struktura

```
simulator.py            uruchomienie symulacji z pliku JSON, zapis logu
dsl_to_json.py          konwersja .simdsl -> .json (z walidacją)
replay.py               odtwarzacz logów .log.jsonl
DSL/                    gramatyka, parser i walidacja konfiguracji
sim/
  core/                 World, SimObject, parametry ciała
  geometry/             kształty, Box
  systems/              physics, engines, sensors, logic
  builders/             budowanie świata i obiektów z konfiguracji
  utils/                kolizje, widoki, logger, pomocnicze
replayer/               panel inspektora i narzędzia odtwarzacza
scenarios/              scenariusze (konfiguracja + log referencyjny)
tests/                  testy jednostkowe i regresyjne
tools/                  skrypty pomocnicze
```

## Instalacja

Wymagany Python 3.10 lub nowszy. Odtwarzacz wymaga tkinter (w standardowej instalacji Pythona na Windows jest dołączony).

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Uruchomienie

```bash
# 1) (opcjonalnie) konwersja konfiguracji DSL do JSON
python dsl_to_json.py scenarios/seek_complex_scene/seek_complex_scene.simdsl scenarios/seek_complex_scene/seek_complex_scene.json

# 2) symulacja (headless), log trafia do logs/
python simulator.py scenarios/seek_complex_scene/seek_complex_scene.json

# 3) odtwarzanie przebiegu (otwiera okno wyboru pliku .jsonl)
python replay.py
```

Uruchomienie `python simulator.py` bez argumentu otwiera okno wyboru pliku konfiguracji. Skrypty uruchamiaj z katalogu głównego projektu.

## Scenariusz referencyjny: `seek_complex_scene`

Plik `scenarios/seek_complex_scene/`:

- `seek_complex_scene.simdsl` – konfiguracja w DSL,
- `seek_complex_scene.json` – ta sama konfiguracja po konwersji i walidacji,
- `seek_complex_scene.log.jsonl` – referencyjny log przebiegu (3500 kroków, `delta_t` = 0,01 s).

Świat 100 x 80: poruszający się cel (okrąg) i dwa drony z wirnikami (`seeker_A`, `seeker_B`), każdy sterowany funkcją `seek_control` z modułu `sim/systems/logic/my_module.py`, która zwraca wektor w stronę celu.

Uwaga: dalsza część trajektorii jest wrażliwa numerycznie (sprzężenie zwrotne i kolizje). Ponowne uruchomienie na innej wersji Pythona lub bibliotek może dać minimalnie inny przebieg. Test regresyjny porównuje z logiem referencyjnym tylko pierwsze kroki.

## Format konfiguracji (skrót)

```
world {
  delta_t: 0.01;
  iterations: 3500;
  boundary_point: [100, 80];          # obszar od (0,0) do (100,80)
  log_file: "logs/moj_log.jsonl";

  object "nazwa" {
    positionXY: [20, 30];
    velocityXY: [0, 0];
    theta: 0.0;  omega: 0.0;
    static: false;
    shape: circle(r = 3.0);           # lub polygon(points = [...])
    bodyParams { mass: 3.0; I: 0.35; drag_lin_forward: 0.03; drag_lin_side: 0.35; drag_rot: 0.1; }
    engines: [ rotor(id = "r1", rotor_omega_max = 80.0, tau_motor = 0.01,
                     k_thrust = 3.1e-5, angle_offset = 0.0, position_local = [0.0, 5.2]) ];
    sensors: [];
    logic: custom(logic_module = "sim.systems.logic.my_module",
                  logic_function = "seek_control", target_id = "moving_target");
  }
}
```

Pełny, działający przykład jest w `scenarios/seek_complex_scene/seek_complex_scene.simdsl`.

## Testy

```bash
pytest -q tests
pytest -q tools/low_level_mixer_debug.py
```

## Znane ograniczenia

- Kolizja niszczy obiekt (brak odbicia); obiekt całkowicie poza obszarem świata także jest niszczony.
- Świat jest prostokątny i ograniczony (brak zawijania granic).
- Brak interfejsu Gymnasium/PettingZoo i brak ziarna losowego z `reset(seed)` (symulacja jest deterministyczna, ale nie ma jeszcze losowości).
- Polityka uczona nie jest jeszcze podłączona; służy do tego logika `custom`.

## Plan rozwoju

1. Świat periodyczny (zawijanie pozycji, najkrótsze odległości, kopie obiektów przy granicy dla kolizji i sensorów).
2. Odbicie po kolizji (wektor minimalnej translacji z SAT) z opcją niszczenia.
3. Nakładka Gymnasium/PettingZoo (Parallel API), `reset(seed)`, tryb bez renderowania.
4. Obserwacje z sensorów, nagrody indywidualne i zespołowe, trening PPO.
