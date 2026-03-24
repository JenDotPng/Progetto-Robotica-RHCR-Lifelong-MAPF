"""
Sensitivity sweep su parametri temporali w e h
=========================================================
Esegue lo sweep su:
  - maps/warehouse_map.grid  (scenario SORTING)
  - maps/sorting_map.grid                 (scenario SORTING)

Parametri variati:
  w (planning_window) ∈ {20, 40, 60}
  h (simulation_window) ∈ {3, 5, 8}  con vincolo h ≤ w

Fisso:
  Agenti (k): 50
  Solver: PBS, ECBS, WHCA  (LRA escluso: fallisce sempre su SORTING)
  Seeds: 1, 2, 3
  simulation_time: 400
  cutoff_time: 120 s

Output: exp/sensitivity_sweep/  (raw CSV + summary CSV + grafici)

Uso:
  python3 sweep_sensitivity.py
  python3 sweep_sensitivity.py --k 80 --time 300
    python3 sweep_sensitivity.py --plots_only --output exp/sensitivity_sweep_warehouse_optimized
"""

import subprocess
import os
import sys
import time
import argparse
import glob
from collections import OrderedDict
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── Configurazione ────────────────────────────────────────────────────────────
EXE_CANDIDATES = [
    "./build/lifelong",
    "./build/Release/lifelong",
    "./build/Debug/lifelong",
    "./build/RelWithDebInfo/lifelong",
    "./build/MinSizeRel/lifelong",
    "./build_macos/lifelong",
    "./build_macos/Release/lifelong",
    "./build_macos/Debug/lifelong",
    "./build_macos/RelWithDebInfo/lifelong",
    "./build_macos/MinSizeRel/lifelong",
]

MAPS = {
    "warehouse_optimized": {
        "path":     "maps/warehouse_optimized.grid",
        "scenario": "SORTING",
        "heur":     "maps/warehouse_optimized_heuristics_table.txt",
        "solvers": ["PBS", "WHCA", "ECBS"],
    },
    #"sorting": {
    #    "path":     "maps/sorting_map.grid",
    #    "scenario": "SORTING",
    #    "heur":     "maps/sorting_map_heuristics_table.txt",
    #    "solvers": ["PBS", "ECBS", "WHCA"],
    #},
}

# Configurazioni solver (args aggiuntivi)
SOLVER_ARGS = {
    "PBS":  [],
    "ECBS": ["--suboptimal_bound", "2.0"],
    "WHCA": [],
    "LRA":  [],
}

WS = [15, 40, 50, 60, 70, 80]      # planning_window, w=80
HS = [5, 10, 15, 20, 25, 30]         # simulation_window (h ≤ w sempre), h=20
SEEDS = [42]


def resolve_executable_path() -> str:
    """Trova il binario lifelong in percorsi CMake comuni."""
    for candidate in EXE_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # fallback: cerca ricorsivamente in build/ eventuali varianti
    dynamic_candidates = sorted(glob.glob("./build*/**/lifelong", recursive=True))
    for candidate in dynamic_candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return ""


# ── Helpers ───────────────────────────────────────────────────────────────────
def cleanup_heuristics(map_path: str):
    base = os.path.splitext(map_path)[0]
    for suffix in ["_heuristics_table.txt", "_rotation_heuristics_table.txt"]:
        f = base + suffix
        if os.path.exists(f):
            os.remove(f)
            print(f"  [cache] rimossa: {f}")


