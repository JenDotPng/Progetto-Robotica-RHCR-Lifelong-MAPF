"""
Stress test multi-solver su mappa warehouse in scenario SORTING.

Scopo:
- valutare la scalabilita dei solver (PBS/ECBS/WHCA) al crescere degli agenti;
- usare una configurazione temporale piu lunga (simulation_time elevato) per stress test prolungati;
- confrontare robustezza e prestazioni su mappa warehouse ottimizzata.

Funzionamento:
1) prepara i comandi lifelong.exe con mappa warehouse_optimized e parametri h/w dedicati;
2) esegue i test per ciascuna combinazione seed/agenti/solver;
3) acquisisce metriche da solver.csv e valuta stato Success/Fail/Timeout;
4) pulisce la cache euristica dopo ogni esecuzione;
5) salva report CSV aggregati e grafici di runtime/throughput.

Modalita di utilizzo:
- esecuzione completa: python warehouse_final_stress_test.py
- solo rigenerazione report e grafici:
    python warehouse_final_stress_test.py --report-only --output-base <cartella_output>

Output principali:
- final_report.csv
- final_report_summary.csv
- chart_runtime.png
- chart_throughput.png
"""

import argparse
import subprocess
import os
import pandas as pd
import matplotlib.pyplot as plt
import time

def cleanup_heuristics_cache(map_path, consider_rotation=False):
    """
    Cancella la tabella euristica associata a una mappa per forzare la rigenerazione.
    
    Args:
        map_path: Percorso del file .grid (es. "maps/warehouse_map.grid")
        consider_rotation: Se True, cancella anche la tabella con rotazioni
    """
    # Estrai il nome base della mappa (senza estensione)
    map_name = os.path.splitext(map_path)[0]
    
    # Costruisci i nomi dei file euristica
    heuristics_files = [f"{map_name}_heuristics_table.txt"]
    if consider_rotation:
        heuristics_files.append(f"{map_name}_rotation_heuristics_table.txt")
    
    for heuristics_file in heuristics_files:
        if os.path.exists(heuristics_file):
            try:
                os.remove(heuristics_file)
                print(f"[DEBUG] ✓ Cancellata cache euristica: {heuristics_file}")
            except Exception as e:
                print(f"[DEBUG] ✗ Errore cancellazione {heuristics_file}: {e}")
        else:
            print(f"[DEBUG] · Cache euristica non trovata (già pulita): {heuristics_file}")



# Usa seaborn se disponibile, altrimenti fallback matplotlib.
try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


def count_completed_tasks(tasks_file):
    """Conta i task completati (tempo > 0) dal file tasks.txt."""
    if not os.path.exists(tasks_file):
        return 0

    total = 0
    with open(tasks_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Prima riga: numero agenti.
    for line in lines[1:]:
        entries = [entry for entry in line.strip().split(";") if entry]
        for entry in entries:
            cols = entry.split(",")
            if len(cols) < 2:
                continue
            try:
                timestep = int(cols[1])
            except ValueError:
                continue
            if timestep > 0:
                total += 1
    return total

def run_super_test():
    EXE = r".\build\Release\lifelong.exe"

    # Array di agenti: confronto PBS/ECBS/WHCA.
    AGENTS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]

    # Array di agenti: confronto ECBS per k=1100-1500.
    # AGENTS = [1100, 1200, 1300, 1400, 1500]
    
    SEEDS = [42]

    TIME = 3000
    CUTOFF = 240
    PROCESS_TIMEOUT = 300

    OUTPUT_BASE = "exp/stress_test_warehouse_optimized/ECBS_comparison_k_1100-1500"  
    MAP = "maps/warehouse_optimized.grid" 
    

    solver_cfg = {
    "PBS":  {"extra": "",                    "w": 15, "h": 5},
    "ECBS": {"extra": "--suboptimal_bound 2.0", "w": 15, "h": 5},
    "WHCA": {"extra": "",                    "w": 30, "h": 5},
    }

    all_data = []

    if not os.path.exists(OUTPUT_BASE):
        os.makedirs(OUTPUT_BASE)

    for seed in SEEDS:
        for k in AGENTS:
            #for solver, extra in solvers.items():
            for solver, cfg in solver_cfg.items():
                w = cfg["w"]
                h = cfg["h"]
                extra = cfg["extra"]
                run_id = f"{solver}_k{k}_seed{seed}_w{w}_h{h}"
                out_dir = os.path.join(OUTPUT_BASE, run_id)
                print(f"\n[TEST] Solver: {solver} | Agenti: {k} | Seed: {seed}...")

                cmd = [
                    EXE, "-m", MAP, "-k", str(k),
                    "--scenario", "SORTING",
                    "--output", out_dir,
                    "--solver", solver,
                    "--simulation_time", str(TIME),
                    "--seed", str(seed),
                    "--cutoffTime", str(CUTOFF),
                    "--planning_window", str(w),   # w: planning horizon (w >= h)
                    "--simulation_window", str(h)  # h: replanning period
                ]
                if extra:
                    cmd.extend(extra.split())

                print(f"Comando: {' '.join(cmd)}")
                print(f"Eseguibile esiste: {os.path.exists(EXE)}")
                print(f"Mappa esiste: {os.path.exists(MAP)}")

                start_t = time.time()
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=PROCESS_TIMEOUT,
                        check=True,
                    )
                    print(f"Output: {result.stdout[-200:] if result.stdout else 'Nessun output'}")
                    
                    csv_file = os.path.join(out_dir, "solver.csv")
                    if os.path.exists(csv_file):
                        # solver.csv e senza header.
                        df = pd.read_csv(csv_file, header=None)
                        tasks_file = os.path.join(out_dir, "tasks.txt")
                        throughput = count_completed_tasks(tasks_file)
                        avg_runtime = pd.to_numeric(df.iloc[:, 0], errors="coerce").mean()
                        robust_success = throughput > 0 and pd.notna(avg_runtime)

                        if not robust_success:
                            print(
                                f"!!! {solver} RISULTATO NON ROBUSTO con {k} agenti e seed {seed} "
                                f"(throughput={throughput}, avg_runtime={avg_runtime})"
                            )
                        
                        all_data.append({
                            "Seed": seed,
                            "Solver": solver,
                            "Agenti": k,
                            "Runtime": float(avg_runtime) if pd.notna(avg_runtime) else 0.0,
                            "Throughput": throughput,
                            "Status": "Success" if robust_success else "Fail"
                        })
                    else:
                        raise FileNotFoundError("CSV non generato")

                except subprocess.CalledProcessError as e:
                    print(f"!!! {solver} FALLITO con {k} agenti e seed {seed}")
                    print(f"Return code: {e.returncode}")
                    print(f"Stdout: {e.stdout[-500:] if e.stdout else 'Nessun output'}")
                    print(f"Stderr: {e.stderr[-500:] if e.stderr else 'Nessun stderr'}")
                    all_data.append({
                        "Seed": seed,
                        "Solver": solver,
                        "Agenti": k,
                        "Runtime": 0,
                        "Throughput": 0,
                        "Status": "Fail"
                    })
                except subprocess.TimeoutExpired:
                    print(f"!!! {solver} TIMEOUT con {k} agenti e seed {seed} (>{PROCESS_TIMEOUT}s)")
                    all_data.append({
                        "Seed": seed,
                        "Solver": solver,
                        "Agenti": k,
                        "Runtime": 0,
                        "Throughput": 0,
                        "Status": "Timeout"
                    })
                except Exception as e:
                    print(f"!!! {solver} ERRORE con {k} agenti e seed {seed}: {str(e)[:200]}")
                    all_data.append({
                        "Seed": seed,
                        "Solver": solver,
                        "Agenti": k,
                        "Runtime": 0,
                        "Throughput": 0,
                        "Status": "Fail"
                    })

                finally:
                    print(f"\n[CLEANUP] Pulizia cache per {MAP}...")
                    cleanup_heuristics_cache(MAP, consider_rotation=False)  # Forza ricostruzione coerente tra run.
                    print("")

    results_df = pd.DataFrame(all_data)
    save_reports_and_charts(results_df, OUTPUT_BASE)


