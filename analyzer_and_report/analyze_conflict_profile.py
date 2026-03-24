"""
Profilo di collisioni e ripianificazioni per timestep
==============================================================
Legge i file solver.csv dagli esperimenti esistenti (w=40, h=5) e traccia:
  - Numero medio di conflitti per finestra temporale (col 8: num_of_collisions)
  - Runtime per finestra temporale (col 0)
  - Confronto warehouse vs sorting per stesso k

Colonne solver.csv (PBS/ECBS):
  0: runtime(s)  1: HL_exp  2: HL_gen  3: LL_exp  4: LL_gen
  5: flowtime    6: min_flowtime  7: avg_path  8: num_collisions
  9: timestep   10: k           11: seed

Output: exp/analysis_conflicts/

Uso:
  python3 analyze_conflict_profile.py
  python3 analyze_conflict_profile.py --k 50 80
"""

import os
import argparse
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Configurazione ────────────────────────────────────────────────────────────
EXPERIMENTS = {
    "sorting": {
        "base":    "../exp/sorting",
        "label":   "sorting_map",
        "color":   "#2196F3",
        "solvers": ["PBS", "ECBS", "WHCA"],
    },
    "warehouse": {
        "base":    "../exp/movingAI_warehouse_final",
        "label":   "warehouse_map",
        "color":   "#FF5722",
        "solvers": ["WHCA", "ECBS"],
    },
}
AGENTS   = [20, 50, 80, 100, 120]
OUTPUT_DIR = "../exp/analysis_conflicts"

# Indici colonne solver.csv
COL_RUNTIME    = 0
COL_COLLISIONS = 8    # PBS: dummy_start->num_of_collisions
COL_HL_EXP     = 1    # High-level nodes expanded (proxy complessità)
COL_FLOWTIME   = 5
COL_TIMESTEP   = 9
COL_K          = 10

SENS_RUN_RE = re.compile(
    r"^(?P<map>sorting|warehouse)_(?P<solver>PBS|ECBS|WHCA|LRA)_k(?P<k>\d+)"
    r"(?:_w(?P<w>\d+)_h(?P<h>\d+)_seed(?P<seed>\d+))?$"
)


def parse_run_name(run_name: str) -> dict | None:
    """Parsa nome cartella run in formato classico o sensitivity sweep."""
    m = SENS_RUN_RE.match(run_name)
    if not m:
        return None
    d = m.groupdict()
    return {
        "map": d["map"],
        "solver": d["solver"],
        "k": int(d["k"]),
        "w": int(d["w"]) if d.get("w") else None,
        "h": int(d["h"]) if d.get("h") else None,
        "seed": int(d["seed"]) if d.get("seed") else None,
    }


def aggregate_profiles(dfs: list[pd.DataFrame]) -> pd.DataFrame | None:
    """Media per indice-finestra su più run (es. semi diversi)."""
    valid = [d[["runtime", "collisions"]].reset_index(drop=True)
             for d in dfs if d is not None and not d.empty]
    if not valid:
        return None
    stacked = pd.concat(valid, keys=range(len(valid)), names=["run", "step"])
    agg = stacked.groupby(level="step").mean(numeric_only=True)
    agg = agg.reset_index(drop=True)
    return agg