def run_experiment(exe, map_path, scenario, solver, extra_args,
                   k, w, h, seed, sim_time, cutoff, out_dir) -> dict:
    """Lancia una singola run e restituisce le metriche."""
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        exe,
        "-m", map_path,
        "-k", str(k),
        "--scenario", scenario,
        "--output", out_dir,
        "--solver", solver,
        "--simulation_time", str(sim_time),
        "--planning_window", str(w),
        "--simulation_window", str(h),
        "--cutoffTime", str(cutoff),
        "--seed", str(seed),
        "--screen", "1",
    ] + extra_args

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            timeout=cutoff + 60,
            capture_output=True,
            text=True,
        )
        elapsed = time.time() - t0
        stderr_out = (proc.stderr or "").strip()

        # Crash noti → riporta ragione
        if proc.returncode != 0:
            reason = "crash"
            if "disconnected" in (proc.stdout + proc.stderr).lower():
                reason = "disconnected_graph"
            elif "heuristic" in (proc.stdout + proc.stderr).lower():
                reason = "heuristic_mismatch"
            elif "segmentation" in stderr_out.lower():
                reason = "segfault"
            return {"status": reason, "runtime": None,
                    "throughput": 0, "avg_collisions": None,
                    "stderr": stderr_out[:200]}

        csv_path = os.path.join(out_dir, "solver.csv")
        if not os.path.exists(csv_path):
            return {"status": "no_csv", "runtime": None,
                    "throughput": 0, "avg_collisions": None, "stderr": ""}

        df = pd.read_csv(csv_path, header=None)
        if df.empty:
            return {"status": "empty_csv", "runtime": None,
                    "throughput": 0, "avg_collisions": None, "stderr": ""}

        # colonne PBS/ECBS/WHCA:
        # 0:runtime  1:HL_exp  2:HL_gen  3:LL_exp  4:LL_gen
        # 5:flowtime  6:min_flowtime  7:avg_path  8:collisions
        # 9:timestep  10:k  11:seed
        avg_runtime    = df.iloc[:, 0].mean()        # runtime medio per finestra (s)
        throughput     = len(df)                     # n. finestre pianificate
        avg_collisions = df.iloc[:, 8].mean() if df.shape[1] > 8 else 0

        return {
            "status":         "success",
            "runtime":        avg_runtime,
            "throughput":     throughput,
            "avg_collisions": avg_collisions,
            "wall_time":      elapsed,
            "stderr":         "",
        }

    except subprocess.TimeoutExpired:
        return {"status": "timeout", "runtime": None,
                "throughput": 0, "avg_collisions": None, "stderr": ""}
    except Exception as e:
        return {"status": f"error:{e}", "runtime": None,
                "throughput": 0, "avg_collisions": None, "stderr": str(e)}


