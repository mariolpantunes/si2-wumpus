console.log("script.js loading...");

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
    console.log("App constructor initializing...");
    const serverHost = window.location.hostname || "localhost";
    this.serverUrl = `ws://${serverHost}:8765`;
    this.ws = null;
    this.reconnectAttempts = 0;

    this.canvas = document.getElementById("sim-canvas");
    this.ctx = this.canvas.getContext("2d");
    this.cellSize = 40;

    this.agentCanvas = document.getElementById("agent-canvas");
    this.agentCtx = this.agentCanvas.getContext("2d");

    this.mode = "idle";
    this.mapData = null;
    this.simState = null;
    this.editTool = "floor";

    this.setupWebsocket();
    this.setupCanvasEvents();
    console.log("App initialized.");
  }

  setupWebsocket() {
    console.log("Connecting to " + this.serverUrl);
    this.ws = new WebSocket(this.serverUrl);

    this.ws.onopen = () => {
      console.log("Connected to backend");
      this.reconnectAttempts = 0;
      this.ws.send(JSON.stringify({ client: "frontend" }));
      document.getElementById("agent-status").innerText = "Connected";
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "map_list") {
        const select = document.getElementById("map-select");
        if (select) {
            select.innerHTML = "";
            data.maps.forEach((m) => {
              const opt = document.createElement("option");
              opt.value = m;
              opt.innerText = m;
              select.appendChild(opt);
            });
        }
      } else if (data.type === "update") {
        this.mapData = data.map;
        this.simState = data.state;

        // Clear agent UI if this looks like a fresh reset (score 0, 1 visit)
        if (this.simState && this.simState.score === 0 && Object.keys(this.simState.visits || {}).length <= 1) {
            this.agentCtx.clearRect(0, 0, this.agentCanvas.width, this.agentCanvas.height);
            const container = document.getElementById("percept-tags");
            if (container) container.innerHTML = '<span class="percept-tag neutral">NONE</span>';
        }

        const controls = document.getElementById("sim-controls");
        if (controls) controls.classList.remove("hidden");
        
        const status = document.getElementById("agent-status");
        if (status) {
            status.innerText = data.agent_connected ? "Agent: Connected" : "Agent: Waiting...";
        }

        if (!data.agent_connected) {
            const brainPanel = document.getElementById("agent-brain-panel");
            if (brainPanel) brainPanel.style.display = "none";
            this.agentCtx.clearRect(0, 0, this.agentCanvas.width, this.agentCanvas.height);
        }
        
        if (this.simState) {
            const scoreVal = document.getElementById("score-val");
            const arrowsVal = document.getElementById("arrows-val");
            if (scoreVal) scoreVal.innerText = `Score: ${this.simState.score}`;
            if (arrowsVal) arrowsVal.innerText = `Arrows: ${this.simState.arrows}`;
        }

        this.resizeCanvas();
        this.draw();
      } else if (data.type === "agent_telemetry") {
        const brainPanel = document.getElementById("agent-brain-panel");
        if (brainPanel) brainPanel.style.display = "flex";
        this.updateAgentBrainUI(data.data);
      }
    };

    this.ws.onclose = () => {
      console.log("Websocket connection closed");
      const status = document.getElementById("agent-status");
      if (status) status.innerText = "Disconnected. Reconnecting...";
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      this.reconnectAttempts++;
      setTimeout(() => this.setupWebsocket(), delay);
    };

    this.ws.onerror = (err) => {
      console.error("Websocket error:", err);
      this.ws.close();
    };
  }

  resizeCanvas() {
    if (!this.mapData) return;
    const w = this.mapData.width * this.cellSize;
    const h = this.mapData.height * this.cellSize;
    
    if (this.canvas.width !== w || this.canvas.height !== h) {
        this.canvas.width = w;
        this.canvas.height = h;
        this.agentCanvas.width = w;
        this.agentCanvas.height = h;
        
        this.agentCtx.clearRect(0, 0, w, h);
        const tags = document.getElementById("percept-tags");
        if (tags) tags.innerHTML = '<span class="percept-tag neutral">NONE</span>';
    }
  }

  updateAgentBrainUI(telemetry) {
    if (!this.mapData) return;

    this.agentCtx.clearRect(0, 0, this.agentCanvas.width, this.agentCanvas.height);

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

    if (telemetry.percepts) {
      const container = document.getElementById("percept-tags");
      if (container) {
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
    }

    const probs = telemetry.current_probs || { N: 0, S: 0, E: 0, W: 0 };
    ["N", "S", "E", "W"].forEach((dir) => {
      const p = probs[dir] || 0;
      const pct = Math.round(p * 100);
      const bar = document.getElementById(`prob-${dir}`);
      const txt = document.getElementById(`txt-${dir}`);
      if (bar) {
          bar.style.width = `${pct}%`;
          if (p === 0) bar.style.backgroundColor = "var(--nord11)";
          else if (p > 0.4) bar.style.backgroundColor = "var(--nord14)";
          else bar.style.backgroundColor = "var(--nord13)";
      }
      if (txt) txt.innerText = `${pct}%`;
    });
  }

  showMenu(menuId) {
    document.querySelectorAll(".panel").forEach((p) => p.classList.add("hidden"));
    const menu = document.getElementById(menuId);
    if (menu) menu.classList.remove("hidden");
    this.mode = menuId === "edit-menu" ? "edit" : "idle";
    if (menuId === "main-menu") this.mapData = null;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  loadMap() {
    const select = document.getElementById("map-select");
    const filename = select ? select.value : null;
    if (filename) {
      this.mode = "run";
      this.ws.send(JSON.stringify({ action: "load_map", filename }));
    }
  }

  startSimulation() { this.ws.send(JSON.stringify({ action: "start_sim" })); }
  stopSimulation() { this.ws.send(JSON.stringify({ action: "stop_sim" })); }
  resetSimulation() { this.ws.send(JSON.stringify({ action: "reset_sim" })); }

  createNewMap() {
    const w = parseInt(document.getElementById("new-map-w").value);
    const h = parseInt(document.getElementById("new-map-h").value);
    const type = document.getElementById("new-map-type").value;
    const isTeleport = document.getElementById("new-map-teleport").checked;

    const grid = Array(h).fill().map(() => Array(w).fill("floor"));
    this.mapData = {
      width: w, height: h, type: type, teleport: isTeleport,
      grid: grid, start: [0, 0], target: [w - 1, h - 1],
    };
    this.simState = null;
    const tools = document.getElementById("editor-tools");
    if (tools) tools.classList.remove("hidden");
    this.resizeCanvas();
    this.draw();
  }

  setEditTool(tool) { this.editTool = tool; }

  saveMap() {
    const nameInput = document.getElementById("new-map-name");
    const name = (nameInput && nameInput.value) || "new_map";
    this.ws.send(JSON.stringify({ action: "save_map", filename: name, map_data: this.mapData }));
    alert("Map saved!");
  }

  setupCanvasEvents() {
    this.canvas.addEventListener("mousedown", (e) => {
      if (this.mode !== "edit" || !this.mapData) return;
      const rect = this.canvas.getBoundingClientRect();
      const x = Math.floor((e.clientX - rect.left) / this.cellSize);
      const y = Math.floor((e.clientY - rect.top) / this.cellSize);

      if (x >= 0 && x < this.mapData.width && y >= 0 && y < this.mapData.height) {
        if (["floor", "obstacle", "pit", "wumpus", "gold"].includes(this.editTool)) {
          this.mapData.grid[y][x] = this.editTool;
        } else if (this.editTool === "start") {
          this.mapData.start = [x, y];
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

        if (["floor", "pit", "wumpus", "gold", "arrow"].includes(cell)) {
          let color = "#D8DEE9";
          if (this.simState && this.simState.visits[key]) {
            color = interpolateColor(color, this.simState.visits[key], 15);
          }
          this.ctx.fillStyle = color;
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
          this.ctx.strokeStyle = "#E5E9F0";
          this.ctx.strokeRect(cx, cy, this.cellSize, this.cellSize);

          if (this.mapData.teleport && (x === 0 || x === this.mapData.width - 1 || y === 0 || y === this.mapData.height - 1)) {
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

          if (cell !== "floor" || cell === "arrow") {
            this.ctx.font = "24px sans-serif";
            this.ctx.textAlign = "center";
            this.ctx.textBaseline = "middle";
            this.ctx.shadowColor = "rgba(0,0,0,0.4)";
            this.ctx.shadowBlur = 4;
            this.ctx.shadowOffsetX = 2;
            this.ctx.shadowOffsetY = 2;

            let emoji = "";
            if (cell === "pit") emoji = "🕳️";
            else if (cell === "wumpus") {
                if (this.simState && !this.simState.wumpus_alive) emoji = "";
                else emoji = "🐲";
            }
            else if (cell === "gold") emoji = "💰";
            else if (cell === "arrow") emoji = "🏹";

            this.ctx.fillText(emoji, cx + this.cellSize / 2, cy + this.cellSize / 2 + 2);
            this.ctx.shadowColor = "transparent";
          }
        } else if (cell === "obstacle") {
          let color = "#4C566A";
          if (this.simState && this.simState.hits[key]) {
            color = interpolateColor(color, this.simState.hits[key], 5);
          }
          this.ctx.fillStyle = color;
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
        }

        if (this.mapData.start && x === this.mapData.start[0] && y === this.mapData.start[1]) {
          this.ctx.fillStyle = "rgba(235, 203, 139, 0.5)";
          this.ctx.fillRect(cx, cy, this.cellSize, this.cellSize);
        }
      }
    }

    if (this.simState && this.simState.last_arrow_path) {
      this.ctx.strokeStyle = "rgba(235, 203, 139, 0.8)";
      this.ctx.setLineDash([5, 5]);
      this.ctx.lineWidth = 3;
      this.ctx.beginPath();
      const [ax, ay] = this.simState.agent_pos;
      this.ctx.moveTo(ax * this.cellSize + this.cellSize/2, ay * this.cellSize + this.cellSize/2);
      this.simState.last_arrow_path.forEach(pos => {
        this.ctx.lineTo(pos[0] * this.cellSize + this.cellSize/2, pos[1] * this.cellSize + this.cellSize/2);
      });
      this.ctx.stroke();
      this.ctx.setLineDash([]);
      this.ctx.lineWidth = 1;
      
      if (this.simState.last_arrow_path.length > 0) {
        const last = this.simState.last_arrow_path[this.simState.last_arrow_path.length - 1];
        this.ctx.fillStyle = "#EBCB8B";
        this.ctx.font = "20px sans-serif";
        this.ctx.textAlign = "center";
        this.ctx.textBaseline = "middle";
        this.ctx.fillText("🏹", last[0] * this.cellSize + this.cellSize/2, last[1] * this.cellSize + this.cellSize/2);
      }
    }

    if (this.simState && this.simState.agent_pos) {
      const [ax, ay] = this.simState.agent_pos;
      const centerX = ax * this.cellSize + this.cellSize / 2;
      const centerY = ay * this.cellSize + this.cellSize / 2;
      const radius = this.cellSize / 2 - 4;
      const gradient = this.ctx.createRadialGradient(centerX - radius / 3, centerY - radius / 3, radius / 5, centerX, centerY, radius);
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
console.log("script.js execution complete.");
