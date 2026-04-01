import asyncio
import json
import logging

import websockets

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - AGENT - %(levelname)s - %(message)s"
)


class BaseAgent:
    """
    Abstract base class for Wumpus World agents.
    Handles all websocket communications and state updates.
    Subclasses MUST implement the deliberate() method.
    """

    def __init__(self, server_uri="ws://localhost:8765"):
        self.server_uri = server_uri
        self.current_state = None

    async def run(self):
        """Main connection loop."""
        try:
            async with websockets.connect(self.server_uri) as websocket:
                await websocket.send(json.dumps({"client": "agent"}))
                logging.info(f"Connected to {self.server_uri}")

                async for message in websocket:
                    data = json.loads(message)

                    if data.get("type") == "state":
                        self.current_state = data

                        if self.current_state.get("objective_reached"):
                            if not getattr(self, "idle_logged", False):
                                # Force one final thought process to update the UI
                                await self.deliberate()
                                await self.send_telemetry(websocket)
                                logging.info("Objective reached. Idling...")
                                self.idle_logged = True
                            continue
                        else:
                            self.idle_logged = False

                        # Ask the subclass for the next move based purely on percepts
                        action = await self.deliberate()

                        if action:
                            # Send telemetry before moving to sync the UI
                            await self.send_telemetry(websocket)
                            await websocket.send(
                                json.dumps({"action": "move", "direction": action})
                            )
                            await asyncio.sleep(0.15)

                    elif data.get("type") == "reset":
                        self.reset_memory()
                        logging.info("Memory wiped due to simulation reset.")

        except Exception as e:
            logging.error(f"Connection error: {e}")

    async def deliberate(self):
        """
        The core decision loop.
        MUST return one of: 'N', 'S', 'E', 'W' or None.
        """
        raise NotImplementedError("Subclasses must implement deliberate()")

    def reset_memory(self):
        """Clears internal tracking variables when the simulation resets."""
        pass

    async def send_telemetry(self, websocket):
        """Packages internal memory/probabilities and sends them to the frontend UI."""
        pass
