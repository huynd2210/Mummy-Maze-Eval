# Mummy Maze Solver

Quick solver for Mummy Maze-like puzzles using A* search.

## Features

- **Automatic borders**: No need to manually add `#` characters around your maze - the system automatically adds walls around the perimeter
- **Clean representation**: Use `.` to represent floor tiles for better readability
- **Entity mapping**: White mummies (W), red mummies (R), and scorpions (S) are now part of the tile mapping system
- **Edge walls**: Use `|`, `-`, and `+` to create walls between tiles for more flexible maze designs

## Usage (PowerShell):

```powershell
python -m mummy_maze.cli .\levels\sample1.txt
```

## ASCII Legend:

- `#` wall (automatically added around maze borders)
- `.` floor tile
- `E` exit
- `T` trap (kills player only)
- `K` key (toggles all gates when stepped on)
- `G` gate (present; starts closed)
- `g` gate (present; starts open)
- `P` player
- `W` white mummy (horizontal-priority, placed on floor)
- `R` red mummy (vertical-priority, placed on floor)
- `S` scorpion (placed on floor)
- `|` vertical wall between tiles
- `-` horizontal wall between tiles
- `+` wall intersection (both vertical and horizontal)

**Note**: Characters `W`, `R`, and `S` are now part of the tile mapping system and work consistently with the automatic border addition. They represent entities that are placed on floor tiles.

**Edge Walls**: Characters `|`, `-`, and `+` represent walls that are placed between tiles rather than occupying entire tiles. These walls block movement between adjacent tiles, allowing for more flexible maze designs.

## Example Level Format:

```
P...W..E
....#...
....K.G.
........
```

**Note**: The system automatically adds walls around the perimeter, so you only need to define the interior of your maze.

Turn order: player (optionally stay) → white/red mummies twice → scorpions once.

Notes: Rules modeled after classic behavior; collisions resolve deterministically, gates toggle when any entity steps on a key.



