from sim.vectors.vec2d import Vec
from sim.utils.angular_helper import norm_pm_pi
import math
from typing import Tuple

def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def midle_lewel_control12(
    object_theta: float,
    object_omega: float,
    object_velocityXY: Vec,
    v_dir: Vec,
    distance_to_target: float,
    dt: float,
    *,
    state: dict
) -> Tuple[float, float]:
    """
    Wersja poprawiona:
    - przewidywanie kąta (prediction) na podstawie object_omega
    - estymacja przyspieszenia kątowego (domega) z poprzedniego kroku
    - adaptacyjne Kp_yaw / K_side zależne od prędkości bocznej
    - płynny thrust_gate (nie odcinamy ciągu nagle; minimalny micro-thrust)
    - lepsze wykorzystanie vel_forward/vel_side
    - zapis prev_omega w state
    """

    # ==================================================
    # STAN
    # ==================================================
    prev_u_thrust = state.get("u_thrust", 0.0)
    prev_u_yaw = state.get("u_yaw", 0.0)
    yaw_filt = state.get("u_yaw_filtered", 0.0)
    vel_side_filt = state.get("vel_side_filtered", 0.0)
    prev_vel_err = state.get("prev_vel_err", 0.0)
    prev_omega = state.get("prev_omega", 0.0)

    # ==================================================
    # KINEMATYKA
    # ==================================================
    vx, vy = v_dir
    vel_x, vel_y = object_velocityXY

    speed = math.hypot(vel_x, vel_y)
    vel_forward = vel_x * vx + vel_y * vy
    vel_side = vel_x * (-vy) + vel_y * vx

    # ==================================================
    # PARAMETRY (ENERGETYCZNE / ADAPTACYJNE)
    # ==================================================
    # bazowe wzmocnienia (możesz dalej stroić)
    Kp_yaw_base = 0.7
    K_side_base = 0.25

    Kp_vel = 0.6
    Kd_vel = 0.18
    THRUST_CRUISE = 0.12

    V_MAX = 3.0
    TRACK_DIST = 18.0

    YAW_DEAD = math.radians(3.5)

    MAX_DU_THRUST = 0.8 * dt
    MAX_DU_YAW = 0.35 * dt

    # przewidywanie / skale
    OMEGA_FREE = 0.12
    OMEGA_FULL = 0.6

    # minimalny micro-thrust gdy gate zamknięty (pozwala na drobne korekty)
    MIN_THRUST_WHEN_GATE_CLOSED = 0.02

    # ==================================================
    # FILTRY
    # ==================================================
    alpha_side = 0.25
    tau_yaw = 0.07

    # filtr prędkości bocznej (anizotropia)
    vel_side_filt = (
        alpha_side * vel_side
        + (1.0 - alpha_side) * vel_side_filt
    )

    # estymacja przyspieszenia kątowego (domega)
    domega = (object_omega - prev_omega) / max(dt, 1e-6)

    # ==================================================
    # BŁĄD KIERUNKU + PREDYKCJA KĄTA
    # ==================================================
    # przewidujemy przyszły kąt (prosty model: theta_future = theta + omega * t_pred)
    # t_pred zależy od prędkości (przy większej prędkości przewidujemy dalej)
    t_pred = clamp(0.05 + 0.35 * (speed / max(V_MAX, 1e-6)), 0.05, 0.5)
    theta_pred = object_theta + object_omega * t_pred
    angle_err_now = norm_pm_pi(math.atan2(vy, vx) - object_theta)
    angle_err_pred = norm_pm_pi(math.atan2(vy, vx) - theta_pred)

    # mieszanka: dajemy nieco większą wagę predykcji (przewidywanie zapobiega „przekręcaniu się”)
    angle_err = 0.6 * angle_err_pred + 0.4 * angle_err_now
    if abs(angle_err) < YAW_DEAD:
        angle_err = 0.0

    # ==================================================
    # MIARA "ZŁEGO USTAWIENIA" (energia + geometria)
    # ==================================================
    # większy współczynnik przy vel_side (bo boczny ruch jest kosztowny)
    dir_error = (
        abs(angle_err)
        + 0.9 * abs(vel_side_filt)
        + 0.2 * abs(object_omega)  # obroty też kosztują
    )

    # ==================================================
    # PŁYNNY THRUST GATE (bez ostrych progów)
    # ==================================================
    # podstawowy gate (1-> pełny thrust, 0-> zamknięty). Skalujemy łagodnie.
    thrust_gate_raw = 1.0 - dir_error / 1.4
    thrust_gate = clamp(thrust_gate_raw, 0.0, 1.0)

    # Jeżeli poruszamy się do tyłu (vel_forward < 0), dodatkowo ograniczamy thrust
    if vel_forward < -0.05:
        # skalowanie malejące z tylną prędkością
        back_scale = clamp(1.0 + vel_forward / 0.6, 0.0, 1.0)
        thrust_gate *= back_scale

    # upewnij się, że przy zamkniętym gate jest minimalny micro-thrust
    if thrust_gate < 0.05:
        thrust_gate = max(thrust_gate, MIN_THRUST_WHEN_GATE_CLOSED)

    # ==================================================
    # ADAPTACYJNE WZMOCNIENIA YAW / K_SIDE
    # ==================================================
    # przy dużej vel_side obniżamy Kp_yaw (żeby nie dokładać skrętu, który pogłębi slip),
    # za to zwiększamy K_side (redukcja slipu).
    vel_side_scale = clamp(abs(vel_side_filt) / 1.2, 0.0, 1.0)
    Kp_yaw = Kp_yaw_base * clamp(1.0 - 0.5 * vel_side_scale, 0.45, 1.0)
    K_side = K_side_base * clamp(1.0 + 0.8 * vel_side_scale, 1.0, 1.8)

    # dodatkowa adaptacja: przy dużej omega hamuj agresję yaw_ctrl
    omega_scale = clamp(abs(object_omega) / OMEGA_FULL, 0.0, 1.0)

    # ==================================================
    # YAW – najpierw hamuj energię, potem korekcja kierunku
    # ==================================================
    # dynamiczne tłumienie: im większe ω tym większe tłumienie, ale z wygładzaniem (omega_scale)
    yaw_damp = -2.0 * object_omega * clamp(omega_scale + 0.1, 0.0, 1.5)

    # sprzężenie z domega: jeśli angular acceleration wskazuje, że ω rośnie, dodaj delikatne tłumienie
    domega_brake = 0.0
    if domega * object_omega > 0.0:
        # jeśli ω rośnie (domega i omega mają ten sam znak), dobijemy tłumienie
        domega_brake = -0.5 * domega  # znak dostosowany

    # yaw_ctrl – korekcja kierunku + zapobieganie przesterowaniu przez ω
    yaw_ctrl = (
        Kp_yaw * angle_err
        - K_side * clamp(vel_side_filt, -1.2, 1.2)
        - 0.5 * object_omega  # bezpośrednie tłumienie "anty-przester"
    )

    # skala zależna od prędkości forward: przy niskiej prędkości chętniej skręcamy
    yaw_scale = clamp(1.0 - (speed / max(V_MAX, 1e-6)) * 0.5, 0.5, 1.2)

    u_yaw_raw = yaw_damp + domega_brake + yaw_ctrl * yaw_scale
    # ograniczenie surowe
    u_yaw = clamp(u_yaw_raw, -0.95, 0.95)

    # ==================================================
    # THRUST – dopiero gdy ma sens
    # ==================================================
    v_des = V_MAX * min(1.0, distance_to_target / TRACK_DIST)
    vel_err = v_des - vel_forward
    d_vel = (vel_err - prev_vel_err) / max(dt, 1e-6)

    u_thrust_raw = THRUST_CRUISE + Kp_vel * vel_err + Kd_vel * d_vel
    # apply thrust gate (smooth) and limit
    u_thrust = clamp(thrust_gate * u_thrust_raw, 0.0, 1.0)

    # ==================================================
    # FILTR YAW + RATE LIMIT
    # ==================================================
    alpha = dt / (tau_yaw + dt)
    yaw_filt = alpha * u_yaw + (1 - alpha) * yaw_filt

    u_yaw = clamp(
        yaw_filt,
        prev_u_yaw - MAX_DU_YAW,
        prev_u_yaw + MAX_DU_YAW
    )

    u_thrust = clamp(
        u_thrust,
        prev_u_thrust - MAX_DU_THRUST,
        prev_u_thrust + MAX_DU_THRUST
    )

    # ==================================================
    # ZAPIS STANU
    # ==================================================
    state.update({
        "u_yaw": u_yaw,
        "u_thrust": u_thrust,
        "u_yaw_filtered": yaw_filt,
        "vel_side_filtered": vel_side_filt,
        "prev_vel_err": vel_err,
        "prev_omega": object_omega,
    })

    return u_thrust, u_yaw


# uwzględnia tłumienie liniowe aizotropowe


# do architektury tłumienia liniowego izotropowego
