function hexToRgb(hex) {
  const bigint = parseInt(hex.replace("#", ""), 16);
  return {
    r: (bigint >> 16) & 255,
    g: (bigint >> 8) & 255,
    b: bigint & 255,
  };
}

function interpolateColor(baseHex, intensity, maxIntensity = 10) {
  const targetHex = "#BF616A";
  const base = hexToRgb(baseHex);
  const target = hexToRgb(targetHex);
  const factor = Math.min(intensity / maxIntensity, 1);

  const r = Math.round(base.r + factor * (target.r - base.r));
  const g = Math.round(base.g + factor * (target.g - base.g));
  const b = Math.round(base.b + factor * (target.b - base.b));

  return `rgb(${r}, ${g}, ${b})`;
}

class App {
  constructor() {
    const serverHost = window.location.hostname;
    this.ws = new WebSocket(`ws://${serverHost}:8765`);
    this.canvas = document.getElementById("sim-canvas");
    this.ctx = this.canvas.getContext("2d");
    this.cellSize = 40;

    this.mode = "idle";
    this.mapData = null;
    this.simState = null;
    this.editTool = "floor";

    this.setupWebsocket();
    this.setupCanvasEvents();
    this.agentCanvas = document.getElementById("agent-canvas");
    this.agentCtx = this.agentCanvas.getContext("2d");
  }

