import os
import re
import json
from llm_prompt import Prompt
from mummy_env import Game

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

ALLOWED = {"UP", "DOWN", "LEFT", "RIGHT", "WAIT", "UNDO", "RESET"}


def parse_action(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    # Prefer explicit "Action: <ACTION>"
    m = re.search(r"Action\s*:\s*([A-Za-z]+)", text)
    if m:
        cand = m.group(1).strip().upper()
        if cand in ALLOWED:
            return cand
    # Fallback: first allowed token found in text
    up = text.upper()
    for a in ["UP", "DOWN", "LEFT", "RIGHT", "WAIT", "UNDO", "RESET"]:
        if a in up:
            return a
    return None


def main():
    model = os.environ.get("LLM_MODEL", "openrouter/meta-llama/llama-3.1-8b-instruct")
    board_path = os.environ.get("BOARD", "data/board.json")

    with open(board_path, "r", encoding="utf-8") as f:
        board = json.load(f)

    game = Game(board)
    ascii_state = game.to_text()

    prompt = (
        INSTRUCTIONS
        + "\nCurrent grid (double-resolution):\n\n"
        + ascii_state
        + "\n\nRespond ONLY with: Action: <UP|DOWN|LEFT|RIGHT|WAIT|UNDO|RESET>\n"
    )

    print("# Sending prompt to LLM (model=", model, ")...", sep="")
    p = Prompt(modelName=model, message=prompt, promptStrategy=Prompt.deliverLiteLLMPrompt, temperature=0.2)
    reply = p.deliver()

    print("\n# Raw reply:\n", reply)
    action = parse_action(reply) or "WAIT"
    print("\n# Parsed action:", action)

    res = game.step(action)
    print("\n# Resulting grid:\n")
    print(res.ascii)
    print("\n# Summary:")
    print(json.dumps({
        "action": res.action,
        "moved": res.moved,
        "blocked": res.blocked,
        "toggled": res.toggled,
        "pos": res.pos,
        "done": res.done,
        "won": res.won,
        "reason": res.reason,
    }, indent=2))


if __name__ == "__main__":
    main()

