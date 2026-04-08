# <img src="frontend/favicon.svg" alt="logo" width="128" height="128" align="middle"> SI2 - Wumpus

SI2-Wumpus is a modular simulation environment for the classic Wumpus World game, designed for testing and developing autonomous agents. The project features a Python-based WebSocket backend that handles the simulation engine, an HTML5 Canvas-based frontend for real-time visualization, and an extensible agent system that allows for easy implementation of custom AI strategies.

The primary objective of the game depends on the map type: in `wumpus` mode, the agent must find and collect the gold; in `maze` mode, it must reach a specific target; and in `room` mode, it must explore all reachable floor tiles. Agents can move in four cardinal directions (North, South, East, West) and can shoot arrows to kill the Wumpus, while avoiding deadly pits and the Wumpus itself.

## Game Rules

The simulation follows the standard Wumpus World logic with additional features:
- **Percepts**: At each step, the agent receives a set of percepts:
  - `stench`: The Wumpus is in an adjacent cell.
  - `breeze`: A pit is in an adjacent cell.
  - `glitter`: Gold is in the current cell.
  - `bump`: The agent walked into an obstacle or the edge of the map.
  - `scream`: The Wumpus was killed by an arrow.
- **Actions**: The agent can perform the following actions:
  - `move`: Move one cell in a direction ('N', 'S', 'E', 'W').
  - `shoot`: Fire an arrow in a direction ('N', 'S', 'E', 'W').
- **World State**: The world is a grid of cells which can contain floors, obstacles, pits, the Wumpus, or gold. If teleportation is enabled, the grid is toroidal (wrapping around edges).
- **Scoring**:
  - -1 for each move.
  - -10 for shooting an arrow.
  - -1000 for dying (falling in a pit or being eaten by the Wumpus).
  - +1000 for achieving the objective (finding gold, reaching target, or exploring the room).

## Setup

The simulation can be launched using Docker Compose for the full stack, or manually using a Python virtual environment for the agents.

### 1. Launch the Simulation Stack
Use Docker Compose to start the backend and the frontend viewer:
```bash
docker compose up
```
The frontend will be available at `http://localhost:8080` (or the port specified in `compose.yml`).

### 2. Prepare the Agent Environment
Create a virtual environment and install the required dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyright ruff
```

### 3. Execute Agents
Agents are executed locally and connect to the backend via WebSockets:
```bash
# To run the manual control agent:
python agents/manual_agent.py

# To run the dummy (random) agent:
python agents/dummy_agent.py
```

## Project Structure

- `backend/`: Python server using `websockets`.
  - `server.py`: Main simulation engine. Handles map loading, agent movement, and state broadcasting.
- `frontend/`: HTML5 Canvas-based visualization and map editor.
  - `index.html`: UI structure.
  - `script.js`: Frontend logic, WebSocket client, and Canvas rendering.
  - `styles.css`: UI styling.
- `agents/`: Autonomous agents that connect to the backend.
  - `base_agent.py`: Abstract base class for all agents.
  - `dummy_agent.py`: A simple random agent implementation.
  - `manual_agent.py`: Manual terminal-based control agent.
- `maps/`: JSON files defining maze and room layouts.
- `compose.yml`: Docker Compose configuration for running the full stack.

## Development

To develop a new agent, you should subclass the `BaseAgent` and implement the `deliberate` method. For more details on the available state and structure, refer to the [Project Structure](#project-structure) section.

```python
from typing import Optional, Union, Tuple
from agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    """Custom agent implementation."""

    async def deliberate(self) -> Optional[Union[str, Tuple[str, str]]]:
        """
        Logic for deciding the next action.
        Returns 'N', 'S', 'E', 'W' for movement, 
        or ('shoot', direction) for shooting.
        """
        percepts = self.current_state.get("percepts", {})
        if percepts.get("glitter"):
            return None # Stop if we found the gold
        
        return "N" # Move North by default
```

## Authors

* **Mário Antunes** - [mariolpantunes](https://github.com/mariolpantunes)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
