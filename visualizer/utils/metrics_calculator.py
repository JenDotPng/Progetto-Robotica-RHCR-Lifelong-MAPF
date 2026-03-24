"""
Metrics Calculator for MAPF Experiments
Computes performance metrics and statistics
"""

import numpy as np
from typing import List, Dict, Tuple
from collections import defaultdict
import pandas as pd


def compute_makespan(paths) -> int:
    """Compute makespan (maximum path length)."""
    if not paths or not any(paths):
        return 0
    return max(len(path) for path in paths if path)


def compute_sum_of_costs(paths) -> int:
    """Compute sum of costs (sum of all path lengths)."""
    return sum(len(path) for path in paths)


def compute_flowtime(paths) -> float:
    """
    Compute average flowtime (average time to reach goal).
    Flowtime = timestep when agent reaches its goal.
    """
    flowtimes = []
    for path in paths:
        if path:
            # Flowtime is the last timestep in the path
            flowtimes.append(path[-1].timestep)
    return np.mean(flowtimes) if flowtimes else 0.0


def count_completed_tasks_from_tasks(tasks: Dict) -> int:
    """Count completed tasks from tasks.txt-parsed structure.

    Preferred source is goal_timesteps (one timestamp per completed goal).
    If unavailable, fall back to goals list as a best effort.
    """
    if not tasks or not isinstance(tasks, dict):
        return 0

    goal_timesteps = tasks.get('goal_timesteps')
    if isinstance(goal_timesteps, list) and goal_timesteps:
        return sum(len(agent_times) for agent_times in goal_timesteps if isinstance(agent_times, list))

    goals = tasks.get('goals')
    if isinstance(goals, list) and goals:
        # RHCR format: list of goal lists; legacy format may be a flat list.
        if isinstance(goals[0], list):
            return sum(len(agent_goals) for agent_goals in goals if isinstance(agent_goals, list))
        return len(goals)

    return 0


def compute_throughput(paths, max_timestep: int, tasks: Dict = None) -> float:
    """Compute throughput as completed tasks for the loaded experiment.

    For RHCR lifelong experiments, throughput is the number of completed tasks
    extracted from tasks.txt. When tasks are unavailable, fall back to the
    previous proxy (active paths normalized by max_timestep).
    """
    completed_tasks = count_completed_tasks_from_tasks(tasks)
    if completed_tasks > 0:
        return float(completed_tasks)

    # Fallback for datasets without task history.
    completed_proxy = len([p for p in paths if p])
    return completed_proxy / max_timestep if max_timestep > 0 else 0.0


def detect_conflicts(paths) -> List[Tuple[int, int, int, str]]:
    """
    Detect conflicts between agents.
    
    Returns:
        List of (agent1, agent2, timestep, conflict_type) tuples
        conflict_type: 'vertex' or 'edge'
    """
    conflicts = []
    
    # Build location-time map
    location_time_map = defaultdict(list)
    for agent_id, path in enumerate(paths):
        for state in path:
            location_time_map[(state.location, state.timestep)].append(agent_id)
    
    # Find vertex conflicts (two agents at same location at same time)
    for (loc, time), agents in location_time_map.items():
        if len(agents) > 1:
            for i in range(len(agents)):
                for j in range(i+1, len(agents)):
                    conflicts.append((agents[i], agents[j], time, 'vertex'))
    
    # Find edge conflicts (two agents swap locations)
    for agent1_id, path1 in enumerate(paths):
        for agent2_id, path2 in enumerate(paths):
            if agent1_id >= agent2_id:
                continue
            for t in range(min(len(path1), len(path2)) - 1):
                loc1_t = path1[t].location
                loc1_t1 = path1[t+1].location
                loc2_t = path2[t].location
                loc2_t1 = path2[t+1].location
                
                # Edge conflict: agent1 moves from loc1_t to loc1_t1
                # while agent2 moves from loc2_t to loc2_t1
                # and loc1_t == loc2_t1 and loc1_t1 == loc2_t
                if loc1_t == loc2_t1 and loc1_t1 == loc2_t:
                    conflicts.append((agent1_id, agent2_id, t, 'edge'))
    
    return conflicts


