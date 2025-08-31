# LLM Evaluation on Mummy Maze 

Evaluating LLM reasoning capabilities through the game Mummy Maze. 

## Quick Start

### Web Interface (Recommended for beginners)

1. **Start the web server**:
   ```bash
   python app.py
   ```
2. **Open your browser** and go to `http://127.0.0.1:5000`
3. **Use the Level Editor** (`/`) to create and edit levels
4. **Use the Game Interface** (`/play`) to play levels with AI or manually

## Usage

### Web Level Editor

The web editor provides an intuitive interface for creating maze levels:

- **Grid Controls**: Set board dimensions and create new boards
- **Entity Tools**: Place player, mummies, scorpions, traps, keys, and exits
- **Wall Tools**: Create walls and gates between cells
- **Export Options**: Save as JSON or export in various formats

### Web Game Interface

Play levels with AI assistance or manual control:

- **Board Selection**: Choose from saved boards
- **LLM Integration**: Use AI models for automated gameplay
- **Manual Control**: Step through moves manually
- **Run History**: View and replay completed games

### Command-line Solver

The CLI solver works with ASCII text files:

```bash
# Solve a level file
python -m mummy_maze.cli levels/my_level.txt

# View help
python -m mummy_maze.cli --help
```

## Level Format

### Web Editor Format (JSON)

Levels are stored as JSON files with the following structure:

```json
{
  "rows": 8,
  "cols": 8,
  "v_walls": [[...]],      // Vertical walls between columns
  "h_walls": [[...]],      // Horizontal walls between rows
  "v_gates": [[...]],      // Vertical gates between columns
  "h_gates": [[...]],      // Horizontal gates between rows
  "player": [0, 0],        // Player starting position [row, col]
  "exit": [7, 7],          // Exit position [row, col]
  "white_mummies": [],     // List of white mummy positions
  "red_mummies": [],       // List of red mummy positions
  "scorpions": [],         // List of scorpion positions
  "traps": [],             // List of trap positions
  "keys": []               // List of key positions
}
```

### ASCII Format (for CLI solver)

For command-line solving, use ASCII text files:

```
P...W..E
....#...
....K.G.
........
```

**ASCII Legend**:
- `P` - Player (Theseus)
- `E` - Exit
- `W` - White mummy (horizontal priority)
- `R` - Red mummy (vertical priority)
- `S` - Scorpion
- `T` - Trap
- `K` - Key
- `G` - Gate (closed)
- `g` - Gate (open)
- `#` - Wall
- `.` - Floor tile

## Game Rules

- **Turn Order**: Player → White/Red mummies (2x) → Scorpions (1x)
- **Movement**: Entities move one tile per turn
- **Mummy Behavior**: 
  - White mummies prioritize horizontal movement
  - Red mummies prioritize vertical movement
- **Collisions**: Mummies survive scorpion encounters
- **Gates**: Toggle open/closed when any entity steps on a key
- **Winning**: Reach the exit tile
- **Losing**: Hit a trap or get caught by a mummy

## Project Structure

```
Theseus-Minotaur/
├── app.py                 # Main Flask web application
├── mummy_maze/           # Core solver package
│   ├── __init__.py       # Package initialization
│   ├── cli.py           # Command-line interface
│   ├── level.py         # Level parsing and representation
│   ├── solver.py        # A* search algorithm
│   ├── state.py         # Game state management
│   └── types.py         # Type definitions
├── templates/            # HTML templates
│   ├── index.html       # Level editor interface
│   └── play.html        # Game interface
├── static/              # CSS and JavaScript files
├── data/                # Saved boards and run history
│   ├── boards/          # Level files
│   └── runs/            # Game run logs
├── levels/              # ASCII level files (for CLI)
└── requirements.txt     # Python dependencies
```

## Dependencies

- **Flask** (>=3.0.0) - Web framework
- **Python 3.8+** - Core runtime

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Adding New Features

1. The core solver logic is in `mummy_maze/solver.py`
2. Web interface components are in `templates/` and `static/`
3. Level parsing is handled in `mummy_maze/level.py`

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the terms specified in the LICENSE file.

## Acknowledgments

- Inspired by classic Mummy Maze puzzle games
- Uses A* search algorithm for optimal pathfinding
- Web interface built with Flask and modern JavaScript



