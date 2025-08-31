import os
import json
import sys

# Ensure repo root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app, BOARDS_DIR  # type: ignore


def test_save_as_and_list():
    client = flask_app.test_client()
    # Minimal board payload
    board = {
        'rows': 2, 'cols': 2,
        'v_walls': [[True, False, True],[True, False, True]],
        'h_walls': [[True, True],[False, False],[True, True]],
        'v_gates': [[False, False, False],[False, False, False]],
        'h_gates': [[False, False],[False, False],[False, False]],
        'player': [0,0], 'exit': [1,1],
        'white_mummies': [], 'red_mummies': [], 'traps': [], 'keys': [], 'scorpions': []
    }
    name = 'save_as_test.json'
    # Save As
    r = client.post(f'/api/boards/{name}', json=board)
    assert r.status_code == 200
    j = r.get_json()
    assert j['status'] == 'ok' and j['name'] == name
    # Confirm file exists
    path = os.path.join(BOARDS_DIR, name)
    assert os.path.exists(path)
    # Listed in /api/boards
    r = client.get('/api/boards')
    assert r.status_code == 200
    j = r.get_json()
    assert name in j.get('boards', [])
