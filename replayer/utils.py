import copy
import math


def get_vec(v):
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return float(v[0]), float(v[1])
    if isinstance(v, dict):
        return float(v.get("x", 0.0)), float(v.get("y", 0.0))
    return 0.0, 0.0


def rotate_pt(px, py, cx, cy, angle):
    s = math.sin(angle)
    c = math.cos(angle)
    dx, dy = px - cx, py - cy
    return dx * c - dy * s + cx, dx * s + dy * c + cy


def build_spec_indices(base_objs):
    """
    Z base_objs (z world_init) buduje indeksy:
    { obj_id: { 'spec': base, 'engines': {eng_id: spec}, 'sensors': {sensor_id: spec} } }
    """
    idx = {}
    for oid, base in base_objs.items():
        spec = base
        eng_map = {}
        for e in spec.get("engines", []):
            eid = e.get("id")
            if eid is not None:
                eng_map[str(eid)] = e
        sen_map = {}
        for s in spec.get("sensors", []):
            sid = s.get("id")
            if sid is not None:
                sen_map[str(sid)] = s
        idx[str(oid)] = {"spec": spec, "engines": eng_map, "sensors": sen_map}
    return idx


def compute_engine_world(pos_obj, theta_obj, eng_spec, eng_state):
    """
    pos_obj: [x,y] object world pos
    theta_obj: object theta (rad)
    eng_spec: engine specification from init (local pos, angle_local, ...)
    eng_state: engine state from frame (thrust, thrust_vector maybe)
    returns dict with world pos and thrust vector
    """
    ox, oy = get_vec(pos_obj)
    # engine local position key may be 'positionXY_local' or 'position' in spec
    lx, ly = get_vec(eng_spec.get("positionXY_local") or eng_spec.get("position") or eng_spec.get("positionXY") or [0.0, 0.0])
    rx, ry = rotate_pt(lx, ly, 0.0, 0.0, float(theta_obj or 0.0))
    ex, ey = ox + rx, oy + ry

    # thrust vector: prefer state-provided (likely world), otherwise compute from local direction/angle
    if eng_state and eng_state.get("thrust_vector"):
        tv = eng_state.get("thrust_vector")
        tx, ty = float(tv[0]), float(tv[1])
    else:
        # prefer angle_local in spec
        ang_local = float(eng_spec.get("angle_local", 0.0))
        ang_world = ang_local + float(theta_obj or 0.0)
        thrust = float(eng_state.get("thrust", 0.0)) if eng_state else float(eng_spec.get("default_thrust", 0.0))
        tx, ty = math.cos(ang_world) * thrust, math.sin(ang_world) * thrust

    return {"id": eng_spec.get("id"), "pos": [ex, ey], "thrust_vec": [tx, ty], "thrust": eng_state.get("thrust") if eng_state else None}


def _wrap_angle(a):
    # normalizacja do zakresu [0, 2*pi)
    TWO_PI = 2.0 * math.pi
    a = float(a) % TWO_PI
    if a < 0:
        a += TWO_PI
    return a

def normalize_angle_rad(a):
    # opcjonalnie: znormalizuj do [-pi, pi) lub [0, 2pi)
    return ((a + math.pi) % (2 * math.pi)) - math.pi

