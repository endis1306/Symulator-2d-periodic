from __future__ import annotations

import math
from typing import List
from sim.utils.views import EngineControlView
from sim.vectors.vec2dM import VecM

def debug_low_level_control(
    object_position,
    engines,
    u_thrust,
    u_yaw
):
    omegas = low_level_control(object_position, engines, u_thrust, u_yaw)

    # --- oblicz thrust i moment faktyczny ---
    T_i_max = [e.k_thrust * (e.omega_max ** 2) for e in engines]
    T_max = sum(T_i_max)

    T_cmd = max(0.0, min(1.0, u_thrust)) * T_max

    p_list = []
    for e in engines:
        rx = e.position[0] - object_position[0]
        ry = e.position[1] - object_position[1]
        d = e.thrust_dir
        p = rx * d[1] - ry * d[0]
        p_list.append(p)

    tau_capacity = sum(abs(p * Tm) for p, Tm in zip(p_list, T_i_max))
    tau_cmd = max(-1.0, min(1.0, u_yaw)) * tau_capacity

    Ti_actual = [e.k_thrust * (w ** 2) for e, w in zip(engines, omegas)]
    T_actual = sum(Ti_actual)
    tau_actual = sum(p * Ti for p, Ti in zip(p_list, Ti_actual))

    print("====== LOW LEVEL MIXER DEBUG ======")
    print(f"u_thrust = {u_thrust:.3f}, u_yaw = {u_yaw:.3f}")
    print(f"T_cmd = {T_cmd:.6f}, T_actual = {T_actual:.6f}")
    print(f"tau_cmd = {tau_cmd:.6f}, tau_actual = {tau_actual:.6f}")
    print(f"T residual = {T_cmd - T_actual:.6e}")
    print(f"tau error  = {tau_cmd - tau_actual:.6e}")
    print("omegas =", ["{:.2f}".format(w) for w in omegas])
    print("Ti     =", ["{:.4f}".format(Ti) for Ti in Ti_actual])
    print("p_list =", ["{:.4f}".format(p) for p in p_list])
    print("===================================")

    return {
        "T_cmd": T_cmd,
        "T_actual": T_actual,
        "tau_cmd": tau_cmd,
        "tau_actual": tau_actual,
        "omegas": omegas,
        "Ti": Ti_actual,
        "p_list": p_list,
    }


