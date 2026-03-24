#!/usr/bin/env python3
"""
compare_experiments.py

Scopo
- Confrontare in modo sistematico piu esperimenti MAPF e produrre un report
    comparativo con tabella metriche, grafici e sintesi testuale.

Funzionalita principali
- Caricamento di directory esperimento tramite utilita `data_loader`.
- Calcolo metriche aggregate tramite `metrics_calculator`.
- Generazione tabella comparativa (DataFrame pandas) con:
    - solver, numero agenti, makespan, flowtime, throughput,
        runtime e conflitti (vertex/edge/total).
- Produzione grafici PNG ad alta risoluzione (300 DPI):
    - makespan, flowtime, runtime (scala log), conflitti.
- Generazione radar chart multi-metrica quando il numero di esperimenti e piccolo.
- Esportazione report HTML finale con:
    - summary best-performer,
    - tabella completa,
    - grafici incorporati,
    - dettaglio per esperimento.
- Supporto alla selezione automatica delle run via `--auto-detect` e `--base-dir`.

Input attesi
- Una o piu cartelle esperimento contenenti dati compatibili con il visualizer
    (ad es. `paths.txt`, `config.txt`, mappa e metriche derivate).
- In alternativa, una lista di solver da auto-rilevare in una directory base.

Output attesi
- File HTML di confronto (default: `comparison_report.html`).
- Cartella grafici (default: `comparison_plots/`) con immagini PNG.

Esempi di utilizzo
- Confronto manuale:
    python compare_experiments.py exp1 exp2 exp3 --output comparison_report.html

- Auto-detect per solver:
    python compare_experiments.py --auto-detect PBS ECBS WHCA --base-dir ../exp

Note operative
- Il backend matplotlib e impostato su `Agg` per esecuzione non interattiva
    (batch/server/headless).
- Lo script stampa a terminale lo stato di caricamento e un riepilogo finale.
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from data_loader import load_experiment, discover_experiments
from metrics_calculator import compute_metrics_summary


class ExperimentComparison:
    """Compare multiple experiments and generate comparative analysis"""
    
    def __init__(self, experiment_paths: List[str]):
        self.experiments = []
        self.metrics = []
        
        print("Loading experiments...")
        for path in experiment_paths:
            try:
                exp_data = load_experiment(path)
                exp_metrics = compute_metrics_summary(exp_data)
                
                self.experiments.append({
                    'path': path,
                    'name': os.path.basename(path),
                    'data': exp_data,
                    'metrics': exp_metrics
                })
                
                print(f"  ✓ {os.path.basename(path)}")
            except Exception as e:
                print(f"  ✗ {os.path.basename(path)}: {e}")
        
        print(f"\nLoaded {len(self.experiments)} experiments")
    
    def generate_comparison_table(self) -> pd.DataFrame:
        """Generate comparison table with key metrics"""
        
        data = []
        for exp in self.experiments:
            metrics = exp['metrics']
            config = exp['data'].config
            
            row = {
                'Experiment': exp['name'],
                'Solver': config.get('solver', 'Unknown'),
                'Agents': len(exp['data'].paths),
                'Makespan': metrics['makespan'],
                'Flowtime': metrics['flowtime'],
                'Throughput': metrics['throughput'],
                'Runtime (s)': config.get('runtime', 0),
                'Vertex Conflicts': metrics['vertex_conflicts'],
                'Edge Conflicts': metrics['edge_conflicts'],
                'Total Conflicts': metrics['vertex_conflicts'] + metrics['edge_conflicts']
            }
            
            # Add solver-specific parameters
            if 'window_size' in config:
                row['Window Size'] = config['window_size']
            if 'weight' in config:
                row['Weight (ω)'] = config['weight']
            
            data.append(row)
        
        return pd.DataFrame(data)
    
    def generate_performance_plots(self, output_dir: str):
        """Generate comparative performance plots"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract data for plotting
        names = [exp['name'] for exp in self.experiments]
        makespans = [exp['metrics']['makespan'] for exp in self.experiments]
        flowtimes = [exp['metrics']['flowtime'] for exp in self.experiments]
        runtimes = [exp['data'].config.get('runtime', 0) for exp in self.experiments]
        conflicts = [
            exp['metrics']['vertex_conflicts'] + exp['metrics']['edge_conflicts']
            for exp in self.experiments
        ]
        
        # Color scheme
        colors = plt.cm.Set3(np.linspace(0, 1, len(self.experiments)))
        
        # 1. Makespan comparison
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(range(len(names)), makespans, color=colors)
        ax.set_xlabel('Experiment', fontsize=12)
        ax.set_ylabel('Makespan (timesteps)', fontsize=12)
        ax.set_title('Makespan Comparison', fontsize=14, fontweight='bold')
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for i, (bar, val) in enumerate(zip(bars, makespans)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                   f'{val}', ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'comparison_makespan.png'), dpi=300)
        plt.close()
        
        # 2. Flowtime comparison
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(range(len(names)), flowtimes, color=colors)
        ax.set_xlabel('Experiment', fontsize=12)
        ax.set_ylabel('Flowtime (timesteps)', fontsize=12)
        ax.set_title('Flowtime Comparison', fontsize=14, fontweight='bold')
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.grid(axis='y', alpha=0.3)
        
        for i, (bar, val) in enumerate(zip(bars, flowtimes)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                   f'{val:.0f}', ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'comparison_flowtime.png'), dpi=300)
        plt.close()
        
        # 3. Runtime comparison
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(range(len(names)), runtimes, color=colors)
        ax.set_xlabel('Experiment', fontsize=12)
        ax.set_ylabel('Runtime (seconds)', fontsize=12)
        ax.set_title('Computational Runtime Comparison', fontsize=14, fontweight='bold')
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.grid(axis='y', alpha=0.3)
        ax.set_yscale('log')  # Log scale for runtime
        
        for i, (bar, val) in enumerate(zip(bars, runtimes)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                   f'{val:.3f}s', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'comparison_runtime.png'), dpi=300)
        plt.close()
        
        # 4. Conflicts comparison
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(range(len(names)), conflicts, color=colors)
        ax.set_xlabel('Experiment', fontsize=12)
        ax.set_ylabel('Total Conflicts', fontsize=12)
        ax.set_title('Conflict Count Comparison', fontsize=14, fontweight='bold')
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.grid(axis='y', alpha=0.3)
        
        for i, (bar, val) in enumerate(zip(bars, conflicts)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                   f'{val}', ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'comparison_conflicts.png'), dpi=300)
        plt.close()
        
        # 5. Multi-metric radar chart
        if len(self.experiments) <= 5:  # Only for small comparisons
            self._generate_radar_chart(output_dir, colors)
        
        print(f"Generated performance plots in {output_dir}/")
    
    def _generate_radar_chart(self, output_dir: str, colors):
        """Generate radar chart for multi-dimensional comparison"""
        
        # Normalize metrics for radar chart
        categories = ['Makespan', 'Flowtime', 'Runtime', 'Conflicts', 'Throughput']
        
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
        
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]  # Complete the circle
        
        for i, exp in enumerate(self.experiments):
            metrics = exp['metrics']
            config = exp['data'].config
            
            values = [
                metrics['makespan'],
                metrics['flowtime'],
                config.get('runtime', 0) * 1000,  # Scale runtime
                metrics['vertex_conflicts'] + metrics['edge_conflicts'],
                metrics['throughput'] * 10000  # Scale throughput
            ]
            
            # Normalize to 0-1 range
            max_values = [
                max(e['metrics']['makespan'] for e in self.experiments),
                max(e['metrics']['flowtime'] for e in self.experiments),
                max(e['data'].config.get('runtime', 0) for e in self.experiments) * 1000,
                max(e['metrics']['vertex_conflicts'] + e['metrics']['edge_conflicts'] 
                    for e in self.experiments),
                max(e['metrics']['throughput'] for e in self.experiments) * 10000
            ]
            
            normalized = [v / m if m > 0 else 0 for v, m in zip(values, max_values)]
            normalized += normalized[:1]
            
            ax.plot(angles, normalized, 'o-', linewidth=2, label=exp['name'], color=colors[i])
            ax.fill(angles, normalized, alpha=0.15, color=colors[i])
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, 1)
        ax.set_title('Multi-Metric Performance Comparison', size=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax.grid(True)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'comparison_radar.png'), dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_html_report(self, output_path: str, plots_dir: str):
        """Generate comprehensive HTML comparison report"""
        
        table_df = self.generate_comparison_table()
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MAPF Experiment Comparison</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #e94560;
            border-bottom: 3px solid #e94560;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #16213e;
            margin-top: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #16213e;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .best {{
            background-color: #d4edda;
            font-weight: bold;
        }}
        .worst {{
            background-color: #f8d7da;
        }}
        .plot-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .plot-item {{
            text-align: center;
        }}
        .plot-item img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .summary {{
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .summary h3 {{
            margin-top: 0;
            color: #1976d2;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 MAPF Experiment Comparison Report</h1>
        <p><strong>Generated:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Experiments Compared:</strong> {len(self.experiments)}</p>
        
        <div class="summary">
            <h3>Summary</h3>
            {self._generate_summary_html()}
        </div>
        
        <h2>📊 Comparison Table</h2>
        {table_df.to_html(index=False, classes='comparison-table', border=0)}
        
        <h2>📈 Performance Plots</h2>
        <div class="plot-grid">
"""
        
        # Add plots
        plot_files = [
            'comparison_makespan.png',
            'comparison_flowtime.png',
            'comparison_runtime.png',
            'comparison_conflicts.png'
        ]
        
        if os.path.exists(os.path.join(plots_dir, 'comparison_radar.png')):
            plot_files.append('comparison_radar.png')
        
        for plot_file in plot_files:
            plot_path = os.path.join(plots_dir, plot_file)
            if os.path.exists(plot_path):
                html += f"""
            <div class="plot-item">
                <img src="{plot_file}" alt="{plot_file}">
            </div>
"""
        
        html += """
        </div>
        
        <h2>🔍 Detailed Analysis</h2>
"""
        
        # Add detailed experiment info
        for exp in self.experiments:
            html += self._generate_experiment_detail_html(exp)
        
        html += """
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"Generated HTML report: {output_path}")
    
    def _generate_summary_html(self) -> str:
        """Generate summary statistics HTML"""
        
        if not self.experiments:
            return "<p>No experiments to compare.</p>"
        
        # Find best/worst performers
        best_makespan = min(self.experiments, key=lambda e: e['metrics']['makespan'])
        best_flowtime = min(self.experiments, key=lambda e: e['metrics']['flowtime'])
        best_runtime = min(self.experiments, key=lambda e: e['data'].config.get('runtime', float('inf')))
        best_conflicts = min(self.experiments, 
            key=lambda e: e['metrics']['vertex_conflicts'] + e['metrics']['edge_conflicts'])
        
        html = f"""
<ul>
    <li><strong>Best Makespan:</strong> {best_makespan['name']} ({best_makespan['metrics']['makespan']} timesteps)</li>
    <li><strong>Best Flowtime:</strong> {best_flowtime['name']} ({best_flowtime['metrics']['flowtime']:.2f} timesteps)</li>
    <li><strong>Fastest Runtime:</strong> {best_runtime['name']} ({best_runtime['data'].config.get('runtime', 0):.3f}s)</li>
    <li><strong>Fewest Conflicts:</strong> {best_conflicts['name']} 
        ({best_conflicts['metrics']['vertex_conflicts'] + best_conflicts['metrics']['edge_conflicts']} total)</li>
</ul>
"""
        return html
    
    def _generate_experiment_detail_html(self, exp: Dict[str, Any]) -> str:
        """Generate detailed HTML for single experiment"""
        
        metrics = exp['metrics']
        config = exp['data'].config
        
        html = f"""
<div class="experiment-detail" style="border-left: 4px solid #e94560; padding-left: 15px; margin: 20px 0;">
    <h3>{exp['name']}</h3>
    <p><strong>Solver:</strong> {config.get('solver', 'Unknown')}</p>
    <p><strong>Agents:</strong> {len(exp['data'].paths)}</p>
    <p><strong>Grid:</strong> {exp['data'].grid.width} × {exp['data'].grid.height}</p>
    <p><strong>Makespan:</strong> {metrics['makespan']} timesteps</p>
    <p><strong>Flowtime:</strong> {metrics['flowtime']:.2f} timesteps</p>
    <p><strong>Runtime:</strong> {config.get('runtime', 0):.3f} seconds</p>
    <p><strong>Conflicts:</strong> {metrics['vertex_conflicts']} vertex + {metrics['edge_conflicts']} edge 
       = {metrics['vertex_conflicts'] + metrics['edge_conflicts']} total</p>
</div>
"""
        return html


def main():
    parser = argparse.ArgumentParser(description='Compare MAPF experiments')
    parser.add_argument('experiments', nargs='*', help='Paths to experiment directories')
    parser.add_argument('--output', '-o', default='comparison_report.html',
                       help='Output HTML file path')
    parser.add_argument('--plots-dir', default='comparison_plots',
                       help='Directory to save plots')
    parser.add_argument('--auto-detect', nargs='+',
                       help='Auto-detect experiments for these solvers (e.g., PBS ECBS WHCA)')
    parser.add_argument('--base-dir', default='../exp',
                       help='Base directory for experiments (used with --auto-detect)')
    
    args = parser.parse_args()
    
    # Determine experiment paths
    experiment_paths = args.experiments
    
    if args.auto_detect:
        print(f"Auto-detecting experiments for solvers: {', '.join(args.auto_detect)}")
        all_experiments = discover_experiments(args.base_dir)
        
        # Filter experiments by solver name
        experiment_paths = []
        for solver in args.auto_detect:
            matching = [exp for exp in all_experiments if solver.upper() in exp.upper()]
            experiment_paths.extend(matching)
        
        print(f"Found {len(experiment_paths)} matching experiments")
    
    if not experiment_paths:
        print("Error: No experiments specified!")
        print("Usage:")
        print("  python compare_experiments.py exp1 exp2 [exp3 ...]")
        print("  python compare_experiments.py --auto-detect PBS ECBS WHCA")
        return 1
    
    # Create comparison
    comparison = ExperimentComparison(experiment_paths)
    
    if not comparison.experiments:
        print("Error: No valid experiments loaded!")
        return 1
    
    # Generate outputs
    comparison.generate_performance_plots(args.plots_dir)
    comparison.generate_html_report(args.output, args.plots_dir)
    
    print(f"\n✓ Comparison complete!")
    print(f"  Report: {args.output}")
    print(f"  Plots: {args.plots_dir}/")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
