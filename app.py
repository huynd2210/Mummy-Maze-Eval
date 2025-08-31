from flask import Flask, render_template, request, jsonify
import os
import json
import uuid
from datetime import datetime
from copy import deepcopy

# Optional LLM prompt integration
try:
    from llm_prompt import Prompt  # type: ignore
except Exception:  # pragma: no cover
    Prompt = None  # type: ignore

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RUNS_DIR = os.path.join(DATA_DIR, 'runs')
BOARDS_DIR = os.path.join(DATA_DIR, 'boards')
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
    os.makedirs(RUNS_DIR, exist_ok=True)
    os.makedirs(BOARDS_DIR, exist_ok=True)


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
    os.makedirs(RUNS_DIR, exist_ok=True)
    os.makedirs(BOARDS_DIR, exist_ok=True)


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


def _is_safe_board_name(name: str) -> bool:
    # Allow only simple names like "foo.json", alnum, dash, underscore, dot
    if not isinstance(name, str) or len(name) == 0 or len(name) > 128:
        return False
    import re
    return re.fullmatch(r"[A-Za-z0-9_.-]+", name) is not None and name.lower().endswith('.json')


def list_boards() -> list[str]:
    ensure_data_dir()
    names: list[str] = []
    # Include classic single board if present
    if os.path.exists(BOARD_PATH):
        names.append('board.json')
    # Include boards in data/boards
    if os.path.isdir(BOARDS_DIR):
        for fn in os.listdir(BOARDS_DIR):
            if fn.lower().endswith('.json') and _is_safe_board_name(fn):
                names.append(fn)
    # De-dup while preserving order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def load_board_named(name: str | None) -> tuple[str, dict]:
    """Load a normalized board by name. Returns (board_name, board_dict).
    - name == None or 'board.json' -> load data/board.json
    - else load data/boards/<name>
    """
    ensure_data_dir()
    if not name or name == 'board.json':
        return 'board.json', load_board()
    if not _is_safe_board_name(name):
        raise ValueError('invalid_board_name')
    path = os.path.join(BOARDS_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError('board_not_found')
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return name, normalize_board(raw)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/play')
def play():
    return render_template('play.html')


@app.get('/api/board')
def api_get_board():
    board = load_board()
    return jsonify(board)


@app.get('/api/boards')
def api_list_boards():
    try:
        names = list_boards()
        default = 'board.json' if 'board.json' in names else (names[0] if names else None)
        return jsonify({'boards': names, 'default': default})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


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


# ---------------------- LLM Run Orchestration ----------------------
# Simple in-memory store; also persisted to data/runs/<run_id>.json
RUNS = {}

INSTRUCTIONS = (
    "Task: You are an explorer in the game Mummy Maze Deluxe. The objective is to reach the exit without being caught.\n"
    "The game is played on a grid with the following rules:\n\n"
    "You (the explorer) move first, exactly one square per turn (up, down, left, or right).\n\n"
    "Then, all enemies move:\n\n"
    "White mummy: Moves up to 2 squares per turn. Prioritizes moving horizontally toward you if possible, otherwise vertically.\n\n"
    "Red mummy: Moves up to 2 squares per turn. Prioritizes moving vertically toward you if possible, otherwise horizontally.\n\n"
    "Scorpion: Moves 1 square per turn, directly toward you.\n\n"
    "Enemies cannot move diagonally. You cannot move diagonally.\n\n"
    "If a mummy or scorpion lands on your square, you lose.\n\n"
    "If a white and red mummy collide, the one that moved second survives.\n\n"
    "If a mummy collides with a scorpion, the mummy survives.\n\n"
    "Stepping on a trap kills the explorer but does not affect enemies.\n\n"
    "Stepping on a key toggles gates for all characters.\n\n"
    "The output format is: \"Action: <action>\".\n\n"
    "Available actions are: UP, DOWN, LEFT, RIGHT, WAIT, UNDO, RESET.\n"
)

ALLOWED_ACTIONS = {"UP", "DOWN", "LEFT", "RIGHT", "WAIT", "UNDO", "RESET"}

def parse_action_text(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    t = text.strip()
    import re
    m = re.search(r"Action\s*:\s*([A-Za-z]+)", t)
    if m:
        cand = m.group(1).strip().upper()
        if cand in ALLOWED_ACTIONS:
            return cand
    u = t.upper()
    for a in ["UP","DOWN","LEFT","RIGHT","WAIT","UNDO","RESET"]:
        if a in u:
            return a
    return None


@app.post('/api/run/start')
def api_run_start():
    try:
        ensure_data_dir()
        body = request.get_json(force=True) or {}
        model = body.get('model') or os.environ.get('LLM_MODEL') or 'openrouter/meta-llama/llama-3.1-8b-instruct'
        temperature = float(body.get('temperature', 0.2))
        board_name = body.get('board')
        micro = bool(body.get('micro', True))
        # Load requested board (defaults to board.json)
        loaded_name, board = load_board_named(board_name)
        from mummy_env import Game  # import here to avoid circulars
        game = Game(board)
        ascii_state = game.to_text()
        rid = str(uuid.uuid4())
        run = {
            'id': rid,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'model': model,
'temperature': temperature,
            'board_name': loaded_name,
            'micro': micro,
            'game': game,
'move_count': 0,
            'repeat_count': 0,
            'last_player_ascii': ascii_state,
            'no_change_streak': 0,
            'last_ascii': ascii_state,
            'ended': False,
            'result': None,
            'reason': None,
            'log': [
                {
                    'type': 'system',
                    'content': INSTRUCTIONS,
                },
                {
                    'type': 'state',
                    'ascii': ascii_state,
                }
            ]
        }
        RUNS[rid] = run
        # persist initial
        _persist_run(rid)
        return jsonify({'run_id': rid, 'ascii': ascii_state, 'board': game.board, 'board_name': loaded_name, 'move_count': 0, 'repeat_count': 0}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.post('/api/run/step')
def api_run_step():
    try:
        body = request.get_json(force=True) or {}
        rid = body.get('run_id')
        mode = (body.get('mode') or 'llm').lower()  # 'llm' or 'human'
        human_action = body.get('action')
        run = RUNS.get(rid)
        if not run:
            return jsonify({'status': 'error', 'message': 'invalid_run'}), 400
        if run['ended']:
            return jsonify({'status': 'error', 'message': 'run_ended'}), 400

        game = run['game']
        ascii_state = game.to_text()
        action = None
        prompt_text = None
        llm_reply = None

        # Determine micro or turn-based
        is_micro = bool(run.get('micro', False))
        current_phase = getattr(game, 'phase', 'player') if is_micro else 'turn'

        if mode == 'human':
            action = human_action or 'WAIT'
        else:
            if is_micro and current_phase != 'player':
                # Don't ask LLM on non-player phases
                action = 'WAIT'
            else:
                if Prompt is None:
                    return jsonify({'status': 'error', 'message': 'LLM unavailable'}), 500
                # Build prompt
                prompt_text = INSTRUCTIONS + "\nCurrent grid (double-resolution):\n\n" + ascii_state + "\n\nRespond ONLY with: Action: <UP|DOWN|LEFT|RIGHT|WAIT|UNDO|RESET>\n"
                p = Prompt(modelName=run['model'], message=prompt_text, promptStrategy=Prompt.deliverLiteLLMPrompt, temperature=run['temperature'])
                llm_reply = p.deliver()
                # Print full reply to backend logs
                try:
                    print(f"[LLM reply] run={rid} phase={current_phase} model={run['model']} reply={llm_reply!r}")
                except Exception:
                    pass
                parsed = parse_action_text(llm_reply) or 'WAIT'
                action = parsed

        # Apply step
        if is_micro:
            res = game.step_micro(action)
        else:
            res = game.step(action)

        new_ascii = res.ascii
        # Only player's phase increments moves and 3-fold repetition counter
        if is_micro:
            if getattr(res, 'phase', '') == 'player':
                run['move_count'] = run.get('move_count', 0) + 1
                if new_ascii == run.get('last_player_ascii'):
                    run['repeat_count'] = run.get('repeat_count', 0) + 1
                else:
                    run['repeat_count'] = 0
                run['last_player_ascii'] = new_ascii
        else:
            run['move_count'] = run.get('move_count', 0) + 1
            if new_ascii == run.get('last_player_ascii'):
                run['repeat_count'] = run.get('repeat_count', 0) + 1
            else:
                run['repeat_count'] = 0
            run['last_player_ascii'] = new_ascii

        # Maintain last_ascii for display diffs (not used for 3-fold)
        if new_ascii == run.get('last_ascii'):
            run['no_change_streak'] = run.get('no_change_streak', 0) + 1
        else:
            run['no_change_streak'] = 0
        run['last_ascii'] = new_ascii

        # Log the exchange
        if prompt_text is not None:
            run['log'].append({'type': 'user_prompt', 'content': prompt_text})
        if llm_reply is not None:
            run['log'].append({
                'type': 'assistant',
                'content': str(llm_reply),
                'parsed_action': action,
                'phase': current_phase,
                'model': run.get('model'),
                'time': datetime.utcnow().isoformat() + 'Z',
            })
        run['log'].append({
            'type': 'env',
            'action': res.action,
'summary': {
                'moved': res.moved,
                'blocked': res.blocked,
                'toggled': res.toggled,
                'pos': res.pos,
                'done': res.done,
                'won': res.won,
                'reason': res.reason,
                'phase': getattr(res, 'phase', 'turn'),
            },
            'events': getattr(res, 'events', []),
            'ascii': new_ascii,
        })

        # Check termination conditions
        if res.done:
            run['ended'] = True
            run['result'] = 'win' if res.won else 'lose'
            run['reason'] = 'goal' if res.won else (res.reason or 'caught')
        elif run['move_count'] >= 100:
            run['ended'] = True
            run['result'] = 'lose'
            run['reason'] = 'move_cap'
        elif run.get('repeat_count', 0) >= 3:
            run['ended'] = True
            run['result'] = 'lose'
            run['reason'] = 'threefold'

        _persist_run(rid)

        return jsonify({
            'status': 'ok',
            'run_id': rid,
            'action': res.action,
            'ascii': new_ascii,
            'board': game.board,
            'done': run['ended'],
            'won': res.won,
'move_count': run['move_count'],
            'repeat_count': run.get('repeat_count', 0),
            'reason': run['reason'] if run['ended'] else None,
'last_reply': (str(llm_reply) if llm_reply is not None else None),
            'phase': getattr(res, 'phase', 'turn'),
            'events': getattr(res, 'events', []),
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.get('/api/run/state')
def api_run_state():
    rid = request.args.get('run_id')
    run = RUNS.get(rid)
    if not run:
        return jsonify({'status': 'error', 'message': 'invalid_run'}), 400
    game = run['game']
    return jsonify({
        'run_id': rid,
        'ascii': game.to_text(),
        'board': game.board,
        'board_name': run.get('board_name'),
        'move_count': run['move_count'],
        'repeat_count': run.get('repeat_count', 0),
        'ended': run['ended'],
        'result': run['result'],
        'reason': run['reason'],
    })


@app.get('/api/run/replay')
def api_run_replay():
    rid = request.args.get('run_id')
    run = RUNS.get(rid)
    if not run:
        # try load from file
        path = os.path.join(RUNS_DIR, f'{rid}.json') if rid else None
        if not path or not os.path.exists(path):
            return jsonify({'status': 'error', 'message': 'invalid_run'}), 400
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'run_id': rid, 'log': data.get('log', [])})
    return jsonify({'run_id': rid, 'log': run['log']})


@app.get('/api/run/list')
def api_run_list():
    ensure_data_dir()
    items = []
    for name in os.listdir(RUNS_DIR):
        if name.endswith('.json'):
            items.append(name[:-5])
    return jsonify({'runs': items, 'active': list(RUNS.keys())})


@app.post('/api/run/stop')
def api_run_stop():
    body = request.get_json(force=True) or {}
    rid = body.get('run_id')
    run = RUNS.get(rid)
    if not run:
        return jsonify({'status': 'error', 'message': 'invalid_run'}), 400
    run['ended'] = True
    run['result'] = run['result'] or 'stopped'
    run['reason'] = run['reason'] or 'stopped'
    _persist_run(rid)
    return jsonify({'status': 'ok'})


def _persist_run(rid: str) -> None:
    try:
        ensure_data_dir()
        run = RUNS.get(rid)
        if not run:
            return
        # Prepare serializable snapshot (exclude Game object)
        data = {
            'id': run['id'],
            'created_at': run['created_at'],
            'model': run['model'],
            'temperature': run['temperature'],
            'move_count': run['move_count'],
            'no_change_streak': run['no_change_streak'],
            'ended': run['ended'],
            'result': run['result'],
            'reason': run['reason'],
            'log': run['log'],
            'board_name': run.get('board_name'),
            'board': run['game'].board,
        }
        out = os.path.join(RUNS_DIR, f'{rid}.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


if __name__ == '__main__':
    app.run(debug=True)
