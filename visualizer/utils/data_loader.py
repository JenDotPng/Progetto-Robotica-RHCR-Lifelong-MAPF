"""
Data Loader per il visualizer web 

Scopo
- caricare e normalizzare i file di un esperimento MAPF per il visualizer web;
- convertire i dati grezzi (config, mappa, path, task, statistiche solver)
    in strutture Python coerenti e facili da serializzare in JSON.

Funzionamento
1) legge config.txt con supporto a separatori "=" e ":";
2) individua il file mappa .grid usando solo la cartella progetto maps/;
3) carica la mappa (dimensioni e metadati celle);
4) carica i path agenti da paths.txt (formato RHCR e formati legacy);
5) carica i task da tasks.txt (goals e goal_timesteps);
6) carica solver.csv (se presente) con colonne nominali;
7) costruisce e restituisce un oggetto ExperimentData.

Input attesi per una cartella esperimento
- contenuto cartella esperimento: config.txt, paths.txt, solver.csv, tasks.txt
- mappa: file .grid in project_root/maps 

Output principali
- State: stato agente (location, orientation, timestep)
- GridInfo: informazioni mappa e conversioni loc<->(x,y)
- ExperimentData: pacchetto completo per visualizzazione e metriche
    contenente nome esperimento, config, grid, paths, tasks, solver_stats, map_file

Comportamento in caso di dati mancanti
- file opzionali mancanti generano warning non bloccanti;
- se la mappa non viene trovata in maps/, viene sollevato FileNotFoundError;
- parser paths/tasks tenta fallback compatibili con formati diversi.

Uso rapido (debug locale)
- python data_loader.py <cartella_esperimento>
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import pandas as pd


@dataclass
class State:
    """Represents an agent state at a specific timestep."""
    location: int
    orientation: int
    timestep: int

    @staticmethod
    def from_string(s: str) -> 'State':
        """Parse state from format: (loc,orient,time)"""
        s = s.strip('()')
        parts = s.split(',')
        return State(int(parts[0]), int(parts[1]), int(parts[2]))
    
    def __repr__(self):
        return f"({self.location},{self.orientation},{self.timestep})"


@dataclass
class GridInfo:
    """Information about the grid map."""
    width: int
    height: int
    cells: List[Dict]
    
    def loc_to_xy(self, loc: int) -> Tuple[int, int]:
        """Convert location ID to (x, y) coordinates using column-major ordering."""
        x = loc // self.height
        y = loc % self.height
        return (x, y)
    
    def xy_to_loc(self, x: int, y: int) -> int:
        """Convert (x, y) coordinates to location ID using column-major ordering."""
        return x * self.height + y
    
    def is_obstacle(self, loc: int) -> bool:
        """Check if location is an obstacle."""
        if 0 <= loc < len(self.cells):
            return self.cells[loc]['type'] == 'Obstacle'
        return True


@dataclass
class ExperimentData:
    """Complete data for a single experiment."""
    name: str
    config: Dict
    grid: GridInfo
    paths: List[List[State]]
    tasks: Dict
    solver_stats: Optional[pd.DataFrame]
    map_file: str


def load_config(config_file: str) -> Dict:
    """Load configuration from config.txt."""
    config = {}
    try:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
                elif ':' in line:
                    key, value = line.split(':', 1)
                    config[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"Warning: {config_file} not found")
    return config


def load_grid(grid_file: str) -> GridInfo:
    """Load grid map from .grid file."""
    with open(grid_file, 'r') as f:
        lines = [l.strip() for l in f.readlines()]
    
    # Parse grid size
    width, height = map(int, lines[1].split(','))
    
    # Parse cell information
    cells = []
    for line in lines[3:]:  # Skip header lines
        if not line:
            continue
        parts = line.split(',')
        cell = {
            'id': int(parts[0]),
            'type': parts[1],
            'station': parts[2],
            'x': int(parts[3]),
            'y': int(parts[4])
        }
        cells.append(cell)
    
    return GridInfo(width, height, cells)


def load_paths(paths_file: str, grid: Optional[GridInfo] = None) -> List[List[State]]:
    """
    Load agent paths from paths.txt.
    
    Supported formats:
    1. RHCR-style:
       - First line: number of agents
       - Each following line: "loc,orient,time;loc,orient,time;..."
    2. timestep: agent_id (x, y)
    3. agent_id: (loc,orient,time) (loc,orient,time) ...
    """
    agent_paths = {}  # agent_id -> list of states
    
    try:
        with open(paths_file, 'r') as f:
            raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        
        if not raw_lines:
            print(f"  Warning: {paths_file} is empty")
            return []
        
        # Detect RHCR-style format (first line = number of agents)
        use_rhcr = False
        try:
            num_agents = int(raw_lines[0])
            if len(raw_lines) > 1 and ';' in raw_lines[1] and ':' not in raw_lines[1]:
                use_rhcr = True
        except ValueError:
            num_agents = 0
        
        if use_rhcr:
            paths = []
            for i in range(1, min(num_agents, len(raw_lines) - 1) + 1):
                states_str = raw_lines[i].split(';')
                robot_path = []
                for state_str in states_str:
                    s = state_str.strip()
                    if not s:
                        continue
                    try:
                        robot_path.append(State.from_string(s))
                    except Exception:
                        print(f"  Warning: Could not parse RHCR state: {s}")
                paths.append(robot_path)
            return paths
        
        # Other supported formats
        for line_num, line in enumerate(raw_lines, 1):
            # Try to parse: "timestep: agent_id (x, y)"
            if ':' in line:
                parts = line.split(':', 1)
                try:
                    timestep = int(parts[0].strip())
                    rest = parts[1].strip()
                    
                    # Parse "agent_id (x, y)"
                    if '(' in rest and ')' in rest:
                        agent_id_str = rest.split('(')[0].strip()
                        coords_str = rest.split('(')[1].split(')')[0]
                        
                        agent_id = int(agent_id_str)
                        x, y = map(int, coords_str.split(','))
                        
                        if agent_id not in agent_paths:
                            agent_paths[agent_id] = []
                        
                        if grid is not None:
                            loc = grid.xy_to_loc(x, y)
                            agent_paths[agent_id].append(State(loc, -1, timestep))
                        else:
                            agent_paths[agent_id].append(State(x, y, timestep))
                except (ValueError, IndexError):
                    # Try alternative format: agent_id: (loc,orient,time) (loc,orient,time) ...
                    try:
                        agent_id = int(parts[0].strip())
                        path_str = parts[1].strip()
                        states = []
                        for state_str in path_str.split():
                            state_str = state_str.strip()
                            if state_str:
                                states.append(State.from_string(state_str))
                        agent_paths[agent_id] = states
                    except Exception:
                        print(f"  Warning: Could not parse line {line_num}: {line[:50]}...")
                        continue
        
        # Convert to list sorted by agent_id
        if agent_paths:
            max_agent = max(agent_paths.keys())
            paths = []
            for agent_id in range(max_agent + 1):
                if agent_id in agent_paths:
                    sorted_states = sorted(agent_paths[agent_id], key=lambda s: s.timestep)
                    paths.append(sorted_states)
                else:
                    paths.append([])
            return paths
        
        print(f"  Warning: No valid paths parsed from {paths_file}")
        return []
    
    except FileNotFoundError:
        print(f"  Warning: {paths_file} not found")
        return []
    except Exception as e:
        print(f"  Error loading paths: {e}")
        return []


def load_tasks(tasks_file: str) -> Dict:
    """Load agent tasks from tasks.txt."""
    tasks = {'starts': [], 'goals': [], 'goal_timesteps': []}
    try:
        with open(tasks_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            return tasks

        # Legacy format:
        #   Start: ...
        #   Goal: ...
        if any(line.startswith('Start') or line.startswith('Goal') for line in lines):
            for line in lines:
                if line.startswith('Start'):
                    tasks['starts'] = [int(x) for x in line.split(':', 1)[1].split()]
                elif line.startswith('Goal'):
                    tasks['goals'] = [int(x) for x in line.split(':', 1)[1].split()]
            return tasks

        # RHCR format:
        # first line is num_agents, then one line per agent:
        # start_loc,time,time;goal1,time,time;goal2,time,time;...
        try:
            num_agents = int(lines[0])
        except ValueError:
            return tasks

        starts = []
        goals = []
        goal_timesteps = []
        for i in range(1, min(num_agents + 1, len(lines))):
            parts = [p.strip() for p in lines[i].split(';') if p.strip()]
            agent_starts = []
            agent_goals = []
            agent_goal_timesteps = []

            for j, part in enumerate(parts):
                values = [v.strip() for v in part.split(',') if v.strip()]
                if not values:
                    continue

                try:
                    loc = int(values[0])
                except ValueError:
                    continue

                goal_timestep = None
                if len(values) > 1:
                    try:
                        goal_timestep = int(values[1])
                    except ValueError:
                        goal_timestep = None

                # Skip pending/unassigned entries (e.g. "loc,-1,") and invalid sentinels.
                if loc == -1 or goal_timestep == -1:
                    continue

                if j == 0:
                    agent_starts.append(loc)
                else:
                    agent_goals.append(loc)
                    if goal_timestep is not None:
                        agent_goal_timesteps.append(goal_timestep)

            starts.append(agent_starts)
            goals.append(agent_goals)
            goal_timesteps.append(agent_goal_timesteps)

        tasks['starts'] = starts
        tasks['goals'] = goals
        tasks['goal_timesteps'] = goal_timesteps
    except FileNotFoundError:
        print(f"Warning: {tasks_file} not found")
    return tasks


def load_solver_stats(solver_file: str) -> Optional[pd.DataFrame]:
    """Load solver statistics from solver.csv."""
    try:
        df = pd.read_csv(solver_file, header=None, names=[
            'runtime', 'num_HL', 'num_LL', 'num_HL_edges', 'num_LL_states',
            'num_CT', 'num_conflicting_pairs', 'avg_path_len', 'num_replan',
            'timestep', 'num_agents', 'seed'
        ])
        return df
    except FileNotFoundError:
        print(f"Warning: {solver_file} not found")
        return None


def find_map_file(config: Dict, exp_folder: str) -> Optional[str]:
    """Find map only inside project-level maps directory."""
    map_name = config.get('map', '').split('/')[-1]

    # Add .grid extension if missing
    if map_name and not map_name.endswith('.grid'):
        map_name += '.grid'

    project_root = Path(__file__).resolve().parents[2]
    maps_dir = project_root / 'maps'
    if not maps_dir.exists():
        return None

    # If map_name is specified, search only inside project maps.
    if map_name:
        map_file = maps_dir / map_name
        if map_file.exists():
            return str(map_file)
        return None

    # Optional fallback when config has no explicit map field.
    for grid_file in maps_dir.glob('*.grid'):
        return str(grid_file)
    
    return None


def load_experiment(exp_folder: str) -> ExperimentData:
    """
    Load complete experiment data from a folder.
    
    Args:
        exp_folder: Path to experiment folder (e.g., ../exp/test)
        
    Returns:
        ExperimentData object with all loaded data
    """
    exp_path = Path(exp_folder)
    exp_name = exp_path.name
    
    print(f"Loading experiment: {exp_name}")
    
    # Load config
    config_file = exp_path / 'config.txt'
    config = load_config(str(config_file))
    
    # Find and load grid
    map_file = find_map_file(config, str(exp_path))
    if map_file is None:
        raise FileNotFoundError(f"Could not find map file for {exp_name}")
    
    grid = load_grid(map_file)
    print(f"  Map: {Path(map_file).stem} ({grid.width}x{grid.height})")
    
    # Load paths
    paths_file = exp_path / 'paths.txt'
    paths = load_paths(str(paths_file), grid)
    print(f"  Agents: {len(paths)}")
    
    # Warn if experiment is empty
    if not paths or len(paths) == 0:
        print(f" !! WARNING: No agents found in {exp_name}!")
        print(f"      Check if {paths_file} exists and contains valid data")
    
    # Load tasks
    tasks_file = exp_path / 'tasks.txt'
    tasks = load_tasks(str(tasks_file))
    
    # Load solver stats
    solver_file = exp_path / 'solver.csv'
    solver_stats = load_solver_stats(str(solver_file))
    
    # Compute max timestep
    max_timestep = 0
    for path in paths:
        if path:
            max_timestep = max(max_timestep, max(s.timestep for s in path))
    print(f"  Max timestep: {max_timestep}")
    
    # Extract solver info
    solver_name = config.get('solver', 'Unknown')
    print(f"  Solver: {solver_name}")
    
    return ExperimentData(
        name=exp_name,
        config=config,
        grid=grid,
        paths=paths,
        tasks=tasks,
        solver_stats=solver_stats,
        map_file=map_file
    )


def discover_experiments(exp_base_folder: str) -> List[str]:
    """
    Discover all experiment folders in the exp/ directory.
    
    Args:
        exp_base_folder: Base experiments folder (e.g., ../exp)
        
    Returns:
        List of experiment folder paths
    """
    exp_path = Path(exp_base_folder)
    experiments = []
    
    # Look for folders with paths.txt
    for item in exp_path.rglob('paths.txt'):
        exp_folder = item.parent
        experiments.append(str(exp_folder))
    
    return sorted(experiments)


def load_multiple_experiments(exp_folders: List[str]) -> List[ExperimentData]:
    """
    Load multiple experiments.
    
    Args:
        exp_folders: List of experiment folder paths
        
    Returns:
        List of ExperimentData objects
    """
    experiments = []
    for folder in exp_folders:
        try:
            exp_data = load_experiment(folder)
            experiments.append(exp_data)
        except Exception as e:
            print(f"Error loading {folder}: {e}")
    
    return experiments


if __name__ == '__main__':
    # Test data loading
    import sys
    
    if len(sys.argv) > 1:
        exp_folder = sys.argv[1]
        data = load_experiment(exp_folder)
        print(f"\nSuccessfully loaded experiment: {data.name}")
        print(f"Configuration keys: {list(data.config.keys())}")
        print(f"Number of agents: {len(data.paths)}")
        if data.solver_stats is not None:
            print(f"Solver stats shape: {data.solver_stats.shape}")
    else:
        print("Usage: python data_loader.py <experiment_folder>")
        print("Example: python data_loader.py ../../exp/tesi_final_results/PBS_k20")
