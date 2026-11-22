from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List
from sim.vectors.vec2d import Vec
from sim.vectors.vec2dM import VecM


@dataclass
class Box:
    minx: float
    miny: float
    maxx: float
    maxy: float

    @classmethod
    def from_radial_sector(cls, center: VecM, r: float, start_angle: float, end_angle: float) -> Box:
        """
        Tworzy AABB obejmujący wycinek koła zdefiniowany przez kąty globalne.
        start_angle i end_angle w radianach.
        """
        cx, cy = center
        points = []

        # 1. Dodaj centrum
        points.append(center)

        # 2. Dodaj końce łuku
        points.append((cx + r * math.cos(start_angle), cy + r * math.sin(start_angle)))
        points.append((cx + r * math.cos(end_angle), cy + r * math.sin(end_angle)))

        # 3. Sprawdź punkty ekstremalne (k * PI/2)
        # Iterujemy po całkowitych wielokrotnościach PI/2 w zakresie kątów
        step = math.pi / 2
        k_min = math.ceil(start_angle / step)
        k_max = math.floor(end_angle / step)

        for k in range(k_min, k_max + 1):
            ang = k * step
            points.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))

        return cls.from_points(points)

    @classmethod
    def from_points(cls, points: List[Vec]) -> Box:
        if not points:
            raise ValueError("Lista punktów przy tworzeniu obiektu typu Box jest pusta.")

        minx = miny = float("inf")
        maxx = maxy = float("-inf")

        for x, y in points:
            if x < minx:
                minx = x
            if y < miny:
                miny = y
            if x > maxx:
                maxx = x
            if y > maxy:
                maxy = y
        return cls(minx, miny, maxx, maxy)

    @classmethod
    def from_circle(cls, center: VecM, r: float) -> Box:
        cx, cy = center
        return cls(cx - r, cy - r, cx + r, cy + r)

    def intersects(self, other: Box) -> bool:
        return not (self.maxx < other.minx or
                    self.minx > other.maxx or
                    self.maxy < other.miny or
                    self.miny > other.maxy)

    def contains_box(self, other: Box) -> bool:
        return (self.minx <= other.minx and
                self.maxx >= other.maxx and
                self.miny <= other.miny and
                self.maxy >= other.maxy)

    def touches_or_exits(self, other: Box, eps: float = 1e-9) -> bool:
        """
        Zwraca True jeśli ten Box dotyka lub wychodzi poza drugi Box.
        Zwraca False jeśli w całości mieści się wewnątrz 'other' z marginesem eps.
        """
        if (self.minx >= other.minx + eps and
            self.miny >= other.miny + eps and
            self.maxx <= other.maxx - eps and
            self.maxy <= other.maxy - eps):
            return False

        return True


    def width(self) -> float:
        return self.maxx - self.minx

    def height(self) -> float:
        return self.maxy - self.miny

    def expand(self, eps: float) -> None:
        self.minx -= eps; self.miny -= eps; self.maxx += eps; self.maxy += eps

    def reset_from_points(self, points: List[Vec]) -> None:
        b = Box.from_points(points)
        self.minx, self.miny, self.maxx, self.maxy = b.minx, b.miny, b.maxx, b.maxy
