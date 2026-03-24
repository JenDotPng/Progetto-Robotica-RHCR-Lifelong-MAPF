// viewer.js - Main visualization engine for MAPF experiments

class ExperimentViewer {
    constructor(canvasId, data) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.data = data;
        
        // Canvas settings
        this.cellSize = 30;
        this.agentRadius = 5;
        this.padding = 20;
        
        // Agent colors
        this.agentColors = this.generateAgentColors(data.paths.length);
        
        // Animation state
        this.currentTimestep = 0;
        this.isPlaying = false;
        this.playbackSpeed = 1.0;
        this.animationFrame = null;
        this.lastFrameTime = 0;
        
        // Visual options
        this.showGrid = true;
        this.showTrails = false;
        this.showHeatmap = null; // null, 'congestion', 'conflicts', 'velocity'
        this.showAgentIDs = true;
        this.showPaths = false;
        
        // Trail history
        this.agentTrails = new Map();
        this.maxTrailLength = 20;
        
        // Colors
        this.colors = {
            background: '#1a1a2e',
            grid: '#333333',
            obstacle: '#16213e',
            endpoint: '#0f3460',
            agent: '#e94560',
            trail: 'rgba(233, 69, 96, 0.3)',
            path: 'rgba(233, 69, 96, 0.2)',
            text: '#eaeaea',
            conflict: '#ff6b6b'
        };
        
        // Calculate canvas size
        this.setupCanvas();

        // Build location -> (x,y) lookup from grid definition (includes station cells)
        this.locationToXY = new Map();
        if (this.data?.grid?.cells) {
            for (const cell of this.data.grid.cells) {
                if (cell && Number.isInteger(cell.id)) {
                    this.locationToXY.set(cell.id, { x: cell.x, y: cell.y });
                }
            }
        }
        
