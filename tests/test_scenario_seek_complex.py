"""Test regresyjny scenariusza referencyjnego (seek_complex_scene).

Sprawdza, że:
- plik .simdsl po konwersji daje dokładnie ten sam .json, który leży w repozytorium,
- symulacja działa headless i początek przebiegu zgadza się z logiem referencyjnym.
Dalsza część trajektorii jest numerycznie wrażliwa (kolizje, sprzężenie zwrotne),
dlatego porównujemy tylko pierwsze kroki.
"""
import json
from pathlib import Path

import pytest

from DSL.dsl_to_dict import dsl_to_dict
from DSL.configs import WorldConfig
from sim.builders.build_world import build_world

SCENARIO = Path(__file__).resolve().parent.parent / "scenarios" / "seek_complex_scene"
CHECKED_STEPS = 150


def _load_json():
    return json.loads((SCENARIO / "seek_complex_scene.json").read_text(encoding="utf-8"))


def test_simdsl_matches_json():
    raw = dsl_to_dict((SCENARIO / "seek_complex_scene.simdsl").read_text(encoding="utf-8"))
    dumped = json.loads(json.dumps(WorldConfig.model_validate(raw).model_dump()))
    assert dumped == _load_json()


def test_start_of_run_matches_reference_log():
    cfg = _load_json()
    ref = [json.loads(l) for l in (SCENARIO / "seek_complex_scene.log.jsonl").open(encoding="utf-8")]

    world = build_world(cfg)
    world.sync()
    world.check_and_destroy_initial_collisions()
    world.compute_perception()
    assert json.loads(json.dumps(world.serialize_init())) == ref[0]

    for step in range(1, CHECKED_STEPS + 1):
        world.next_state()
        got = {o["id"]: list(o["positionXY"]) for o in world.serialize()["objects"]}
        want = {o["id"]: o["positionXY"] for o in ref[step + 1]["objects"]}
        for oid, pos in want.items():
            assert got[oid] == pytest.approx(pos, abs=1e-6), (step, oid)
