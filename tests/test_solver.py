import unittest

from mummy_maze.level import parse_level
from mummy_maze.solver import solve


class TestMummyMazeSolver(unittest.TestCase):
    def test_trivial_no_enemies(self):
        lvl = parse_level(
            """
            P.E
            """
        )
        plan = solve(lvl)
        self.assertIsNotNone(plan)
        self.assertGreaterEqual(len(plan), 1)

    def test_gate_toggle(self):
        # Player must step on key to open gate and reach exit
        lvl = parse_level(
            """
            P.KGE
            """
        )
        plan = solve(lvl)
        self.assertIsNotNone(plan)
        # Should at least move onto K, then G, then E
        self.assertGreaterEqual(len(plan), 3)


if __name__ == "__main__":
    unittest.main()