def load_from_sensitivity(exp_dir: str, k: int,
                          w: list[int] | None,
                          h: list[int] | None,
                          seed: list[int] | None) -> dict:
    """Carica run da cartelle sensitivity e aggrega per mappa/solver."""
    grouped = {}
    if not os.path.isdir(exp_dir):
        return {}

    for entry in sorted(os.listdir(exp_dir)):
        run_dir = os.path.join(exp_dir, entry)
        if not os.path.isdir(run_dir):
            continue
        meta = parse_run_name(entry)
        if meta is None:
            continue
        if meta["k"] != k:
            continue
        if w and meta["w"] not in w:
            continue
        if h and meta["h"] not in h:
            continue
        if seed and meta["seed"] not in seed:
            continue

        csv_path = os.path.join(run_dir, "solver.csv")
        df = load_solver_csv(csv_path)
        if df is None:
            continue

        label = f"{meta['map']}/{meta['solver']}"
        grouped.setdefault(label, {
            "dfs": [],
            "solver": meta["solver"],
            "exp": meta["map"],
            "w_vals": set(),
            "h_vals": set(),
            "seed_vals": set(),
        })
        grouped[label]["dfs"].append(df)
        if meta["w"] is not None:
            grouped[label]["w_vals"].add(meta["w"])
        if meta["h"] is not None:
            grouped[label]["h_vals"].add(meta["h"])
        if meta["seed"] is not None:
            grouped[label]["seed_vals"].add(meta["seed"])

    loaded = {}
    for label, item in grouped.items():
        agg_df = aggregate_profiles(item["dfs"])
        if agg_df is None:
            continue
        loaded[label] = {
            "df": agg_df,
            "solver": item["solver"],
            "exp": item["exp"],
            "n_runs": len(item["dfs"]),
            "w_vals": sorted(item["w_vals"]),
            "h_vals": sorted(item["h_vals"]),
            "seed_vals": sorted(item["seed_vals"]),
        }
    return loaded


def load_solver_csv(path: str) -> pd.DataFrame | None:
    """Carica solver.csv con gestione robusta del formato."""
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, header=None)
        if df.empty or df.shape[1] < 9:
            return None
        df.columns = list(range(df.shape[1]))
        # Rinomina colonne note
        rename = {
            COL_RUNTIME:    "runtime",
            COL_HL_EXP:     "hl_expanded",
            COL_COLLISIONS: "collisions",
            COL_FLOWTIME:   "flowtime",
            COL_TIMESTEP:   "timestep",
        }
        if df.shape[1] > COL_K:
            rename[COL_K] = "k"
        df = df.rename(columns=rename)
        df["runtime"]    = pd.to_numeric(df["runtime"],    errors="coerce")
        df["collisions"] = pd.to_numeric(df["collisions"], errors="coerce")
        df["flowtime"]   = pd.to_numeric(df["flowtime"],   errors="coerce")
        return df
    except Exception as e:
        print(f"  WARN: errore lettura {path}: {e}")
        return None


# ── Grafici profilo temporale ─────────────────────────────────────────────────
def plot_collision_profile(ax, df: pd.DataFrame, label: str, color: str,
                           window: int = 10):
    """Traccia il profilo collisioni nel tempo con media mobile."""
    if df is None or "collisions" not in df.columns:
        return
    series = df["collisions"].fillna(0)
    timesteps = range(len(series))
    # Media mobile
    rolling = series.rolling(window=window, min_periods=1).mean()
    ax.plot(timesteps, series.values, alpha=0.25, color=color, linewidth=0.5)
    ax.plot(timesteps, rolling.values, label=label, color=color, linewidth=1.5)


def plot_runtime_profile(ax, df: pd.DataFrame, label: str, color: str,
                         window: int = 10):
    """Traccia il profilo runtime per finestra NEL TEMPO."""
    if df is None or "runtime" not in df.columns:
        return
    series = df["runtime"].fillna(0) * 1000  # → ms
    timesteps = range(len(series))
    rolling = series.rolling(window=window, min_periods=1).mean()
    ax.plot(timesteps, series.values, alpha=0.25, color=color, linewidth=0.5)
    ax.plot(timesteps, rolling.values, label=label, color=color, linewidth=1.5)


