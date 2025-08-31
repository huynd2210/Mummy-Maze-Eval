from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from .types import (
    Position,
    TileType,
    MummyType,
    CARDINAL_STEPS,
    ALL_STEPS,
)
from .level import Level


@dataclass(frozen=True)
class EntityState:
    explorer: Position
    mummies: Tuple[Tuple[MummyType, Position], ...]
    scorpions: Tuple[Position, ...]
    gate_open: bool

    def key(self) -> Tuple:
        # Sorting ensures canonical key independent of insertion order
        return (
            self.explorer.as_tuple(),
            tuple(sorted(((mt.name, p.as_tuple()) for mt, p in self.mummies))),
            tuple(sorted((p.as_tuple() for p in self.scorpions))),
            self.gate_open,
        )


def is_blocked(level: Level, pos: Position, gate_open: bool) -> bool:
    if not level.in_bounds(pos):
        return True
    tile = level.tile_at(pos)
    if tile == TileType.WALL:
        return True
    if tile == TileType.GATE and not gate_open:
        return True
    return False


def has_edge_wall_between(level: Level, from_pos: Position, to_pos: Position) -> bool:
    """Check if there's a wall between two adjacent positions."""
    if not level.in_bounds(from_pos) or not level.in_bounds(to_pos):
        return True
    
    # Calculate the edge between the two positions
    dx = to_pos.x - from_pos.x
    dy = to_pos.y - from_pos.y
    
    # Only check for adjacent positions
    if abs(dx) + abs(dy) != 1:
        return False
        
    # For horizontal movement, check if there's a vertical wall
    if dx != 0:  # Horizontal movement
        # Check if the tile we're moving to has a vertical wall character
        if level.tile_at(to_pos) == TileType.WALL:
            return True
        # Also check if there's a wall character in the current tile that blocks this direction
        if level.tile_at(from_pos) == TileType.WALL:
            return True
    
    # For vertical movement, check if there's a horizontal wall
    if dy != 0:  # Vertical movement
        # Check if the tile we're moving to has a horizontal wall character
        if level.tile_at(to_pos) == TileType.WALL:
            return True
        # Also check if there's a wall character in the current tile that blocks this direction
        if level.tile_at(from_pos) == TileType.WALL:
            return True
    
    return False


def is_blocked_with_edge_check(level: Level, from_pos: Position, to_pos: Position, gate_open: bool) -> bool:
    """Check if movement is blocked, including edge walls."""
    # First check if the destination tile itself is blocked
    if is_blocked(level, to_pos, gate_open):
        return True
    
    # Then check if there's an edge wall between the positions
    if has_edge_wall_between(level, from_pos, to_pos):
        return True
    
    return False


def is_exit(level: Level, pos: Position) -> bool:
    return level.tile_at(pos) == TileType.EXIT


def is_trap(level: Level, pos: Position) -> bool:
    return level.tile_at(pos) == TileType.TRAP


def is_key(level: Level, pos: Position) -> bool:
    return level.tile_at(pos) == TileType.KEY


def step_towards(prefer_axis_first: str, src: Position, dst: Position, level: Level, gate_open: bool) -> Position:
    dx = dst.x - src.x
    dy = dst.y - src.y
    candidates: List[Tuple[int, int]] = []
    if prefer_axis_first == "h":
        if dx != 0:
            candidates.append((1 if dx > 0 else -1, 0))
        if dy != 0:
            candidates.append((0, 1 if dy > 0 else -1))
    else:
        if dy != 0:
            candidates.append((0, 1 if dy > 0 else -1))
        if dx != 0:
            candidates.append((1 if dx > 0 else -1, 0))
    # If aligned on one axis, we might have only one candidate
    for step in candidates:
        nxt = src.move(*step)
        if not is_blocked_with_edge_check(level, src, nxt, gate_open):
            return nxt
    # If all preferred steps blocked, stay in place
    return src


def scorpion_step(src: Position, dst: Position, level: Level, gate_open: bool) -> Position:
    dx = abs(dst.x - src.x)
    dy = abs(dst.y - src.y)
    # Move toward explorer on dominant axis; fallback to other axis
    if dx >= dy:
        primary = (1 if dst.x > src.x else -1, 0) if dx != 0 else None
        secondary = (0, 1 if dst.y > src.y else -1) if dy != 0 else None
    else:
        primary = (0, 1 if dst.y > src.y else -1) if dy != 0 else None
        secondary = (1 if dst.x > src.x else -1, 0) if dx != 0 else None
    for step in (primary, secondary):
        if step is None:
            continue
        nxt = src.move(*step)
        if not is_blocked_with_edge_check(level, src, nxt, gate_open):
            return nxt
    return src


