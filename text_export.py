"""
text_export.py

Convert a board JSON (as used by the Flask editor) into a double-resolution ASCII grid.

Double-resolution layout (cell centers at odd indices; edges at even indices):
- Text grid size: H = 2*rows + 1, W = 2*cols + 1
- Cells occupy positions (2*r+1, 2*c+1)
- Vertical edges occupy (2*r+1, 2*c)
- Horizontal edges occupy (2*r, 2*c+1)
- Intersections/junctions occupy (2*r, 2*c)

Join styles:
- 'auto' (default):
    '+' when both a horizontal and vertical edge meet at a junction,
    '-' when only horizontal edges meet,
    '|' when only vertical edges meet.
- 'plus': always '+" at any junction that touches an edge (classic grid look).
- 'line': same as 'auto' (alias) – matches examples like +---+ …

Entities placed in cells (precedence low -> high so later overrides earlier):
  trap (T) < key (K) < scorpion (S) < white mummy (W) < red mummy (R) < exit (E) < player (P)

Gates:
- Horizontal gates rendered as '='
- Vertical gates rendered as ':'

Usage:
    import json
    from text_export import board_to_double_res_text

    with open('data/board.json', 'r', encoding='utf-8') as f:
        board = json.load(f)

    print(board_to_double_res_text(board, join_style='auto'))
"""
from typing import Dict, List, Optional

DEFAULT_SYMBOLS: Dict[str, str] = {
    # edges
    'corner': '+',
    'h_wall': '-',
    'v_wall': '|',
    'h_gate': '=',
    'v_gate': ':',
    'empty': '.',
    # entities
    'player': 'P',
    'exit': 'E',
    'white': 'W',
    'red': 'R',
    'scorpion': 'S',
    'key': 'K',
    'trap': 'T',
}


def _zeros(rows: int, cols: int) -> List[List[bool]]:
    return [[False] * cols for _ in range(rows)]


def _get_matrix(board: dict, name: str, rows: int, cols: int) -> List[List[bool]]:
    m = board.get(name)
    if not isinstance(m, list) or len(m) != rows:
        return _zeros(rows, cols)
    out: List[List[bool]] = []
    for r in range(rows):
        row = m[r]
        if not isinstance(row, list) or len(row) != cols:
            out.append([False] * cols)
        else:
            out.append([bool(v) for v in row])
    return out


def board_to_double_res_text(board: dict, join_style: str = 'auto', symbols: Optional[Dict[str, str]] = None) -> str:
    syms = dict(DEFAULT_SYMBOLS)
    if symbols:
        syms.update(symbols)

    rows = int(board.get('rows', 0))
    cols = int(board.get('cols', 0))
    if rows <= 0 or cols <= 0:
        return ''

    # Edge matrices (with fallbacks if fields are missing)
    v_walls = _get_matrix(board, 'v_walls', rows, cols + 1)
    h_walls = _get_matrix(board, 'h_walls', rows + 1, cols)
    v_gates = _get_matrix(board, 'v_gates', rows, cols + 1)
    h_gates = _get_matrix(board, 'h_gates', rows + 1, cols)

    H = 2 * rows + 1
    W = 2 * cols + 1
    grid: List[List[str]] = [[syms['empty'] for _ in range(W)] for _ in range(H)]

    # Draw horizontal edges
    for r in range(rows + 1):
        rr = 2 * r
        for c in range(cols):
            cc = 2 * c + 1
            if h_walls[r][c]:
                grid[rr][cc] = syms['h_wall']
            elif h_gates[r][c]:
                grid[rr][cc] = syms['h_gate']

    # Draw vertical edges
    for r in range(rows):
        for c in range(cols + 1):
            rr = 2 * r + 1
            cc = 2 * c
            if v_walls[r][c]:
                grid[rr][cc] = syms['v_wall']
            elif v_gates[r][c]:
                grid[rr][cc] = syms['v_gate']

    # Determine junction characters at intersections
    def has_h(r: int, c: int) -> bool:
        return ((c > 0 and (h_walls[r][c-1] or h_gates[r][c-1])) or
                (c < cols and (h_walls[r][c]   or h_gates[r][c])))

    def has_v(r: int, c: int) -> bool:
        return ((r > 0 and (v_walls[r-1][c] or v_gates[r-1][c])) or
                (r < rows and (v_walls[r][c]   or v_gates[r][c])))

    def has_h_wall(r: int, c: int) -> bool:
        return ((c > 0 and h_walls[r][c-1]) or (c < cols and h_walls[r][c]))

    def has_v_wall(r: int, c: int) -> bool:
        return ((r > 0 and v_walls[r-1][c]) or (r < rows and v_walls[r][c]))

    for r in range(rows + 1):
        for c in range(cols + 1):
            rr = 2 * r
            cc = 2 * c
            h_edge = has_h(r, c)
            v_edge = has_v(r, c)
            if not h_edge and not v_edge:
                continue  # leave as empty
            if join_style == 'plus':
                grid[rr][cc] = syms['corner']
            else:  # 'auto' or 'line'
                if h_edge and v_edge:
                    grid[rr][cc] = syms['corner']
                elif h_edge:
                    grid[rr][cc] = syms['h_wall'] if has_h_wall(r, c) else syms['h_gate']
                else:  # v_edge only
                    grid[rr][cc] = syms['v_wall'] if has_v_wall(r, c) else syms['v_gate']

    # Place entities (low -> high priority)
    def in_bounds(rc) -> bool:
        return (isinstance(rc, (list, tuple)) and len(rc) == 2 and
                isinstance(rc[0], int) and isinstance(rc[1], int) and
                0 <= rc[0] < rows and 0 <= rc[1] < cols)

    def put_cell(rc, ch: str) -> None:
        if not in_bounds(rc):
            return
        r, c = int(rc[0]), int(rc[1])
        grid[2*r + 1][2*c + 1] = ch

    # Collect lists (fallbacks if missing)
    white = board.get('white_mummies') or []
    red = board.get('red_mummies') or []
    traps = board.get('traps') or []
    keys = board.get('keys') or []
    scorpions = board.get('scorpions') or []

    # Low -> high precedence
    for rc in traps: put_cell(rc, syms['trap'])
    for rc in keys: put_cell(rc, syms['key'])
    for rc in scorpions: put_cell(rc, syms['scorpion'])
    for rc in white: put_cell(rc, syms['white'])
    for rc in red: put_cell(rc, syms['red'])

    exit_rc = board.get('exit')
    if in_bounds(exit_rc):
        put_cell(exit_rc, syms['exit'])

    player_rc = board.get('player')
    if in_bounds(player_rc):
        put_cell(player_rc, syms['player'])

    # Convert to string
    return "\n".join("".join(row) for row in grid)


if __name__ == '__main__':
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'data/board.json'
    with open(path, 'r', encoding='utf-8') as f:
        board = json.load(f)
    print(board_to_double_res_text(board, join_style='auto'))

