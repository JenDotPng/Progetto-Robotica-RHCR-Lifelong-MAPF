"""
Confronto normalizzato: throughput e runtime per agente e per cella
=============================================================================
Legge i dati esistenti di exp/sorting/ e exp/movingAI_warehouse_final/
e produce metriche scalate: throughput/agente, runtime/agente, throughput/densità

Mappe:
  sorting_map.grid            → exp/sorting/
  warehouse_map-10-20-10-2-2  → exp/movingAI_warehouse_final/

Output: exp/analysis_normalized/ (CSV + grafici)

Uso:
  python3 analyze_normalized_metrics.py
"""

import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Configurazione cartelle risultati ─────────────────────────────────────────
EXP_DIRS = {
    "sorting": {
        "base":    "../exp/sorting",
        "map":     "../maps/sorting_map.grid",
        "solvers": ["PBS", "ECBS", "WHCA"],   # LRA escluso (sempre fail)
        "agents":  [20, 50, 80, 100, 120],
    },
    "warehouse": {
        "base":    "../exp/movingAI_warehouse_final",
        "map":     "../maps/warehouse_map-10-20-10-2-2.grid",
        "solvers": ["WHCA", "ECBS"],
        "agents":  [20, 50, 80, 100, 120],
    },
}

OUTPUT_DIR = "../exp/analysis_normalized"

# Colonne solver.csv (PBS/ECBS/WHCA):
# 0:runtime, 1:HL_exp, 2:HL_gen, 3:LL_exp, 4:LL_gen,
# 5:flowtime, 6:min_flowtime, 7:avg_path, 8:collisions, 9:timestep, 10:k, 11:seed
COL_RUNTIME    = 0
COL_COLLISIONS = 8
COL_TIMESTEP   = 9
COL_K          = 10


# ── Parsing mappa RHCR (formato custom) ───────────────────────────────────────
def parse_grid(map_path: str) -> dict:
    """Ritorna informazioni sulle celle della mappa RHCR."""
    with open(map_path) as f:
        f.readline()                       # "Grid size (x,y)"
        dims = f.readline().strip().split(",")
        x_size, y_size = int(dims[0]), int(dims[1])
        f.readline()                       # header CSV
        counts = {}
        for line in f:
            parts = line.strip().split(",")
            if len(parts) > 1:
                cell_type = parts[1]
                counts[cell_type] = counts.get(cell_type, 0) + 1

    total      = x_size * y_size
    n_obstacle = counts.get("Obstacle", 0)
    n_free     = total - n_obstacle
    return {
        "x_size":     x_size,
        "y_size":     y_size,
        "total":      total,
        "n_obstacle": n_obstacle,
        "n_free":     n_free,
        "types":      counts,
        "obstacle_pct": n_obstacle / total * 100,
    }


# ── Caricamento dati solver.csv ───────────────────────────────────────────────
def load_experiment(csv_path: str) -> pd.DataFrame | None:
    """Carica un solver.csv e ritorna il DataFrame, None se mancante/vuoto."""
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path, header=None)
        if df.empty:
            return None
        return df
    except Exception:
        return None


