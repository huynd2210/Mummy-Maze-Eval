import json
import builtins
import types
import pytest
import os, sys
# Ensure repository root on path for direct module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mummy_env import Game


def fresh_board(rows=2, cols=2):
    # Minimal board constructor mirroring app.make_board
    v_walls = [[False] * (cols + 1) for _ in range(rows)]
    h_walls = [[False] * cols for _ in range(rows + 1)]
    # boundary walls
    for r in range(rows):
        v_walls[r][0] = True
        v_walls[r][cols] = True
    for c in range(cols):
        h_walls[0][c] = True
        h_walls[rows][c] = True

    board = {
        "rows": rows,
        "cols": cols,
        "v_walls": v_walls,
        "h_walls": h_walls,
        "v_gates": [[False] * (cols + 1) for _ in range(rows)],
        "h_gates": [[False] * cols for _ in range(rows + 1)],
        "player": [0, 0],
        "exit": None,
        "white_mummies": [],
        "red_mummies": [],
        "traps": [],
        "keys": [],
        "scorpions": [],
    }
    return board


def test_move_blocked_by_top_boundary():
    b = fresh_board(2, 2)
    g = Game(b)
    res = g.step('UP')
    assert res.ok is True
    assert res.moved is False and res.blocked is True
    assert res.pos == (0, 0)


def test_move_right_open_edge():
    b = fresh_board(2, 2)
    g = Game(b)
    res = g.step('RIGHT')
    assert res.moved is True and res.blocked is False
    assert res.pos == (0, 1)


def test_move_blocked_by_internal_wall():
    b = fresh_board(2, 2)
    # Wall between (0,0) and (0,1)
    b["v_walls"][0][1] = True
    g = Game(b)
    res = g.step('RIGHT')
    assert res.moved is False and res.blocked is True
    assert res.pos == (0, 0)


def test_gate_blocks_and_toggle_on_key():
    rows, cols = 2, 2
    b = fresh_board(rows, cols)
    # Place a key on (0,1) so landing there toggles all gates
    b["keys"] = [[0, 1]]
    # Ensure the edge to the right is initially open (no wall/gate)
    b["v_gates"][0][1] = False
    g = Game(b)

    total_gates = rows * (cols + 1) + (rows + 1) * cols

    # Move RIGHT onto key -> toggles all gates
    res = g.step('RIGHT')
    assert res.moved is True and res.blocked is False
    assert res.toggled == total_gates
    assert res.pos == (0, 1)

    # Now the same edge should be closed by a gate after toggle
    res2 = g.step('LEFT')
    assert res2.moved is False and res2.blocked is True
    assert res2.pos == (0, 1)


def test_exit_win_and_game_over():
    b = fresh_board(2, 2)
    b["exit"] = [0, 1]
    g = Game(b)
    res = g.step('RIGHT')
    assert res.won is True and res.done is True
    # Any further action should be rejected with game_over
    after = g.step('RIGHT')
    assert after.ok is False and after.reason == 'game_over'


def test_undo_and_reset():
    b = fresh_board(2, 2)
    g = Game(b)
    r1 = g.step('RIGHT')
    assert r1.pos == (0, 1)
    # UNDO -> back to (0,0)
    r2 = g.step('UNDO')
    assert r2.pos == (0, 0)
    # RESET -> back to initial
    r3 = g.step('RESET')
    assert r3.pos == (0, 0)


def test_parse_action_prefix_and_wait():
    b = fresh_board(2, 2)
    # Put a white mummy so we can detect movement on WAIT
    b["white_mummies"] = [[1, 0]]
    b["player"] = [1, 1]
    g = Game(b)
    # prefix form
    r1 = g.step('Action: up')
    # Parsed and executed as UP; not necessarily blocked depending on position
    assert r1.action == 'UP'
    # WAIT increments step count; enemies move
    # Next step should be rejected if game already over after enemy moves
    r2 = g.step('wait')
    assert r2.ok is False and r2.reason == 'game_over'


def test_ascii_has_dots_and_gates():
    b = fresh_board(2, 2)
    # Add an internal gates to ensure '=' and ':' appear in text
    b["h_gates"][1][0] = True  # between (0,0)-(1,0)
    b["v_gates"][0][1] = True  # between (0,0)-(0,1)
    g = Game(b)
    text = g.to_text()
    # Dots for empty areas
    assert '.' in text
    # '=' for horizontal gate, ':' for vertical gate
    assert '=' in text and ':' in text


def test_invalid_action():
    b = fresh_board(2, 2)
    g = Game(b)
    res = g.step('JUMP')
    assert res.ok is False and res.reason == 'invalid_action'


