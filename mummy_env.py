"""
Mummy Maze-like environment for applying simple actions.

This module implements a minimal step-based environment on top of the board
JSON schema produced by the Flask editor (walls, gates, entities).

Supported actions (case-insensitive, with or without leading "Action:"):
- UP, DOWN, LEFT, RIGHT: attempt to move the player one cell
- WAIT: do nothing
- UNDO: revert the last applied action
- RESET: restore the initial state

Rules implemented:
- Movement is blocked by walls or closed gates.
- Stepping onto a key cell toggles all gates (closed <-> open) for both player and enemies.
- Stepping onto a trap kills the player (game over, lose). Enemies ignore traps.
- Reaching the exit sets done = True, won = True (enemies do not move on that turn).
- After the player's action, enemies move: white/red mummies take two steps (priority based), then scorpions take one step.

Usage (as library):
    from mummy_env import Game
    import json

    board = json.load(open('data/board.json', 'r', encoding='utf-8'))
    game = Game(board)
    print(game.to_text())
    res = game.step('UP')
    print(res['ascii'])

CLI (one-shot):
    python mummy_env.py data/board.json UP RIGHT WAIT

This prints the final board after applying the sequence, and a JSON summary.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Dict, List, Optional, Tuple, Any
import json
import sys

from text_export import board_to_double_res_text

Action = str


def _ensure_fields(board: Dict[str, Any]) -> None:
    rows = int(board.get('rows', 0))
    cols = int(board.get('cols', 0))
    if rows <= 0 or cols <= 0:
        raise ValueError('Invalid board dimensions')

    # Required edge fields
    def ensure_matrix(name: str, r: int, c: int):
        m = board.get(name)
        if not isinstance(m, list) or len(m) != r:
            board[name] = [[False] * c for _ in range(r)]
        else:
            # fix row lengths
            for i in range(r):
                row = m[i] if i < len(m) and isinstance(m[i], list) else []
                if len(row) != c:
                    if len(row) < c:
                        row = list(row) + [False] * (c - len(row))
                    else:
                        row = row[:c]
                m[i] = [bool(x) for x in row]
            board[name] = m

    ensure_matrix('v_walls', rows, cols + 1)
    ensure_matrix('h_walls', rows + 1, cols)
    ensure_matrix('v_gates', rows, cols + 1)
    ensure_matrix('h_gates', rows + 1, cols)

    # Entities
    board['player'] = board.get('player') if _in_bounds_rc(board.get('player'), rows, cols) else None
    board['exit'] = board.get('exit') if _in_bounds_rc(board.get('exit'), rows, cols) else None
    for name in ['white_mummies', 'red_mummies', 'traps', 'keys', 'scorpions']:
        lst = board.get(name)
        if not isinstance(lst, list):
            board[name] = []
        else:
            board[name] = [[int(r), int(c)] for r, c in lst if _in_bounds_rc([r, c], rows, cols)]

    # Enforce boundary walls
    for r in range(rows):
        board['v_walls'][r][0] = True
        board['v_walls'][r][cols] = True
    for c in range(cols):
        board['h_walls'][0][c] = True
        board['h_walls'][rows][c] = True


def _in_bounds_rc(rc: Any, rows: int, cols: int) -> bool:
    return (
        isinstance(rc, (list, tuple)) and len(rc) == 2 and
        isinstance(rc[0], int) and isinstance(rc[1], int) and
        0 <= rc[0] < rows and 0 <= rc[1] < cols
    )


def _edge_blocked(board: Dict[str, Any], r: int, c: int, dr: int, dc: int) -> bool:
    rows = board['rows']
    cols = board['cols']
    # bounds for target cell
    nr = r + dr
    nc = c + dc
    if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
        return True
    # determine edge occupancy
    if dr == 0 and dc == -1:  # left
        return board['v_walls'][r][c] or board['v_gates'][r][c]
    if dr == 0 and dc == 1:   # right
        return board['v_walls'][r][c + 1] or board['v_gates'][r][c + 1]
    if dr == -1 and dc == 0:  # up
        return board['h_walls'][r][c] or board['h_gates'][r][c]
    if dr == 1 and dc == 0:   # down
        return board['h_walls'][r + 1][c] or board['h_gates'][r + 1][c]
    raise ValueError('Invalid direction')


def _toggle_all_gates(board: Dict[str, Any]) -> int:
    """Flip all gate bits; return number toggled."""
    cnt = 0
    vg = board['v_gates']
    hg = board['h_gates']
    for r in range(len(vg)):
        for c in range(len(vg[r])):
            vg[r][c] = not vg[r][c]
            cnt += 1
    for r in range(len(hg)):
        for c in range(len(hg[r])):
            hg[r][c] = not hg[r][c]
            cnt += 1
    return cnt


DIRS: Dict[str, Tuple[int, int]] = {
    'UP': (-1, 0),
    'DOWN': (1, 0),
    'LEFT': (0, -1),
    'RIGHT': (0, 1),
}


@dataclass
class StepResult:
    ok: bool
    action: str
    moved: bool
    blocked: bool
    toggled: int
    pos: Optional[Tuple[int, int]]
    won: bool
    done: bool
    reason: Optional[str]
    ascii: str


class Game:
    def __init__(self, board: Dict[str, Any]):
        b = deepcopy(board)
        _ensure_fields(b)
        self.initial = deepcopy(b)
        self.reset()

    @classmethod
    def from_json_file(cls, path: str) -> 'Game':
        with open(path, 'r', encoding='utf-8') as f:
            b = json.load(f)
        return cls(b)

    def reset(self) -> None:
        self.board = deepcopy(self.initial)
        self.done = False
        self.won = False
        self.history: List[Dict[str, Any]] = []
        self.step_count = 0

    def snapshot(self) -> Dict[str, Any]:
        return {
            'board': deepcopy(self.board),
            'done': self.done,
            'won': self.won,
            'step_count': self.step_count,
        }

    def restore(self, snap: Dict[str, Any]) -> None:
        self.board = snap['board']
        self.done = snap['done']
        self.won = snap['won']
        self.step_count = snap.get('step_count', 0)

    @staticmethod
    def parse_action(s: str) -> Optional[str]:
        if not isinstance(s, str):
            return None
        t = s.strip()
        if not t:
            return None
        # allow prefix like "Action: UP"
        if ':' in t:
            _, t2 = t.split(':', 1)
            t = t2.strip()
        t = t.upper()
        if t in DIRS or t in {'WAIT', 'UNDO', 'RESET'}:
            return t
        return None

    def to_text(self, join_style: str = 'auto') -> str:
        return board_to_double_res_text(self.board, join_style=join_style)

    def step(self, action: Action) -> StepResult:
        a = self.parse_action(action)
        if a is None:
            return StepResult(False, str(action), False, False, 0, self._pos(), self.won, self.done, 'invalid_action', self.to_text())

        if a == 'RESET':
            self.reset()
            return StepResult(True, a, False, False, 0, self._pos(), self.won, self.done, None, self.to_text())

        if a == 'UNDO':
            if not self.history:
                return StepResult(False, a, False, False, 0, self._pos(), self.won, self.done, 'no_history', self.to_text())
            snap = self.history.pop()
            self.restore(snap)
            return StepResult(True, a, False, False, 0, self._pos(), self.won, self.done, None, self.to_text())

        if self.done:
            return StepResult(False, a, False, False, 0, self._pos(), self.won, self.done, 'game_over', self.to_text())

        # Record state for UNDO
        self.history.append(self.snapshot())

        moved = False
        blocked = False
        toggled = 0

        if a == 'WAIT':
            # no movement, no toggles
            pass
        else:
            dr, dc = DIRS[a]
            pr, pc = self._pos() or (None, None)
            if pr is None:
                # No player set on board
                blocked = True
            else:
                if _edge_blocked(self.board, pr, pc, dr, dc):
                    blocked = True
                else:
                    # Move
                    self.board['player'] = [pr + dr, pc + dc]
                    moved = True
                    # Step onto key? toggle all gates
                    if self._on_key():
                        toggled = _toggle_all_gates(self.board)

        # Check traps (lose immediately if on trap)
        if self._on_trap():
            self.done = True
            self.won = False
        # Check exit (win immediately; enemies do not move if you reached exit)
        elif self._on_exit():
            self.done = True
            self.won = True
        else:
            # Enemies move if game not already won
            self._enemies_turn()

        self.step_count += 1

        return StepResult(True, a, moved, blocked, toggled, self._pos(), self.won, self.done, None, self.to_text())

    # Enemy turn processing -------------------------------------------------
    def _enemies_turn(self) -> None:
        # Two mummy steps (white and red), then one scorpion step
        for _ in range(2):
            if self.done:
                return
            self._mummy_phase()
            if self._player_captured():
                self.done = True
                self.won = False
                return
        if not self.done:
            self._scorpion_phase()
            if self._player_captured():
                self.done = True
                self.won = False

    def _player_captured(self) -> bool:
        p = self._pos()
        if p is None:
            return False
        # Any enemy on player's cell?
        for rc in (self.board.get('white_mummies') or []):
            if rc[0] == p[0] and rc[1] == p[1]:
                return True
        for rc in (self.board.get('red_mummies') or []):
            if rc[0] == p[0] and rc[1] == p[1]:
                return True
        for rc in (self.board.get('scorpions') or []):
            if rc[0] == p[0] and rc[1] == p[1]:
                return True
        return False

    def _mummy_phase(self) -> None:
        # Build list of mummies in a deterministic order: whites then reds
        mummies = [("white", [int(r), int(c)]) for (r,c) in (self.board.get('white_mummies') or [])]
        mummies += [("red", [int(r), int(c)]) for (r,c) in (self.board.get('red_mummies') or [])]
        # Occupancy includes all enemies at phase start
        occ = { (rc[0], rc[1]): (typ, i) for i, (typ, rc) in enumerate(mummies) }
        # Also include scorpions to allow collisions (mover survives rule)
        scorpions = [[int(r), int(c)] for (r,c) in (self.board.get('scorpions') or [])]
        sc_occ = { (r, c): ("scorpion", i) for i, (r, c) in enumerate(scorpions) }
        # Process sequentially; last mover into a square wins
        survivors: list[tuple[str, list[int]]] = []
        # Keep track if an entity is still alive
        alive_mummy = [True] * len(mummies)
        alive_scorp = [True] * len(scorpions)

        for i, (typ, rc) in enumerate(mummies):
            if not alive_mummy[i]:
                continue
            r, c = rc
            dr, dc = self._mummy_dir(typ, r, c)
            if dr == 0 and dc == 0:
                # No move
                survivors.append((typ, [r, c]))
                continue
            if _edge_blocked(self.board, r, c, dr, dc):
                # Can't move due to edge block
                survivors.append((typ, [r, c]))
                continue
            nr, nc = r + dr, c + dc
            # Check collisions
            if (nr, nc) in occ:
                # Kill occupant mummy; mover survives and takes the square
                occ.pop((nr, nc), None)
                # Mark that occupant as dead by scanning mummies list
                for j, (_t2, rc2) in enumerate(mummies):
                    if alive_mummy[j] and rc2[0] == nr and rc2[1] == nc:
                        alive_mummy[j] = False
                        break
                # Update occupancy: remove mover's old and set new
                occ.pop((r, c), None)
                occ[(nr, nc)] = (typ, i)
                survivors.append((typ, [nr, nc]))
            elif (nr, nc) in sc_occ and alive_scorp[sc_occ[(nr, nc)][1]]:
                # Mummy moves onto scorpion -> mover survives
                sidx = sc_occ[(nr, nc)][1]
                alive_scorp[sidx] = False
                occ.pop((r, c), None)
                occ[(nr, nc)] = (typ, i)
                survivors.append((typ, [nr, nc]))
            else:
                # Empty or player cell
                prc = self._pos()
                if prc is not None and (nr, nc) == prc:
                    # Capture will be detected after phase; still move into cell
                    pass
                occ.pop((r, c), None)
                occ[(nr, nc)] = (typ, i)
                survivors.append((typ, [nr, nc]))
            # If landing on a key, toggle all gates
            if self._cell_has_key(nr, nc):
                _toggle_all_gates(self.board)

        # Update board lists and remove dead scorpions
        self.board['white_mummies'] = [pos for (t, pos) in survivors if t == 'white']
        self.board['red_mummies'] = [pos for (t, pos) in survivors if t == 'red']
        self.board['scorpions'] = [scorpions[i] for i in range(len(scorpions)) if alive_scorp[i]]

    def _mummy_dir(self, typ: str, r: int, c: int) -> tuple[int, int]:
        # Direction towards player based on priority
        p = self._pos()
        if p is None:
            return (0, 0)
        pr, pc = p
        dv = pr - r
        dh = pc - c
        # sign
        sv = 1 if dv > 0 else (-1 if dv < 0 else 0)
        sh = 1 if dh > 0 else (-1 if dh < 0 else 0)
        if typ == 'white':
            # horizontal first if closes distance and available
            if sh != 0 and not _edge_blocked(self.board, r, c, 0, sh):
                return (0, sh)
            if sv != 0 and not _edge_blocked(self.board, r, c, sv, 0):
                return (sv, 0)
            return (0, 0)
        else:  # 'red'
            if sv != 0 and not _edge_blocked(self.board, r, c, sv, 0):
                return (sv, 0)
            if sh != 0 and not _edge_blocked(self.board, r, c, 0, sh):
                return (0, sh)
            return (0, 0)

    def _scorpion_phase(self) -> None:
        # Scorpions move one step towards player
        scs = [[int(r), int(c)] for (r,c) in (self.board.get('scorpions') or [])]
        # Occupancy of enemies (post-mummy)
        occ = { (r, c): ('scorpion', i) for i, (r, c) in enumerate(scs) }
        for (r, c) in (self.board.get('white_mummies') or []):
            occ[(r, c)] = ('white', -1)
        for (r, c) in (self.board.get('red_mummies') or []):
            occ[(r, c)] = ('red', -1)

        alive_scorp = [True] * len(scs)
        new_scs: list[list[int]] = []

        for i, (r, c) in enumerate(scs):
            if not alive_scorp[i]:
                continue
            dr, dc = self._scorpion_dir(r, c)
            if dr == 0 and dc == 0:
                new_scs.append([r, c])
                continue
            if _edge_blocked(self.board, r, c, dr, dc):
                new_scs.append([r, c])
                continue
            nr, nc = r + dr, c + dc
            # Collisions: mover survives rule
            if (nr, nc) in occ:
                typ, _idx = occ[(nr, nc)]
                if typ in ('white', 'red'):
                    # Mover (scorpion) survives per mover-wins rule
                    # Remove the mummy it collided with
                    if typ == 'white':
                        self.board['white_mummies'] = [rc for rc in self.board['white_mummies'] if not (rc[0]==nr and rc[1]==nc)]
                    else:
                        self.board['red_mummies'] = [rc for rc in self.board['red_mummies'] if not (rc[0]==nr and rc[1]==nc)]
                    occ.pop((nr, nc), None)
                    occ.pop((r, c), None)
                    occ[(nr, nc)] = ('scorpion', i)
                    new_scs.append([nr, nc])
                else:
                    # Another scorpion occupied; last mover wins
                    # Remove the previous scorpion
                    # Find its index if present
                    for j, (sr, sc) in enumerate(scs):
                        if alive_scorp[j] and sr == nr and sc == nc:
                            alive_scorp[j] = False
                            break
                    occ.pop((nr, nc), None)
                    occ.pop((r, c), None)
                    occ[(nr, nc)] = ('scorpion', i)
                    new_scs.append([nr, nc])
            else:
                # Empty or player cell
                prc = self._pos()
                if prc is not None and (nr, nc) == prc:
                    pass  # capture handled after phase
                occ.pop((r, c), None)
                occ[(nr, nc)] = ('scorpion', i)
                new_scs.append([nr, nc])
            # If landing on a key, toggle all gates
            if self._cell_has_key(nr, nc):
                _toggle_all_gates(self.board)

        self.board['scorpions'] = [rc for k, rc in enumerate(new_scs) if alive_scorp[k] or k < len(new_scs)]

    def _scorpion_dir(self, r: int, c: int) -> tuple[int, int]:
        # Move like a mummy (white behavior: horizontal-first if it reduces distance), but only one step overall.\r
        return self._mummy_dir('white', r, c)

    # helpers
    def _pos(self) -> Optional[Tuple[int, int]]:
        p = self.board.get('player')
        if isinstance(p, list) and len(p) == 2:
            return int(p[0]), int(p[1])
        return None

    def _on_exit(self) -> bool:
        p = self.board.get('player')
        e = self.board.get('exit')
        return isinstance(p, list) and isinstance(e, list) and p == e

    def _on_key(self) -> bool:
        p = self.board.get('player')
        if not (isinstance(p, list) and len(p) == 2):
            return False
        pr, pc = p
        return self._cell_has_key(pr, pc)

    def _on_trap(self) -> bool:
        p = self.board.get('player')
        if not (isinstance(p, list) and len(p) == 2):
            return False
        pr, pc = p
        return self._cell_has_trap(pr, pc)

    def _cell_has_key(self, r: int, c: int) -> bool:
        return any((k and len(k) == 2 and k[0] == r and k[1] == c) for k in (self.board.get('keys') or []))

    def _cell_has_trap(self, r: int, c: int) -> bool:
        return any((t and len(t) == 2 and t[0] == r and t[1] == c) for t in (self.board.get('traps') or []))


def _main(argv: List[str]) -> int:
    if len(argv) < 2:
        print('usage: python mummy_env.py <board.json> [ACTIONS ...]', file=sys.stderr)
        return 2
    board_path = argv[1]
    actions = argv[2:]
    game = Game.from_json_file(board_path)
    for a in actions:
        res = game.step(a)
        print(f'\n=== {res.action} ===')
        print(res.ascii)
        if res.reason:
            print(f'# reason: {res.reason}')
        if res.done:
            break
    # Final summary as JSON
    summary = {
        'pos': game._pos(),
        'done': game.done,
        'won': game.won,
        'steps': game.step_count,
    }
    print('\n# summary:')
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv))