def save_reports_and_charts(results_df, output_base):
    results_df.to_csv(f"{output_base}/final_report.csv", index=False)

    summary_df = (
        results_df
        .groupby(["Solver", "Agenti"], as_index=False)
        .agg(
            Runs=("Status", "count"),
            Success_Rate=("Status", lambda s: (s == "Success").mean()),
            Runtime_Mean=("Runtime", "mean"),
            Runtime_Std=("Runtime", "std"),
            Throughput_Mean=("Throughput", "mean"),
            Throughput_Std=("Throughput", "std")
        )
    )
    summary_df["Runtime_Std"] = summary_df["Runtime_Std"].fillna(0.0)
    summary_df["Throughput_Std"] = summary_df["Throughput_Std"].fillna(0.0)
    summary_df = summary_df.sort_values(["Agenti", "Solver"])
    summary_df.to_csv(f"{output_base}/final_report_summary.csv", index=False)
    
    if HAS_SEABORN:
        sns.set_theme(style="whitegrid")
    
    plt.figure(figsize=(10,6))
    success_data = results_df[results_df['Status']=='Success']
    
    if HAS_SEABORN:
        sns.lineplot(data=success_data, x="Agenti", y="Runtime", hue="Solver", marker="o", linewidth=2)
    else:
        for s in results_df["Solver"].unique():
            s_data = success_data[success_data["Solver"] == s]
            plt.plot(s_data["Agenti"], s_data["Runtime"], marker='o', label=s)
        plt.legend()

    plt.title("Scalabilità Computazionale: Runtime vs Numero Agenti")
    plt.ylabel("Tempo di calcolo medio (ms)")
    plt.xlabel("Numero Agenti (k)")
    plt.savefig(f"{output_base}/chart_runtime.png")

    plt.figure(figsize=(10,6))
    if HAS_SEABORN:
        sns.barplot(data=results_df, x="Agenti", y="Throughput", hue="Solver")
    else:
        # Con run multipli per lo stesso k/solver aggrega prima della visualizzazione.
        results_df.pivot_table(
            index='Agenti',
            columns='Solver',
            values='Throughput',
            aggfunc='mean'
        ).plot(kind='bar', ax=plt.gca())
    
    plt.title("Analisi Throughput: Task completati nel tempo T")
    plt.ylabel("Numero Task")
    plt.savefig(f"{output_base}/chart_throughput.png")

    print(f"\nConfronto completato con successo!")
    print(f"I file sono stati salvati in: {os.path.abspath(output_base)}")
    print(f"Report aggregato multi-seed salvato in: {os.path.abspath(output_base)}/final_report_summary.csv")


def parse_args():
    parser = argparse.ArgumentParser(description="Stress test SORTING con modalita report-only")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Rigenera summary e grafici dal final_report.csv esistente senza rilanciare i test.",
    )
    parser.add_argument(
        "--output-base",
        default="exp/sorting_map/final_stress_test/sorting_k_50-1200_h5_w10",
        help="Cartella output contenente final_report.csv.",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    if args.report_only:
        report_file = os.path.join(args.output_base, "final_report.csv")
        if not os.path.exists(report_file):
            raise FileNotFoundError(f"Report non trovato: {report_file}")
        df_report = pd.read_csv(report_file)
        save_reports_and_charts(df_report, args.output_base)
    else:
        run_super_test()