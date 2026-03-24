#!/usr/bin/env python3
"""
Genera i grafici per il report sperimentale MAPF.

Grafici prodotti:
1) Heatmap operativita solver vs k (status + throughput annotato)
2) Curva throughput per agente vs k (ECBS vs PBS su warehouse_optimized)
3) Runtime vs Throughput (Pareto)
4) Successo nominale vs successo operativo (sorting)
5) Grafico transizione di regime (sorting)
6) Boxplot runtime (se disponibili piu seed)

Uso:
  python3 generate_report_plots.py
  python3 generate_report_plots.py --output exp/analysis_report_plots --operational-threshold 1000
"""

from __future__ import annotations

import argparse
import glob
import os
from typing import List, Tuple

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import pandas as pd
import numpy as np


SORTING_REPORT = "../exp/stress_test_sorting_map/final_comparison/final_report.csv"
SORTING_SUMMARY = "../exp/stress_test_sorting_map/final_comparison/final_report_summary.csv"

WH_ECBS_REPORT = "../exp/stress_test_warehouse_optimized/ECBS_comparison_k_100-1000/final_report.csv"
WH_PBS_REPORT = "../exp/stress_test_warehouse_optimized/PBS_comparison_k_100-1000/final_report.csv"
WH_WHCA_REPORT = "../exp/stress_test_warehouse_optimized/WHCA_comparison_k_100-1000/final_report.csv"
WH_ECBS_EXT_REPORT = "../exp/stress_test_warehouse_optimized/ECBS_comparison_k_1100-1500/final_report.csv"

WH_ECBS_SUMMARY = "../exp/stress_test_warehouse_optimized/ECBS_comparison_k_100-1000/final_report_summary.csv"
WH_PBS_SUMMARY = "../exp/stress_test_warehouse_optimized/PBS_comparison_k_100-1000/final_report_summary.csv"

SENSITIVITY_RAW_CANDIDATES = [
    "../exp/sensitivity_sweep_k50/sensitivity_raw.csv",
    "../exp/sensitivity_sweep_k80/sensitivity_raw.csv",
]

SENSITIVITY_SUMMARY_CANDIDATES = [
    "../exp/sensitivity_sweep_k50/sensitivity_summary.csv",
    "../exp/sensitivity_sweep_k80/sensitivity_summary.csv",
]

BOTTLENECK_AGG_HEATMAPS = [
    "../exp/sensitivity_sweep_k50/analysis_bottleneck/heatmap_aggregated.png",
    "../exp/sensitivity_sweep_k80/analysis_bottleneck/heatmap_aggregated.png",
]


def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File non trovato: {path}")
    return pd.read_csv(path)


def _read_existing_csvs(paths: List[str]) -> List[pd.DataFrame]:
    out = []
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            out.append(pd.read_csv(p))
        except Exception:
            continue
    return out