def collect_data(exp_dirs: dict, grid_info: dict) -> pd.DataFrame:
    """Raccoglie tutti i dati di solver.csv dalle cartelle degli esperimenti."""
    records = []

    for map_name, cfg in exp_dirs.items():
        base    = cfg["base"]
        g_info  = grid_info[map_name]

        for solver in cfg["solvers"]:
            for k in cfg["agents"]:
                run_dir  = os.path.join(base, f"{solver}_k{k}")
                csv_path = os.path.join(run_dir, "solver.csv")

                df = load_experiment(csv_path)
                if df is None:
                    status = "missing"
                    throughput     = 0
                    avg_runtime    = None
                    avg_collisions = None
                    flowtime       = None
                else:
                    status         = "success"
                    throughput     = len(df)
                    avg_runtime    = df.iloc[:, COL_RUNTIME].mean() * 1000   # → ms
                    avg_collisions = df.iloc[:, COL_COLLISIONS].mean()
                    flowtime       = df.iloc[:, 5].mean() if df.shape[1] > 5 else None

                # Metriche normalizzate
                density = k / g_info["n_free"]   # agenti per cella libera

                records.append({
                    "map":            map_name,
                    "solver":         solver,
                    "k":              k,
                    "status":         status,
                    "throughput":     throughput,
                    "avg_runtime_ms": avg_runtime,
                    "avg_collisions": avg_collisions,
                    "avg_flowtime":   flowtime,
                    # Normalizzazioni
                    "thr_per_agent":  throughput / k if throughput else 0,
                    "rt_per_agent":   avg_runtime / k if avg_runtime else None,
                    "density":        density,
                    "thr_per_density":throughput / density if (throughput and density) else 0,
                    "n_free":         g_info["n_free"],
                    "obstacle_pct":   g_info["obstacle_pct"],
                })

    return pd.DataFrame(records)


# ── Grafici ───────────────────────────────────────────────────────────────────
def plot_normalized(df: pd.DataFrame, out_dir: str):
    plt.rcParams.update({"font.size": 9, "figure.dpi": 150})
    colors = {"sorting": "#2196F3", "warehouse": "#FF5722"}
    markers = {"PBS": "o", "ECBS": "s", "WHCA": "^"}
    solvers_common = ["WHCA"]   # solver presente su ENTRAMBE le mappe

    ok = df[df["status"] == "success"].copy()

    # ── Figure 1: throughput assoluto vs k ────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, metric, ylabel in zip(
        axes,
        ["throughput",    "avg_runtime_ms"],
        ["Throughput (n. finestre pianificate)", "Runtime medio/finestra (ms)"],
    ):
        for map_name, grp in ok.groupby("map"):
            for solver, sgrp in grp.groupby("solver"):
                ax.plot(sgrp["k"], sgrp[metric],
                        color=colors.get(map_name, "gray"),
                        marker=markers.get(solver, "x"),
                        label=f"{map_name} / {solver}",
                        linewidth=1.5)
        ax.set_xlabel("Numero agenti (k)")
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Throughput e Runtime assoluti", fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "fig1_absolute.png"), bbox_inches="tight")
    plt.close()
    print("  [plot] fig1_absolute.png")

    # ── Figure 2: throughput/agente e runtime/agente ──────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, metric, ylabel in zip(
        axes,
        ["thr_per_agent", "rt_per_agent"],
        ["Throughput / agente", "Runtime medio/finestra per agente (ms)"],
    ):
        for map_name, grp in ok.groupby("map"):
            for solver, sgrp in grp.groupby("solver"):
                if metric == "rt_per_agent" and sgrp[metric].isna().all():
                    continue
                ax.plot(sgrp["k"], sgrp[metric],
                        color=colors.get(map_name, "gray"),
                        marker=markers.get(solver, "x"),
                        label=f"{map_name} / {solver}",
                        linewidth=1.5)
        ax.set_xlabel("Numero agenti (k)")
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Metriche normalizzate per agente", fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "fig2_per_agent.png"), bbox_inches="tight")
    plt.close()
    print("  [plot] fig2_per_agent.png")

    # ── Figure 3: throughput per densità agenti ───────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 4))
    for map_name, grp in ok.groupby("map"):
        for solver, sgrp in grp.groupby("solver"):
            ax.plot(sgrp["density"] * 100, sgrp["thr_per_density"],
                    color=colors.get(map_name, "gray"),
                    marker=markers.get(solver, "x"),
                    label=f"{map_name} / {solver}",
                    linewidth=1.5)
    ax.set_xlabel("Densità agenti (% celle libere occupate)")
    ax.set_ylabel("Throughput / densità")
    ax.set_title("Throughput normalizzato per densità\n"
                 "(mostra se la geometria o la densità domina la performance)",
                 fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "fig3_per_density.png"), bbox_inches="tight")
    plt.close()
    print("  [plot] fig3_per_density.png")

    # ── Figure 4: confronto diretto WHCA su entrambe le mappe ────────────────
    whca = ok[ok["solver"] == "WHCA"]
    if not whca.empty:
        fig, axes = plt.subplots(1, 3, figsize=(13, 4))
        metrics = [
            ("throughput",    "Throughput (n. finestre)"),
            ("thr_per_agent", "Throughput / agente"),
            ("avg_collisions","Collisioni medie/finestra"),
        ]
        for ax, (metric, ylabel) in zip(axes, metrics):
            for map_name, grp in whca.groupby("map"):
                ax.plot(grp["k"], grp[metric],
                        color=colors.get(map_name, "gray"),
                        marker="^", label=map_name, linewidth=2)
            ax.set_xlabel("k")
            ax.set_ylabel(ylabel)
            ax.set_title(f"WHCA: {ylabel}")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
        fig.suptitle("WHCA — Confronto diretto Warehouse vs Sorting",
                     fontweight="bold")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "fig4_whca_comparison.png"),
                    bbox_inches="tight")
        plt.close()
        print("  [plot] fig4_whca_comparison.png")


