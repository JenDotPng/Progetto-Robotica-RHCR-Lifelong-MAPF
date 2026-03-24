#!/usr/bin/env python3
"""
Batch processing of MAPF experiments for analysis and visualization.

Processamento batch di esperimenti MAPF per analisi e visualizzazione.

Scopo
- individuare automaticamente esperimenti in una directory base;
- filtrare esperimenti per solver o naming;
- generare artefatti di visualizzazione (JSON e HTML statico);
- opzionalmente generare figure per tesi/report;
- costruire un riepilogo aggregato degli esiti del batch.

Flusso operativo
1) discovery delle cartelle esperimento (presenza di paths.txt);
2) applicazione eventuale filtro per solver;
3) caricamento dati esperimento (config, mappa, path, task, solver stats);
4) calcolo metriche principali;
5) export output richiesti (json/html);
6) aggregazione risultati (success/fail + metriche sintetiche).

Input attesi
- directory base esperimenti (default: ../exp);
- per ogni esperimento: paths.txt (obbligatorio per l'animazione);
- file opzionali consigliati: config.txt, tasks.txt, solver.csv;
- mappa .grid risolvibile tramite data_loader nella cartella maps del progetto.

Output prodotti
- per-esperimento:
    - data.json (dataset per viewer)
    - viewer.html (pagina statica)
- batch:
    - lista risultati con stato, errori e metriche principali.

Note operative
- il processamento e parallelizzato con ThreadPoolExecutor;
- errori su un singolo esperimento non bloccano l'intero batch;
- l'export video non e gestito in questo script.

Uso rapido
- python batch_process.py --all
- python batch_process.py --solver PBS ECBS
- python batch_process.py --thesis-figures
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add utils to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from data_loader import discover_experiments, load_experiment
from metrics_calculator import compute_metrics_summary

# Import visualization modules
from visualize_experiment import export_experiment_to_json, export_static_html


class BatchProcessor:
    """Batch process multiple experiments"""
    
    def __init__(self, base_dir: str = '../exp'):
        self.base_dir = base_dir
        self.experiments = []
        self.results = []
    
    def discover_all_experiments(self, solver_filter: List[str] = None):
        """Discover all experiments in base directory"""
        
        print(f"Discovering experiments in {self.base_dir}...")
        all_experiments = discover_experiments(self.base_dir)
        
        # Filter by solver if specified
        if solver_filter:
            self.experiments = [
                exp for exp in all_experiments
                if any(solver.upper() in exp.upper() for solver in solver_filter)
            ]
            print(f"Found {len(self.experiments)} experiments matching solvers: {', '.join(solver_filter)}")
        else:
            self.experiments = all_experiments
            print(f"Found {len(self.experiments)} experiments total")
        
        return self.experiments
    
    def process_experiment(self, exp_path: str, output_dir: str, 
                          export_json: bool = True, 
                          export_html: bool = True) -> Dict:
        """Process a single experiment"""
        
        exp_name = os.path.basename(exp_path)
        result = {
            'name': exp_name,
            'path': exp_path,
            'status': 'pending',
            'outputs': []
        }
        
        try:
            # Load experiment
            exp_data = load_experiment(exp_path)
            metrics = compute_metrics_summary(exp_data)
            
            # Create output directory
            exp_output_dir = os.path.join(output_dir, exp_name)
            os.makedirs(exp_output_dir, exist_ok=True)
            
            # Export JSON
            if export_json:
                json_path = os.path.join(exp_output_dir, 'data.json')
                export_experiment_to_json(exp_data, json_path)
                result['outputs'].append(json_path)
            
            # Export HTML
            if export_html:
                html_path = os.path.join(exp_output_dir, 'viewer.html')
                export_static_html(exp_path, html_path)
                result['outputs'].append(html_path)
            
            result['status'] = 'success'
            result['metrics'] = {
                'makespan': metrics['makespan'],
                'flowtime': metrics['flowtime'],
                'conflicts': metrics['vertex_conflicts'] + metrics['edge_conflicts']
            }
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
        
        return result
    
    def batch_process(self, output_dir: str = 'batch_output',
                     export_json: bool = True,
                     export_html: bool = True,
                     max_workers: int = 4):
        """Process all experiments in parallel"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nProcessing {len(self.experiments)} experiments...")
        print(f"Output directory: {output_dir}")
        print(f"Export options: JSON={export_json}, HTML={export_html}")
        print()
        
        # Process experiments in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.process_experiment,
                    exp_path,
                    output_dir,
                    export_json,
                    export_html
                ): exp_path
                for exp_path in self.experiments
            }
            
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)
                completed += 1
                
                status_icon = '✓' if result['status'] == 'success' else '✗'
                print(f"[{completed}/{len(self.experiments)}] {status_icon} {result['name']}")
                
                if result['status'] == 'failed':
                    print(f"    Error: {result['error']}")
        
        # Generate summary
        self._generate_summary_report(output_dir)
        
        print(f"\n✓ Batch processing complete!")
        print(f"  Successful: {sum(1 for r in self.results if r['status'] == 'success')}")
        print(f"  Failed: {sum(1 for r in self.results if r['status'] == 'failed')}")
        print(f"  Output: {output_dir}/")
    
    def _generate_summary_report(self, output_dir: str):
        """Generate summary report for batch processing"""
        
        summary_path = os.path.join(output_dir, 'batch_summary.html')
        
        successful = [r for r in self.results if r['status'] == 'success']
        failed = [r for r in self.results if r['status'] == 'failed']
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Processing Summary</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
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
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-box {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            text-align: center;
            border-left: 4px solid #e94560;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            color: #16213e;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        .experiment-list {{
            margin: 20px 0;
        }}
        .experiment-item {{
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            background: #f8f9fa;
            border-left: 4px solid #28a745;
        }}
        .experiment-item.failed {{
            border-left-color: #dc3545;
        }}
        .experiment-name {{
            font-weight: bold;
            color: #16213e;
            margin-bottom: 5px;
        }}
        .experiment-metrics {{
            color: #666;
            font-size: 14px;
        }}
        .error-message {{
            color: #dc3545;
            font-size: 14px;
            margin-top: 5px;
        }}
        .outputs {{
            margin-top: 10px;
        }}
        .outputs a {{
            display: inline-block;
            margin-right: 10px;
            color: #007bff;
            text-decoration: none;
            padding: 5px 10px;
            background: white;
            border-radius: 3px;
            font-size: 12px;
        }}
        .outputs a:hover {{
            background: #007bff;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📦 Batch Processing Summary</h1>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">{len(self.results)}</div>
                <div class="stat-label">Total Experiments</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{len(successful)}</div>
                <div class="stat-label">Successful</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{len(failed)}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{len([o for r in successful for o in r.get('outputs', [])])}</div>
                <div class="stat-label">Output Files</div>
            </div>
        </div>
        
        <h2>✓ Successful Experiments ({len(successful)})</h2>
        <div class="experiment-list">
"""
        
        for result in successful:
            metrics = result.get('metrics', {})
            html += f"""
            <div class="experiment-item">
                <div class="experiment-name">{result['name']}</div>
                <div class="experiment-metrics">
                    Makespan: {metrics.get('makespan', 'N/A')} | 
                    Flowtime: {metrics.get('flowtime', 'N/A'):.2f} | 
                    Conflicts: {metrics.get('conflicts', 'N/A')}
                </div>
                <div class="outputs">
"""
            for output in result.get('outputs', []):
                rel_path = os.path.relpath(output, output_dir)
                filename = os.path.basename(output)
                html += f'<a href="{rel_path}">{filename}</a>'
            
            html += """
                </div>
            </div>
"""
        
        if failed:
            html += f"""
        </div>
        
        <h2>✗ Failed Experiments ({len(failed)})</h2>
        <div class="experiment-list">
"""
            for result in failed:
                html += f"""
            <div class="experiment-item failed">
                <div class="experiment-name">{result['name']}</div>
                <div class="error-message">Error: {result.get('error', 'Unknown error')}</div>
            </div>
"""
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"  Summary report: {summary_path}")
    
    def generate_thesis_figures(self, output_dir: str = 'thesis_figures'):
        """Generate publication-quality figures for thesis"""
        
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nGenerating thesis figures...")
        
        # Configure matplotlib for publication quality
        plt.rcParams['figure.dpi'] = 300
        plt.rcParams['savefig.dpi'] = 300
        plt.rcParams['font.size'] = 10
        plt.rcParams['figure.figsize'] = (6.5, 4)  # Standard column width
        plt.rcParams['font.family'] = 'serif'
        
        # Load all experiment data
        exp_data = []
        for exp_path in self.experiments:
            try:
                data = load_experiment(exp_path)
                metrics = compute_metrics_summary(data)
                exp_data.append({
                    'name': os.path.basename(exp_path),
                    'data': data,
                    'metrics': metrics
                })
            except:
                pass
        
        if not exp_data:
            print("No valid experiments found!")
            return
        
        # Group by solver
        solvers = {}
        for exp in exp_data:
            solver = exp['data'].config.get('solver', 'Unknown')
            if solver not in solvers:
                solvers[solver] = []
            solvers[solver].append(exp)
        
        # Generate figures
        self._generate_scalability_figure(solvers, output_dir)
        self._generate_performance_comparison(solvers, output_dir)
        self._generate_window_size_analysis(solvers, output_dir)
        
        print(f"✓ Thesis figures saved to {output_dir}/")
    
    def _generate_scalability_figure(self, solvers: Dict, output_dir: str):
        """Generate scalability analysis figure"""
        
        import matplotlib.pyplot as plt
        import numpy as np
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        
        for solver_name, experiments in solvers.items():
            # Sort by number of agents
            experiments.sort(key=lambda e: len(e['data'].paths))
            
            agents = [len(e['data'].paths) for e in experiments]
            makespans = [e['metrics']['makespan'] for e in experiments]
            runtimes = [e['data'].config.get('runtime', 0) for e in experiments]
            
            ax1.plot(agents, makespans, 'o-', label=solver_name, linewidth=2)
            ax2.plot(agents, runtimes, 's-', label=solver_name, linewidth=2)
        
        ax1.set_xlabel('Number of Agents')
        ax1.set_ylabel('Makespan (timesteps)')
        ax1.set_title('Scalability: Solution Quality')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2.set_xlabel('Number of Agents')
        ax2.set_ylabel('Runtime (seconds)')
        ax2.set_title('Scalability: Computational Cost')
        ax2.set_yscale('log')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'figure_scalability.pdf'), bbox_inches='tight')
        plt.savefig(os.path.join(output_dir, 'figure_scalability.png'), bbox_inches='tight')
        plt.close()
        
        print("  ✓ Scalability figure")
    
    def _generate_performance_comparison(self, solvers: Dict, output_dir: str):
        """Generate solver performance comparison figure"""
        
        import matplotlib.pyplot as plt
        import numpy as np
        
        fig, axes = plt.subplots(2, 2, figsize=(10, 8))
        
        solver_names = list(solvers.keys())
        metrics_to_plot = [
            ('makespan', 'Makespan (timesteps)'),
            ('flowtime', 'Flowtime (timesteps)'),
            ('vertex_conflicts', 'Conflicts'),
            ('runtime', 'Runtime (seconds)')
        ]
        
        for idx, (metric, ylabel) in enumerate(metrics_to_plot):
            ax = axes[idx // 2, idx % 2]
            
            data_by_solver = []
            for solver in solver_names:
                if metric == 'runtime':
                    values = [e['data'].config.get('runtime', 0) for e in solvers[solver]]
                else:
                    values = [e['metrics'].get(metric, 0) for e in solvers[solver]]
                data_by_solver.append(values)
            
            ax.boxplot(data_by_solver, labels=solver_names)
            ax.set_ylabel(ylabel)
            ax.set_title(ylabel)
            ax.grid(axis='y', alpha=0.3)
            
            if metric == 'runtime':
                ax.set_yscale('log')
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'figure_performance_comparison.pdf'), bbox_inches='tight')
        plt.savefig(os.path.join(output_dir, 'figure_performance_comparison.png'), bbox_inches='tight')
        plt.close()
        
        print("  ✓ Performance comparison figure")
    
    def _generate_window_size_analysis(self, solvers: Dict, output_dir: str):
        """Generate window size parameter analysis (for window-based solvers)"""
        
        import matplotlib.pyplot as plt
        import numpy as np
        
        # Filter window-based solvers
        window_solvers = {
            name: exps for name, exps in solvers.items()
            if any('window_size' in e['data'].config for e in exps)
        }
        
        if not window_solvers:
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        
        for solver_name, experiments in window_solvers.items():
            # Group by window size
            window_data = {}
            for exp in experiments:
                w = exp['data'].config.get('window_size')
                if w is not None:
                    if w not in window_data:
                        window_data[w] = []
                    window_data[w].append(exp)
            
            if not window_data:
                continue
            
            windows = sorted(window_data.keys())
            makespans = [np.mean([e['metrics']['makespan'] for e in window_data[w]]) 
                        for w in windows]
            success_rates = [len(window_data[w]) / len(experiments) for w in windows]
            
            ax1.plot(windows, makespans, 'o-', label=solver_name, linewidth=2)
            ax2.plot(windows, success_rates, 's-', label=solver_name, linewidth=2)
        
        ax1.set_xlabel('Window Size')
        ax1.set_ylabel('Average Makespan')
        ax1.set_title('Window Size vs. Solution Quality')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2.set_xlabel('Window Size')
        ax2.set_ylabel('Success Rate')
        ax2.set_title('Window Size vs. Success Rate')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim([0, 1.1])
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'figure_window_analysis.pdf'), bbox_inches='tight')
        plt.savefig(os.path.join(output_dir, 'figure_window_analysis.png'), bbox_inches='tight')
        plt.close()
        
        print("  ✓ Window size analysis figure")


def main():
    parser = argparse.ArgumentParser(description='Batch process MAPF experiments')
    parser.add_argument('--base-dir', default='../exp',
                       help='Base directory containing experiments')
    parser.add_argument('--all', action='store_true',
                       help='Process all experiments')
    parser.add_argument('--solver', nargs='+',
                       help='Process only these solvers (e.g., PBS ECBS WHCA)')
    parser.add_argument('--output-dir', default='batch_output',
                       help='Output directory for processed experiments')
    parser.add_argument('--export-json', action='store_true', default=True,
                       help='Export JSON data files')
    parser.add_argument('--export-html', action='store_true', default=True,
                       help='Export standalone HTML viewers')
    parser.add_argument('--thesis-figures', action='store_true',
                       help='Generate publication-quality figures for thesis')
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of parallel workers')
    
    args = parser.parse_args()
    
    # Create batch processor
    processor = BatchProcessor(args.base_dir)
    
    # Discover experiments
    if args.all or args.solver:
        processor.discover_all_experiments(solver_filter=args.solver)
    else:
        print("Error: Specify --all or --solver to select experiments")
        return 1
    
    if not processor.experiments:
        print("No experiments found!")
        return 1
    
    # Generate thesis figures
    if args.thesis_figures:
        processor.generate_thesis_figures()
        return 0
    
    # Batch process
    processor.batch_process(
        output_dir=args.output_dir,
        export_json=args.export_json,
        export_html=args.export_html,
        max_workers=args.workers
    )
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
