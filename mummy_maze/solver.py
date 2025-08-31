from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .types import Position, ALL_STEPS
from .level import Level
from .state import (
    EntityState,
    initial_state_for_level,
    enumerate_player_moves,
    simulate_enemies,
    is_exit,
)


@dataclass
class Step:
    position: Position
    description: str


def reconstruct_path(came_from: Dict[Tuple, Tuple[Tuple, Step]], current_key: Tuple) -> List[Step]:
    steps: List[Step] = []
    while current_key in came_from:
        prev_key, step = came_from[current_key]
        steps.append(step)
        current_key = prev_key
    steps.reverse()
    return steps


def heuristic_to_exit(level: Level, pos: Position) -> int:
    # Find nearest exit tile by Manhattan distance
    best = 0
    found_any = False
    for y in range(level.height):
        for x in range(level.width):
            if level.tiles[y][x].name == "EXIT":
                d = abs(x - pos.x) + abs(y - pos.y)
                if not found_any or d < best:
                    best = d
                    found_any = True
    return best if found_any else 0


def solve(level: Level, max_expansions: int = 200000) -> Optional[List[Step]]:
    start = initial_state_for_level(level)
    start_key = start.key()

    open_heap: List[Tuple[int, int, Tuple, EntityState]] = []
    g_score: Dict[Tuple, int] = {start_key: 0}
    came_from: Dict[Tuple, Tuple[Tuple, Step]] = {}

    f0 = heuristic_to_exit(level, start.explorer)
    heapq.heappush(open_heap, (f0, 0, start_key, start))

    expansions = 0

    while open_heap:
        _, g, key, state = heapq.heappop(open_heap)
        if g != g_score.get(key, 10 ** 9):
            continue

        # If already at exit (after player's move step), consider solved
        if is_exit(level, state.explorer):
            return reconstruct_path(came_from, key)

        if expansions > max_expansions:
            return None
        expansions += 1

        # Generate player moves
        for dx, dy in ALL_STEPS:
            nxt_pos = state.explorer.move(dx, dy)
            # Simulate via enumerate to check legality
            legal_moves = {p.as_tuple() for p in enumerate_player_moves(level, state)}
            if nxt_pos.as_tuple() not in legal_moves:
                continue

            # Immediate win if stepping on exit before enemies move
            if is_exit(level, nxt_pos):
                step = Step(position=nxt_pos, description=f"Player to {nxt_pos}")
                came_from[(state.explorer.move(dx, dy).as_tuple(), tuple(sorted(((mt.name, p.as_tuple()) for mt, p in state.mummies))), tuple(sorted((p.as_tuple() for p in state.scorpions))), state.gate_open)] = (key, step)
                return reconstruct_path(came_from, (state.explorer.move(dx, dy).as_tuple(), tuple(sorted(((mt.name, p.as_tuple()) for mt, p in state.mummies))), tuple(sorted((p.as_tuple() for p in state.scorpions))), state.gate_open))

            next_state, captured = simulate_enemies(level, state, nxt_pos)
            if captured or next_state is None:
                continue

            next_key = next_state.key()
            tentative_g = g + 1
            if tentative_g < g_score.get(next_key, 10 ** 9):
                g_score[next_key] = tentative_g
                came_from[next_key] = (key, Step(position=nxt_pos, description=f"Player to {nxt_pos}"))
                f = tentative_g + heuristic_to_exit(level, next_state.explorer)
                heapq.heappush(open_heap, (f, tentative_g, next_key, next_state))

    return None