# ── Analisi per k fisso ───────────────────────────────────────────────────────
def analyze_fixed_k(k: int, sensitivity_dir: str | None = None,
                    w: list[int] | None = None,
                    h: list[int] | None = None,
                    seed: list[int] | None = None):
    """Analisi profilo per un particolare numero di agenti."""
    print(f"\n  k={k}:")
    if sensitivity_dir:
        loaded = load_from_sensitivity(sensitivity_dir, k, w=w, h=h, seed=seed)
        for key, item in loaded.items():
            df = item["df"]
            print(f"    {key}: {len(df)} finestre medie, run={item['n_runs']}, "
                  f"w={item['w_vals'] or ['*']}, h={item['h_vals'] or ['*']}, "
                  f"seed={item['seed_vals'] or ['*']}, "
                  f"collisions_mean={df['collisions'].mean():.2f}, "
                  f"runtime_mean={df['runtime'].mean()*1000:.2f}ms")
    else:
        loaded = {}
        for exp_name, cfg in EXPERIMENTS.items():
            for solver in cfg["solvers"]:
                run_dir  = os.path.join(cfg["base"], f"{solver}_k{k}")
                csv_path = os.path.join(run_dir, "solver.csv")
                df = load_solver_csv(csv_path)
                if df is not None:
                    key = f"{exp_name}/{solver}"
                    loaded[key] = {"df": df, "cfg": cfg, "solver": solver,
                                   "exp": exp_name}
                    print(f"    {key}: {len(df)} finestre, "
                          f"collisions_mean={df['collisions'].mean():.2f}, "
                          f"runtime_mean={df['runtime'].mean()*1000:.2f}ms")

    if not loaded:
        print(f"    Nessun dato trovato per k={k}")
        return

    # Figure 1: profilo collisioni nel tempo
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=False)
    ax_coll, ax_rt = axes

    for key, item in loaded.items():
        df  = item["df"]
        cfg = item.get("cfg", {})
        color  = cfg.get("color", "#2196F3") if item["solver"] == "PBS" else (
            "#4CAF50" if item["exp"] == "sorting" else "#FF9800")
        plot_collision_profile(ax_coll, df, label=key, color=color)
        plot_runtime_profile(ax_rt, df, label=key, color=color)

    ax_coll.set_xlabel("Finestra di pianificazione (ordine temporale)")
    ax_coll.set_ylabel("Num. collisioni iniziali (pre-risoluzione)")
    ax_coll.set_title(f"Profilo conflitti per finestra — k={k}\n"
                      f"(linea spessa = media mobile su 10 finestre)", fontsize=9)
    ax_coll.legend(fontsize=7, loc="upper right")
    ax_coll.grid(True, alpha=0.3)

    ax_rt.set_xlabel("Finestra di pianificazione")
    ax_rt.set_ylabel("Runtime per finestra (ms)")
    ax_rt.set_title(f"Profilo runtime — k={k}", fontsize=9)
    ax_rt.legend(fontsize=7, loc="upper right")
    ax_rt.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, f"conflict_profile_k{k}.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    [plot] {out_path}")

    return loaded


