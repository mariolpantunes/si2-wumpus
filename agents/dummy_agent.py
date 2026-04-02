import asyncio
import json
import os
import random
from typing import Any, Optional, Set, Tuple, Union

from agents.base_agent import BaseAgent


class DummyAgent(BaseAgent):
    """
    A purely random agent for the Wumpus World.
    It ignores all percepts and walks randomly, frequently bumping into walls or dying.
    """

    def __init__(self, server_uri: Optional[str] = None) -> None:
        """
        Initializes the dummy agent.

        Args:
            server_uri: The URI of the simulation server.
        """
        if server_uri is None:
            server_uri = os.environ.get("WUMPUS_SERVER", "ws://localhost:8765")
        super().__init__(server_uri)
        self.visited: Set[str] = set()

    def update_memory(self) -> None:
        """Track where we have been just to paint the UI blue."""
        if self.current_state:
            pos = self.current_state.get("position")
            if pos:
                self.visited.add(f"{pos[0]},{pos[1]}")

    async def deliberate(self) -> Optional[Union[str, Tuple[str, str]]]:
        """Completely ignore percepts and pick a random action."""
        # 10% chance to shoot in a random direction
        if random.random() < 0.1:
            return ("shoot", random.choice(["N", "S", "E", "W"]))

        # Pick a random direction
        return random.choice(["N", "S", "E", "W"])

    def reset_memory(self) -> None:
        """Clears the set of visited tiles."""
        self.visited.clear()

    async def send_telemetry(self, websocket: Any) -> None:
        """Send basic telemetry so the UI renders the explored path."""
        percepts = self.current_state.get("percepts", {}) if self.current_state else {}
        payload = {
            "action": "telemetry",
            "data": {
                "visited": list(self.visited),
                "percepts": percepts,
                "current_probs": {"N": 0.25, "S": 0.25, "E": 0.25, "W": 0.25},
            },
        }
        await websocket.send(json.dumps(payload))


if __name__ == "__main__":
    agent = DummyAgent()
    asyncio.run(agent.run())