def toggle_gate_if_on_key(pos: Position, gate_open: bool, level: Level) -> bool:
    if is_key(level, pos):
        return not gate_open
    return gate_open


def enumerate_player_moves(level: Level, state: EntityState) -> List[Position]:
    results: List[Position] = []
    for dx, dy in ALL_STEPS:
        nxt = state.explorer.move(dx, dy)
        if is_blocked_with_edge_check(level, state.explorer, nxt, state.gate_open):
            continue
        if is_trap(level, nxt):
            continue
        # Cannot move into enemy square initially
        occupied = {p.as_tuple() for _, p in state.mummies}
        occupied.update(p.as_tuple() for p in state.scorpions)
        if nxt.as_tuple() in occupied:
            continue
        results.append(nxt)
    return results


def resolve_enemy_collisions(mummies: List[Tuple[MummyType, Position]], scorpions: List[Position]) -> Tuple[List[Tuple[MummyType, Position]], List[Position]]:
    # If mummy and scorpion occupy same cell -> scorpion dies.
    scorpion_set = {p.as_tuple() for p in scorpions}
    kept_scorpions: List[Position] = []
    mummy_positions = {p.as_tuple() for _, p in mummies}
    for s in scorpions:
        if s.as_tuple() not in mummy_positions:
            kept_scorpions.append(s)

    # If two mummies collide, one is destroyed: remove the later-moving one (stable by order)
    seen: set[Tuple[int, int]] = set()
    kept_mummies: List[Tuple[MummyType, Position]] = []
    for mt, pos in mummies:
        key = pos.as_tuple()
        if key in seen:
            # drop this one
            continue
        seen.add(key)
        kept_mummies.append((mt, pos))

    return kept_mummies, kept_scorpions


def simulate_enemies(level: Level, state: EntityState, explorer_after_move: Position) -> Tuple[EntityState | None, bool]:
    gate_open = state.gate_open
    mummies: List[Tuple[MummyType, Position]] = list(state.mummies)
    scorpions: List[Position] = list(state.scorpions)

    # Scorpions move one step per turn (after player), mummies move two steps (with capture checks after each)
    # Movement order per substep: mummies step 1, check capture; mummies step 2, check capture; then scorpions step 1, check capture.

    # Toggle gates if the explorer just stepped on a key
    gate_open = toggle_gate_if_on_key(explorer_after_move, gate_open, level)

    # Mummy step 1
    new_mummies: List[Tuple[MummyType, Position]] = []
    for mt, pos in mummies:
        if mt == MummyType.WHITE:
            nxt = step_towards("h", pos, explorer_after_move, level, gate_open)
        else:
            nxt = step_towards("v", pos, explorer_after_move, level, gate_open)
        gate_open = toggle_gate_if_on_key(nxt, gate_open, level)
        new_mummies.append((mt, nxt))
        if nxt == explorer_after_move:
            return None, True
    mummies = new_mummies

    # Resolve mummy-mummy collisions after step 1
    mummies, scorpions = resolve_enemy_collisions(mummies, scorpions)

    # Mummy step 2
    new_mummies = []
    for mt, pos in mummies:
        if mt == MummyType.WHITE:
            nxt = step_towards("h", pos, explorer_after_move, level, gate_open)
        else:
            nxt = step_towards("v", pos, explorer_after_move, level, gate_open)
        gate_open = toggle_gate_if_on_key(nxt, gate_open, level)
        new_mummies.append((mt, nxt))
        if nxt == explorer_after_move:
            return None, True
    mummies = new_mummies

    # Resolve mummy-mummy collisions after step 2
    mummies, scorpions = resolve_enemy_collisions(mummies, scorpions)

    # Scorpion step 1
    new_scorpions: List[Position] = []
    for pos in scorpions:
        nxt = scorpion_step(pos, explorer_after_move, level, gate_open)
        gate_open = toggle_gate_if_on_key(nxt, gate_open, level)
        new_scorpions.append(nxt)
        if nxt == explorer_after_move:
            return None, True
    scorpions = new_scorpions

    # Resolve mummy-scorpion collisions
    mummies, scorpions = resolve_enemy_collisions(mummies, scorpions)

    return (
        EntityState(
            explorer=explorer_after_move,
            mummies=tuple(mummies),
            scorpions=tuple(scorpions),
            gate_open=gate_open,
        ),
        False,
    )


def initial_state_for_level(level: Level) -> EntityState:
    return EntityState(
        explorer=level.explorer,
        mummies=tuple(level.mummies),
        scorpions=tuple(level.scorpions),
        gate_open=level.gate_open,
    )


