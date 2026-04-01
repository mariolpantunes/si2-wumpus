import asyncio
import json
import sys
import termios
import tty

from agents.base_agent import BaseAgent


def getch():
    """Reads a single character from the standard input (Linux/macOS)."""
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

    def __init__(self, server_uri="ws://localhost:8765"):
        super().__init__(server_uri)
        self.key_mapping = {"w": "N", "s": "S", "d": "E", "a": "W"}
        self.visited = set()

    async def deliberate(self):
        """Prompts the user for a valid WASD input."""

        if self.current_state.get("objective_reached"):
            return None

        pos = self.current_state.get("position")
        self.visited.add(f"{pos[0]},{pos[1]}")

        percepts = self.current_state.get("percepts", {})
        active_percepts = [k.capitalize() for k, v in percepts.items() if v]
        percept_str = ", ".join(active_percepts) if active_percepts else "None"

        print(f"\n--- Agent at {pos} ---")
        print(f"Percepts: [{percept_str}]")
        print("Press W/A/S/D to move (or Ctrl+C to quit)... ", end="", flush=True)

        while True:
            user_input = await asyncio.to_thread(getch)

            if user_input == "\x03":
                print("\nExiting...")
                sys.exit(0)

            if user_input in self.key_mapping:
                action = self.key_mapping[user_input]
                print(action)  # Echo the choice
                return action

    def reset_memory(self):
        self.visited.clear()

    async def send_telemetry(self, websocket):
        """Pass the current percepts to the UI to update the tags panel."""
        payload = {
            "action": "telemetry",
            "data": {
                "visited": list(self.visited),
                "percepts": self.current_state.get("percepts", {}),
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