# ── Plot ──────────────────────────────────────────────────────────────────────
def plot_sensitivity(df: pd.DataFrame, out_dir: str, simulation_time: int):
    """Genera grafici di sensitivity per ogni mappa e solver."""
    plt.rcParams.update({"font.size": 9, "figure.dpi": 150})
    maps   = df["map"].unique()

    for map_name in maps:
        sub = df[df["map"] == map_name]
        solvers = sub["solver"].dropna().unique()

        if len(solvers) == 0:
            continue

        fig, axes = plt.subplots(len(solvers), 2,
                                 figsize=(10, 3.5 * len(solvers)),
                                 squeeze=False)
        fig.suptitle(f"Sensitivity w/h — {map_name}", fontsize=11, fontweight="bold")

        for row, solver in enumerate(solvers):
            s = sub[sub["solver"] == solver]
            ax_tp  = axes[row, 0]
            ax_rt  = axes[row, 1]

            # Alcuni solver producono curve throughput identiche per piu valori di w:
            # raggruppiamo per firma della serie per evitare linee sovrapposte invisibili.
            tp_groups = OrderedDict()
            for w in WS:
                grp = s[s["w"] == w].groupby("h")[["throughput", "runtime"]].mean()
                if grp.empty:
                    continue

                tp_series = grp["throughput"].reindex(HS)
                signature = tuple(
                    (h, None if pd.isna(v) else round(float(v), 6))
                    for h, v in tp_series.items()
                )
                if signature not in tp_groups:
                    tp_groups[signature] = {
                        "ws": [w],
                        "x": grp.index,
                        "y": grp["throughput"],
                    }
                else:
                    tp_groups[signature]["ws"].append(w)

                ax_rt.plot(grp.index, grp["runtime"],   marker="s", label=f"w={w}")

            for group in tp_groups.values():
                label_ws = ",".join(str(x) for x in group["ws"])
                ax_tp.plot(group["x"], group["y"], marker="o", label=f"w={label_ws}")

            ax_tp.set_title(f"{solver} — Throughput (finestre)")
            ax_tp.set_xlabel("h (simulation_window)")
            ax_tp.set_ylabel("N. finestre completate")
            ax_tp.legend(fontsize=7)
            ax_tp.grid(True, alpha=0.3)

            ax_rt.set_title(f"{solver} — Runtime medio/finestra (s)")
            ax_rt.set_xlabel("h (simulation_window)")
            ax_rt.set_ylabel("Avg runtime (s)")
            ax_rt.legend(fontsize=7)
            ax_rt.grid(True, alpha=0.3)

        plt.tight_layout()
        fig_path = os.path.join(out_dir, f"sensitivity_{map_name}.png")
        plt.savefig(fig_path, bbox_inches="tight")
        plt.close()
        print(f"  [plot] {fig_path}")

    # Heatmap: throughput medio per (w, h) aggregato su solver/seed.
    # I fallimenti restano inclusi (throughput=0), coerente con i line plot.
    for map_name in maps:
        sub = df[df["map"] == map_name]
        if sub.empty:
            continue
        pivot = sub.pivot_table(values="throughput",
                                index="h", columns="w", aggfunc="mean")
        fig, ax = plt.subplots(figsize=(5, 3))
        im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"w={c}" for c in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"h={i}" for i in pivot.index])
        ax.set_title(f"Throughput medio — {map_name}")
        plt.colorbar(im, ax=ax, label="finestre completate")
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot.values[i, j]
                if not pd.isna(val):
                    ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                            color="black", fontsize=8)
        plt.tight_layout()
        hm_path = os.path.join(out_dir, f"heatmap_{map_name}.png")
        plt.savefig(hm_path, bbox_inches="tight")
        plt.close()
        print(f"  [plot] {hm_path}")

        # Heatmap normalizzata in [0,1] rispetto al massimo teorico:
        # throughput teorico = simulation_time / h  =>  throughput_norm = throughput * h / simulation_time
        sub_norm = sub.copy()
        sub_norm["throughput_norm"] = (sub_norm["throughput"] * sub_norm["h"]) / float(simulation_time)
        sub_norm["throughput_norm"] = sub_norm["throughput_norm"].clip(lower=0.0, upper=1.0)
        pivot_norm = sub_norm.pivot_table(values="throughput_norm",
                                          index="h", columns="w", aggfunc="mean")

        fig, ax = plt.subplots(figsize=(5, 3))
        im = ax.imshow(pivot_norm.values, aspect="auto", cmap="viridis", vmin=0.0, vmax=1.0)
        ax.set_xticks(range(len(pivot_norm.columns)))
        ax.set_xticklabels([f"w={c}" for c in pivot_norm.columns])
        ax.set_yticks(range(len(pivot_norm.index)))
        ax.set_yticklabels([f"h={i}" for i in pivot_norm.index])
        ax.set_title(f"Throughput normalizzato [0,1] — {map_name}")
        plt.colorbar(im, ax=ax, label="throughput normalizzato")
        for i in range(len(pivot_norm.index)):
            for j in range(len(pivot_norm.columns)):
                val = pivot_norm.values[i, j]
                if not pd.isna(val):
                    ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                            color="white" if val > 0.5 else "black", fontsize=8)
        plt.tight_layout()
        hm_norm_path = os.path.join(out_dir, f"heatmap_normalized_{map_name}.png")
        plt.savefig(hm_norm_path, bbox_inches="tight")
        plt.close()
        print(f"  [plot] {hm_norm_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Sensitivity sweep w/h")
    parser.add_argument("--k",    type=int, default=100,  help="Numero agenti fisso")
    parser.add_argument("--time", type=int, default=1500, help="simulation_time")
    parser.add_argument("--cutoff", type=int, default=240, help="cutoff_time (s)")
    parser.add_argument("--output", default="exp/sensitivity_sweep_warehouse_optimized")
    parser.add_argument("--plots_only", action="store_true",
                        help="Rigenera solo i grafici dal CSV raw esistente (niente nuove run)")
    parser.add_argument("--skip_existing", action="store_true",
                        help="Salta run già presenti (solver.csv esiste)")
    args = parser.parse_args()

    if args.plots_only:
        raw_path = os.path.join(args.output, "sensitivity_raw.csv")
        if not os.path.exists(raw_path):
            print(f"ERRORE: raw CSV non trovato: {raw_path}")
            print("Esegui prima lo sweep completo o passa una cartella output corretta.")
            sys.exit(1)
        df_all = pd.read_csv(raw_path)
        if df_all.empty:
            print(f"ERRORE: raw CSV vuoto: {raw_path}")
            sys.exit(1)
        plot_sensitivity(df_all, args.output, args.time)
        print("[OK] Grafici rigenerati da risultati esistenti.")
        print(f"Input: {raw_path}")
        print(f"Output dir: {args.output}")
        print(f"simulation_time per normalizzazione: {args.time}")
        return

    exe_path = resolve_executable_path()
    if not exe_path:
        print("ERRORE: binario non trovato (lifelong)")
        print("Percorsi controllati:")
        for candidate in EXE_CANDIDATES:
            print(f"  - {candidate}")
        print("Compila prima con:")
        print("  cmake -S . -B build")
        print("  cmake --build build -j")
        sys.exit(1)
    print(f"[INFO] Eseguibile trovato: {exe_path}")

    os.makedirs(args.output, exist_ok=True)
    results = []
    total = sum(
        len(map_cfg.get("solvers", list(SOLVER_ARGS.keys()))) * len(WS) * len(HS) * len(SEEDS)
        for map_cfg in MAPS.values()
    )
    done  = 0

    for map_name, map_cfg in MAPS.items():
        map_solvers = map_cfg.get("solvers", list(SOLVER_ARGS.keys()))

        for solver_name in map_solvers:
            solver_extra = SOLVER_ARGS.get(solver_name, [])

            for w in WS:
                for h in HS:
                    if h > w:
                        done += len(SEEDS)
                        continue  # vincolo h ≤ w

                    for seed in SEEDS:
                        done += 1
                        tag     = f"{map_name}_{solver_name}_k{args.k}_w{w}_h{h}_seed{seed}"
                        out_dir = os.path.join(args.output, tag)

                        csv_path = os.path.join(out_dir, "solver.csv")
                        if args.skip_existing and os.path.exists(csv_path):
                            print(f"[{done}/{total}] SKIP  {tag}")
                            try:
                                df_ex = pd.read_csv(csv_path, header=None)
                                results.append({
                                    "map": map_name, "solver": solver_name,
                                    "k": args.k, "w": w, "h": h, "seed": seed,
                                    "status": "success",
                                    "throughput":     len(df_ex),
                                    "runtime":        df_ex.iloc[:, 0].mean(),
                                    "avg_collisions": df_ex.iloc[:, 8].mean() if df_ex.shape[1] > 8 else 0,
                                })
                            except Exception:
                                pass
                            continue

                        # La cache euristica va rimossa PRIMA DI OGNI RUN:
                        # load_heuristics_table modifica types[] marcando come
                        # Obstacle le celle con distanza INT_MAX; la validazione
                        # successiva fallisce se la mappa ha nodi disconnessi.
                        # Ricalcolare le euristiche ogni volta è più sicuro.
                        cleanup_heuristics(map_cfg["path"])

                        print(f"[{done}/{total}] RUN   {tag}")
                        res = run_experiment(
                            exe_path, map_cfg["path"], map_cfg["scenario"],
                            solver_name, solver_extra,
                            args.k, w, h, seed,
                            args.time, args.cutoff, out_dir
                        )
                        status_msg = res['status']
                        if res.get('stderr'):
                            status_msg += f" ({res['stderr'][:60]})"
                        print(f"          → {status_msg}  "
                              f"thr={res['throughput']}  "
                              f"rt={res['runtime']}")
                        results.append({
                            "map": map_name, "solver": solver_name,
                            "k": args.k, "w": w, "h": h, "seed": seed,
                            **{k2: v for k2, v in res.items() if k2 != 'stderr'},
                        })

    # Salva raw CSV
    df_all = pd.DataFrame(results)
    raw_path = os.path.join(args.output, "sensitivity_raw.csv")
    df_all.to_csv(raw_path, index=False)
    print(f"\n[OK] Raw CSV salvato: {raw_path}")

    # Summary: media su seed
    ok = df_all[df_all["status"] == "success"]
    summary_cols = ["map", "solver", "w", "h"]
    summary = ok.groupby(summary_cols)[["throughput", "runtime", "avg_collisions"]].mean().reset_index()
    summary["success_rate"] = ok.groupby(summary_cols)["status"].count().values / len(SEEDS)
    sum_path = os.path.join(args.output, "sensitivity_summary.csv")
    summary.to_csv(sum_path, index=False)
    print(f"[OK] Summary CSV salvato: {sum_path}")

    # Grafici
    if not df_all.empty:
        try:
            plot_sensitivity(df_all, args.output, args.time)
        except Exception as e:
            print(f"[WARN] Plotting fallito: {e}")

    print("\nDone.")
    print(f"Risultati in: {args.output}/")
    print("File chiave:")
    print(f"  {raw_path}")
    print(f"  {sum_path}")


if __name__ == "__main__":
    main()
