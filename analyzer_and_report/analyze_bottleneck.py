"""
Analisi bottleneck strutturale nella warehouse
========================================================
Legge i file paths.txt degli esperimenti warehouse e calcola:
  - Heatmap di occupazione celle (flusso medio per cella)
  - Corridoi chiave (celle Travel con massimo flusso)
  - Saturazione: cells con load > soglia
  - Suggerimenti di micro-modifica mappa

Usa i paths.txt disponibili in exp/movingAI_warehouse_final/
(WHCA_k20, WHCA_k100, WHCA_k120, ECBS_k50)

Output: exp/analysis_bottleneck/

Uso:
  python3 analyze_bottleneck.py
  python3 analyze_bottleneck.py --exp_dir exp/movingAI_warehouse_final
"""

import os
import sys
import csv
import argparse
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from collections import defaultdict

MAP_PATH    = "../maps/warehouse_map-10-20-10-2-2.grid"
EXP_BASE    = "../exp/movingAI_warehouse_final"
OUTPUT_DIR  = "../exp/analysis_bottleneck"

# Soglia flusso (percentile) per classificare cella come bottleneck
BOTTLENECK_PERCENTILE = 90

RUN_RE = re.compile(
    r"^(?P<map>sorting|warehouse)_(?P<solver>PBS|ECBS|WHCA|LRA)_k(?P<k>\d+)"
    r"(?:_w(?P<w>\d+)_h(?P<h>\d+)_seed(?P<seed>\d+))?$"
)


def parse_run_k(run_name: str, default: int = 1) -> int:
    m = RUN_RE.match(run_name)
    if m:
        return int(m.group("k"))
    return default


# ── Parsing mappa RHCR ────────────────────────────────────────────────────────
class GridInfo:
    def __init__(self, map_path: str):
        with open(map_path) as f:
            f.readline()                     # "Grid size (x,y)"
            dims = f.readline().strip().split(",")
            self.x_size = int(dims[0])
            self.y_size = int(dims[1])
            reader = csv.DictReader(f)
            self.cells = {}                  # cellid → {"type", "x", "y", "station"}
            self.type_cells = defaultdict(list)

            for row in reader:
                cid = int(row["id"])
                self.cells[cid] = {
                    "type":    row["type"],
                    "x":       int(row["x"]),
                    "y":       int(row["y"]),
                    "station": row.get("station", ""),
                }
                self.type_cells[row["type"]].append(cid)

        self.total     = self.x_size * self.y_size
        self.n_obstacle = len(self.type_cells.get("Obstacle", []))
        self.n_free    = self.total - self.n_obstacle
        print(f"  Mappa: {self.x_size}×{self.y_size} = {self.total} celle")
        print(f"  Libere: {self.n_free}  |  Ostacoli: {self.n_obstacle}")
        for t, lst in sorted(self.type_cells.items()):
            print(f"    {t:20s}: {len(lst)}")

    def cellid_to_xy(self, cellid: int):
        """Converte cellid (indice lineare) a (x, y)."""
        if cellid in self.cells:
            c = self.cells[cellid]
            return c["x"], c["y"]
        # Fallback: calcolo geometrico
        return cellid % self.x_size, cellid // self.x_size

    def xy_to_cellid(self, x: int, y: int) -> int:
        return y * self.x_size + x

    def cell_type(self, cellid: int) -> str:
        return self.cells.get(cellid, {}).get("type", "Unknown")


# ── Parsing paths.txt ─────────────────────────────────────────────────────────
def parse_paths(paths_file: str, grid: GridInfo) -> np.ndarray:
    """
    Legge paths.txt e ritorna la heatmap di occupazione (x_size × y_size).
    Formato: riga 1 = N_agenti; righe 2..N+1 = percorso agente
    Percorso: cellid,orient,t;cellid,orient,t;...
    """
    heatmap = np.zeros((grid.y_size, grid.x_size), dtype=np.int64)
    n_agents = 0
    n_steps  = 0

    with open(paths_file) as f:
        first_line = f.readline().strip()
        try:
            n_agents_total = int(first_line)
        except ValueError:
            print(f"  WARN: formato paths.txt inatteso, prima riga: {first_line!r}")
            return heatmap

        for agent_id, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            steps = line.split(";")
            for step in steps:
                step = step.strip()
                if not step:
                    continue
                parts = step.split(",")
                if len(parts) < 1:
                    continue
                try:
                    cellid = int(parts[0])
                except ValueError:
                    continue
                x, y = grid.cellid_to_xy(cellid)
                if 0 <= x < grid.x_size and 0 <= y < grid.y_size:
                    heatmap[y, x] += 1
                    n_steps += 1

    if n_agents_total > 0:
        print(f"  Agenti: {n_agents_total}  |  Passi totali: {n_steps}")
    return heatmap


