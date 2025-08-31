from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from .types import Position, TileType, MummyType


@dataclass
class Level:
    width: int
    height: int
    tiles: List[List[TileType]]
    gate_open: bool
    explorer: Position
    mummies: List[Tuple[MummyType, Position]]
    scorpions: List[Position]

    def in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def tile_at(self, pos: Position) -> TileType:
        return self.tiles[pos.y][pos.x]


CHAR_TO_TILE = {
    "#": TileType.WALL,
    ".": TileType.FLOOR,
    "E": TileType.EXIT,
    "T": TileType.TRAP,
    "K": TileType.KEY,
    "G": TileType.GATE,  # gates present; closed if gate_open is False
    "g": TileType.GATE,  # gates present; open if gate_open is True
    "W": TileType.FLOOR,  # white mummy (placed on floor)
    "R": TileType.FLOOR,  # red mummy (placed on floor)
    "S": TileType.FLOOR,  # scorpion (placed on floor)
}


def parse_level(ascii_map: str) -> Level:
    lines_raw = [line.rstrip("\n") for line in ascii_map.splitlines() if line.strip("\n") != ""]
    if not lines_raw:
        raise ValueError("Empty level content")

    # Double-resolution grid: cells on odd positions, walls on even positions
    # Each character in the input represents a cell, walls go between them
    cell_width = max(len(line) for line in lines_raw)
    cell_height = len(lines_raw)
    
    # Grid size: 2*cell_width + 1 for walls, 2*cell_height + 1 for walls
    width = 2 * cell_width + 1
    height = 2 * cell_height + 1
    
    # Create the full grid with walls around perimeter
    tiles: List[List[TileType]] = [[TileType.WALL for _ in range(width)] for _ in range(height)]
    
    # Fill interior with floor tiles (odd positions)
    for y in range(1, height - 1, 2):
        for x in range(1, width - 1, 2):
            tiles[y][x] = TileType.FLOOR

    explorer: Position | None = None
    mummies: List[Tuple[MummyType, Position]] = []
    scorpions: List[Position] = []
    saw_G = False
    saw_g = False

    # Parse the maze content
    for y, line in enumerate(lines_raw):
        for x, ch in enumerate(line):
            if x < cell_width:
                # Convert cell position to grid position (odd coordinates)
                grid_x = 2 * x + 1
                grid_y = 2 * y + 1
                pos = Position(grid_x, grid_y)
                
                if ch in CHAR_TO_TILE:
                    tiles[grid_y][grid_x] = CHAR_TO_TILE[ch]
                    if ch == "G":
                        saw_G = True
                    elif ch == "g":
                        saw_g = True
                    elif ch == "W":
                        mummies.append((MummyType.WHITE, pos))
                    elif ch == "R":
                        mummies.append((MummyType.RED, pos))
                    elif ch == "S":
                        scorpions.append(pos)
                elif ch == "P":
                    explorer = pos
                    tiles[grid_y][grid_x] = TileType.FLOOR
                elif ch == "|":
                    # Vertical wall - place on even column between cells
                    wall_x = grid_x + 1
                    if wall_x < width - 1:
                        tiles[grid_y][wall_x] = TileType.WALL
                    tiles[grid_y][grid_x] = TileType.FLOOR
                elif ch == "-":
                    # Horizontal wall - place on even row between cells
                    wall_y = grid_y + 1
                    if wall_y < height - 1:
                        tiles[wall_y][grid_x] = TileType.WALL
                    tiles[grid_y][grid_x] = TileType.FLOOR
                elif ch == "+":
                    # Wall intersection - place both types of walls
                    wall_x = grid_x + 1
                    wall_y = grid_y + 1
                    if wall_x < width - 1:
                        tiles[grid_y][wall_x] = TileType.WALL
                    if wall_y < height - 1:
                        tiles[wall_y][grid_x] = TileType.WALL
                    tiles[grid_y][grid_x] = TileType.FLOOR
                else:
                    # Unrecognized symbols are treated as floor
                    tiles[grid_y][grid_x] = TileType.FLOOR

    if explorer is None:
        raise ValueError("Level must define explorer 'P'")

    if saw_G and saw_g:
        raise ValueError("Level uses both 'G' and 'g'. Use one to set initial gate state.")

    gate_open = saw_g and not saw_G

    return Level(
        width=width,
        height=height,
        tiles=tiles,
        gate_open=gate_open,
        explorer=explorer,
        mummies=mummies,
        scorpions=scorpions,
    )


def load_level_from_file(path: str | Path) -> Level:
    text = Path(path).read_text(encoding="utf-8")
    return parse_level(text)



