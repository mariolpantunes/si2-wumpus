import asyncio
import json
import logging
import os
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

# Configure standard logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class SimulationServer:
    """
    Simulation server for the Wumpus World environment.

    Handles map loading, agent actions, and frontend synchronization.
    Supports 'wumpus', 'maze', and 'room' map types.
    """

    def __init__(self) -> None:
        """Initializes the simulation server and default state."""
        self.frontend_ws: Any = None
        self.agent_ws: Any = None
        self.maps_dir: str = "maps"
        self.current_map: Optional[Dict[str, Any]] = None
        self.current_map_name: Optional[str] = None
        self.running: bool = False
        self.sim_state: Dict[str, Any] = {}

        # Initialize default state
        self._initialize_empty_state()

        if not os.path.exists(self.maps_dir):
            os.makedirs(self.maps_dir)
            logging.info(f"Created maps directory at: {os.path.abspath(self.maps_dir)}")

    def _initialize_empty_state(self) -> None:
        """Sets the simulation state to a clean baseline."""
        self.sim_state = {
            "agent_pos": [0, 0],
            "visits": {},
            "hits": {},
            "bumped": False,
            "scream": False,
            "wumpus_alive": True,
            "arrows": 1,
            "score": 0,
            "game_over": False,
            "termination_reason": None,
            "last_arrow_path": None,
            "total_reachable": 0,
        }

    def _wrap_coords(self, x: int, y: int) -> Tuple[int, int]:
        """
        Applies toroidal wrapping if enabled for the current map.

        Args:
            x: The x-coordinate.
            y: The y-coordinate.

        Returns:
            A tuple of (wrapped_x, wrapped_y).
        """
        if not self.current_map:
            return x, y

        width = self.current_map["width"]
        height = self.current_map["height"]

        if self.current_map.get("teleport", False):
            return x % width, y % height
        return x, y

    def _calculate_reachable_tiles(self) -> int:
        """
        Calculates the number of reachable floor tiles from the start position.

        Uses BFS to explore the grid, accounting for teleportation and obstacles.

        Returns:
            The total number of reachable non-obstacle tiles.
        """
        if not self.current_map:
            return 0

        width = self.current_map["width"]
        height = self.current_map["height"]
        grid = self.current_map["grid"]
        start = tuple(self.current_map["start"])
        teleport = self.current_map.get("teleport", False)

        # Start is an obstacle? (unlikely but check)
        if grid[start[1]][start[0]] == "obstacle":
            return 0

        queue = deque([start])
        visited = {start}

        while queue:
            x, y = queue.popleft()

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if teleport:
                    nx %= width
                    ny %= height

                if 0 <= nx < width and 0 <= ny < height:
                    if (nx, ny) not in visited and grid[ny][nx] != "obstacle":
                        visited.add((nx, ny))
                        queue.append((nx, ny))
        return len(visited)

    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """
        Starts the websocket server.

        Args:
            host: The host to bind to.
            port: The port to listen on.
        """
        import websockets

        logging.info(f"Starting websocket server on ws://{host}:{port}")
        async with websockets.serve(self.handle_client, host, port):
            await asyncio.Future()

    async def handle_client(self, websocket: Any) -> None:
        """
        Handles an incoming websocket connection.

        Args:
            websocket: The websocket connection.
        """
        client_type = "Unknown"
        try:
            init_msg = await websocket.recv()
            data = json.loads(init_msg)
            client_type = data.get("client", "Unknown")

            if client_type == "frontend":
                await self._setup_frontend(websocket)
            elif client_type == "agent":
                await self._setup_agent(websocket)
            else:
                logging.warning(f"Unknown client type attempted connection: {client_type}")

        except Exception as e:
            logging.error(f"Error handling client {client_type}: {e}")
        finally:
            await self._cleanup_client(websocket)

    async def _setup_frontend(self, websocket: Any) -> None:
        """
        Sets up a new frontend connection.

        Args:
            websocket: The websocket connection.
        """
        if self.frontend_ws:
            logging.info("Closing previous frontend connection.")
            await self.frontend_ws.close()

        self.frontend_ws = websocket
        logging.info("Frontend connected.")

        self.reset_sim()
        if self.agent_ws:
            await self.agent_ws.send(json.dumps({"type": "reset"}))

        await self.send_map_list()
        await self.update_frontend()
        await self.frontend_loop(websocket)

    async def _setup_agent(self, websocket: Any) -> None:
        """
        Sets up a new agent connection.

        Args:
            websocket: The websocket connection.
        """
        if self.agent_ws:
            logging.info("Closing previous agent connection.")
            await self.agent_ws.close()

        self.agent_ws = websocket
        logging.info("Agent connected.")
        await self.send_agent_state()
        await self.agent_loop(websocket)

    async def _cleanup_client(self, websocket: Any) -> None:
        """
        Cleans up a client connection.

        Args:
            websocket: The websocket connection to cleanup.
        """
        if websocket == self.frontend_ws:
            self.frontend_ws = None
            logging.info("Frontend session cleared.")
        elif websocket == self.agent_ws:
            self.agent_ws = None
            logging.info("Agent session cleared.")

    async def frontend_loop(self, websocket: Any) -> None:
        """
        Main loop for frontend communication.

        Args:
            websocket: The websocket connection.
        """
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")

                if action == "load_map":
                    self.load_map(data.get("filename"))
                elif action == "save_map":
                    self.save_map(data.get("filename"), data.get("map_data"))
                    await self.send_map_list()
                elif action == "start_sim":
                    self.running = True if self.current_map else False
                elif action == "stop_sim":
                    self.running = False
                elif action == "reset_sim":
                    self.reset_sim()
                    if self.agent_ws:
                        await self.agent_ws.send(json.dumps({"type": "reset"}))

                await self.update_frontend()
                if self.agent_ws:
                    await self.send_agent_state()
            except Exception as e:
                logging.error(f"Error processing frontend message: {e}")

    async def agent_loop(self, websocket: Any) -> None:
        """
        Main loop for agent communication.

        Args:
            websocket: The websocket connection.
        """
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")

                if action == "telemetry":
                    if self.frontend_ws:
                        await self.frontend_ws.send(
                            json.dumps(
                                {
                                    "type": "agent_telemetry",
                                    "data": data.get("data"),
                                }
                            )
                        )
                    continue

                # Process physical actions only if game is active
                if self.current_map and self.running and not self.sim_state.get("game_over"):
                    self.sim_state["scream"] = False
                    if action == "move":
                        self.process_move(data.get("direction"))
                        self.sim_state["score"] -= 1
                        self.check_objective()
                    elif action == "shoot":
                        if self.sim_state["arrows"] > 0:
                            self.process_shoot(data.get("direction"))
                            self.sim_state["score"] -= 10
                        else:
                            self.sim_state["last_arrow_path"] = None
                            logging.warning("Agent tried to shoot with no arrows.")

                await self.update_frontend()
                await self.send_agent_state()
            except Exception as e:
                logging.error(f"Error processing agent message: {e}")

    def process_move(self, direction: str) -> None:
        """
        Processes an agent move action.

        Args:
            direction: The direction to move ('N', 'S', 'E', 'W').
        """
        x, y = self.sim_state["agent_pos"]

        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}.get(direction, (0, 0))
        nx, ny = self._wrap_coords(x + dx, y + dy)

        if not self.current_map:
            return

        width, height = self.current_map["width"], self.current_map["height"]
        self.sim_state["bumped"] = False

        if 0 <= nx < width and 0 <= ny < height:
            if self.current_map["grid"][ny][nx] == "obstacle":
                key = f"{nx},{ny}"
                self.sim_state["hits"][key] = self.sim_state["hits"].get(key, 0) + 1
                self.sim_state["bumped"] = True
            else:
                self.sim_state["agent_pos"] = [nx, ny]

                # Arrow pickup logic
                if self.current_map["grid"][ny][nx] == "arrow":
                    self.sim_state["arrows"] += 1
                    self.current_map["grid"][ny][nx] = "floor"
                    logging.info("Agent picked up an arrow!")

                key = f"{nx},{ny}"
                self.sim_state["visits"][key] = self.sim_state["visits"].get(key, 0) + 1
        else:
            self.sim_state["bumped"] = True

    def process_shoot(self, direction: str) -> None:
        """
        Processes an agent shoot action.

        Args:
            direction: The direction to shoot ('N', 'S', 'E', 'W').
        """
        if not self.current_map:
            return

        self.sim_state["last_arrow_path"] = None
        self.sim_state["arrows"] -= 1
        x, y = self.sim_state["agent_pos"]
        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}.get(direction, (0, 0))

        width, height = self.current_map["width"], self.current_map["height"]
        # Use width for E/W and height for N/S to correctly bound the ray
        max_dist = width if dx != 0 else height

        path: List[List[int]] = []
        nx, ny = x + dx, y + dy
        hit_wumpus = False
        last_valid_pos = None

        # Raycast for the arrow
        for _ in range(max_dist):
            nx, ny = self._wrap_coords(nx, ny)
            if not (0 <= nx < width and 0 <= ny < height):
                break

            cell = self.current_map["grid"][ny][nx]
            if cell == "obstacle":
                break

            path.append([nx, ny])
            last_valid_pos = (nx, ny)

            if cell == "wumpus" and self.sim_state["wumpus_alive"]:
                self.sim_state["wumpus_alive"] = False
                self.sim_state["scream"] = True
                hit_wumpus = True
                logging.info("Scream! The Wumpus was killed!")
                break

            nx += dx
            ny += dy

        # Set to None if empty to prevent frontend crashes
        self.sim_state["last_arrow_path"] = path if path else None

        # If it didn't hit anything, it lands on the ground (only if floor)
        if (not hit_wumpus) and last_valid_pos:
            lx, ly = last_valid_pos
            cell_at_landing = self.current_map["grid"][ly][lx]
            if cell_at_landing == "floor":
                self.current_map["grid"][ly][lx] = "arrow"
                logging.info(f"Arrow landed on the ground at {lx}, {ly}")
            elif cell_at_landing == "pit":
                logging.info(f"Arrow fell into a pit at {lx}, {ly} and is lost.")
            else:
                logging.info(f"Arrow hit {cell_at_landing} and broke.")

    def get_percepts(self) -> Dict[str, bool]:
        """
        Calculates current percepts for the agent.

        Returns:
            A dictionary of percepts: stench, breeze, glitter, bump, scream.
        """
        if not self.current_map:
            return {}

        x, y = self.sim_state["agent_pos"]
        grid = self.current_map["grid"]
        percepts = {
            "stench": False,
            "breeze": False,
            "glitter": grid[y][x] == "gold",
            "bump": self.sim_state.get("bumped", False),
            "scream": self.sim_state.get("scream", False),
        }

        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = self._wrap_coords(x + dx, y + dy)
            if 0 <= nx < self.current_map["width"] and 0 <= ny < self.current_map["height"]:
                cell = grid[ny][nx]
                if cell == "pit":
                    percepts["breeze"] = True
                if cell == "wumpus" and self.sim_state["wumpus_alive"]:
                    percepts["stench"] = True

        return percepts

    def reset_sim(self) -> None:
        """Resets the simulation to the initial state."""
        if self.current_map:
            start_pos = self.current_map.get("start", [0, 0])
            self._initialize_empty_state()
            self.sim_state["agent_pos"] = start_pos
            self.sim_state["visits"] = {f"{start_pos[0]},{start_pos[1]}": 1}

            if self.current_map.get("type") == "room":
                self.sim_state["total_reachable"] = self._calculate_reachable_tiles()

            self.running = False
            logging.info("Simulation reset. Click 'Start' to begin.")

    def check_objective(self) -> None:
        """Checks if the agent has reached an objective or died."""
        if not self.current_map:
            return

        x, y = self.sim_state["agent_pos"]
        cell = self.current_map["grid"][y][x]
        map_type = self.current_map.get("type", "wumpus")

        # Death conditions (universal)
        if cell == "wumpus" and self.sim_state["wumpus_alive"]:
            self._end_game("GAME OVER: Wumpus!", -1000)
            return
        elif cell == "pit":
            self._end_game("GAME OVER: Pit!", -1000)
            return

        # Success conditions
        if map_type == "wumpus":
            if cell == "gold":
                self._end_game("VICTORY: Gold!", 1000)
        elif map_type == "maze":
            target = self.current_map.get("target")
            if target and x == target[0] and y == target[1]:
                self._end_game("VICTORY: Target Reached!", 1000)
        elif map_type == "room":
            if len(self.sim_state["visits"]) >= self.sim_state["total_reachable"]:
                self._end_game("VICTORY: All Tiles Visited!", 1000)

    def _end_game(self, message: str, score_mod: int) -> None:
        """
        Ends the game with a message and score modifier.

        Args:
            message: The message to log.
            score_mod: The value to add to the score.
        """
        self.running = False
        self.sim_state["game_over"] = True
        self.sim_state["termination_reason"] = message
        self.sim_state["score"] += score_mod
        logging.info(message)

    async def send_agent_state(self) -> None:
        """Sends current state to the agent."""
        if not self.agent_ws:
            return
        payload = {
            "type": "state",
            "position": self.sim_state["agent_pos"],
            "objective_reached": self.sim_state["game_over"],
            "termination_reason": self.sim_state.get("termination_reason"),
            "map_name": self.current_map_name,
            "running": self.running,
            "width": self.current_map.get("width", 0) if self.current_map else 0,
            "height": self.current_map.get("height", 0) if self.current_map else 0,
            "start": (self.current_map.get("start", [0, 0]) if self.current_map else [0, 0]),
            "percepts": self.get_percepts(),
            "score": self.sim_state["score"],
            "arrows": self.sim_state["arrows"],
        }
        await self.agent_ws.send(json.dumps(payload))

    async def update_frontend(self) -> None:
        """Sends current state to the frontend."""
        if self.frontend_ws:
            await self.frontend_ws.send(
                json.dumps(
                    {
                        "type": "update",
                        "map": self.current_map,
                        "state": self.sim_state,
                        "running": self.running,
                        "agent_connected": self.agent_ws is not None,
                    }
                )
            )

    async def send_map_list(self) -> None:
        """Sends the list of available maps to the frontend."""
        if self.frontend_ws:
            maps = sorted([f for f in os.listdir(self.maps_dir) if f.endswith(".json")])
            await self.frontend_ws.send(json.dumps({"type": "map_list", "maps": maps}))

    def validate_map(self, map_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Simple validation of map structure.

        Args:
            map_data: The map data to validate.

        Returns:
            A tuple of (is_valid, error_message).
        """
        if not isinstance(map_data, dict):
            return False, "Map data must be a dictionary"

        required_fields = ["width", "height", "grid", "start"]
        for field in required_fields:
            if field not in map_data:
                return False, f"Missing required field: {field}"

        width = map_data["width"]
        height = map_data["height"]
        grid = map_data["grid"]

        if not isinstance(grid, list) or len(grid) != height:
            return False, "Invalid grid height."

        for row in grid:
            if not isinstance(row, list) or len(row) != width:
                return False, "Invalid grid width."

        start = map_data["start"]
        if not isinstance(start, list) or len(start) != 2:
            return False, "Invalid start position format"
        if not (0 <= start[0] < width and 0 <= start[1] < height):
            return False, "Start position out of bounds"

        return True, ""

    def load_map(self, filename: str) -> None:
        """
        Loads a map from a file.

        Args:
            filename: The name of the file to load.
        """
        try:
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(self.maps_dir, safe_filename)
            with open(filepath, "r") as f:
                data = json.load(f)
            valid, msg = self.validate_map(data)
            if valid:
                self.current_map = data
                self.current_map_name = filename
                self.reset_sim()
            else:
                logging.error(f"Invalid map {safe_filename}: {msg}")
        except Exception as e:
            logging.error(f"Load error: {e}")

    def save_map(self, filename: str, map_data: Dict[str, Any]) -> None:
        """
        Saves a map to a file.

        Args:
            filename: The name of the file to save.
            map_data: The map data to save.
        """
        try:
            valid, msg = self.validate_map(map_data)
            if not valid:
                logging.error(f"Save error: {msg}")
                return
            safe_filename = os.path.basename(filename)
            if not safe_filename.endswith(".json"):
                safe_filename += ".json"
            with open(os.path.join(self.maps_dir, safe_filename), "w") as f:
                json.dump(map_data, f)
            logging.info(f"Saved: {safe_filename}")
        except Exception as e:
            logging.error(f"Save error: {e}")


if __name__ == "__main__":
    server = SimulationServer()
    asyncio.run(server.start())