def test_white_mummy_horizontal_priority_two_steps():
    # 1x6 row: white at c=0, player at c=3 -> after WAIT, white moves two steps to c=2
    b = fresh_board(rows=1, cols=6)
    b["player"] = [0, 3]
    b["white_mummies"] = [[0, 0]]
    g = Game(b)
    g.step('WAIT')
    assert g.board['white_mummies'][0] == [0, 2]
    assert g.done is False  # not captured yet


def test_red_mummy_vertical_priority_two_steps():
    # 4x1 column: red at r=0, player at r=3 -> after WAIT, red moves two steps to r=2
    b = fresh_board(rows=4, cols=1)
    b["player"] = [3, 0]
    b["red_mummies"] = [[0, 0]]
    g = Game(b)
    g.step('WAIT')
    assert g.board['red_mummies'][0] == [2, 0]


def test_white_mummy_fallback_vertical_when_horizontal_blocked():
    # 3x3: player at (2,1), white at (0,1). Horizontal delta=0; prefer vertical, moves down two.
    b = fresh_board(rows=3, cols=3)
    b["player"] = [2, 1]
    b["white_mummies"] = [[0, 1]]
    g = Game(b)
    g.step('WAIT')
    assert g.board['white_mummies'][0] == [2, 1]


def test_scorpion_moves_one_step_like_white_horizontal_first():
    b = fresh_board(rows=2, cols=2)
    b["player"] = [1, 1]
    b["scorpions"] = [[0, 0]]
    g = Game(b)
    g.step('WAIT')
    # Equal dv/dh -> white-priority goes horizontal first
    assert g.board['scorpions'][0] == [0, 1]


def test_mummy_vs_mummy_collision_last_mover_wins():
    # 1x6, player far right, two whites adjacent at 2 and 3; first moves into 3 and kills the occupant
    b = fresh_board(rows=1, cols=6)
    b["player"] = [0, 5]
    b["white_mummies"] = [[0, 2], [0, 3]]
    g = Game(b)
    g.step('WAIT')
    # After first phase, only one white survives, at c=3; second phase moves to c=4
    assert len(g.board['white_mummies']) == 1
    assert g.board['white_mummies'][0] == [0, 4]


def test_mummy_defeats_scorpion_mover_wins_rule():
    # White moves into scorpion, white survives
    b = fresh_board(rows=1, cols=4)
    b["player"] = [0, 3]
    b["white_mummies"] = [[0, 1]]
    b["scorpions"] = [[0, 2]]
    g = Game(b)
    g.step('WAIT')
    assert g.board['scorpions'] == []
    # White moves two steps: from 1 to 2 (kills scorpion), then to 3 (captures player)
    assert g.done is True and g.won is False

def test_enemy_toggles_gates_on_key_mummy():
    # White mummy stepping onto a key toggles all gates
    b = fresh_board(rows=1, cols=3)
    b["player"] = [0, 2]
    b["white_mummies"] = [[0, 0]]
    b["keys"] = [[0, 1]]
    g = Game(b)
    # Before: all gates false
    assert all(not any(row) for row in g.board['v_gates']) and all(not any(row) for row in g.board['h_gates'])
    g.step('WAIT')
    # After: gates toggled at least once (now true)
    assert any(any(row) for row in g.board['v_gates']) or any(any(row) for row in g.board['h_gates'])

def test_enemy_toggles_gates_on_key_scorpion():
    b = fresh_board(rows=1, cols=3)
    b["player"] = [0, 2]
    b["scorpions"] = [[0, 0]]
    b["keys"] = [[0, 1]]
    g = Game(b)
    # Before: all gates false
    assert all(not any(row) for row in g.board['v_gates']) and all(not any(row) for row in g.board['h_gates'])
    g.step('WAIT')
    # After: scorpion hits key and toggles gates
    assert any(any(row) for row in g.board['v_gates']) or any(any(row) for row in g.board['h_gates'])


def test_enemy_captures_player():
    b = fresh_board(rows=1, cols=4)
    b["player"] = [0, 3]
    b["white_mummies"] = [[0, 1]]
    g = Game(b)
    g.step('WAIT')
    assert g.done is True and g.won is False

def test_player_dies_on_trap_not_enemies():
    # Player stepping on trap dies
    b = fresh_board(rows=1, cols=3)
    b["player"] = [0, 0]
    b["traps"] = [[0, 1]]
    g = Game(b)
    res = g.step('RIGHT')
    assert g.done is True and g.won is False
    # Enemies ignore traps
    b2 = fresh_board(rows=1, cols=4)
    b2["player"] = [0, 3]
    b2["white_mummies"] = [[0, 1]]
    b2["traps"] = [[0, 2]]
    g2 = Game(b2)
    g2.step('WAIT')
    # White moved into trap at [0,2] then to [0,3] capturing player; trap had no effect on the mummy
    assert g2.done is True and g2.won is False
