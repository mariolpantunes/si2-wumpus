import asyncio
import json
import os
import sys
import termios
import tty
from typing import Any, Dict, Optional, Set, Tuple, Union

from agents.base_agent import BaseAgent


def getch() -> str:
    """
    Reads a single character from the standard input (Linux/macOS).

    Returns:
        The character read from stdin.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch.lower()


class ManualAgent(BaseAgent):
    """
    An agent controlled manually via the terminal using W, A, S, D keys instantly.

    Adapted for Wumpus World partial observability.
    """

    def __init__(self, server_uri: Optional[str] = None) -> None:
        """
        Initializes the manual agent.

        Args:
            server_uri: The URI of the simulation server.
        """
        if server_uri is None:
            server_uri = os.environ.get("WUMPUS_SERVER", "ws://localhost:8765")
        super().__init__(server_uri)
        self.key_mapping: Dict[str, str] = {"w": "N", "s": "S", "d": "E", "a": "W"}
        self.shoot_mapping: Dict[str, str] = {"i": "N", "k": "S", "l": "E", "j": "W"}
        self.visited: Set[str] = set()

    def update_memory(self) -> None:
        """Tracks the current position to update the UI."""
        if self.current_state:
            pos = self.current_state.get("position")
            if pos:
                self.visited.add(f"{pos[0]},{pos[1]}")

    async def deliberate(self) -> Optional[Union[str, Tuple[str, str]]]:
        """
        Prompts the user for a valid input.

        Returns:
            The chosen move or shoot action.
        """
        if not self.current_state:
            return None

        pos = self.current_state.get("position")
        percepts = self.current_state.get("percepts", {})
        active_percepts = [k.capitalize() for k, v in percepts.items() if v]
        percept_str = ", ".join(active_percepts) if active_percepts else "None"

        score = self.current_state.get("score", 0)
        arrows = self.current_state.get("arrows", 0)

        print(f"\n--- Agent at {pos} | Score: {score} | Arrows: {arrows} ---")
        print(f"Percepts: [{percept_str}]")

        if self.current_state.get("objective_reached"):
            return None

        print("Move: W/A/S/D | Shoot: I/J/K/L | Quit: Ctrl+C")

        while True:
            user_input = await asyncio.to_thread(getch)

            if user_input == "\x03":
                print("\nExiting...")
                sys.exit(0)

            if user_input in self.key_mapping:
                action = self.key_mapping[user_input]
                print(f"Moving {action}")
                return action

            if user_input in self.shoot_mapping:
                direction = self.shoot_mapping[user_input]
                print(f"Shooting {direction}")
                return ("shoot", direction)

    def reset_memory(self) -> None:
        """Clears the set of visited tiles."""
        self.visited.clear()

    async def send_telemetry(self, websocket: Any) -> None:
        """
        Pass the current percepts to the UI to update the tags panel.

        Args:
            websocket: The websocket connection to the server.
        """
        percepts = self.current_state.get("percepts", {}) if self.current_state else {}
        payload = {
            "action": "telemetry",
            "data": {
                "visited": list(self.visited),
                "percepts": percepts,
                "agent_pos": self.current_state.get("position") if self.current_state else None,
                "current_probs": {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0},
            },
        }
        await websocket.send(json.dumps(payload))


if __name__ == "__main__":
    agent = ManualAgent()
    print("Starting Manual Wumpus Agent...")
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\nAgent shut down manually.")
