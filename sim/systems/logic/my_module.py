from sim.vectors.vec2d import to_vec2, vec_sub


def seek_control(so_view, sos_view, params):
    target_id = params["target_id"]
    target = next((o for o in sos_view if o.id == target_id), None)

    if target is None:
        return to_vec2(0.0, 0.0)

    return vec_sub(target.positionXY, so_view.positionXY)
