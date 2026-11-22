# physics.py
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from sim.vectors.vec2dM import VecM, vec_mulM, vec_addM, vec_dotM, vec_subM, to_vec2M

if TYPE_CHECKING:
    from sim.core.sim_object import SimObject


@dataclass
class Physics:
    eps: float = 1e-7
    simobj: SimObject = field(init=False, default=None, repr=False)


    def sync(self, simobj: SimObject):
        self.simobj = simobj

    def drop(self):
        self.simobj = None

    def step(self, deltaT: float) -> None:
        b = self.simobj.bodyParams
        e = self.simobj.enginesControl
        T_XY, tau = e.get_thrust_and_torque()

        self._linear_step(mass=b.mass, drag_lin_forward=b.drag_lin_forward,
                          drag_lin_side=b.drag_lin_side, T_XY=T_XY, dt=deltaT)

        self._angular_step(I=b.I, drag_rot=b.drag_rot, tau=tau, dt=deltaT)

    def _linear_step(
            self,
            mass: float,
            drag_lin_forward: float,
            drag_lin_side: float,
            T_XY: VecM,
            dt: float
    ) -> None:
        v = self.simobj.velocityXY
        theta = self.simobj.theta

        c = math.cos(theta)
        s = math.sin(theta)

        # --- globalny tensor oporu R D R^T ---
        Dxx = drag_lin_forward * c * c + drag_lin_side * s * s
        Dyy = drag_lin_forward * s * s + drag_lin_side * c * c
        Dxy = (drag_lin_forward - drag_lin_side) * s * c

        # F = -D * v
        drag_force = to_vec2M(
            -(Dxx * v[0] + Dxy * v[1]),
            -(Dxy * v[0] + Dyy * v[1])
        )

        total_force = vec_addM(T_XY, drag_force)

        acc = vec_mulM(total_force, 1.0 / mass)
        self.simobj.accelerationXY = acc

        # semi-implicit Euler
        self.simobj.velocityXY = vec_addM(
            v,
            vec_mulM(acc, dt)
        )

        self.simobj.positionXY = vec_addM(
            self.simobj.positionXY,
            vec_mulM(self.simobj.velocityXY, dt)
        )

    def _angular_step(self, I: float, drag_rot: float, tau: float, dt: float) -> None:
        if I <= 0:
            raise ValueError("Moment bezwładności musi być > 0")

        drag_tau = -drag_rot * self.simobj.omega
        total_tau = tau + drag_tau
        alpha = total_tau / I

        # semi-implicit Euler
        self.simobj.omega += alpha * dt
        self.simobj.theta += self.simobj.omega * dt

        self.simobj.alpha = alpha
