import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple, Union

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - AGENT - %(levelname)s - %(message)s")


class BaseAgent:
    """
    Abstract base class for Wumpus World agents.

    Handles all websocket communications and state updates.
    Subclasses MUST implement the deliberate() method.
    """

    def __init__(self, server_uri: str = "ws://localhost:8765") -> None:
        """
        Initializes the base agent.

        Args:
            server_uri: The URI of the simulation server.
        """
        self.server_uri: str = server_uri
        self.current_state: Optional[Dict[str, Any]] = None
        self.idle_logged: bool = False

    async def run(self) -> None:
        """Main connection loop."""
        try:
            async with websockets.connect(self.server_uri) as websocket:
                await websocket.send(json.dumps({"client": "agent"}))
                logging.info(f"Connected to {self.server_uri}")

                async for message in websocket:
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    data = json.loads(message)

                    if data.get("type") == "state":
                        self.current_state = data

                        if not self.current_state:
                            continue

                        if self.current_state.get("objective_reached"):
                            if not self.idle_logged:
                                # Force one final thought process to update the UI
                                self.update_memory()
                                await self.send_telemetry(websocket)
                                logging.info("Objective reached. Idling...")
                                self.idle_logged = True
                            continue
                        else:
                            self.idle_logged = False

                        # Update memory and telemetry BEFORE deliberating
                        # (which might block for user input)
                        self.update_memory()
                        await self.send_telemetry(websocket)

                        if not self.current_state.get("running"):
                            continue

                        # Ask the subclass for the next move based purely on percepts
                        action_data = await self.deliberate()

                        if action_data:
                            # Send telemetry again in case deliberate() updated
                            # probabilities or thoughts
                            await self.send_telemetry(websocket)

                            if isinstance(action_data, tuple):
                                action, direction = action_data
                                await websocket.send(json.dumps({"action": action, "direction": direction}))
                            else:
                                await websocket.send(json.dumps({"action": "move", "direction": action_data}))
                            await asyncio.sleep(0.15)

                    elif data.get("type") == "reset":
                        self.current_state = None
                        self.reset_memory()
                        # Immediately update UI to show cleared state
                        await self.send_telemetry(websocket)
                        logging.info("Memory wiped due to simulation reset.")

        except Exception as e:
            logging.error(f"Connection error: {e}")

    async def deliberate(self) -> Optional[Union[str, Tuple[str, str]]]:
        """
        The core decision loop.

        MUST return one of: 'N', 'S', 'E', 'W', ('shoot', direction) or None.

        Returns:
            The chosen action and direction, or None.
        """
        raise NotImplementedError("Subclasses must implement deliberate()")

    def update_memory(self) -> None:
        """Updates internal state based on current_state percepts and position."""
        pass

    def reset_memory(self) -> None:
        """Clears internal tracking variables when the simulation resets."""
        pass

    async def send_telemetry(self, websocket: Any) -> None:
        """
        Packages internal memory/probabilities and sends them to the frontend UI.

        Args:
            websocket: The websocket connection to the server.
        """
        pass
