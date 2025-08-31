from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from .level import load_level_from_file
from .solver import solve


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Solve Mummy Maze levels from ASCII files.")
    parser.add_argument("level", type=str, help="Path to level file")
    args = parser.parse_args(argv)

    level_path = Path(args.level)
    level = load_level_from_file(level_path)
    plan = solve(level)
    if plan is None:
        print("No solution found.")
        return 1
    print(f"Solution in {len(plan)} moves:")
    for i, step in enumerate(plan, 1):
        print(f"{i:3d}. {step.description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