def compute_congestion_heatmap(paths, grid, max_timestep: int) -> np.ndarray:
    """
    Compute congestion heatmap showing how many times each cell was visited.
    
    Returns:
        2D array of shape (height, width) with visit counts
    """
    heatmap = np.zeros((grid.height, grid.width))
    
    for path in paths:
        for state in path:
            x, y = grid.loc_to_xy(state.location)
            if 0 <= x < grid.width and 0 <= y < grid.height:
                heatmap[y, x] += 1
    
    return heatmap


def compute_conflict_density_heatmap(paths, grid, max_timestep: int) -> np.ndarray:
    """
    Compute conflict density heatmap showing locations with most conflicts.
    
    Returns:
        2D array of shape (height, width) with conflict counts
    """
    heatmap = np.zeros((grid.height, grid.width))
    conflicts = detect_conflicts(paths)
    
    for agent1, agent2, timestep, conf_type in conflicts:
        if timestep < len(paths[agent1]):
            state = paths[agent1][timestep]
            x, y = grid.loc_to_xy(state.location)
            if 0 <= x < grid.width and 0 <= y < grid.height:
                heatmap[y, x] += 1
    
    return heatmap


def compute_velocity_heatmap(paths, grid, max_timestep: int) -> np.ndarray:
    """
    Compute velocity heatmap showing average agent speed at each location.
    
    Returns:
        2D array of shape (height, width) with average velocities
    """
    velocity_sum = np.zeros((grid.height, grid.width))
    visit_count = np.zeros((grid.height, grid.width))
    
    for path in paths:
        for i in range(len(path) - 1):
            state1 = path[i]
            state2 = path[i+1]
            
            # Velocity = distance / time
            loc1 = state1.location
            loc2 = state2.location
            dt = state2.timestep - state1.timestep
            
            if dt > 0:
                x1, y1 = grid.loc_to_xy(loc1)
                x2, y2 = grid.loc_to_xy(loc2)
                distance = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                velocity = distance / dt
                
                x, y = grid.loc_to_xy(loc1)
                if 0 <= x < grid.width and 0 <= y < grid.height:
                    velocity_sum[y, x] += velocity
                    visit_count[y, x] += 1
    
    # Average velocity
    heatmap = np.divide(velocity_sum, visit_count, 
                       out=np.zeros_like(velocity_sum), 
                       where=visit_count!=0)
    
    return heatmap


def identify_bottlenecks(paths, grid, threshold_percentile=90) -> List[Tuple[int, int]]:
    """
    Identify bottleneck locations (highly congested cells).
    
    Args:
        paths: Agent paths
        grid: Grid information
        threshold_percentile: Percentile threshold for bottleneck detection
        
    Returns:
        List of (x, y) coordinates of bottleneck cells
    """
    # Return empty list if no paths
    if not paths or not any(paths):
        return []
    
    heatmap = compute_congestion_heatmap(paths, grid, 0)
    nonzero_values = heatmap[heatmap > 0]
    
    # Return empty if no congestion
    if len(nonzero_values) == 0:
        return []
    
    threshold = np.percentile(nonzero_values, threshold_percentile)
    
    bottlenecks = []
    for y in range(grid.height):
        for x in range(grid.width):
            if heatmap[y, x] >= threshold:
                bottlenecks.append((x, y))
    
    return bottlenecks


