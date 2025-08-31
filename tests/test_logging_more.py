import os
import sys
import json
import pytest

# Ensure repo root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app, BOARDS_DIR  # type: ignore
from mummy_env import Game


def minimal_board(rows=2, cols=2):
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


def write_board_file(name: str, board: dict) -> str:
    os.makedirs(BOARDS_DIR, exist_ok=True)
    path = os.path.join(BOARDS_DIR, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(board, f)
    return path


def test_player_toggle_key_event_logging():
    # 2x2: put an internal horizontal gate and an internal vertical gate to be toggled
    board = minimal_board(2, 2)
    board['player'] = [0,0]
    board['keys'] = [[0,1]]
    # Internal gates
    board['v_gates'][0][1] = True
    board['h_gates'][1][0] = True
    # Open the vertical gate between (0,0) and (0,1) so player can reach key
    board['v_gate_open'] = [
        [False, True, False],
        [False, False, False],
    ]
    g = Game(board)
    res = g.step_micro('RIGHT')  # player onto key
    ev = res.events
    # Player toggled gates
    assert any(e.get('type') == 'toggle_gates' and e.get('by') == 'player' for e in ev)


def test_trap_event_and_done():
    board = minimal_board(1, 2)
    board['player'] = [0,0]
    board['traps'] = [[0,1]]
    g = Game(board)
    res = g.step_micro('RIGHT')
    assert any(e.get('type') == 'trap' and e.get('who') == 'player' for e in res.events)
    assert res.done is True and res.won is False


def test_exit_event_and_done():
    board = minimal_board(1, 2)
    board['player'] = [0,0]
    board['exit'] = [0,1]
    g = Game(board)
    res = g.step_micro('RIGHT')
    assert any(e.get('type') == 'exit' for e in res.events)
    assert res.done is True and res.won is True


def test_mummy_moves_simultaneous_no_collision_event():
    # 1x6: two whites at c=2 and c=3; with simultaneous resolution there is no collision event on first mummy phase
    board = minimal_board(rows=1, cols=6)
    board['player'] = [0,5]
    board['white_mummies'] = [[0,2], [0,3]]
    g = Game(board)
    _ = g.step_micro('WAIT')  # player phase
    res = g.step_micro('WAIT')  # mummy1
    # No collision event expected; both issue move events
    assert all(e.get('type') != 'collision' for e in res.events)
    assert sum(1 for e in res.events if e.get('type') == 'move' and e.get('entity') == 'white') >= 1


def test_collision_mummy_vs_scorpion_event():
    # 1x4: player at c=3, white at c=1, scorpion at c=2
    board = minimal_board(rows=1, cols=4)
    board['player'] = [0,3]
    board['white_mummies'] = [[0,1]]
    board['scorpions'] = [[0,2]]
    g = Game(board)
    _ = g.step_micro('WAIT')
    res = g.step_micro('WAIT')
    assert any(e.get('type') == 'collision' and e.get('winner') == 'white' and e.get('loser') == 'scorpion' for e in res.events)


def test_scorpion_move_event_and_server_threefold_end():
    # Board with a scorpion so scorpion phase emits a move event
    board = minimal_board(rows=2, cols=2)
    board['player'] = [1,1]
    board['scorpions'] = [[0,0]]
    g = Game(board)
    _ = g.step_micro('WAIT')  # player
    _ = g.step_micro('WAIT')  # mummy1
    _ = g.step_micro('WAIT')  # mummy2
    res = g.step_micro('WAIT')  # scorpion phase
    assert any(e.get('type') == 'move' and e.get('entity') == 'scorpion' for e in res.events)

    # Now check server-side 3-fold repetition end
    board2 = minimal_board(rows=1, cols=2)
    board2['player'] = [0,0]
    fname = 'threefold.json'
    write_board_file(fname, board2)
    client = flask_app.test_client()
    r = client.post('/api/run/start', json={'model': 'dummy', 'board': fname, 'micro': True})
    assert r.status_code == 200
    j = r.get_json(); rid = j['run_id']

    # Player WAIT 1 -> player phase
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json(); assert j['phase'] == 'player' and j['repeat_count'] == 1 and not j['done']
    # Advance 3 enemy phases
    for _ in range(3):
        r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
        j = r.get_json()
    # Player WAIT 2
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json(); assert j['phase'] == 'player' and j['repeat_count'] == 2 and not j['done']
    # Advance 3 enemy phases
    for _ in range(3):
        r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
        j = r.get_json()
    # Player WAIT 3 -> should end by threefold
    r = client.post('/api/run/step', json={'run_id': rid, 'mode': 'human', 'action': 'WAIT'})
    j = r.get_json()
    assert j['phase'] == 'player' and j['repeat_count'] == 3 and j['done'] is True
    assert j['reason'] == 'threefold'