# thrust and yaw -> omegas
def low_level_control(object_position: VecM, engines: List[EngineControlView], u_thrust: float, u_yaw: float) -> List[float]:
    '''
    Fizyczny mixer: rozdziela całkowity thrust i żądany yaw-moment
    na poszczególne silniki korzystając z rzeczywistych parametrów Rotor.
    Zwraca listę omega (rad/s) dla każdego silnika.
    '''


    n = len(engines)
    if n == 0:
        return []

    # clamp wejść
    u_thrust = max(0.0, min(1.0, float(u_thrust)))
    u_yaw = max(-1.0, min(1.0, float(u_yaw)))

    # --- 1) maksima thrust per engine (w N) ---
    T_i_max = [e.k_thrust * (e.omega_max ** 2) for e in engines]
    T_max = sum(T_i_max)

    if T_max <= 0.0:
        return [0.0] * n


    # --- 2) współczynniki "momentu na jednostkę thrust" p_i = r x d (bez T) ---
    # p_i takie, że τ_i = p_i * T_i
    p_list = []
    obj_pos = object_position

    for e in engines:
        pos = e.position
        rx = pos[0] - obj_pos[0]
        ry = pos[1] - obj_pos[1]
        d = e.thrust_dir  # unit vector
        px = rx * d[1] - ry * d[0]  # r x d
        p_list.append(px)

    # --- 3) maksymalna zdolność yaw (wartość bezwzględna) ---
    tau_capacity = sum(abs(p * Tm) for p, Tm in zip(p_list, T_i_max))
    # jeśli tau_capacity == 0 -> yaw niemożliwy
    # znormalizuj surowe tau_cmd
    T_cmd = u_thrust * T_max
    tau_cmd = u_yaw * (tau_capacity if tau_capacity > 0.0 else 0.0)

    # --- 4) baza rozdziału thrustu: proporcjonalnie do możliwości ---
    if T_max > 0:
        T_base = [T_cmd * (Tm / T_max) for Tm in T_i_max]
    else:
        T_base = [T_cmd / n for _ in range(n)]

    # funkcja pomocnicza do iteracyjnej alokacji (przy clampach)
    remaining = list(range(n))
    T_alloc = T_base[:]  # start
    locked = [False] * n
    max_iters = n

    for _iter in range(max_iters):
        # zestaw indeksów, które jeszcze pracują
        idxs = [i for i in remaining if not locked[i]]
        m = len(idxs)
        if m == 0:
            break

        # zbuduj lokalne a11,a12,a22 dla niezamrożonych
        a11_loc = m
        a12_loc = sum(p_list[i] for i in idxs)
        a22_loc = sum((p_list[i] ** 2) for i in idxs)
        det_loc = a11_loc * a22_loc - a12_loc * a12_loc

        # oblicz tau already contributed by locked ones and remaining base
        tau_locked = sum(p_list[i] * T_alloc[i] for i in range(n) if locked[i])
        # tau remaining current:
        tau_remaining_current = sum(p_list[i] * T_alloc[i] for i in idxs)
        # we want remaining to provide tau_cmd - tau_locked
        tau_needed_loc = tau_cmd - tau_locked - tau_remaining_current

        # If determinant is too small, fall back to simple proportional distribution
        if abs(det_loc) < 1e-12:
            # distribute tau_needed among idxs proportionally to p_i (by sign)
            sum_p_squared = sum(p_list[i] ** 2 for i in idxs)
            for i in idxs:
                if sum_p_squared > 1e-12:
                    delta = tau_needed_loc * p_list[i] / sum_p_squared
                    T_alloc[i] += delta
        else:
            lam0 = -a12_loc * tau_needed_loc / det_loc
            lam1 = a11_loc * tau_needed_loc / det_loc

            # delta for each free engine
            for i in idxs:
                delta = lam0 + lam1 * p_list[i]
                T_alloc[i] += delta

        # clamp and lock any that went out of bounds
        changed = False
        for i in idxs:
            if T_alloc[i] < 0.0:
                T_alloc[i] = 0.0
                locked[i] = True
                changed = True
            elif T_alloc[i] > T_i_max[i]:
                T_alloc[i] = T_i_max[i]
                locked[i] = True
                changed = True

        if not changed:
            break  # sukces

    # final safety clamp and small corrections to ensure sum(T_alloc) == T_cmd (distribute error)
    sum_T = sum(T_alloc)
    if sum_T <= 0:
        # fallback: equally distribute
        T_alloc = [T_cmd / n for _ in range(n)]
    else:
        scale = T_cmd / sum_T
        T_alloc = [max(0.0, min(T_i_max[i], T_alloc[i] * scale)) for i in range(n)]

    # last fallback: if still mismatch due to clamps, redistribute residual to non-clamped engines
    sum_T = sum(T_alloc)
    residual = T_cmd - sum_T
    if abs(residual) > 1e-9:
        free_idxs = [i for i in range(n) if 0.0 < T_alloc[i] < T_i_max[i]]
        if free_idxs:
            add_per = residual / len(free_idxs)
            for i in free_idxs:
                T_alloc[i] = max(0.0, min(T_i_max[i], T_alloc[i] + add_per))

    # convert thrust -> omega
    omegas = []
    for i, e in enumerate(engines):
        Ti = max(0.0, min(T_i_max[i], T_alloc[i]))
        if e.k_thrust <= 0:
            omega = 0.0
        else:
            omega = math.sqrt(max(0.0, Ti / e.k_thrust))
            # saturate to physical max
            omega = min(omega, e.omega_max)
        omegas.append(omega)

    return omegas
