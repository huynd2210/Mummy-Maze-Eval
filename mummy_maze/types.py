from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Tuple


class TileType(Enum):
    WALL = auto()
    FLOOR = auto()
    EXIT = auto()
    TRAP = auto()
    KEY = auto()
    GATE = auto()


class MummyType(Enum):
    WHITE = auto()
    RED = auto()


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def as_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def manhattan_distance(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def move(self, dx: int, dy: int) -> "Position":
        return Position(self.x + dx, self.y + dy)


# Cardinal movement deltas
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
STAY = (0, 0)

CARDINAL_STEPS = (UP, DOWN, LEFT, RIGHT)
ALL_STEPS = (UP, DOWN, LEFT, RIGHT, STAY)