def print_summary(df: pd.DataFrame, grid_info: dict):
    print("\n" + "="*60)
    print("SOMMARIO — Proprietà mappe")
    print("="*60)
    for map_name, info in grid_info.items():
        print(f"\n  {map_name}:")
        print(f"    Dimensioni:       {info['x_size']} × {info['y_size']} = {info['total']} celle")
        print(f"    Ostacoli:         {info['n_obstacle']} ({info['obstacle_pct']:.1f}%)")
        print(f"    Celle libere:     {info['n_free']}")
        if "types" in info:
            for t, c in sorted(info["types"].items()):
                print(f"      {t:20s}: {c}")

    print("\n" + "="*60)
    print("SOMMARIO — Metriche normalizzate (k=50)")
    print("="*60)
    k50 = df[(df["k"] == 50) & (df["status"] == "success")]
    if k50.empty:
        print("  Nessun dato con k=50")
        return
    cols = ["map", "solver", "throughput", "thr_per_agent",
            "avg_runtime_ms", "rt_per_agent", "avg_collisions"]
    avail = [c for c in cols if c in k50.columns]
    print(k50[avail].to_string(index=False, float_format=lambda x: f"{x:.3f}"))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Leggi proprietà mappe
    print("Analisi mappe...")
    grid_info = {}
    for map_name, cfg in EXP_DIRS.items():
        try:
            grid_info[map_name] = parse_grid(cfg["map"])
            print(f"  {map_name}: {grid_info[map_name]['n_free']} celle libere "
                  f"su {grid_info[map_name]['total']} "
                  f"({grid_info[map_name]['obstacle_pct']:.1f}% ostacoli)")
        except FileNotFoundError:
            print(f"  WARN: mappa non trovata: {cfg['map']}")
            grid_info[map_name] = {"n_free": 1, "total": 1,
                                   "obstacle_pct": 0, "x_size": 0, "y_size": 0}

    # 2. Raccolta dati
    print("\nCaricamento dati sperimentali...")
    df = collect_data(EXP_DIRS, grid_info)

    # Salva dati grezzi
    raw_path = os.path.join(OUTPUT_DIR, "normalized_metrics.csv")
    df.to_csv(raw_path, index=False)
    print(f"  CSV salvato: {raw_path}")

    # 3. Sommario testuale
    print_summary(df, grid_info)

    # 4. Grafici
    print("\nGenerazione grafici...")
    try:
        plot_normalized(df, OUTPUT_DIR)
    except Exception as e:
        print(f"  WARN: plotting fallito: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nDone. Output in: {OUTPUT_DIR}/")
    print("Interpretazione:")
    print("  fig1 → differenze assolute (influenzate da k e geometria)")
    print("  fig2 → normalizzato per agente (isola effetto algoritmo)")
    print("  fig3 → normalizzato per densità (isola effetto geometria)")
    print("  fig4 → confronto diretto WHCA warehouse vs sorting")


if __name__ == "__main__":
    main()