# ── Analisi corridoi ──────────────────────────────────────────────────────────
def analyze_corridors(heatmap: np.ndarray, grid: GridInfo,
                      n_agents: int) -> pd.DataFrame:
    """
    Calcola il flusso per ogni cella Travel e identifica i bottleneck.
    Flusso = occupazione_totale / n_agenti (normalized agent-timesteps/agent).
    """
    records = []
    total_timesteps = heatmap.sum()

    for cellid, info in grid.cells.items():
        if info["type"] == "Obstacle":
            continue
        x, y   = info["x"], info["y"]
        count  = heatmap[y, x]
        if count == 0:
            continue

        # Conta ostacoli adiacenti (proxy di "strettezza" del corridoio)
        neighbors = [(x-1,y), (x+1,y), (x,y-1), (x,y+1)]
        n_obstacle_adj = sum(
            1 for nx, ny in neighbors
            if 0 <= nx < grid.x_size and 0 <= ny < grid.y_size
            and grid.cells.get(grid.xy_to_cellid(nx, ny), {}).get("type") == "Obstacle"
        )

        records.append({
            "cellid":         cellid,
            "x":              x,
            "y":              y,
            "type":           info["type"],
            "station":        info["station"],
            "occupancy":      int(count),
            "flow_per_agent": count / max(n_agents, 1),
            "n_obstacles_adj": n_obstacle_adj,
            "is_narrow":      n_obstacle_adj >= 2,   # ≥2 lati bloccati
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Soglia bottleneck
    travel_flows = df[df["type"] == "Travel"]["occupancy"]
    if not travel_flows.empty:
        threshold = np.percentile(travel_flows, BOTTLENECK_PERCENTILE)
        df["is_bottleneck"] = (df["type"] == "Travel") & (df["occupancy"] >= threshold)
    else:
        df["is_bottleneck"] = False

    return df.sort_values("occupancy", ascending=False)


def suggest_modifications(df_corridors: pd.DataFrame, grid: GridInfo) -> list:
    """
    Suggerisce micro-modifiche sulla base dei bottleneck identificati.
    Ritorna una lista di dizionari con suggerimenti.
    """
    suggestions = []
    bottlenecks = df_corridors[df_corridors["is_bottleneck"] & df_corridors["is_narrow"]]

    for _, row in bottlenecks.head(5).iterrows():
        # Trova celle adiacenti che sono ostacoli (candidate all'allargamento)
        x, y   = row["x"], row["y"]
        adj_obstacles = []
        for nx, ny in [(x-1,y), (x+1,y), (x,y-1), (x,y+1)]:
            if 0 <= nx < grid.x_size and 0 <= ny < grid.y_size:
                cid = grid.xy_to_cellid(nx, ny)
                if grid.cells.get(cid, {}).get("type") == "Obstacle":
                    adj_obstacles.append((nx, ny))

        suggestions.append({
            "bottleneck_xy":   (x, y),
            "occupancy":       row["occupancy"],
            "flow_per_agent":  row["flow_per_agent"],
            "adj_obstacles":   adj_obstacles,
            "action":          "Allarga corridoio → converti ostacolo adiacente in Travel",
            "candidate_cells": adj_obstacles[:2],
        })

    # Stazioni con alto flusso (potenziale spostamento)
    high_station = df_corridors[
        df_corridors["type"].isin(["Induct", "Eject"]) &
        (df_corridors["occupancy"] > df_corridors["occupancy"].quantile(0.8))
    ]
    for _, row in high_station.head(3).iterrows():
        suggestions.append({
            "bottleneck_xy":   (row["x"], row["y"]),
            "occupancy":       row["occupancy"],
            "type":            row["type"],
            "action":          f"Valuta spostamento stazione {row['type']} in zona meno congestionata",
            "candidate_cells": [],
        })

    return suggestions


# ── Visualizzazione ───────────────────────────────────────────────────────────
def plot_heatmap(heatmap: np.ndarray, grid: GridInfo, df_corridors: pd.DataFrame,
                 title: str, out_path: str):
    """Genera heatmap di flusso con overlay dei bottleneck."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))

    # Pannello 1: heatmap colore
    ax = axes[0]
    obstacle_mask = np.zeros((grid.y_size, grid.x_size), dtype=bool)
    for cid, info in grid.cells.items():
        if info["type"] == "Obstacle":
            obstacle_mask[info["y"], info["x"]] = True

    display = heatmap.astype(float).copy()
    display[obstacle_mask] = np.nan

    im = ax.imshow(display, cmap="hot_r", aspect="equal",
                   origin="upper", interpolation="nearest")
    # Ostacoli in grigio scuro
    gray_overlay = obstacle_mask.astype(float)
    gray_overlay[~obstacle_mask] = np.nan
    ax.imshow(gray_overlay, cmap="Greys", vmin=0, vmax=1,
              aspect="equal", origin="upper", alpha=0.7, interpolation="nearest")

    plt.colorbar(im, ax=ax, label="Occupazione (timestep-agente)")
    ax.set_title(f"{title}\nHeatmap flusso agenti", fontsize=9)
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    # Pannello 2: bottleneck evidenziati
    ax2 = axes[1]
    ax2.imshow(display, cmap="Blues", aspect="equal",
               origin="upper", alpha=0.5, interpolation="nearest")
    ax2.imshow(gray_overlay, cmap="Greys", vmin=0, vmax=1,
               aspect="equal", origin="upper", alpha=0.7, interpolation="nearest")

    if not df_corridors.empty:
        bn = df_corridors[df_corridors["is_bottleneck"]]
        if not bn.empty:
            ax2.scatter(bn["x"], bn["y"], c="red", s=8, zorder=5,
                        label=f"Bottleneck (top {100-BOTTLENECK_PERCENTILE}%)")

        induct = df_corridors[df_corridors["type"] == "Induct"]
        eject  = df_corridors[df_corridors["type"] == "Eject"]
        if not induct.empty:
            ax2.scatter(induct["x"], induct["y"], c="lime", s=4,
                        zorder=4, label="Induct", alpha=0.5)
        if not eject.empty:
            ax2.scatter(eject["x"], eject["y"], c="yellow", s=4,
                        zorder=4, label="Eject", alpha=0.5)

    ax2.set_title(f"{title}\nBottleneck (rosso) e stazioni", fontsize=9)
    ax2.set_xlabel("x")
    ax2.set_ylabel("y")
    ax2.legend(fontsize=6, loc="upper right")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [plot] {out_path}")


def plot_flow_histogram(df_corridors: pd.DataFrame, title: str, out_path: str):
    """Distribuzione del flusso per le celle Travel."""
    travel = df_corridors[df_corridors["type"] == "Travel"]["occupancy"]
    if travel.empty:
        return

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(travel, bins=50, color="#2196F3", edgecolor="white", alpha=0.8)
    threshold = np.percentile(travel, BOTTLENECK_PERCENTILE)
    ax.axvline(threshold, color="red", linewidth=1.5,
               label=f"Soglia bottleneck ({BOTTLENECK_PERCENTILE}° percentile = {threshold:.0f})")
    ax.set_xlabel("Occupazione cella (timestep-agente)")
    ax.set_ylabel("N. celle")
    ax.set_title(f"{title}\nDistribuzione flusso celle Travel")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [plot] {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Bottleneck analysis warehouse")
    parser.add_argument("--exp_dir", default=EXP_BASE)
    parser.add_argument("--map",     default=MAP_PATH)
    parser.add_argument("--output",  default=OUTPUT_DIR)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # 1. Carica mappa
    print("Caricamento mappa warehouse...")
    try:
        grid = GridInfo(args.map)
    except FileNotFoundError:
        print(f"ERRORE: mappa non trovata: {args.map}")
        sys.exit(1)

    # 2. Trova tutti i paths.txt
    paths_files = []
    for root, dirs, files in os.walk(args.exp_dir):
        for fname in files:
            if fname == "paths.txt":
                paths_files.append(os.path.join(root, fname))
    paths_files.sort()

    if not paths_files:
        print(f"\nNESSUN paths.txt trovato in {args.exp_dir}")
        print("Suggerimento: esegui un esperimento con --screen 1 (default)")
        print("  ./build/lifelong -m maps/warehouse_map-10-20-10-2-2.grid "
              "-k 50 --scenario SORTING --solver PBS "
              "--planning_window 40 --simulation_window 5 "
              "--output exp/wh_bottleneck_test --simulation_time 400")
        sys.exit(0)

    print(f"\nTrovati {len(paths_files)} file paths.txt:")
    for p in paths_files:
        print(f"  {p}")

    # 3. Agrega heatmap da tutti i run
    combined_heatmap = np.zeros((grid.y_size, grid.x_size), dtype=np.int64)
    run_info = []

    for pf in paths_files:
        run_name = os.path.basename(os.path.dirname(pf))
        k = parse_run_k(run_name, default=1)

        print(f"\nAnalisi: {run_name} (k={k})...")
        hm = parse_paths(pf, grid)
        df_corr = analyze_corridors(hm, grid, k)

        if not df_corr.empty:
            # Plot per singolo run
            plot_heatmap(hm, grid, df_corr,
                         title=run_name,
                         out_path=os.path.join(args.output, f"heatmap_{run_name}.png"))
            plot_flow_histogram(df_corr,
                                title=run_name,
                                out_path=os.path.join(args.output, f"hist_{run_name}.png"))

            # Salva top corridoi
            top50 = df_corr.head(50)
            top50.to_csv(os.path.join(args.output, f"corridors_{run_name}.csv"),
                         index=False)

            # Suggerimenti modifiche
            suggestions = suggest_modifications(df_corr, grid)
            print(f"\n  TOP 10 celle più congestionate ({run_name}):")
            for _, row in df_corr.head(10).iterrows():
                bn = "★ BOTTLENECK" if row["is_bottleneck"] else ""
                narrow = "(stretto)" if row["is_narrow"] else ""
                print(f"    ({row['x']:3d},{row['y']:3d}) "
                      f"type={row['type']:8s} "
                      f"occupancy={row['occupancy']:6d} "
                      f"flow/agent={row['flow_per_agent']:.1f} "
                      f"{narrow} {bn}")

            if suggestions:
                print(f"\n  Suggerimenti micro-modifiche ({run_name}):")
                for i, s in enumerate(suggestions, 1):
                    print(f"    {i}. Cella {s['bottleneck_xy']}: {s['action']}")
                    if s.get("candidate_cells"):
                        print(f"       Candidati da convertire: {s['candidate_cells']}")

            run_info.append({
                "run":          run_name,
                "k":            k,
                "n_bottleneck": int(df_corr["is_bottleneck"].sum()),
                "max_flow":     df_corr["occupancy"].max(),
                "mean_flow":    df_corr[df_corr["type"] == "Travel"]["occupancy"].mean(),
                "pct_saturated": (df_corr["is_bottleneck"].sum() / max(
                    len(df_corr[df_corr["type"] == "Travel"]), 1)) * 100,
            })

        combined_heatmap += hm

    # 4. Heatmap aggregata (tutti i run)
    print("\n\nAnalisi aggregata (tutti i run)...")
    df_agg = analyze_corridors(combined_heatmap, grid, n_agents=1)  # flusso assoluto
    if not df_agg.empty:
        plot_heatmap(combined_heatmap, grid, df_agg,
                     title="Aggregato (tutti i run)",
                     out_path=os.path.join(args.output, "heatmap_aggregated.png"))
        df_agg.to_csv(os.path.join(args.output, "corridors_aggregated.csv"),
                      index=False)

    # 5. Report testuale
    if run_info:
        df_report = pd.DataFrame(run_info)
        report_path = os.path.join(args.output, "bottleneck_report.csv")
        df_report.to_csv(report_path, index=False)
        print(f"\n\nReport salvato: {report_path}")
        print(df_report.to_string(index=False))

        print("\n" + "="*60)
        print("INTERPRETAZIONE")
        print("="*60)
        print("  mean_flow  → flusso medio nelle celle Travel (agent-timestep).")
        print("  max_flow   → cella più congestionata.")
        print("  pct_saturated → % celle Travel che superano il 90° percentile.")
        print("  Se pct_saturated >> 10% → congestione strutturale, non solo algoritmica.")
        print("  Azione suggerita: allarga i corridoi ★ BOTTLENECK stretti (is_narrow=True)")
        print("  nella mappa o sposta le stazioni ad alta frequenza.")

    print(f"\nDone. Output in: {args.output}/")


if __name__ == "__main__":
    main()
