from dataclasses import dataclass


@dataclass(frozen=True)
class BodyParams:
    drag_lin_forward: float = 0.0
    drag_lin_side: float = 0.0
    drag_rot: float = 0.0
    I: float = 1.0
    mass: float = 1.0

    def __post_init__(self):

        for name, val in [("drag_forward", self.drag_lin_forward), ("drag_side", self.drag_lin_side), ("drag_rot", self.drag_rot), ("I", self.I), ("mass", self.mass)]:
            if not isinstance(val, (float, int)):
                raise TypeError(f"Pole '{name}' musi być liczbą, a nie {type(val).__name__}.")

        if self.drag_lin_forward < 0:
            raise ValueError("Współczynnik oporu liniowego (drag_lin_forward) nie może być ujemny.")
        if self.drag_lin_side < 0:
            raise ValueError("Współczynnik oporu liniowego (drag_lin_side) nie może być ujemny.")
        if self.drag_rot < 0:
            raise ValueError("Współczynnik oporu obrotowego (drag_rot) nie może być ujemny.")
        if self.I <= 0:
            raise ValueError("Moment bezwładności (I) musi być dodatni.")
        if self.mass <= 0:
            raise ValueError("Masa (mass) musi być dodatnia.")

    def to_dict(self) -> dict:
        return {
            "mass": self.mass,
            "I": self.I,
            "drag_lin_forward": self.drag_lin_forward,
            "drag_lin_side": self.drag_lin_side,
            "drag_rot": self.drag_rot,
        }
