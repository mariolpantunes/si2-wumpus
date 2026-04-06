# <img src="frontend/favicon.svg" alt="logo" width="128" height="128" align="middle"> SI2 - Wumpus World Simulator

A modular Wumpus World simulation platform with a Python-based WebSocket backend, an HTML/JS frontend for visualization, and an extensible agent system.

## Features

- **Partial Observability**: Agents only receive percepts (`stench`, `breeze`, `glitter`, `bump`, `scream`) and their current position.
- **Visualizer**: Real-time ground truth and agent-perspective visualization using HTML5 Canvas.
- **Map Editor**: Built-in editor to create, save, and load custom Wumpus World maps.
- **Modular Agents**: Easy-to-extend `BaseAgent` class for implementing custom AI agents.
- **Advanced Mechanics**: Supports toroidal (wrapping) maps, arrow pickups, and pickable arrows on misses.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/si2-wumpus.git
    cd si2-wumpus
    ```

2.  **Create a virtual environment and install dependencies**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## Usage

### 1. Start the Backend
The server manages the game state and coordinates communication between the frontend and the agent.
```bash
python3 backend/server.py
```

### 2. Open the Frontend
Open `frontend/index.html` in any modern web browser.
- Use the **Run Map** menu to load an existing map from the `maps/` directory.
- Use the **Edit Map** menu to create and save new maps.

### 3. Run an Agent
Connect an agent to the running simulation.

- **Manual Control**:
  ```bash
  python3 agents/manual_agent.py
  ```
  Control the agent using `W/A/S/D` for movement and `I/J/K/L` for shooting.

- **Random (Dummy) Agent**:
  ```bash
  python3 agents/dummy_agent.py
  ```

## Project Structure

- `backend/server.py`: The core simulation logic and WebSocket server.
- `frontend/`: HTML, CSS, and JavaScript for the web-based UI.
- `agents/`:
    - `base_agent.py`: Abstract base class handling WebSocket communication.
    - `manual_agent.py`: Keyboard-controlled agent.
    - `dummy_agent.py`: Randomly acting agent.
- `maps/`: JSON files defining Wumpus World environments.

## Development

### Adding a New Agent
To create a new agent, subclass `BaseAgent` and implement the `deliberate()` method:

```python
from agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    async def deliberate(self):
        # Access percepts via self.current_state['percepts']
        # Return 'N', 'S', 'E', 'W', or ('shoot', direction)
        return 'N'
```
## Authors

  * **Mário Antunes** - [mariolpantunes](https://github.com/mariolpantunes)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