def _normalize_status(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Status" in out.columns:
        out["Status"] = out["Status"].astype(str).str.strip().str.replace("\r", "", regex=False)
    return out


def _status_code(status: str) -> int:
    s = (status or "").strip().lower()
    if s == "success":
        return 2
    if s == "timeout":
        return 1
    if s == "fail":
        return 0
    return -1


def plot_heatmap_operativita(df: pd.DataFrame, out_path: str, title: str) -> None:
    work = df.copy()
    work["code"] = work["Status"].map(_status_code)

    solvers = sorted(work["Solver"].unique())
    ks = sorted(work["Agenti"].unique())

    grid = pd.DataFrame(index=solvers, columns=ks, data=-1)
    tp_grid = pd.DataFrame(index=solvers, columns=ks, data=0.0)
    ann = pd.DataFrame(index=solvers, columns=ks, data="")

    for _, row in work.iterrows():
        s = row["Solver"]
        k = int(row["Agenti"])
        grid.loc[s, k] = int(row["code"])
        tp = int(row["Throughput"])
        tp_grid.loc[s, k] = float(tp)
        st = str(row["Status"])
        ann.loc[s, k] = f"{st}\nTP={tp}"

    arr_status = grid.values.astype(float)
    arr_tp = tp_grid.values.astype(float)

    cmap_status = mcolors.ListedColormap(["#c62828", "#ef6c00", "#2e7d32", "#9e9e9e"])
    norm_status = mcolors.BoundaryNorm([-1.5, -0.5, 0.5, 1.5, 2.5], cmap_status.N)

    fig, axes = plt.subplots(1, 2, figsize=(2.1 * len(ks), 1.8 + 1.2 * len(solvers)), constrained_layout=True)
    ax_status, ax_tp = axes

    im1 = ax_status.imshow(arr_status, cmap=cmap_status, norm=norm_status, aspect="auto")
    ax_status.set_xticks(range(len(ks)))
    ax_status.set_xticklabels([str(k) for k in ks], rotation=0)
    ax_status.set_yticks(range(len(solvers)))
    ax_status.set_yticklabels(solvers)
    ax_status.set_xlabel("Numero agenti (k)")
    ax_status.set_ylabel("Solver")
    ax_status.set_title("Operativita (status)")

    for i, s in enumerate(solvers):
        for j, k in enumerate(ks):
            code = grid.loc[s, k]
            label = {2: "S", 1: "T", 0: "F", -1: "-"}.get(int(code), "-")
            color = "white" if code in (0, 1, 2) else "black"
            ax_status.text(j, i, label, ha="center", va="center", fontsize=10, fontweight="bold", color=color)

    cbar1 = fig.colorbar(im1, ax=ax_status, ticks=[-1, 0, 1, 2], fraction=0.046, pad=0.04)
    cbar1.ax.set_yticklabels(["N/A", "Fail", "Timeout", "Success"])

    vmax = max(1.0, float(arr_tp.max()))
    im2 = ax_tp.imshow(arr_tp, cmap="YlGnBu", aspect="auto", vmin=0, vmax=vmax)
    ax_tp.set_xticks(range(len(ks)))
    ax_tp.set_xticklabels([str(k) for k in ks], rotation=0)
    ax_tp.set_yticks(range(len(solvers)))
    ax_tp.set_yticklabels(solvers)
    ax_tp.set_xlabel("Numero agenti (k)")
    ax_tp.set_ylabel("Solver")
    ax_tp.set_title("Throughput")

    for i, s in enumerate(solvers):
        for j, k in enumerate(ks):
            val = int(tp_grid.loc[s, k])
            code = int(grid.loc[s, k])
            txt = f"{val}" if code != -1 else "-"
            color = "white" if val > 0.55 * vmax else "black"
            ax_tp.text(j, i, txt, ha="center", va="center", fontsize=8, color=color)

    fig.colorbar(im2, ax=ax_tp, fraction=0.046, pad=0.04)
    fig.suptitle(title, fontsize=12)

    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_tp_per_agent_ecbs_pbs(ecbs_summary: pd.DataFrame, pbs_summary: pd.DataFrame, out_path: str) -> None:
    ec = ecbs_summary.copy()
    pb = pbs_summary.copy()

    ec = ec[ec["Success_Rate"] > 0].copy()
    pb = pb[pb["Success_Rate"] > 0].copy()

    ec["tp_per_agent"] = ec["Throughput_Mean"] / ec["Agenti"]
    pb["tp_per_agent"] = pb["Throughput_Mean"] / pb["Agenti"]

    merged = pd.merge(
        ec[["Agenti", "tp_per_agent", "Runtime_Mean"]].rename(columns={"tp_per_agent": "ec_tp_ag", "Runtime_Mean": "ec_rt"}),
        pb[["Agenti", "tp_per_agent", "Runtime_Mean"]].rename(columns={"tp_per_agent": "pb_tp_ag", "Runtime_Mean": "pb_rt"}),
        on="Agenti",
        how="inner",
    )
    merged["runtime_ratio_pb_over_ec"] = merged["pb_rt"] / merged["ec_rt"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
    ax1, ax2 = axes

    ax1.plot(ec["Agenti"], ec["tp_per_agent"], marker="o", linewidth=2, label="ECBS", color="#1565C0")
    ax1.plot(pb["Agenti"], pb["tp_per_agent"], marker="o", linewidth=2, label="PBS", color="#2E7D32")
    ax1.set_title("Throughput per agente")
    ax1.set_xlabel("Numero agenti (k)")
    ax1.set_ylabel("TP/agente")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2.plot(merged["Agenti"], merged["runtime_ratio_pb_over_ec"], marker="s", linewidth=2, color="#8E24AA")
    ax2.axhline(1.0, linestyle="--", color="#555555", linewidth=1)
    ax2.set_title("Costo relativo: runtime PBS / runtime ECBS")
    ax2.set_xlabel("Numero agenti (k)")
    ax2.set_ylabel("Rapporto runtime")
    ax2.grid(True, alpha=0.3)

    fig.suptitle("Warehouse_optimized: ECBS vs PBS", fontsize=12)
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_metric_vs_k(df_summary: pd.DataFrame, metric_col: str, y_label: str, title: str, out_path: str) -> None:
    colors = {"PBS": "#2E7D32", "ECBS": "#1565C0", "WHCA": "#EF6C00", "LRA": "#9E9E9E"}
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for solver, grp in df_summary.groupby("Solver"):
        grp = grp.sort_values("Agenti")
        ax.plot(grp["Agenti"], grp[metric_col], marker="o", linewidth=2, label=solver, color=colors.get(solver, "#333333"))
    ax.set_title(title)
    ax.set_xlabel("Numero agenti (k)")
    ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_sensitivity_heatmap_throughput(df_summary: pd.DataFrame, map_name: str, out_path: str) -> None:
    # Aggrega su solver e k per mostrare la zona w/h piu robusta
    work = df_summary[df_summary["map"] == map_name].copy()
    if work.empty:
        return
    agg = work.groupby(["w", "h"], as_index=False)["throughput"].mean()
    pivot = agg.pivot(index="w", columns="h", values="throughput").sort_index().sort_index(axis=1)
    arr = pivot.values.astype(float)

    fig, ax = plt.subplots(figsize=(6.8, 5.2))
    vmax = max(1.0, float(np.nanmax(arr)))
    im = ax.imshow(arr, cmap="YlOrRd", aspect="auto", vmin=0, vmax=vmax)

    hs = pivot.columns.tolist()
    ws = pivot.index.tolist()
    ax.set_xticks(range(len(hs)))
    ax.set_xticklabels([str(h) for h in hs])
    ax.set_yticks(range(len(ws)))
    ax.set_yticklabels([str(w) for w in ws])
    ax.set_xlabel("Periodo ripianificazione (h)")
    ax.set_ylabel("Orizzonte (w)")
    ax.set_title(f"Heatmap throughput {map_name}: w vs h")

    for i, w in enumerate(ws):
        for j, h in enumerate(hs):
            v = pivot.loc[w, h]
            txt = "-" if pd.isna(v) else f"{v:.1f}"
            color = "white" if (not pd.isna(v) and v > 0.55 * vmax) else "black"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8, color=color)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Throughput medio")
    # Riferimento visivo alla regola w:h circa 3:1
    ax.text(0.02, -0.18, "Riferimento: zona attesa ottima vicino a w:h ≈ 3:1", transform=ax.transAxes, fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_deadlock_risk_vs_w(df_raw: pd.DataFrame, map_name: str, out_path: str) -> None:
    work = df_raw[df_raw["map"] == map_name].copy()
    if work.empty:
        return

    work["status"] = work["status"].astype(str).str.strip().str.lower()
    # Proxy deadlock/stallo: non-success (include disconnected_graph, fail, timeout)
    work["deadlock_like"] = (work["status"] != "success").astype(int)
    agg = work.groupby(["solver", "w"], as_index=False)["deadlock_like"].mean()

    solvers = sorted(agg["solver"].unique())
    ws = sorted(agg["w"].unique())
    x = np.arange(len(ws), dtype=float)
    width = 0.8 / max(1, len(solvers))
    colors = {"PBS": "#2E7D32", "ECBS": "#1565C0", "WHCA": "#EF6C00", "LRA": "#9E9E9E"}

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for idx, s in enumerate(solvers):
        y = []
        sub = agg[agg["solver"] == s]
        for w in ws:
            r = sub[sub["w"] == w]
            y.append(float(r["deadlock_like"].iloc[0]) if not r.empty else 0.0)
        offset = (idx - (len(solvers) - 1) / 2.0) * width
        ax.bar(x + offset, y, width=width, label=s, color=colors.get(s, "#555555"), alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels([str(w) for w in ws])
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("Orizzonte (w)")
    ax.set_ylabel("Rischio deadlock-like (quota run non-success)")
    ax.set_title(f"Rischio deadlock-like vs w — {map_name}")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_topology_comparison(wh_map_raw: pd.DataFrame, wh_opt_report: pd.DataFrame, out_path: str) -> None:
    # Mappa standard (warehouse) da sensitivity_raw
    a = wh_map_raw.copy()
    a["status"] = a["status"].astype(str).str.strip().str.lower()
    a["throughput"] = pd.to_numeric(a["throughput"], errors="coerce").fillna(0)

    # Mappa ottimizzata da stress warehouse_optimized
    b = wh_opt_report.copy()
    b["Status"] = b["Status"].astype(str).str.strip().str.lower()
    b["Throughput"] = pd.to_numeric(b["Throughput"], errors="coerce").fillna(0)

    solvers = sorted(set(a["solver"].unique()) | set(b["Solver"].unique()))
    rows = []
    for s in solvers:
        a_s = a[a["solver"] == s]
        b_s = b[b["Solver"] == s]

        max_tp_std = float(a_s["throughput"].max()) if not a_s.empty else 0.0
        max_tp_opt = float(b_s["Throughput"].max()) if not b_s.empty else 0.0

        ok_std = a_s[(a_s["status"] == "success") & (a_s["throughput"] > 0)]
        ok_opt = b_s[(b_s["Status"] == "success") & (b_s["Throughput"] > 0)]
        max_k_std = int(ok_std["k"].max()) if not ok_std.empty else 0
        max_k_opt = int(ok_opt["Agenti"].max()) if not ok_opt.empty else 0

        rows.append((s, max_tp_std, max_tp_opt, max_k_std, max_k_opt))

    comp = pd.DataFrame(rows, columns=["solver", "tp_std", "tp_opt", "k_std", "k_opt"]) if rows else pd.DataFrame()
    if comp.empty:
        return

    x = np.arange(len(comp), dtype=float)
    width = 0.36

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    ax1, ax2 = axes

    ax1.bar(x - width / 2, comp["tp_std"], width=width, label="Warehouse", color="#78909C")
    ax1.bar(x + width / 2, comp["tp_opt"], width=width, label="Warehouse optimized", color="#00897B")
    ax1.set_title("Throughput massimo")
    ax1.set_xticks(x)
    ax1.set_xticklabels(comp["solver"].tolist())
    ax1.set_ylabel("Max throughput")
    ax1.grid(True, axis="y", alpha=0.25)
    ax1.legend()

    ax2.bar(x - width / 2, comp["k_std"], width=width, label="Warehouse", color="#78909C")
    ax2.bar(x + width / 2, comp["k_opt"], width=width, label="Warehouse optimized", color="#00897B")
    ax2.set_title("Numero massimo agenti gestiti")
    ax2.set_xticks(x)
    ax2.set_xticklabels(comp["solver"].tolist())
    ax2.set_ylabel("Max k con success")
    ax2.grid(True, axis="y", alpha=0.25)

    fig.suptitle("Confronto topologia: warehouse vs warehouse_optimized", fontsize=12)
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_occupancy_aggregated_heatmaps(heatmap_paths: List[str], out_path: str) -> None:
    existing = [p for p in heatmap_paths if os.path.exists(p)]
    if not existing:
        return
    imgs = [plt.imread(p) for p in existing]

    fig, axes = plt.subplots(1, len(imgs), figsize=(6.2 * len(imgs), 5.1), constrained_layout=True)
    if len(imgs) == 1:
        axes = [axes]

    for i, (ax, img, path) in enumerate(zip(axes, imgs, existing)):
        ax.imshow(img)
        ax.axis("off")
        tag = "k50" if "k50" in path else ("k80" if "k80" in path else f"view{i+1}")
        ax.set_title(f"Occupazione aggregata ({tag})")

    fig.suptitle("Heatmap saturazione traffico (bottleneck aggregati)", fontsize=12)
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_rolling_horizon_diagram(out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 3.2))
    ax.set_xlim(0, 26)
    ax.set_ylim(0, 4)

    # Timeline base
    ax.hlines(1.0, 0.5, 25.5, color="#424242", linewidth=1.8)
    for t in range(0, 26, 2):
        ax.vlines(t + 0.5, 0.85, 1.15, color="#616161", linewidth=1)
        ax.text(t + 0.5, 0.45, str(t), ha="center", va="center", fontsize=8)

    # Finestre rolling horizon (w=8) con ripianificazione ogni h=3
    windows = [(0.5, 8.5, "#BBDEFB"), (3.5, 11.5, "#90CAF9"), (6.5, 14.5, "#64B5F6"), (9.5, 17.5, "#42A5F5")]
    y0 = 2.0
    for i, (a, b, c) in enumerate(windows):
        rect = plt.Rectangle((a, y0 + 0.35 * i), b - a, 0.32, color=c, alpha=0.9)
        ax.add_patch(rect)
        ax.text((a + b) / 2, y0 + 0.35 * i + 0.16, f"finestra w (step {i+1})", ha="center", va="center", fontsize=8)

    for t in [0.5, 3.5, 6.5, 9.5]:
        ax.annotate("", xy=(t, 1.8), xytext=(t, 1.15), arrowprops=dict(arrowstyle="->", color="#E65100", lw=1.6))
        ax.text(t, 1.92, "replan", ha="center", va="bottom", fontsize=8, color="#E65100")

    ax.text(0.6, 3.55, "Rolling Horizon: ripianifica ogni h, esegue su finestra w", fontsize=10, fontweight="bold")
    ax.text(0.6, 3.2, "Esempio illustrativo: w=8, h=3", fontsize=9)
    ax.axis("off")
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close()


def plot_potential_function_diagram(out_path: str) -> None:
    w = np.arange(10, 81)
    # Curva concettuale: potenziale cresce con saturazione
    p_w = 0.25 + 0.72 * (1 - np.exp(-(w - 10) / 16.0))
    threshold = 0.68

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.plot(w, p_w, color="#1565C0", linewidth=2.4, label="P(w)")
    ax.axhline(threshold, color="#C62828", linestyle="--", linewidth=1.8, label="soglia p")

    below = w[p_w < threshold]
    if len(below) > 0:
        xb = int(below[-1])
        yb = float(p_w[w == xb][0])
        ax.scatter([xb], [yb], color="#C62828", zorder=3)
        ax.annotate("P(w) < p: incrementa w", xy=(xb, yb), xytext=(xb + 8, yb - 0.18),
                    arrowprops=dict(arrowstyle="->", color="#C62828", lw=1.4), fontsize=9, color="#C62828")

    ax.set_title("Diagramma concettuale della funzione potenziale P(w)")
    ax.set_xlabel("Orizzonte di pianificazione w")
    ax.set_ylabel("Potenziale normalizzato")
    ax.set_ylim(0, 1.02)
    ax.grid(True, alpha=0.28)
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close()


def plot_pareto(df: pd.DataFrame, out_path: str, title: str) -> None:
    work = df.copy()
    work = work[work["Throughput"] > 0].copy()
    colors = {"PBS": "#2E7D32", "ECBS": "#1565C0", "WHCA": "#EF6C00", "LRA": "#9E9E9E"}

    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    for solver, grp in work.groupby("Solver"):
        grp = grp.sort_values("Agenti")
        ax.scatter(grp["Runtime"], grp["Throughput"], s=55, label=solver, color=colors.get(solver, "#444444"), alpha=0.9)
        ax.plot(grp["Runtime"], grp["Throughput"], linewidth=1.2, alpha=0.7, color=colors.get(solver, "#444444"))
        for _, r in grp.iterrows():
            ax.annotate(f"k={int(r['Agenti'])}", (r["Runtime"], r["Throughput"]), fontsize=7, xytext=(3, 3), textcoords="offset points")

    ax.set_title(title)
    ax.set_xlabel("Runtime medio/finestra (s)")
    ax.set_ylabel("Throughput")
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_nominal_vs_operativo(
    df: pd.DataFrame,
    out_path: str,
    threshold: int,
    title: str,
    operativo_label: str | None = None,
) -> None:
    work = df.copy()
    nominal = work.groupby("Solver")["Status"].apply(lambda s: (s == "Success").sum())
    work["operativo_flag"] = ((work["Status"] == "Success") & (work["Throughput"] > threshold)).astype(int)
    operativo = work.groupby("Solver")["operativo_flag"].sum()

    solvers = sorted(set(nominal.index) | set(operativo.index))
    n_vals = [int(nominal.get(s, 0)) for s in solvers]
    o_vals = [int(operativo.get(s, 0)) for s in solvers]

    x = range(len(solvers))
    width = 0.38

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar([i - width / 2 for i in x], n_vals, width=width, label="Successo nominale", color="#1976D2")
    if operativo_label is None:
        operativo_label = f"Successo operativo (TP>{threshold})"
    ax.bar([i + width / 2 for i in x], o_vals, width=width, label=operativo_label, color="#43A047")

    ax.set_xticks(list(x))
    ax.set_xticklabels(solvers)
    ax.set_ylabel("Numero livelli k")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)

    for i, v in enumerate(n_vals):
        ax.text(i - width / 2, v + 0.1, str(v), ha="center", va="bottom", fontsize=8)
    for i, v in enumerate(o_vals):
        ax.text(i + width / 2, v + 0.1, str(v), ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_transizione_regime(
    df_summary: pd.DataFrame,
    out_path: str,
    title_left: str,
    add_sorting_bands: bool = False,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    ax, ax2 = axes

    if add_sorting_bands:
        # Bande di regime valide per sorting final_comparison
        ax.axvspan(100, 300, color="#E8F5E9", alpha=0.8, label="Stabile (100-300)")
        ax.axvspan(400, 800, color="#FFF8E1", alpha=0.8, label="Transizione (400-800)")
        ax.axvspan(900, 1200, color="#FFEBEE", alpha=0.8, label="Critico (900-1200)")

    colors = {"PBS": "#2E7D32", "ECBS": "#1565C0", "WHCA": "#EF6C00"}
    for solver, grp in df_summary.groupby("Solver"):
        ax.plot(grp["Agenti"], grp["Throughput_Mean"], marker="o", linewidth=2, label=solver, color=colors.get(solver, "#333333"))

    ax.set_title(title_left)
    ax.set_xlabel("Numero agenti (k)")
    ax.set_ylabel("Throughput medio")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, ncols=2)

    # Secondo pannello: numero solver operativi per k
    s = df_summary.copy()
    s["operativo"] = ((s["Success_Rate"] > 0) & (s["Throughput_Mean"] > 0)).astype(int)
    count_operativi = s.groupby("Agenti")["operativo"].sum().reset_index()
    ax2.plot(count_operativi["Agenti"], count_operativi["operativo"], marker="o", linewidth=2, color="#6A1B9A")
    ax2.set_title("Numero solver operativi per k")
    ax2.set_xlabel("Numero agenti (k)")
    ax2.set_ylabel("# solver operativi")
    ax2.set_yticks([0, 1, 2, 3])
    ax2.grid(True, alpha=0.3)

    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def _find_multiseed_reports() -> List[Tuple[str, pd.DataFrame]]:
    candidates = []
    for path in sorted(glob.glob("exp/**/final_report.csv", recursive=True)):
        try:
            df = _normalize_status(_read_csv(path))
        except Exception:
            continue
        if not {"Seed", "Solver", "Agenti", "Runtime"}.issubset(df.columns):
            continue
        # Multi-seed reale: almeno una coppia solver-k con >1 run
        counts = df.groupby(["Solver", "Agenti"]).size()
        if (counts > 1).any():
            candidates.append((path, df))
    # Fallback: sensitivity_raw (multi-seed per definizione)
    for path in SENSITIVITY_RAW_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if {"map", "solver", "k", "seed", "status", "runtime"}.issubset(df.columns):
            candidates.append((path, df))

    return candidates


def _load_first_existing(paths: List[str]) -> Tuple[str | None, pd.DataFrame | None]:
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            return p, pd.read_csv(p)
        except Exception:
            continue
    return None, None


def plot_boxplot_runtime(candidates: List[Tuple[str, pd.DataFrame]], out_path: str, note_path: str) -> None:
    if not candidates:
        with open(note_path, "w", encoding="utf-8") as f:
            f.write("Nessun dataset multi-seed trovato: boxplot runtime non generato.\n")
        return

    # Usa il dataset con piu righe
    path, df = max(candidates, key=lambda x: len(x[1]))

    work = df.copy()

    # Caso A: final_report.csv classico
    if {"Solver", "Agenti", "Runtime"}.issubset(work.columns):
        work = _normalize_status(work)
        work = work[(work["Runtime"] > 0) & (work["Status"] == "Success")].copy()
        work["group"] = work["Solver"].astype(str) + "_k" + work["Agenti"].astype(int).astype(str)

    # Caso B: sensitivity_raw.csv
    elif {"map", "solver", "k", "status", "runtime"}.issubset(work.columns):
        work["runtime"] = pd.to_numeric(work["runtime"], errors="coerce")
        work = work[(work["runtime"] > 0) & (work["status"] == "success")].copy()
        work["group"] = work["map"].astype(str) + "/" + work["solver"].astype(str) + "_k" + work["k"].astype(int).astype(str)
        work = work.rename(columns={"runtime": "Runtime"})

    else:
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(f"Formato dataset non supportato per boxplot: {path}\n")
        return

    if work.empty:
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(f"Dataset trovato ma senza runtime validi per boxplot: {path}\n")
        return

    top_labels = work["group"].value_counts().head(16).index.tolist()
    work = work[work["group"].isin(top_labels)].copy()
    grouped = [work.loc[work["group"] == lab, "Runtime"].values for lab in top_labels]

    fig, ax = plt.subplots(figsize=(max(10, 0.62 * len(top_labels)), 5.4))
    ax.boxplot(grouped, tick_labels=top_labels, showfliers=False)
    ax.set_title(f"Runtime boxplot (multi-seed): {path}")
    ax.set_ylabel("Runtime medio/finestra (s)")
    ax.tick_params(axis="x", rotation=65, labelsize=8)
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()

    with open(note_path, "w", encoding="utf-8") as f:
        f.write(f"Boxplot generato da dataset multi-seed: {path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera grafici avanzati per il report MAPF.")
    parser.add_argument("--output", default="exp/analysis_report_plots", help="Cartella output grafici")
    parser.add_argument("--operational-threshold", type=int, default=1000, help="Soglia throughput per successo operativo")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    sorting_report = _normalize_status(_read_csv(SORTING_REPORT))
    sorting_summary = _read_csv(SORTING_SUMMARY)

    wh_reports = [_normalize_status(_read_csv(p)) for p in [WH_ECBS_REPORT, WH_PBS_REPORT, WH_WHCA_REPORT]]
    wh_base = pd.concat(wh_reports, ignore_index=True)
    wh_ext = _normalize_status(_read_csv(WH_ECBS_EXT_REPORT))
    wh_all = pd.concat([wh_base, wh_ext], ignore_index=True)

    wh_ecbs_summary = _read_csv(WH_ECBS_SUMMARY)
    wh_pbs_summary = _read_csv(WH_PBS_SUMMARY)

    sens_summary_parts = _read_existing_csvs(SENSITIVITY_SUMMARY_CANDIDATES)
    sens_summary = pd.concat(sens_summary_parts, ignore_index=True) if sens_summary_parts else pd.DataFrame()

    sens_raw_parts = _read_existing_csvs(SENSITIVITY_RAW_CANDIDATES)
    sens_raw = pd.concat(sens_raw_parts, ignore_index=True) if sens_raw_parts else pd.DataFrame()

    # Summary aggregato warehouse_optimized per tutti i solver (PBS, ECBS, WHCA, ECBS esteso)
    wh_summary_all = (
        wh_all.groupby(["Solver", "Agenti"], as_index=False)
        .agg(
            Throughput_Mean=("Throughput", "mean"),
            Runtime_Mean=("Runtime", "mean"),
            Success_Rate=("Status", lambda s: (s == "Success").mean()),
        )
        .sort_values(["Solver", "Agenti"])
    )

    # 1) Heatmap operativita solver vs k
    plot_heatmap_operativita(
        sorting_report,
        os.path.join(args.output, "heatmap_operativita_sorting.png"),
        "Heatmap operativita solver vs k — Sorting final_comparison",
    )
    plot_heatmap_operativita(
        wh_all,
        os.path.join(args.output, "heatmap_operativita_warehouse_optimized.png"),
        "Heatmap operativita solver vs k — Warehouse_optimized",
    )

    # 2) Throughput per agente vs k (ECBS vs PBS)
    plot_tp_per_agent_ecbs_pbs(
        wh_ecbs_summary,
        wh_pbs_summary,
        os.path.join(args.output, "throughput_per_agent_ecbs_vs_pbs_warehouse_opt.png"),
    )

    # 2b) Throughput e runtime vs k (scalabilita)
    plot_metric_vs_k(
        sorting_summary,
        "Throughput_Mean",
        "Throughput medio",
        "Throughput vs k — Sorting",
        os.path.join(args.output, "throughput_vs_k_sorting.png"),
    )
    plot_metric_vs_k(
        wh_summary_all,
        "Throughput_Mean",
        "Throughput medio",
        "Throughput vs k — Warehouse_optimized",
        os.path.join(args.output, "throughput_vs_k_warehouse_optimized.png"),
    )
    plot_metric_vs_k(
        sorting_summary,
        "Runtime_Mean",
        "Runtime medio/finestra (s)",
        "Runtime vs k — Sorting",
        os.path.join(args.output, "runtime_vs_k_sorting.png"),
    )
    plot_metric_vs_k(
        wh_summary_all,
        "Runtime_Mean",
        "Runtime medio/finestra (s)",
        "Runtime vs k — Warehouse_optimized",
        os.path.join(args.output, "runtime_vs_k_warehouse_optimized.png"),
    )

    # 3) Runtime vs throughput (Pareto)
    plot_pareto(
        sorting_report,
        os.path.join(args.output, "pareto_runtime_vs_throughput_sorting.png"),
        "Pareto runtime vs throughput — Sorting",
    )
    plot_pareto(
        wh_all,
        os.path.join(args.output, "pareto_runtime_vs_throughput_warehouse_opt.png"),
        "Pareto runtime vs throughput — Warehouse_optimized",
    )

    # 4) Successo nominale vs operativo
    plot_nominal_vs_operativo(
        sorting_report,
        os.path.join(args.output, "successo_nominale_vs_operativo_sorting.png"),
        args.operational_threshold,
        "Sorting stress test: successo nominale vs operativo",
    )
    plot_nominal_vs_operativo(
        wh_all,
        os.path.join(args.output, "successo_nominale_vs_operativo_warehouse_optimized.png"),
        args.operational_threshold,
        "Warehouse stress test: successo nominale vs operativo",
    )

    # 5) Transizione di regime
    plot_transizione_regime(
        sorting_summary,
        os.path.join(args.output, "transizione_regime_sorting.png"),
        "Sorting stress test: transizione di regime",
        add_sorting_bands=True,
    )
    plot_transizione_regime(
        wh_summary_all,
        os.path.join(args.output, "transizione_regime_warehouse_optimized.png"),
        "Warehouse stress test: andamento con k",
    )

    # 5b) Grafici analoghi per warehouse_map (da sensitivity raw)
    sens_path, sens_raw = _load_first_existing(SENSITIVITY_RAW_CANDIDATES)
    if sens_raw is not None and {"map", "solver", "k", "status", "throughput"}.issubset(sens_raw.columns):
        wh_map = sens_raw[sens_raw["map"] == "warehouse"].copy()
        if not wh_map.empty:
            wh_map = wh_map.rename(columns={"solver": "Solver", "k": "Agenti", "status": "Status", "throughput": "Throughput"})
            wh_map["Status"] = wh_map["Status"].astype(str).str.capitalize()
            wh_map["Throughput"] = pd.to_numeric(wh_map["Throughput"], errors="coerce").fillna(0)

            plot_nominal_vs_operativo(
                wh_map,
                os.path.join(args.output, "successo_nominale_vs_operativo_warehouse_map.png"),
                0,
                "Warehouse_map sensitivity: successo nominale vs operativo",
                operativo_label="Successo operativo (TP>0)",
            )

            wh_map_summary = (
                wh_map.groupby(["Solver", "Agenti"], as_index=False)
                .agg(
                    Throughput_Mean=("Throughput", "mean"),
                    Success_Rate=("Status", lambda s: (s == "Success").mean()),
                )
                .sort_values(["Solver", "Agenti"])
            )
            wh_map_summary["Runtime_Mean"] = 0.0

            plot_transizione_regime(
                wh_map_summary,
                os.path.join(args.output, "transizione_regime_warehouse_map.png"),
                "Warehouse_map sensitivity: andamento con k",
            )

    # 5c) Sensitivity: heatmap throughput w-h e rischio deadlock
    if not sens_summary.empty and {"map", "w", "h", "throughput"}.issubset(sens_summary.columns):
        plot_sensitivity_heatmap_throughput(
            sens_summary,
            "sorting",
            os.path.join(args.output, "heatmap_throughput_wh_sorting.png"),
        )
        plot_sensitivity_heatmap_throughput(
            sens_summary,
            "warehouse",
            os.path.join(args.output, "heatmap_throughput_wh_warehouse.png"),
        )

    if not sens_raw.empty and {"map", "solver", "w", "status"}.issubset(sens_raw.columns):
        plot_deadlock_risk_vs_w(
            sens_raw,
            "sorting",
            os.path.join(args.output, "deadlock_risk_vs_w_sorting.png"),
        )
        plot_deadlock_risk_vs_w(
            sens_raw,
            "warehouse",
            os.path.join(args.output, "deadlock_risk_vs_w_warehouse.png"),
        )

    # 5d) Impatto topologia: warehouse vs warehouse_optimized
    if not sens_raw.empty and {"map", "solver", "k", "status", "throughput"}.issubset(sens_raw.columns):
        wh_map_raw = sens_raw[sens_raw["map"] == "warehouse"].copy()
        if not wh_map_raw.empty:
            plot_topology_comparison(
                wh_map_raw,
                wh_all,
                os.path.join(args.output, "topology_warehouse_vs_optimized.png"),
            )

    # 5e) Heatmap occupazione aggregata (dai dati visualizer/bottleneck gia generati)
    plot_occupancy_aggregated_heatmaps(
        BOTTLENECK_AGG_HEATMAPS,
        os.path.join(args.output, "heatmap_occupazione_aggregata.png"),
    )

    # 5f) Diagrammi concettuali framework
    plot_rolling_horizon_diagram(
        os.path.join(args.output, "diagramma_rolling_horizon.png"),
    )
    plot_potential_function_diagram(
        os.path.join(args.output, "diagramma_funzione_potenziale.png"),
    )

    # 6) Boxplot runtime se multi-seed
    candidates = _find_multiseed_reports()
    plot_boxplot_runtime(
        candidates,
        os.path.join(args.output, "boxplot_runtime_multiseed.png"),
        os.path.join(args.output, "boxplot_runtime_note.txt"),
    )

    print("\nGrafici generati in:", os.path.abspath(args.output))
    print("- heatmap_operativita_sorting.png")
    print("- heatmap_operativita_warehouse_optimized.png")
    print("- throughput_per_agent_ecbs_vs_pbs_warehouse_opt.png")
    print("- throughput_vs_k_sorting.png")
    print("- throughput_vs_k_warehouse_optimized.png")
    print("- runtime_vs_k_sorting.png")
    print("- runtime_vs_k_warehouse_optimized.png")
    print("- pareto_runtime_vs_throughput_sorting.png")
    print("- pareto_runtime_vs_throughput_warehouse_opt.png")
    print("- successo_nominale_vs_operativo_sorting.png")
    print("- successo_nominale_vs_operativo_warehouse_optimized.png")
    print("- successo_nominale_vs_operativo_warehouse_map.png (da sensitivity, se disponibile)")
    print("- transizione_regime_sorting.png")
    print("- transizione_regime_warehouse_optimized.png")
    print("- transizione_regime_warehouse_map.png (da sensitivity, se disponibile)")
    print("- heatmap_throughput_wh_sorting.png")
    print("- heatmap_throughput_wh_warehouse.png")
    print("- deadlock_risk_vs_w_sorting.png")
    print("- deadlock_risk_vs_w_warehouse.png")
    print("- topology_warehouse_vs_optimized.png")
    print("- heatmap_occupazione_aggregata.png")
    print("- diagramma_rolling_horizon.png")
    print("- diagramma_funzione_potenziale.png")
    print("- boxplot_runtime_multiseed.png (se disponibile) + boxplot_runtime_note.txt")

    # Mini guida di lettura dei grafici
    with open(os.path.join(args.output, "README_PLOTS.md"), "w", encoding="utf-8") as f:
        f.write("# Guida rapida ai grafici\n\n")
        f.write("- heatmap_operativita_*: pannello sinistro = stato (S/T/F), pannello destro = throughput.\n")
        f.write("- throughput_vs_k_* / runtime_vs_k_*: scalabilita al crescere di k per solver.\n")
        f.write("- throughput_per_agent_ecbs_vs_pbs_warehouse_opt: sinistra TP/agente, destra runtime PBS/ECBS.\n")
        f.write("- pareto_runtime_vs_throughput_*: trade-off costo/resa con traiettoria al crescere di k.\n")
        f.write("- successo_nominale_vs_operativo_sorting / _warehouse_optimized: gap tra Success e produttivita reale.\n")
        f.write("- successo_nominale_vs_operativo_warehouse_map: stessa lettura su mappa warehouse (sensitivity).\n")
        f.write("- transizione_regime_sorting / _warehouse_optimized: throughput per solver + numero solver operativi.\n")
        f.write("- transizione_regime_warehouse_map: andamento sensitivity su k per mappa warehouse.\n")
        f.write("- heatmap_throughput_wh_*: sensibilita throughput su griglia (w, h).\n")
        f.write("- deadlock_risk_vs_w_*: rischio stallo-like (quota run non-success) al variare di w.\n")
        f.write("- topology_warehouse_vs_optimized: confronto topologie su max throughput e max k.\n")
        f.write("- heatmap_occupazione_aggregata: saturazione spaziale aggregata (k50/k80).\n")
        f.write("- diagramma_rolling_horizon / diagramma_funzione_potenziale: figure concettuali framework.\n")
        f.write("- boxplot_runtime_multiseed: stabilita runtime su dataset con semi multipli.\n")


if __name__ == "__main__":
    main()