def compute_metrics_summary(exp_data) -> Dict:
    """
    Compute comprehensive metrics summary for an experiment.
    
    Returns:
        Dictionary with all computed metrics
    """
    paths = exp_data.paths
    grid = exp_data.grid
    
    max_timestep = 0
    for path in paths:
        if path:
            max_timestep = max(max_timestep, max(s.timestep for s in path))
    
    conflicts = detect_conflicts(paths)
    bottlenecks = identify_bottlenecks(paths, grid)
    
    # Compute avg_path_length safely
    path_lengths = [len(p) for p in paths if p]
    avg_path_length = np.mean(path_lengths) if path_lengths else 0.0
    
    completed_tasks = count_completed_tasks_from_tasks(exp_data.tasks)

    metrics = {
        'name': exp_data.name,
        'solver': exp_data.config.get('solver', 'Unknown'),
        'num_agents': len(paths),
        'max_timestep': max_timestep,
        'makespan': compute_makespan(paths),
        'sum_of_costs': compute_sum_of_costs(paths),
        'avg_flowtime': compute_flowtime(paths),
        'completed_tasks': completed_tasks,
        'throughput': compute_throughput(paths, max_timestep, exp_data.tasks),
        'num_conflicts': len(conflicts),
        'num_vertex_conflicts': len([c for c in conflicts if c[3] == 'vertex']),
        'num_edge_conflicts': len([c for c in conflicts if c[3] == 'edge']),
        'num_bottlenecks': len(bottlenecks),
        'avg_path_length': avg_path_length,
    }
    
    # Add backwards-compatible aliases
    metrics['flowtime'] = metrics['avg_flowtime']
    metrics['vertex_conflicts'] = metrics['num_vertex_conflicts']
    metrics['edge_conflicts'] = metrics['num_edge_conflicts']
    
    # Add solver stats if available
    if exp_data.solver_stats is not None:
        stats = exp_data.solver_stats
        metrics.update({
            'avg_runtime': stats['runtime'].mean(),
            'max_runtime': stats['runtime'].max(),
            'total_runtime': stats['runtime'].sum(),
            'avg_conflicts_per_step': stats['num_conflicting_pairs'].mean(),
            'total_replans': stats['num_replan'].sum(),
        })
    
    return metrics


def compare_experiments(exp_data_list: List) -> pd.DataFrame:
    """
    Compare multiple experiments and return comparison table.
    
    Args:
        exp_data_list: List of ExperimentData objects
        
    Returns:
        DataFrame with comparison metrics
    """
    metrics_list = []
    
    for exp_data in exp_data_list:
        metrics = compute_metrics_summary(exp_data)
        metrics_list.append(metrics)
    
    df = pd.DataFrame(metrics_list)
    
    # Sort by solver name and num_agents
    if 'solver' in df.columns and 'num_agents' in df.columns:
        df = df.sort_values(['solver', 'num_agents'])
    
    return df


def compute_time_series_metrics(exp_data) -> pd.DataFrame:
    """
    Compute metrics over time (per timestep).
    
    Returns:
        DataFrame with time series metrics
    """
    paths = exp_data.paths
    
    max_timestep = 0
    for path in paths:
        if path:
            max_timestep = max(max_timestep, max(s.timestep for s in path))
    
    time_series = []
    
    for t in range(max_timestep + 1):
        # Count active agents
        active_agents = 0
        locations = set()
        
        for path in paths:
            for state in path:
                if state.timestep == t:
                    active_agents += 1
                    locations.add(state.location)
                    break
        
        time_series.append({
            'timestep': t,
            'active_agents': active_agents,
            'unique_locations': len(locations)
        })
    
    return pd.DataFrame(time_series)


if __name__ == '__main__':
    # Test metrics calculation
    import sys
    sys.path.append('..')
    from utils.data_loader import load_experiment
    
    if len(sys.argv) > 1:
        exp_folder = sys.argv[1]
        data = load_experiment(exp_folder)
        
        print("\nComputing metrics...")
        metrics = compute_metrics_summary(data)
        
        print("\n=== Metrics Summary ===")
        for key, value in metrics.items():
            print(f"{key:25s}: {value}")
        
        print("\n=== Conflicts ===")
        conflicts = detect_conflicts(data.paths)
        print(f"Total conflicts: {len(conflicts)}")
        if conflicts:
            print("First 5 conflicts:")
            for conf in conflicts[:5]:
                print(f"  Agent {conf[0]} vs Agent {conf[1]} at t={conf[2]} ({conf[3]})")
        
        print("\n=== Bottlenecks ===")
        bottlenecks = identify_bottlenecks(data.paths, data.grid)
        print(f"Bottleneck cells: {len(bottlenecks)}")
        if bottlenecks:
            print(f"Locations: {bottlenecks[:10]}")
    else:
        print("Usage: python metrics_calculator.py <experiment_folder>")
