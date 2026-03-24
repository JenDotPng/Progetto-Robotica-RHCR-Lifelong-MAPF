// ui.js - UI controller for experiment viewer

class ViewerUI {
    constructor(viewer) {
        this.viewer = viewer;
        this.agentListRefs = new Map();
        this.setupEventListeners();
        this.updateMetrics();
        this.setupResizeHandler();
        this.populateAgentList();
    }
    
    setupResizeHandler() {
        // Handle window resize
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.viewer.onWindowResize();
            }, 250); // Debounce resize events
        });
    }
    
    setupEventListeners() {
        // Playback controls
        document.getElementById('playBtn')?.addEventListener('click', () => {
            if (this.viewer.isPlaying) {
                this.viewer.pause();
                this.updatePlayButton(false);
            } else {
                this.viewer.play();
                this.updatePlayButton(true);
            }
        });
        
        document.getElementById('resetBtn')?.addEventListener('click', () => {
            this.viewer.reset();
            this.updatePlayButton(false);
        });
        
        document.getElementById('stepBackBtn')?.addEventListener('click', () => {
            this.viewer.pause();
            this.viewer.setTimestep(this.viewer.currentTimestep - 1);
            this.updatePlayButton(false);
        });
        
        document.getElementById('stepForwardBtn')?.addEventListener('click', () => {
            this.viewer.pause();
            this.viewer.setTimestep(this.viewer.currentTimestep + 1);
            this.updatePlayButton(false);
        });
        
        // Speed control
        document.getElementById('speedSlider')?.addEventListener('input', (e) => {
            const speed = parseFloat(e.target.value);
            this.viewer.setSpeed(speed);
            document.getElementById('speedValue').textContent = speed.toFixed(1) + 'x';
        });
        
        // Timeline scrubber
        const timeline = document.getElementById('timeline');
        if (timeline) {
            timeline.max = this.viewer.getMaxTimestep();
            timeline.value = 0;

            let isScrubbingTimeline = false;
            let resumeAfterScrub = false;

            const beginScrub = () => {
                if (isScrubbingTimeline) return;
                isScrubbingTimeline = true;
                resumeAfterScrub = this.viewer.isPlaying;
                if (resumeAfterScrub) {
                    this.viewer.pause();
                    this.updatePlayButton(false);
                }
            };

            const endScrub = () => {
                if (!isScrubbingTimeline) return;
                isScrubbingTimeline = false;
                if (resumeAfterScrub) {
                    this.viewer.play();
                    this.updatePlayButton(true);
                }
                resumeAfterScrub = false;
            };

            timeline.addEventListener('pointerdown', beginScrub);
            timeline.addEventListener('mousedown', beginScrub);
            timeline.addEventListener('touchstart', beginScrub, { passive: true });
            
            timeline.addEventListener('input', (e) => {
                if (!isScrubbingTimeline) {
                    beginScrub();
                }
                this.viewer.setTimestep(parseInt(e.target.value, 10));
            });

            timeline.addEventListener('change', (e) => {
                this.viewer.setTimestep(parseInt(e.target.value, 10));
                endScrub();
            });

            timeline.addEventListener('pointerup', endScrub);
            timeline.addEventListener('mouseup', endScrub);
            timeline.addEventListener('touchend', endScrub);
            timeline.addEventListener('touchcancel', endScrub);
        }
        
        // Visual toggles
        document.getElementById('toggleGrid')?.addEventListener('change', (e) => {
            this.viewer.toggleGrid();
        });
        
        document.getElementById('toggleTrails')?.addEventListener('change', (e) => {
            this.viewer.toggleTrails();
        });
        
        document.getElementById('togglePaths')?.addEventListener('change', (e) => {
            this.viewer.togglePaths();
        });
        
        document.getElementById('toggleAgentIDs')?.addEventListener('change', (e) => {
            this.viewer.toggleAgentIDs();
        });
        
        // Heatmap selector
        document.getElementById('heatmapSelect')?.addEventListener('change', (e) => {
            const type = e.target.value === 'none' ? null : e.target.value;
            this.viewer.setHeatmap(type);
        });
        
        // Override viewer's timestep change callback
        this.viewer.onTimestepChange = () => {
            this.updateTimeline();
            this.updateTimestepDisplay();
            this.updateAgentList();
        };
        
        // Export buttons
        document.getElementById('exportImageBtn')?.addEventListener('click', () => {
            this.exportImage();
        });
        
        document.getElementById('exportVideoBtn')?.addEventListener('click', () => {
            this.exportVideo();
        });
        
        document.getElementById('exportDataBtn')?.addEventListener('click', () => {
            this.exportData();
        });
    }
    
    populateAgentList() {
        const container = document.getElementById('agent-list');
        if (!container) return;
        
        container.innerHTML = '';
        this.agentListRefs.clear();
        
        const data = this.viewer.data;
        if (!data.paths || data.paths.length === 0) return;
        
        for (let i = 0; i < data.paths.length; i++) {
            const path = data.paths[i];
            if (path.length === 0) continue;
            
            const startState = path[0];
            const goalState = path[path.length - 1];
            const color = this.viewer.getAgentColor(i);
            
            const item = document.createElement('div');
            item.className = 'agent-item';

            const details = document.createElement('div');
            details.style.fontSize = '10px';
            details.style.color = '#aaa';
            item.innerHTML = `
                <div class="agent-color" style="background-color: ${color};"></div>
                <div class="agent-info">
                    <div style="font-weight: bold; font-size: 12px;">Agent ${i}</div>
                </div>
            `;

            details.textContent =
                `Start (${startState.x},${startState.y}) -> Final (${goalState.x},${goalState.y})`;
            item.querySelector('.agent-info').appendChild(details);

            this.agentListRefs.set(i, details);
            
            container.appendChild(item);
        }

        this.updateAgentList();
    }

    updateAgentList() {
        if (!this.viewer?.data?.paths) return;

        for (let i = 0; i < this.viewer.data.paths.length; i++) {
            const label = this.agentListRefs.get(i);
            if (!label) continue;

            const path = this.viewer.data.paths[i];
            if (!path || path.length === 0) {
                label.textContent = 'No path';
                continue;
            }

            const stopTimestep = typeof this.viewer.getAgentStopTimestep === 'function'
                ? this.viewer.getAgentStopTimestep(i)
                : this.viewer.currentTimestep;
            const t = Math.min(this.viewer.currentTimestep, stopTimestep);
            const curr = typeof this.viewer.getStateAtOrBefore === 'function'
                ? (this.viewer.getStateAtOrBefore(path, t) || path[path.length - 1])
                : path[Math.min(this.viewer.currentTimestep, path.length - 1)];

            const goals = typeof this.viewer.getAgentGoals === 'function'
                ? this.viewer.getAgentGoals(i)
                : [];

            let reached = 0;
            if (goals.length > 0) {
                for (let k = 0; k < path.length && reached < goals.length; k++) {
                    const state = path[k];
                    const stateT = Number.isFinite(state.timestep) ? state.timestep : k;
                    if (stateT > t) {
                        break;
                    }
                    if (state.location === goals[reached]) {
                        reached += 1;
                    }
                }
            }

            const activeGoal = typeof this.viewer.getActiveGoalState === 'function'
                ? this.viewer.getActiveGoalState(i)
                : null;

            if (activeGoal) {
                label.textContent =
                    `Now (${curr.x},${curr.y}) -> Goal (${activeGoal.x},${activeGoal.y}) [${reached + 1}/${goals.length}]`;
            } else if (goals.length > 0) {
                label.textContent =
                    `Now (${curr.x},${curr.y}) -> Completed all goals [${goals.length}/${goals.length}]`;
            } else {
                const finalState = typeof this.viewer.getStateAtOrBefore === 'function'
                    ? (this.viewer.getStateAtOrBefore(path, stopTimestep) || path[path.length - 1])
                    : path[path.length - 1];
                label.textContent =
                    `Now (${curr.x},${curr.y}) -> Final (${finalState.x},${finalState.y})`;
            }
        }
    }
    
    updatePlayButton(isPlaying) {
        const btn = document.getElementById('playBtn');
        if (btn) {
            btn.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
        }
    }
    
    updateTimeline() {
        const timeline = document.getElementById('timeline');
        if (timeline) {
            timeline.value = this.viewer.currentTimestep;
        }
    }
    
    updateTimestepDisplay() {
        const display = document.getElementById('timestepDisplay');
        if (display) {
            const current = this.viewer.currentTimestep;
            const max = this.viewer.getMaxTimestep();
            display.textContent = `${current} / ${max}`;
        }
    }
    
    updateMetrics() {
        const data = this.viewer.data;
        const metrics = data.metrics;
        
        if (!metrics) return;
        
        // Update metric displays
        this.setMetricValue('numAgents', data.paths.length);
        this.setMetricValue('makespan', metrics.makespan);
        this.setMetricValue('flowtime', metrics.flowtime?.toFixed(2));
        const throughput = metrics.throughput;
        if (Number.isFinite(throughput)) {
            const throughputDisplay = Number.isInteger(throughput)
                ? throughput.toString()
                : throughput.toFixed(4);
            this.setMetricValue('throughput', throughputDisplay);
        } else {
            this.setMetricValue('throughput', '0');
        }
        
        // Conflicts
        const totalConflicts = (metrics.vertex_conflicts || 0) + (metrics.edge_conflicts || 0);
        this.setMetricValue('conflicts', totalConflicts);
        this.setMetricValue('vertexConflicts', metrics.vertex_conflicts || 0);
        this.setMetricValue('edgeConflicts', metrics.edge_conflicts || 0);
        
        // Solver info
        if (data.config) {
            this.setMetricValue('solver', data.config.solver || 'Unknown');
            const rawMap = data.config.map || data.config.map_file || 'Unknown';
            const mapName = String(rawMap).split(/[/\\]/).pop() || 'Unknown';
            this.setMetricValue('mapName', mapName);
            const runtimeSeconds = Number.isFinite(metrics.avg_runtime)
                ? metrics.avg_runtime
                : parseFloat(data.config.runtime || 0);
            this.setMetricValue('runtime', runtimeSeconds.toFixed(3));

            // Use common MAPF naming variants for planning horizon/window.
            const w = data.config.planning_window ?? data.config.window_size ?? data.config.w ?? 'N/A';
            const h = data.config.simulation_window ?? data.config.horizon ?? data.config.h ?? 'N/A';
            this.setMetricValue('paramW', w);
            this.setMetricValue('paramH', h);
        }
        
        // Grid info
        if (data.grid) {
            this.setMetricValue('gridSize', `${data.grid.width} × ${data.grid.height}`);
            this.setMetricValue('obstacles', data.grid.obstacles.length);

            const totalCells = data.grid.width * data.grid.height;
            const obstacleCount = data.grid.obstacles?.length || 0;
            const freeCells = Math.max(totalCells - obstacleCount, 0);
            const freeCellDensity = totalCells > 0
                ? ((freeCells / totalCells) * 100).toFixed(2) + '%'
                : '0%';
            const obstacleDensity = totalCells > 0
                ? ((obstacleCount / totalCells) * 100).toFixed(2) + '%'
                : '0%';

            this.setMetricValue('freeCells', freeCells);
            this.setMetricValue('freeCellDensity', freeCellDensity);
            this.setMetricValue('obstacleDensity', obstacleDensity);
        }
    }

    summarizeTopology(cells) {
        if (!Array.isArray(cells) || cells.length === 0) {
            return 'N/A';
        }

        const counts = {};
        for (const cell of cells) {
            const type = cell?.type || 'Unknown';
            counts[type] = (counts[type] || 0) + 1;
        }

        const summary = Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([type, count]) => `${type}:${count}`)
            .join(' | ');

        return summary || 'N/A';
    }
    
    setMetricValue(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
    
    exportImage() {
        const canvas = this.viewer.canvas;
        const link = document.createElement('a');
        link.download = `experiment_t${this.viewer.currentTimestep}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
    }
    
    exportVideo() {
        alert('Video export requires server-side processing. Use the Python script:\n\n' +
              'python visualize_experiment.py <exp_folder> --export-video recorder.html');
    }
    
    exportData() {
        const data = {
            experiment: this.viewer.data.experiment_name,
            timestep: this.viewer.currentTimestep,
            metrics: this.viewer.data.metrics,
            config: this.viewer.data.config
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.download = 'experiment_data.json';
        link.href = url;
        link.click();
        URL.revokeObjectURL(url);
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (!window.viewer) return;
    
    switch(e.key) {
        case ' ':
            e.preventDefault();
            if (window.viewer.isPlaying) {
                window.viewer.pause();
            } else {
                window.viewer.play();
            }
            break;
        case 'ArrowLeft':
            e.preventDefault();
            window.viewer.pause();
            window.viewer.setTimestep(window.viewer.currentTimestep - 1);
            break;
        case 'ArrowRight':
            e.preventDefault();
            window.viewer.pause();
            window.viewer.setTimestep(window.viewer.currentTimestep + 1);
            break;
        case 'r':
            e.preventDefault();
            window.viewer.reset();
            break;
        case 'g':
            e.preventDefault();
            window.viewer.toggleGrid();
            document.getElementById('toggleGrid').checked = window.viewer.showGrid;
            break;
        case 't':
            e.preventDefault();
            window.viewer.toggleTrails();
            document.getElementById('toggleTrails').checked = window.viewer.showTrails;
            break;
        case 'p':
            e.preventDefault();
            window.viewer.togglePaths();
            document.getElementById('togglePaths').checked = window.viewer.showPaths;
            break;
    }
});

