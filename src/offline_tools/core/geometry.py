"""Shapes in normalised coordinates (0-1 across the image), so they work at any resolution.

The UI draws on a small preview; core functions apply the same shapes to the full-size file.
"""

import math
from dataclasses import dataclass

MIN_RECT_SIZE = 0.002  # boxes thinner than this are treated as accidental clicks


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def clamped(self) -> "Point":
        return Point(_clamp(self.x), _clamp(self.y))

    def to_pixels(self, width: int, height: int) -> tuple[float, float]:
        return self.x * width, self.y * height


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @classmethod
    def from_points(cls, a: Point, b: Point) -> "Rect":
        a, b = a.clamped(), b.clamped()
        return cls(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def is_empty(self) -> bool:
        return self.width < MIN_RECT_SIZE or self.height < MIN_RECT_SIZE

    def contains(self, point: Point) -> bool:
        return self.left <= point.x <= self.right and self.top <= point.y <= self.bottom

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        """Pixel box (left, top, right, bottom), rounded OUTWARD so nothing at the edge leaks."""
        return (
            math.floor(self.left * width),
            math.floor(self.top * height),
            math.ceil(self.right * width),
            math.ceil(self.bottom * height),
        )


# Corners in order: top-left, top-right, bottom-right, bottom-left.
type Quad = tuple[Point, Point, Point, Point]

FULL_QUAD: Quad = (Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1))