        // Initialize
        this.render();
    }
    
    setupCanvas() {
        const container = this.canvas.parentElement;
        const availableWidth = container.clientWidth - 4; // Account for border
        const availableHeight = container.clientHeight - 4;
        
        // Calculate ideal canvas size based on grid
        let idealWidth = this.data.grid.width * this.cellSize + 2 * this.padding;
        let idealHeight = this.data.grid.height * this.cellSize + 2 * this.padding;
        
        // Scale down if canvas is too large for container
        let scale = 1;
        if (idealWidth > availableWidth || idealHeight > availableHeight) {
            scale = Math.min(
                availableWidth / idealWidth,
                availableHeight / idealHeight
            );
        }
        
        // Apply scale
        this.cellSize = Math.max(5, this.cellSize * scale); // Minimum cell size of 5px
        
        const width = this.data.grid.width * this.cellSize + 2 * this.padding;
        const height = this.data.grid.height * this.cellSize + 2 * this.padding;
        
        this.canvas.width = width;
        this.canvas.height = height;
        
        // Set CSS size for proper display
        this.canvas.style.width = width + 'px';
        this.canvas.style.height = height + 'px';
    }
    
    // Handle window resize event
    onWindowResize() {
        this.setupCanvas();
        this.render();
    }
    
    // Generate unique colors for agents
    generateAgentColors(numAgents) {
        const colors = [];
        const hueStep = 360 / numAgents;
        for (let i = 0; i < numAgents; i++) {
            const hue = (i * hueStep) % 360;
            const saturation = 70 + (i % 3) * 10;
            const lightness = 50;
            colors.push(`hsl(${hue}, ${saturation}%, ${lightness}%)`);
        }
        return colors;
    }
    
    // Get agent color
    getAgentColor(agentId) {
        return this.agentColors[agentId % this.agentColors.length];
    }
    
    // Convert grid coordinates to canvas coordinates
    gridToCanvas(x, y) {
        return {
            x: this.padding + x * this.cellSize + this.cellSize / 2,
            y: this.padding + y * this.cellSize + this.cellSize / 2
        };
    }
    
    // Draw a 5-pointed star for goals
    drawStar(ctx, x, y, size, color) {
        const points = 5;
        const innerRadius = size / 2;
        const outerRadius = size;
        const pointAngle = Math.PI / points;
        
        ctx.save();
        ctx.fillStyle = color;
        ctx.strokeStyle = this.colors.background;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        
        for (let i = 0; i < points * 2; i++) {
            const radius = i % 2 === 0 ? outerRadius : innerRadius;
            const angle = (i * Math.PI) / points - Math.PI / 2;
            const px = x + Math.cos(angle) * radius;
            const py = y + Math.sin(angle) * radius;
            
            if (i === 0) {
                ctx.moveTo(px, py);
            } else {
                ctx.lineTo(px, py);
            }
        }
        
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.restore();
    }
    
    // Draw the grid environment
    drawGrid() {
        const ctx = this.ctx;
        const grid = this.data.grid;
        
        // Draw cells
        for (let y = 0; y < grid.height; y++) {
            for (let x = 0; x < grid.width; x++) {
                const pos = this.gridToCanvas(x, y);
                const isObstacle = grid.obstacles.some(obs => obs.x === x && obs.y === y);
                
                // Cell background
                ctx.fillStyle = isObstacle ? this.colors.obstacle : this.colors.background;
                ctx.fillRect(
                    pos.x - this.cellSize / 2,
                    pos.y - this.cellSize / 2,
                    this.cellSize,
                    this.cellSize
                );
                
                // Grid lines
                if (this.showGrid) {
                    ctx.strokeStyle = this.colors.grid;
                    ctx.lineWidth = 1;
                    ctx.strokeRect(
                        pos.x - this.cellSize / 2,
                        pos.y - this.cellSize / 2,
                        this.cellSize,
                        this.cellSize
                    );
                }
            }
        }
    }
    
    // Draw endpoint markers
    drawEndpoints() {
        const ctx = this.ctx;
        
        for (let i = 0; i < this.data.paths.length; i++) {
            const path = this.data.paths[i];
            if (path.length === 0) continue;
            
            const start = path[0];
            const pos = this.gridToCanvas(start.x, start.y);
            
            // Draw start marker (small circle)
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 4, 0, 2 * Math.PI);
            ctx.fillStyle = this.colors.endpoint;
            ctx.fill();
            ctx.strokeStyle = this.colors.agent;
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }

    // Convert location ID to grid coordinates
    locToGrid(location) {
        if (this.locationToXY.has(location)) {
            return this.locationToXY.get(location);
        }

        // Fallback for linearized location IDs: column-major ordering
        const height = this.data.grid.height;
        return {
            x: Math.floor(location / height),
            y: location % height
        };
    }

    // Return goal list for one agent, supporting both legacy and RHCR formats
    getAgentGoals(agentId) {
        const tasks = this.data.tasks;
        if (!tasks || !Array.isArray(tasks.goals)) {
            return [];
        }

        // RHCR format: goals is list of lists
        if (tasks.goals.length > 0 && Array.isArray(tasks.goals[0])) {
            return tasks.goals[agentId] || [];
        }

        // Legacy format: one goal per agent
        if (agentId < tasks.goals.length) {
            return [tasks.goals[agentId]];
        }

        return [];
    }

    // Return goal timestep list for one agent (RHCR format).
    getAgentGoalTimesteps(agentId) {
        const tasks = this.data.tasks;
        if (!tasks || !Array.isArray(tasks.goal_timesteps)) {
            return [];
        }

        if (tasks.goal_timesteps.length > 0 && Array.isArray(tasks.goal_timesteps[0])) {
            return tasks.goal_timesteps[agentId] || [];
        }

        return [];
    }

    getStateTimestep(state, fallbackIndex = 0) {
        if (state && Number.isFinite(state.timestep)) {
            return state.timestep;
        }
        return fallbackIndex;
    }

    // Get the last known state whose timestep is <= targetTimestep.
    getStateAtOrBefore(path, targetTimestep) {
        if (!path || path.length === 0) return null;

        let chosen = path[0];
        for (let i = 1; i < path.length; i++) {
            const candidate = path[i];
            const t = this.getStateTimestep(candidate, i);
            if (t > targetTimestep) break;
            chosen = candidate;
        }
        return chosen;
    }

    // Per-agent stop timestep: prefer tasks.txt completion time, fallback to path end.
    getAgentStopTimestep(agentId) {
        const path = this.data.paths[agentId];
        if (!path || path.length === 0) return 0;

        const goalTimesteps = this.getAgentGoalTimesteps(agentId);
        if (goalTimesteps.length > 0) {
            return goalTimesteps[goalTimesteps.length - 1];
        }

        return this.getStateTimestep(path[path.length - 1], path.length - 1);
    }

    // Compute the active goal at current timestep for one agent
    getActiveGoalState(agentId) {
        const path = this.data.paths[agentId];
        if (!path || path.length === 0) return null;

        const goals = this.getAgentGoals(agentId);
        if (!goals || goals.length === 0) {
            return path[path.length - 1];
        }

        let goalIndex = 0;
        const stopTimestep = this.getAgentStopTimestep(agentId);
        const effectiveTimestep = Math.min(this.currentTimestep, stopTimestep);

        for (let i = 0; i < path.length && goalIndex < goals.length; i++) {
            const state = path[i];
            if (this.getStateTimestep(state, i) > effectiveTimestep) {
                break;
            }
            if (state.location === goals[goalIndex]) {
                goalIndex += 1;
            }
        }

        if (goalIndex >= goals.length) {
            return null;
        }

        const goalXY = this.locToGrid(goals[goalIndex]);
        return {
            x: goalXY.x,
            y: goalXY.y,
            location: goals[goalIndex]
        };
    }
    
    // Draw planned paths
    drawPaths() {
        if (!this.showPaths) return;
        
        const ctx = this.ctx;
        
        for (let i = 0; i < this.data.paths.length; i++) {
            const path = this.data.paths[i];
            if (path.length === 0) continue;
            
            ctx.beginPath();
            ctx.strokeStyle = this.colors.path;
            ctx.lineWidth = 2;
            
            for (let t = this.currentTimestep; t < path.length - 1; t++) {
                const current = this.gridToCanvas(path[t].x, path[t].y);
                const next = this.gridToCanvas(path[t + 1].x, path[t + 1].y);
                
                ctx.moveTo(current.x, current.y);
                ctx.lineTo(next.x, next.y);
            }
            
            ctx.stroke();
        }
    }
    
    // Draw agent trails
    drawTrails() {
        if (!this.showTrails) return;
        
        const ctx = this.ctx;
        
        for (const [agentId, trail] of this.agentTrails) {
            if (trail.length < 2) continue;
            
            ctx.beginPath();
            ctx.strokeStyle = this.colors.trail;
            ctx.lineWidth = 3;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            
            const start = this.gridToCanvas(trail[0].x, trail[0].y);
            ctx.moveTo(start.x, start.y);
            
            for (let i = 1; i < trail.length; i++) {
                const pos = this.gridToCanvas(trail[i].x, trail[i].y);
                const alpha = i / trail.length;
                ctx.globalAlpha = alpha * 0.5;
                ctx.lineTo(pos.x, pos.y);
            }
            
            ctx.stroke();
            ctx.globalAlpha = 1.0;
        }
    }
    
    // Draw heatmap overlay
    drawHeatmap() {
        if (!this.showHeatmap || !this.data.metrics) return;
        
        const ctx = this.ctx;
        let heatmapData = null;
        let maxValue = 0;
        
        // Select heatmap type
        if (this.showHeatmap === 'congestion') {
            heatmapData = this.data.metrics.congestion_heatmap;
        } else if (this.showHeatmap === 'conflicts') {
            heatmapData = this.data.metrics.conflict_heatmap;
        } else if (this.showHeatmap === 'velocity') {
            heatmapData = this.data.metrics.velocity_heatmap;
        }
        
        if (!heatmapData) return;
        
        // Find max value for normalization
        heatmapData.forEach(row => {
            row.forEach(val => {
                maxValue = Math.max(maxValue, val);
            });
        });
        
        if (maxValue === 0) return;
        
        // Draw heatmap cells
        for (let y = 0; y < heatmapData.length; y++) {
            for (let x = 0; x < heatmapData[y].length; x++) {
                const value = heatmapData[y][x];
                if (value === 0) continue;
                
                const intensity = value / maxValue;
                const pos = this.gridToCanvas(x, y);
                
                // Color gradient: blue (low) -> yellow -> red (high)
                let r, g, b;
                if (intensity < 0.5) {
                    r = Math.floor(intensity * 2 * 255);
                    g = Math.floor(intensity * 2 * 255);
                    b = 255;
                } else {
                    r = 255;
                    g = Math.floor((1 - intensity) * 2 * 255);
                    b = 0;
                }
                
                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.4)`;
                ctx.fillRect(
                    pos.x - this.cellSize / 2,
                    pos.y - this.cellSize / 2,
                    this.cellSize,
                    this.cellSize
                );
            }
        }
    }
    
    // Draw agents at current timestep
    drawAgents() {
        const ctx = this.ctx;
        const t = this.currentTimestep;
        
        // Check for conflicts at current timestep
        const conflicts = this.detectCurrentConflicts();
        
        // First draw goals (behind agents)
        for (let i = 0; i < this.data.paths.length; i++) {
            const path = this.data.paths[i];
            if (path.length === 0) continue;
            
            // Get active goal for current timestep
            const goalState = this.getActiveGoalState(i);
            if (!goalState) continue;
            const goalPos = this.gridToCanvas(goalState.x, goalState.y);
            const agentColor = this.getAgentColor(i);
            
            // Draw goal as star
            this.drawStar(ctx, goalPos.x, goalPos.y, this.agentRadius * 2.5, agentColor);
        }
        
        // Then draw agents
        for (let i = 0; i < this.data.paths.length; i++) {
            const path = this.data.paths[i];
            if (path.length === 0) continue;
            
            // Freeze each agent at its own stop timestep.
            const stopTimestep = this.getAgentStopTimestep(i);
            const effectiveTimestep = Math.min(t, stopTimestep);
            const state = this.getStateAtOrBefore(path, effectiveTimestep) || path[path.length - 1];
            const pos = this.gridToCanvas(state.x, state.y);
            
            // Check if agent is in conflict
            const inConflict = conflicts.has(i);
            const agentColor = this.getAgentColor(i);
            
            // Draw agent circle
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, this.agentRadius, 0, 2 * Math.PI);
            ctx.fillStyle = inConflict ? this.colors.conflict : agentColor;
            ctx.fill();
            
            // Draw border
            ctx.strokeStyle = this.colors.background;
            ctx.lineWidth = 1.5;
            ctx.stroke();
            
            // Draw agent ID only if large enough
            if (this.showAgentIDs && this.agentRadius > 4) {
                ctx.fillStyle = this.colors.text;
                ctx.font = 'bold 8px monospace';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(i.toString(), pos.x, pos.y);
            }
            
            // Update trail
            if (this.showTrails) {
                if (!this.agentTrails.has(i)) {
                    this.agentTrails.set(i, []);
                }
                const trail = this.agentTrails.get(i);
                trail.push({x: state.x, y: state.y});
                if (trail.length > this.maxTrailLength) {
                    trail.shift();
                }
            }
        }
    }
    
    // Detect conflicts at current timestep
    detectCurrentConflicts() {
        const conflicts = new Set();
        const t = this.currentTimestep;
        
        // Check vertex conflicts
        const positions = new Map();
        for (let i = 0; i < this.data.paths.length; i++) {
            const path = this.data.paths[i];
            if (path.length === 0) continue;
            
            const stopTimestep = this.getAgentStopTimestep(i);
            const effectiveTimestep = Math.min(t, stopTimestep);
            const state = this.getStateAtOrBefore(path, effectiveTimestep) || path[path.length - 1];
            const key = `${state.x},${state.y}`;
            
            if (positions.has(key)) {
                conflicts.add(i);
                conflicts.add(positions.get(key));
            } else {
                positions.set(key, i);
            }
        }
        
        // Check edge conflicts
        if (t > 0) {
            for (let i = 0; i < this.data.paths.length; i++) {
                const path_i = this.data.paths[i];
                if (path_i.length === 0) continue;
                
                const stop_i = this.getAgentStopTimestep(i);
                const prev_i = this.getStateAtOrBefore(path_i, Math.min(t - 1, stop_i)) || path_i[path_i.length - 1];
                const curr_i = this.getStateAtOrBefore(path_i, Math.min(t, stop_i)) || path_i[path_i.length - 1];
                
                for (let j = i + 1; j < this.data.paths.length; j++) {
                    const path_j = this.data.paths[j];
                    if (path_j.length === 0) continue;
                    
                    const stop_j = this.getAgentStopTimestep(j);
                    const prev_j = this.getStateAtOrBefore(path_j, Math.min(t - 1, stop_j)) || path_j[path_j.length - 1];
                    const curr_j = this.getStateAtOrBefore(path_j, Math.min(t, stop_j)) || path_j[path_j.length - 1];
                    
                    // Edge conflict: agents swap positions
                    if (prev_i.x === curr_j.x && prev_i.y === curr_j.y &&
                        curr_i.x === prev_j.x && curr_i.y === prev_j.y) {
                        conflicts.add(i);
                        conflicts.add(j);
                    }
                }
            }
        }
        
        return conflicts;
    }
    
    // Main render function
    render() {
        // Clear canvas
        this.ctx.fillStyle = this.colors.background;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw layers
        this.drawGrid();
        this.drawHeatmap();
        this.drawEndpoints();
        this.drawPaths();
        this.drawTrails();
        this.drawAgents();
    }
    
    // Animation loop
    animate(timestamp) {
        if (!this.isPlaying) return;
        
        const frameDelay = 1000 / (30 * this.playbackSpeed); // 30 FPS base
        
        if (timestamp - this.lastFrameTime >= frameDelay) {
            this.step();
            this.lastFrameTime = timestamp;
        }
        
        this.animationFrame = requestAnimationFrame((t) => this.animate(t));
    }
    
    // Step forward one timestep
    step() {
        if (this.currentTimestep < this.getMaxTimestep()) {
            this.currentTimestep++;
            this.render();
            this.onTimestepChange();
        } else {
            this.pause();
        }
    }
    
    // Get maximum timestep across all paths
    getMaxTimestep() {
        let max = 0;
        this.data.paths.forEach((path, agentId) => {
            if (path.length === 0) return;
            max = Math.max(max, this.getAgentStopTimestep(agentId));
        });
        return max;
    }
    
    // Playback controls
    play() {
        if (this.currentTimestep >= this.getMaxTimestep()) {
            this.currentTimestep = 0;
        }
        this.isPlaying = true;
        this.lastFrameTime = performance.now();
        this.animationFrame = requestAnimationFrame((t) => this.animate(t));
    }
    
    pause() {
        this.isPlaying = false;
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
    }
    
    reset() {
        this.pause();
        this.currentTimestep = 0;
        this.agentTrails.clear();
        this.render();
        this.onTimestepChange();
    }
    
    setTimestep(t) {
        this.currentTimestep = Math.max(0, Math.min(t, this.getMaxTimestep()));
        this.render();
        this.onTimestepChange();
    }
    
    setSpeed(speed) {
        this.playbackSpeed = Math.max(0.1, Math.min(speed, 10.0));
    }
    
    // Toggle visual options
    toggleGrid() {
        this.showGrid = !this.showGrid;
        this.render();
    }
    
    toggleTrails() {
        this.showTrails = !this.showTrails;
        if (!this.showTrails) {
            this.agentTrails.clear();
        }
        this.render();
    }
    
    togglePaths() {
        this.showPaths = !this.showPaths;
        this.render();
    }
    
    toggleAgentIDs() {
        this.showAgentIDs = !this.showAgentIDs;
        this.render();
    }
    
    setHeatmap(type) {
        this.showHeatmap = type; // null, 'congestion', 'conflicts', 'velocity'
        this.render();
    }
    
    // Callback for timestep changes (override to update UI)
    onTimestepChange() {
        // To be implemented by UI controller
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ExperimentViewer;
}