  setupWebsocket() {
    this.ws.onopen = () => {
      this.ws.send(JSON.stringify({ client: "frontend" }));
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "map_list") {
        const select = document.getElementById("map-select");
        select.innerHTML = "";
        data.maps.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m;
          opt.innerText = m;
          select.appendChild(opt);
        });
      } else if (data.type === "update") {
        this.mapData = data.map;
        this.simState = data.state;
        document.getElementById("sim-controls").classList.remove("hidden");
        document.getElementById("agent-status").innerText = data.agent_connected
          ? "Agent: Connected"
          : "Agent: Waiting...";
        this.resizeCanvas();
        this.draw();
      } else if (data.type === "agent_telemetry") {
        document.getElementById("agent-brain-panel").style.display = "flex";
        this.updateAgentBrainUI(data.data);
      }
    };
  }

  updateAgentBrainUI(telemetry) {
    if (!this.mapData) return;

    this.agentCanvas.width = this.canvas.width;
    this.agentCanvas.height = this.canvas.height;
    this.agentCtx.clearRect(
      0,
      0,
      this.agentCanvas.width,
      this.agentCanvas.height,
    );

    const visited = new Set(telemetry.visited || []);
    for (let y = 0; y < this.mapData.height; y++) {
      for (let x = 0; x < this.mapData.width; x++) {
        const cx = x * this.cellSize;
        const cy = y * this.cellSize;

        if (visited.has(`${x},${y}`)) {
          this.agentCtx.fillStyle = "#81A1C1";
        } else {
          this.agentCtx.fillStyle = "#2E3440";
        }
        this.agentCtx.fillRect(cx, cy, this.cellSize, this.cellSize);
        this.agentCtx.strokeStyle = "#3B4252";
        this.agentCtx.strokeRect(cx, cy, this.cellSize, this.cellSize);
      }
    }

    if (this.simState && this.simState.agent_pos) {
      const [ax, ay] = this.simState.agent_pos;
      this.agentCtx.fillStyle = "#EBCB8B";
      this.agentCtx.beginPath();
      this.agentCtx.arc(
        ax * this.cellSize + this.cellSize / 2,
        ay * this.cellSize + this.cellSize / 2,
        this.cellSize / 3,
        0,
        Math.PI * 2,
      );
      this.agentCtx.fill();
    }

    // Update Percepts UI
    if (telemetry.percepts) {
      const container = document.getElementById("percept-tags");
      container.innerHTML = "";
      let hasPercepts = false;

      for (const [key, value] of Object.entries(telemetry.percepts)) {
        if (value) {
          hasPercepts = true;
          const tag = document.createElement("span");
          tag.className = "percept-tag active";
          tag.innerText = key.toUpperCase();
          container.appendChild(tag);
        }
      }
      if (!hasPercepts) {
        container.innerHTML = '<span class="percept-tag neutral">NONE</span>';
      }
    }

    // Update probability bars
    const probs = telemetry.current_probs || { N: 0, S: 0, E: 0, W: 0 };
    ["N", "S", "E", "W"].forEach((dir) => {
      const p = probs[dir] || 0;
      const pct = Math.round(p * 100);
      document.getElementById(`prob-${dir}`).style.width = `${pct}%`;
      document.getElementById(`txt-${dir}`).innerText = `${pct}%`;

      const bar = document.getElementById(`prob-${dir}`);
      if (p === 0) bar.style.backgroundColor = "var(--nord11)";
      else if (p > 0.4) bar.style.backgroundColor = "var(--nord14)";
      else bar.style.backgroundColor = "var(--nord13)";
    });
  }

  showMenu(menuId) {
    document
      .querySelectorAll(".panel")
      .forEach((p) => p.classList.add("hidden"));
    document.getElementById(menuId).classList.remove("hidden");
    this.mode = menuId === "edit-menu" ? "edit" : "idle";
    if (menuId === "main-menu") this.mapData = null;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  loadMap() {
    const filename = document.getElementById("map-select").value;
    if (filename) {
      this.mode = "run";
      this.ws.send(JSON.stringify({ action: "load_map", filename }));
    }
  }

  startSimulation() {
    this.ws.send(JSON.stringify({ action: "start_sim" }));
  }
  stopSimulation() {
    this.ws.send(JSON.stringify({ action: "stop_sim" }));
  }
  resetSimulation() {
    this.ws.send(JSON.stringify({ action: "reset_sim" }));
  }

  createNewMap() {
    const w = parseInt(document.getElementById("new-map-w").value);
    const h = parseInt(document.getElementById("new-map-h").value);
    const type = document.getElementById("new-map-type").value;
    const isTeleport = document.getElementById("new-map-teleport").checked;

    const grid = Array(h)
      .fill()
      .map(() => Array(w).fill("floor"));
    this.mapData = {
      width: w,
      height: h,
      type: type,
      teleport: isTeleport,
      grid: grid,
      start: [0, 0],
      target: [w - 1, h - 1],
    };
    this.simState = null;

    document.getElementById("editor-tools").classList.remove("hidden");
    this.resizeCanvas();
    this.draw();
  }

  setEditTool(tool) {
    this.editTool = tool;
  }

  saveMap() {
    const name = document.getElementById("new-map-name").value || "new_map";
    this.ws.send(
      JSON.stringify({
        action: "save_map",
        filename: name,
        map_data: this.mapData,
      }),
    );
    alert("Map saved!");
  }

  resizeCanvas() {
    if (!this.mapData) return;
    this.canvas.width = this.mapData.width * this.cellSize;
    this.canvas.height = this.mapData.height * this.cellSize;
  }

  setupCanvasEvents() {
    this.canvas.addEventListener("mousedown", (e) => {
      if (this.mode !== "edit" || !this.mapData) return;
      const rect = this.canvas.getBoundingClientRect();
      const x = Math.floor((e.clientX - rect.left) / this.cellSize);
      const y = Math.floor((e.clientY - rect.top) / this.cellSize);

      if (
        x >= 0 &&
        x < this.mapData.width &&
        y >= 0 &&
        y < this.mapData.height
      ) {
        if (
          ["floor", "obstacle", "pit", "wumpus", "gold"].includes(this.editTool)
        ) {
          this.mapData.grid[y][x] = this.editTool;
        } else if (this.editTool === "start") {
          this.mapData.start = [x, y];
          this.mapData.grid[y][x] = "floor";
        } else if (this.editTool === "target") {
          this.mapData.target = [x, y];
          this.mapData.grid[y][x] = "floor";
        }
        this.draw();
      }
    });
  }

  draw() {
    if (!this.mapData) return;

    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    for (let y = 0; y < this.mapData.height; y++) {
      for (let x = 0; x < this.mapData.width; x++) {
        const cell = this.mapData.grid[y][x];
        const cx = x * this.cellSize;
        const cy = y * this.cellSize;
        const key = `${x},${y}`;

        // Treat Floor, Pit, Wumpus, and Gold all as having a basic floor background
        if (["floor", "pit", "wumpus", "gold"].includes(cell)) {
          let color = "#D8DEE9"; // Light Nord floor color

          // Apply heatmap over the floor
          if (this.simState && this.simState.visits[key]) {
            color = interpolateColor(color, this.simState.visits[key], 15);
          }
          this.ctx.fillStyle = color;
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
          this.ctx.strokeStyle = "#E5E9F0";
          this.ctx.strokeRect(cx, cy, this.cellSize, this.cellSize);

          // Teleport portal overlay
          const isEdge =
            x === 0 ||
            x === this.mapData.width - 1 ||
            y === 0 ||
            y === this.mapData.height - 1;
          if (this.mapData.teleport && isEdge) {
            this.ctx.beginPath();
            this.ctx.moveTo(cx + this.cellSize / 2, cy + 10);
            this.ctx.lineTo(cx + this.cellSize - 10, cy + this.cellSize / 2);
            this.ctx.lineTo(cx + this.cellSize / 2, cy + this.cellSize - 10);
            this.ctx.lineTo(cx + 10, cy + this.cellSize / 2);
            this.ctx.closePath();

            this.ctx.strokeStyle = "rgba(180, 142, 173, 0.9)";
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
            this.ctx.lineWidth = 1;
          }

          // Draw the specific Entity Emojis ON TOP of the light floor
          if (cell !== "floor") {
            this.ctx.font = "24px sans-serif";
            this.ctx.textAlign = "center";
            this.ctx.textBaseline = "middle";

            // Add a slight drop shadow so the emoji pops off the light floor
            this.ctx.shadowColor = "rgba(0,0,0,0.4)";
            this.ctx.shadowBlur = 4;
            this.ctx.shadowOffsetX = 2;
            this.ctx.shadowOffsetY = 2;

            let emoji = "";
            if (cell === "pit") emoji = "🕳️";
            else if (cell === "wumpus") emoji = "🐲";
            else if (cell === "gold") emoji = "💰";

            this.ctx.fillText(
              emoji,
              cx + this.cellSize / 2,
              cy + this.cellSize / 2 + 2,
            );

            // Reset shadow for the next tiles
            this.ctx.shadowColor = "transparent";
          }
        } else if (cell === "obstacle") {
          let color = "#4C566A";
          if (this.simState && this.simState.hits[key]) {
            color = interpolateColor(color, this.simState.hits[key], 5);
          }

          this.ctx.fillStyle = color;
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);

          this.ctx.fillStyle = "rgba(255,255,255,0.1)";
          this.ctx.beginPath();
          this.ctx.moveTo(cx, cy);
          this.ctx.lineTo(cx + this.cellSize, cy);
          this.ctx.lineTo(cx + this.cellSize - 5, cy + 5);
          this.ctx.lineTo(cx + 5, cy + 5);
          this.ctx.fill();

          this.ctx.fillStyle = "rgba(0,0,0,0.3)";
          this.ctx.beginPath();
          this.ctx.moveTo(cx + this.cellSize, cy);
          this.ctx.lineTo(cx + this.cellSize, cy + this.cellSize);
          this.ctx.lineTo(cx + this.cellSize - 5, cy + this.cellSize - 5);
          this.ctx.lineTo(cx + this.cellSize - 5, cy + 5);
          this.ctx.fill();
        }

        // Draw the starting tile highlight
        if (
          this.mapData.start &&
          x === this.mapData.start[0] &&
          y === this.mapData.start[1]
        ) {
          this.ctx.fillStyle = "rgba(235, 203, 139, 0.5)";
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
        }
      }
    }

    // Draw the Agent
    if (this.simState && this.simState.agent_pos) {
      const [ax, ay] = this.simState.agent_pos;
      const centerX = ax * this.cellSize + this.cellSize / 2;
      const centerY = ay * this.cellSize + this.cellSize / 2;
      const radius = this.cellSize / 2 - 4;

      const gradient = this.ctx.createRadialGradient(
        centerX - radius / 3,
        centerY - radius / 3,
        radius / 5,
        centerX,
        centerY,
        radius,
      );
      gradient.addColorStop(0, "#88C0D0");
      gradient.addColorStop(1, "#5E81AC");

      this.ctx.beginPath();
      this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
      this.ctx.fillStyle = gradient;
      this.ctx.fill();

      this.ctx.shadowColor = "rgba(0,0,0,0.5)";
      this.ctx.shadowBlur = 5;
      this.ctx.shadowOffsetX = 2;
      this.ctx.shadowOffsetY = 2;
      this.ctx.fill();
      this.ctx.shadowColor = "transparent";
    }
  }
}

const app = new App();
