import os
import json
import sys
import pytest

# Ensure repo root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app, DATA_DIR, BOARDS_DIR  # type: ignore
from mummy_env import Game


def write_board_file(name: str, board: dict) -> str:
    os.makedirs(BOARDS_DIR, exist_ok=True)
    path = os.path.join(BOARDS_DIR, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(board, f)
    return path


def minimal_board(rows=2, cols=2):
    # Minimal normalized-like board
    v_walls = [[False] * (cols + 1) for _ in range(rows)]
    h_walls = [[False] * cols for _ in range(rows + 1)]
    for r in range(rows):
        v_walls[r][0] = True
        v_walls[r][cols] = True
    for c in range(cols):
        h_walls[0][c] = True
        h_walls[rows][c] = True
    return {
        'rows': rows,
        'cols': cols,
        'v_walls': v_walls,
        'h_walls': h_walls,
        'v_gates': [[False]*(cols+1) for _ in range(rows)],
        'h_gates': [[False]*cols for _ in range(rows+1)],
        'player': [0,0],
        'exit': None,
        'white_mummies': [],
        'red_mummies': [],
        'scorpions': [],
        'traps': [],
        'keys': [],
    }


def test_micro_player_counters_only_and_empty_enemy_events():
    # Board with no enemies: only player steps should increment move_count and repeat_count
    board = minimal_board(2, 2)
    fname = 'test_micro.json'
    write_board_file(fname, board)

    client = flask_app.test_client()
    r = client.post('/api/run/start', json={'model': 'dummy', 'board': fname, 'micro': True})
    assert r.status_code == 200
    j = r.get_json()
    rid = j['run_id']

    # Step 1: player WAIT
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json()
    assert j['phase'] == 'player'
    assert j['move_count'] == 1
    assert j['repeat_count'] == 1  # ASCII unchanged from last player ascii

    # Step 2: mummy1 phase (no enemies) -> counters unchanged, no events
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json()
    assert j['phase'] == 'mummy1'
    assert j['move_count'] == 1 and j['repeat_count'] == 1
    assert isinstance(j['events'], list) and len(j['events']) == 0

    # Step 3: mummy2 phase
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json()
    assert j['phase'] == 'mummy2'
    assert j['move_count'] == 1 and j['repeat_count'] == 1
    assert isinstance(j['events'], list) and len(j['events']) == 0

    # Step 4: scorpion phase, no scorpions -> no events
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json()
    assert j['phase'] == 'scorpion'
    assert j['move_count'] == 1 and j['repeat_count'] == 1
    assert isinstance(j['events'], list) and len(j['events']) == 0

    # Step 5: back to player WAIT -> repeat_count increments
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json()
    assert j['phase'] == 'player'
    assert j['move_count'] == 2 and j['repeat_count'] == 2


def test_mummy_toggle_key_event_logging():
    # 1x3 row: white mummy at (0,0), key at (0,1), gate present and initially OPEN so mummy crosses and toggles
    board = minimal_board(rows=1, cols=3)
    board['player'] = [0,2]
    board['white_mummies'] = [[0,0]]
    board['keys'] = [[0,1]]
    board['v_gates'][0][1] = True
    # Pre-open the gate so mummy can cross
    board['v_gate_open'] = [[False, True, False]]
    g = Game(board)
    # step to mummy1 phase
    _ = g.step_micro('WAIT')  # player phase
    res = g.step_micro('WAIT')  # mummy1 phase
    ev = res.events
    # Expect a toggle_gates caused by white
    assert any(e.get('type') == 'toggle_gates' and e.get('by') == 'white' for e in ev)