def compute_sensor_world(pos_obj, theta_obj, sen_spec, sen_state):
    """
    Zwraca sensor w koordynatach globalnych:
      - id
      - pos: [sx, sy] (global)
      - vision: jeśli jest w spec -> angle_start/angle_end w globalnym układzie
      - scan: jeśli jest w state -> [global_angle_rad, dist]
      - hit: [hx, hy] (global) lub None

    Upraszczamy: zakładamy, że scan jest już w globalnym układzie.
    """
    ox, oy = get_vec(pos_obj)
    t = float(theta_obj or 0.0)

    # Pozycja sensora w globalnym układzie
    #lx, ly = get_vec((sen_spec or {}).get("positionXY") or [0.0, 0.0])
    #rx, ry = rotate_pt(lx, ly, 0.0, 0.0, t)
    #sx, sy = ox + rx, oy + ry
    sx, sy = ox, oy

    # Vision (lokalne kąty -> globalne)
    vision_global = None
    max_range = 0.0
    vision_local = (sen_spec or {}).get("vision")
    if vision_local:
        a0 = float(vision_local.get("angle_start", 0.0))
        a1 = float(vision_local.get("angle_end", 2 * math.pi))
        max_range = float(vision_local.get("max_range", 0.0))
        vision_global = {
            "max_range": max_range,
            "angle_start": a0 + t,
            "angle_end": a1 + t
        }

    # Scan (zakładamy, że globalny)
    scan_global = None
    hit = None
    scan_local = (sen_state or {}).get("scan") if sen_state else None
    if scan_local:
        if isinstance(scan_local, (list, tuple)) and len(scan_local) >= 2:
            global_ang = float(scan_local[0])
            dist = float(scan_local[1])
        elif isinstance(scan_local, dict):
            global_ang = float(scan_local.get("angle", 0.0))
            dist = float(scan_local.get("dist", 0.0))
        else:
            global_ang, dist = 0.0, 0.0

        # oblicz punkt hit
        if dist > 0:
            hx = sx + math.cos(global_ang) * dist
            hy = sy + math.sin(global_ang) * dist
            hit = [hx, hy]

        scan_global = [global_ang, dist]

    return {
        "id": (sen_spec or {}).get("id") if sen_spec else (sen_state or {}).get("id"),
        "pos": [sx, sy],
        "vision": vision_global,
        "scan": scan_global,
        "hit": hit
    }





def normalize_shape(shape):
    """
    Normalize various shape representations into a dict:
    circle -> {"type":"circle", "r": radius}
    polygon -> {"type":"polygon", "points": [[x,y], ...]}
    Accepts:
     - list style: ["circle", r] or ["polygon", [[x,y],...]]
     - dict style already normalized
    """
    if not shape:
        return None

    # if already dict with 'type'
    if isinstance(shape, dict) and "type" in shape:
        # ensure polygon points are list of pairs and radii floats
        if shape["type"] == "polygon" and "points" in shape:
            pts = []
            for p in shape.get("points", []):
                try:
                    pts.append([float(p[0]), float(p[1])])
                except Exception:
                    pass
            return {"type": "polygon", "points": pts}
        if shape["type"] == "circle":
            r = shape.get("r", shape.get("radius", 1.0))
            return {"type": "circle", "r": float(r)}
        return None

    # list/tuple formats
    if isinstance(shape, (list, tuple)) and len(shape) >= 1:
        t = shape[0]
        if isinstance(t, str) and t.lower().startswith("circle"):
            # format: ["circle", r]
            if len(shape) >= 2:
                try:
                    r = float(shape[1])
                except Exception:
                    r = 1.0
            else:
                r = 1.0
            return {"type": "circle", "r": r}
        if isinstance(t, str) and t.lower().startswith("polygon"):
            # format: ["polygon", [[x,y], ...]]
            if len(shape) >= 2:
                pts_raw = shape[1]
                pts = []
                for p in pts_raw:
                    try:
                        pts.append([float(p[0]), float(p[1])])
                    except Exception:
                        pass
                return {"type": "polygon", "points": pts}
    return None

def transform_shape_local_to_global(shape_local, positionXY, theta):
    """
    Given a normalized shape_local (dict) transform to global coords using positionXY and theta.
    Returns a dict in the same normalized format but with polygon points in global coords.
    For circle, we keep radius (center is provided separately by positionXY).
    """
    if not shape_local:
        return None

    px, py = get_vec(positionXY)
    t = float(theta or 0.0)

    if shape_local["type"] == "circle":
        # For drawing we use center = positionXY and radius unchanged.
        return {"type": "circle", "r": float(shape_local.get("r", 1.0)), "center": [px, py]}

    if shape_local["type"] == "polygon":
        pts = []
        for lx, ly in shape_local.get("points", []):
            gx, gy = rotate_pt(lx, ly, 0.0, 0.0, t)
            gx += px
            gy += py
            pts.append([float(gx), float(gy)])
        return {"type": "polygon", "points": pts}

    return None

def reorder_dict_semantic(d):
    ORDER = ["id", "name", "type", "position", "positionXY", "velocity", "velocityXY", "theta", "omega", "mass",
             "engines", "sensors", "destroyed", "removed"]
    if not isinstance(d, dict): return d
    res = {k: reorder_dict_semantic(d[k]) for k in ORDER if k in d}
    for k, v in d.items():
        if k not in res: res[k] = reorder_dict_semantic(v)
    return res