# ── Analisi aggregata (collisioni medie vs k) ─────────────────────────────────
def plot_aggregate_by_k(all_data: dict):
    """
    Grafici aggregati: collisioni medie e runtime medi al variare di k.
    Permette di vedere se il problema scala con densità o è intrinseco alla geometria.
    """
    records = []
    for k, loaded in all_data.items():
        for key, item in loaded.items():
            df  = item["df"]
            records.append({
                "k":            k,
                "experiment":   item["exp"],
                "solver":       item["solver"],
                "label":        key,
                "mean_coll":    df["collisions"].mean(),
                "std_coll":     df["collisions"].std(),
                "max_coll":     df["collisions"].max(),
                "mean_rt_ms":   df["runtime"].mean() * 1000,
                "pct_zero_coll": (df["collisions"] == 0).mean() * 100,
                "success_windows": len(df),
            })

    if not records:
        return None

    df_agg = pd.DataFrame(records)
    agg_path = os.path.join(OUTPUT_DIR, "conflict_summary.csv")
    df_agg.to_csv(agg_path, index=False)
    print(f"\n  [csv] {agg_path}")

    # Grafici
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    labels_seen = set()

    colors = {
        "sorting/PBS":   "#1565C0",
        "sorting/ECBS":  "#42A5F5",
        "sorting/WHCA":  "#00ACC1",
        "warehouse/WHCA":"#E64A19",
        "warehouse/ECBS":"#FF8A65",
    }
    markers = {"PBS": "o", "ECBS": "s", "WHCA": "^"}

    for ax, (metric, ylabel, title) in zip(axes, [
        ("mean_coll",   "Collisioni medie/finestra",      "Conflitti medi"),
        ("max_coll",    "Collisioni max/finestra",         "Conflitti massimi"),
        ("mean_rt_ms",  "Runtime medio/finestra (ms)",     "Runtime"),
    ]):
        for label, grp in df_agg.groupby("label"):
            grp = grp.sort_values("k")
            c = colors.get(label, "gray")
            m = markers.get(grp["solver"].iloc[0], "x")
            ax.plot(grp["k"], grp[metric],
                    color=c, marker=m, linewidth=1.8,
                    label=label if label not in labels_seen else "_nolegend_")
            labels_seen.add(label)
        ax.set_xlabel("Numero agenti (k)")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=9)
        ax.grid(True, alpha=0.3)

    axes[0].legend(fontsize=6, loc="upper left")
    fig.suptitle("Profilo conflitti: warehouse vs sorting (w=40, h=5)",
                 fontweight="bold")
    plt.tight_layout()
    out_agg = os.path.join(OUTPUT_DIR, "conflict_aggregate.png")
    plt.savefig(out_agg, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [plot] {out_agg}")

    # Stampa tabella riassuntiva
    print("\n" + "="*70)
    print("SOMMARIO — Conflitti medi per finestra (w=40, h=5)")
    print("="*70)
    pivot = df_agg.pivot_table(index="label", columns="k",
                               values="mean_coll", aggfunc="mean")
    print(pivot.to_string(float_format=lambda x: f"{x:.2f}"))

    print("\n" + "="*70)
    print("INTERPRETAZIONE")
    print("="*70)
    print("  collisioni medie/finestra ↑ con k → congestione da densità")
    print("  collisioni warehouse >> sorting  → congestione strutturale (geometria)")
    print("  collisioni sorting ≈ 0           → mappa meno sfidante algoritmicamente")
    print("  runtime spike senza spike collisioni → overhead solver (non congestione)")

    return df_agg


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global OUTPUT_DIR
    parser = argparse.ArgumentParser(description="Conflict profile analysis")
    parser.add_argument("--k", nargs="+", type=int, default=None,
                        help="Valori di k da analizzare")
    parser.add_argument("--exp_dir", default=None,
                        help="Directory sensitivity sweep (es. exp/sensitivity_sweep)")
    parser.add_argument("--w", nargs="+", type=int, default=None,
                        help="Filtro planning_window (solo con --exp_dir)")
    parser.add_argument("--h", nargs="+", type=int, default=None,
                        help="Filtro simulation_window (solo con --exp_dir)")
    parser.add_argument("--seed", nargs="+", type=int, default=None,
                        help="Filtro seed (solo con --exp_dir)")
    parser.add_argument("--output", default=OUTPUT_DIR)
    args = parser.parse_args()

    OUTPUT_DIR = args.output
    os.makedirs(args.output, exist_ok=True)

    if args.k is None:
        if args.exp_dir:
            discovered_k = set()
            if os.path.isdir(args.exp_dir):
                for entry in os.listdir(args.exp_dir):
                    meta = parse_run_name(entry)
                    if meta is not None:
                        discovered_k.add(meta["k"])
            args.k = sorted(discovered_k) if discovered_k else [50]
        else:
            args.k = AGENTS

    if args.exp_dir:
        print("Analisi profilo conflitti su sensitivity sweep")
    else:
        print("Analisi profilo conflitti (w=40, h=5 — dati esistenti)")
    print("="*60)

    all_data = {}
    for k in args.k:
        result = analyze_fixed_k(k, sensitivity_dir=args.exp_dir,
                                 w=args.w, h=args.h, seed=args.seed)
        if result:
            all_data[k] = result

    if not all_data:
        print("\nNESSUN dato trovato.")
        print("Assicurati che esistano cartelle tipo exp/sorting/PBS_k50/solver.csv")
        return

    print("\nGenerazione grafici aggregati...")
    df_agg = plot_aggregate_by_k(all_data)

    print(f"\nDone. Output in: {args.output}/")
    print("File generati:")
    print(f"  conflict_profile_k*.png   → profilo temporale per ogni k")
    print(f"  conflict_aggregate.png    → confronto aggregato warehouse vs sorting")
    print(f"  conflict_summary.csv      → tabella numerica")


if __name__ == "__main__":
    main()
