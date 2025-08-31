from flask import Flask, render_template, request, jsonify
import os
import json
from copy import deepcopy

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
BOARD_PATH = os.path.join(DATA_DIR, 'board.json')


def make_board(rows: int, cols: int) -> dict:
    rows = int(rows)
    cols = int(cols)
    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive integers")

    # Vertical walls: rows x (cols+1)
    v_walls = [[False] * (cols + 1) for _ in range(rows)]
    for r in range(rows):
        v_walls[r][0] = True          # left boundary
        v_walls[r][cols] = True       # right boundary

    # Horizontal walls: (rows+1) x cols
    h_walls = [[False] * cols for _ in range(rows + 1)]
    for c in range(cols):
        h_walls[0][c] = True          # top boundary
        h_walls[rows][c] = True       # bottom boundary

    # Gates default to none (all False). Gates are internal edges only.
    v_gates = [[False] * (cols + 1) for _ in range(rows)]
    h_gates = [[False] * cols for _ in range(rows + 1)]

    board = {
        "rows": rows,
        "cols": cols,
        "v_walls": v_walls,
        "h_walls": h_walls,
        "v_gates": v_gates,
        "h_gates": h_gates,
        # Entities/tiles
        "player": None,              # [r, c] or null
        "exit": None,                # [r, c] or null
        "white_mummies": [],         # list[[r,c], ...]
        "red_mummies": [],           # list[[r,c], ...]
        "traps": [],                 # list[[r,c], ...]
        "keys": [],                  # list[[r,c], ...]
    }

    return board


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _zeros(rows: int, cols: int, width_extra: int = 0, height_extra: int = 0):
    # helper to build False matrices of shapes used by edges
    # vertical: rows x (cols+1) => width_extra=1
    # horizontal: (rows+1) x cols => height_extra=1
    if height_extra:
        return [[False] * cols for _ in range(rows + height_extra)]
    if width_extra:
        return [[False] * (cols + width_extra) for _ in range(rows)]
    return [[False] * cols for _ in range(rows)]


def normalize_board(board: dict) -> dict:
    """Return a normalized board dict with required fields and shapes.
    Ensures boundaries are walls, gates are not on boundaries, and entity positions are in-bounds.
    """
    if not isinstance(board, dict):
        raise ValueError("board must be a JSON object")

    rows = int(board.get("rows", 8))
    cols = int(board.get("cols", 8))
    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive integers")

    base = make_board(rows, cols)

    # Merge walls
    for r in range(rows):
        # v_walls
        src_vw = board.get("v_walls") or []
        if r < len(src_vw):
            row = src_vw[r]
            if isinstance(row, list):
                for c in range(min(cols + 1, len(row))):
                    base["v_walls"][r][c] = bool(row[c])
        # enforce boundary walls
        base["v_walls"][r][0] = True
        base["v_walls"][r][cols] = True

    for r in range(rows + 1):
        src_hw = board.get("h_walls") or []
        if r < len(src_hw):
            row = src_hw[r]
            if isinstance(row, list):
                for c in range(min(cols, len(row))):
                    base["h_walls"][r][c] = bool(row[c])
        # enforce boundary walls
        if r == 0 or r == rows:
            for c in range(cols):
                base["h_walls"][r][c] = True

    # Merge gates; ensure no gates on boundaries
    src_vg = board.get("v_gates") or []
    for r in range(rows):
        if r < len(src_vg) and isinstance(src_vg[r], list):
            for c in range(min(cols + 1, len(src_vg[r]))):
                if 0 < c < cols:  # internal only
                    base["v_gates"][r][c] = bool(src_vg[r][c])
    src_hg = board.get("h_gates") or []
    for r in range(1, rows):  # internal rows only
        if r < len(src_hg) and isinstance(src_hg[r], list):
            for c in range(min(cols, len(src_hg[r]))):
                base["h_gates"][r][c] = bool(src_hg[r][c])

    # If an edge is both wall and gate, prefer the explicitly set one based on current content.
    # For simplicity, if both are True, keep wall and drop gate.
    for r in range(rows):
        for c in range(cols + 1):
            if base["v_walls"][r][c] and base["v_gates"][r][c]:
                base["v_gates"][r][c] = False
    for r in range(rows + 1):
        for c in range(cols):
            if base["h_walls"][r][c] and base["h_gates"][r][c]:
                base["h_gates"][r][c] = False

    def in_bounds(rc):
        return (
            isinstance(rc, (list, tuple)) and len(rc) == 2 and
            isinstance(rc[0], int) and isinstance(rc[1], int) and
            0 <= rc[0] < rows and 0 <= rc[1] < cols
        )

    # Entities and tiles
    player = board.get("player", None)
    base["player"] = list(player) if in_bounds(player) else None

    exit_pos = board.get("exit", None)
    base["exit"] = list(exit_pos) if in_bounds(exit_pos) else None

    def normalize_list(name):
        vals = []
        for rc in board.get(name, []) or []:
            if in_bounds(rc):
                vals.append([int(rc[0]), int(rc[1])])
        return vals

    base["white_mummies"] = normalize_list("white_mummies")
    base["red_mummies"] = normalize_list("red_mummies")
    base["traps"] = normalize_list("traps")
    base["keys"] = normalize_list("keys")

    return base


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def save_board(board: dict) -> None:
    ensure_data_dir()
    with open(BOARD_PATH, 'w', encoding='utf-8') as f:
        json.dump(board, f, indent=2)


def load_board() -> dict:
    ensure_data_dir()
    if not os.path.exists(BOARD_PATH):
        board = make_board(8, 8)
        save_board(board)
        return board
    with open(BOARD_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return normalize_board(raw)


@app.route('/')
def index():
    return render_template('index.html')


@app.get('/api/board')
def api_get_board():
    board = load_board()
    return jsonify(board)


@app.post('/api/board')
def api_save_board():
    try:
        incoming = request.get_json(force=True)
        board = normalize_board(incoming)
        save_board(board)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.post('/api/new')
def api_new_board():
    try:
        data = request.get_json(force=True) or {}
        rows = int(data.get('rows', 8))
        cols = int(data.get('cols', 8))
        board = make_board(rows, cols)
        save_board(board)
        return jsonify(board)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True)
