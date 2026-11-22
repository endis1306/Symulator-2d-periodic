# tests/test_sensor_scan.py
import math
import pytest

from sim.systems.sensors.sensor import Sensor
from sim.geometry.shape import RadialSector, Circle, Polygon
from sim.core.sim_object import SimObject
from sim.geometry.box import Box

from typing import Optional, Sequence

def make_simobject_at(
    x: float,
    y: float,
    obj_id: str = "o",
    *,
    shape_type: str = "circle",
    circle_r: float = 1.0,
    poly_points: Optional[Sequence[tuple]] = None
) -> SimObject:
    """
    Factory tworzący SimObject w (x,y).
    - shape_type: "circle" (domyślnie) lub "poly"
    - circle_r: promień koła (jeśli circle)
    - poly_points: lista (x,y) punktów lokalnych wielokąta (jeśli poly).
        Wielokąt musi spełniać wymagania Polygon (zawiera origin, CCW, convex itp.)
    """
    if shape_type == "circle":
        s = Circle(r=float(circle_r))
    elif shape_type == "poly":
        if poly_points is None:
            raise ValueError("Dla shape_type='poly' musisz podać poly_points")
        s = Polygon(points=list(poly_points))
    else:
        raise ValueError(f"Nieznany shape_type: {shape_type}")

    obj = SimObject(obj_id, shape=s)
    # ustawiamy bezpośrednio pola (bez przechodzenia przez API)
    obj.positionXY[0] = float(x)
    obj.positionXY[1] = float(y)
    obj.theta = 0.0

    # wyzeruj cache i zsynchronizuj (żeby shape.sync miało dostęp do get_position/get_theta)
    obj._cached_moved = None
    obj._cached_pos_theta = None
    obj.sync()

    return obj


def make_sensor_on(simobj: SimObject, sensor_id: str = "sensor1",
                   rays_count: int = 5, max_range: float = 20.0, fov: float = math.pi/2,
                   offset_theta: float = 0.0) -> Sensor:
    rs = RadialSector(rays_count=rays_count, max_range=max_range, fov=fov, offset_theta=offset_theta)
    sens = Sensor(sensor_id, detection_shape=rs)
    sens.sync(simobj.sensorsControl)
    sens._cached_moved = None
    sens._cached_pos_theta = None
    return sens

# --- Tests ----------------------------------------------------------

def test_scan_detects_circle_and_ignores_self():
    parent = make_simobject_at(0.0, 0.0, obj_id="parent")
    sensor = make_sensor_on(parent, rays_count=9, max_range=10.0, fov=math.pi / 2)
    target = make_simobject_at(5.0, 0.0, obj_id="t", circle_r=1.0)

    hits = sensor.scan([parent, target])

    assert hits is not None
    assert all(obj_id == "t" for _, _, obj_id in hits)
    # promien wprost na cel trafia w krawedz kola (5 - 1)
    assert min(d for _, d, _ in hits) == pytest.approx(4.0, abs=1e-6)


def test_scan_returns_hits_sorted_by_distance():
    parent = make_simobject_at(0.0, 0.0, obj_id="parent")
    sensor = make_sensor_on(parent, rays_count=9, max_range=20.0, fov=math.pi / 2)
    near = make_simobject_at(5.0, 0.0, obj_id="near")
    hits = sensor.scan([near])
    dists = [d for _, d, _ in hits]
    assert dists == sorted(dists)


def test_scan_picks_closest_object_on_ray():
    parent = make_simobject_at(0.0, 0.0, obj_id="parent")
    sensor = make_sensor_on(parent, rays_count=1, max_range=30.0, fov=0.0)
    near = make_simobject_at(5.0, 0.0, obj_id="near")
    far = make_simobject_at(15.0, 0.0, obj_id="far")

    hits = sensor.scan([far, near])

    assert len(hits) == 1
    assert hits[0][2] == "near"


def test_scan_border_hit_returns_world_boundary():
    parent = make_simobject_at(10.0, 10.0, obj_id="parent")
    sensor = make_sensor_on(parent, rays_count=1, max_range=50.0, fov=0.0)
    world = Box(0.0, 0.0, 30.0, 30.0)

    hits = sensor.scan([], border_box=world)

    assert hits is not None
    assert hits[0][2] == "WORLD_BOUNDARY"
    assert hits[0][1] == pytest.approx(20.0, abs=1e-6)


def test_scan_disabled_returns_none():
    parent = make_simobject_at(0.0, 0.0, obj_id="parent")
    sensor = make_sensor_on(parent)
    sensor.enabled = False
    target = make_simobject_at(5.0, 0.0, obj_id="t")
    assert sensor.scan([target]) is None


def test_scan_ignores_destroyed_and_removed():
    parent = make_simobject_at(0.0, 0.0, obj_id="parent")
    sensor = make_sensor_on(parent, rays_count=5, max_range=20.0, fov=math.pi / 2)
    gone = make_simobject_at(5.0, 0.0, obj_id="gone")
    gone.destroy()
    assert sensor.scan([gone]) is None


def test_scan_respects_max_range():
    parent = make_simobject_at(0.0, 0.0, obj_id="parent")
    sensor = make_sensor_on(parent, rays_count=1, max_range=5.0, fov=0.0)
    far = make_simobject_at(20.0, 0.0, obj_id="far")
    assert sensor.scan([far]) is None


def test_scan_follows_object_after_move():
    parent = make_simobject_at(0.0, 0.0, obj_id="parent")
    sensor = make_sensor_on(parent, rays_count=1, max_range=30.0, fov=0.0)
    target = make_simobject_at(10.0, 0.0, obj_id="t", circle_r=1.0)
    d1 = sensor.scan([target])[0][1]

    parent.positionXY[0] = 2.0
    parent._cached_moved = None
    parent._cached_pos_theta = None
    d2 = sensor.scan([target])[0][1]

    assert d2 == pytest.approx(d1 - 2.0, abs=1e-6)
