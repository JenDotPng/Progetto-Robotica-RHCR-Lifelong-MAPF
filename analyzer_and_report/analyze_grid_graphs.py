#!/usr/bin/env python3
"""
Analisi e visualizzazione di mappe custom RHCR come grafi diretti pesati.

Input attesi:
- warehouse_map.grid
- warehouse_optimized.grid
- sorting_map.grid

Output generati:
- warehouse_grid.png
- warehouse_graph.png
- warehouse_zoom.png
- warehouse.graphml
- warehouse_optimized_grid.png
- warehouse_optimized_graph.png
- warehouse_optimized_zoom.png
- warehouse_optimized.graphml
- sorting_grid.png
- sorting_graph.png
- sorting_zoom.png
- sorting.graphml

Dipendenze:
- networkx
- matplotlib
- numpy
- csv

Python:
- 3.10+
"""

import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import networkx as nx


def _parse_weight(value: str) -> float:
    """Converte il peso da stringa a float; 'inf' -> np.inf."""
    value = value.strip().lower()
    if value == "inf":
        return np.inf
    return float(value)


def parse_custom_grid(file_path: str) -> dict:
    """
    Parsifica una mappa custom RHCR.

    Formato atteso:
        Grid size (x, y)
        X,Y
        id,type,station,x,y,weight_to_NORTH,...

    Ritorna un dizionario con:
    - x_size, y_size
    - cells: lista di celle (dict)
    - cells_by_coord: {(x,y): cell_dict}
    - total_cells, obstacle_cells, obstacle_ratio
    """
    with open(file_path, "r", newline="") as f:
        header_line = f.readline().strip()
        if "grid size" not in header_line.lower():
            raise ValueError(
                f"Formato non valido in {file_path}: prima riga attesa 'Grid size (x, y)'"
            )

        dims_line = f.readline().strip()
        dims = [p.strip() for p in dims_line.split(",")]
        if len(dims) != 2:
            raise ValueError(
                f"Formato dimensioni non valido in {file_path}: '{dims_line}'"
            )

        x_size = int(dims[0])
        y_size = int(dims[1])

        reader = csv.DictReader(f)

        required_fields = {
            "id",
            "type",
            "station",
            "x",
            "y",
            "weight_to_NORTH",
            "weight_to_WEST",
            "weight_to_SOUTH",
            "weight_to_EAST",
            "weight_for_WAIT",
        }
        missing = required_fields.difference(set(reader.fieldnames or []))
        if missing:
            raise ValueError(
                f"Campi mancanti in {file_path}: {sorted(missing)}"
            )

        cells = []
        cells_by_coord = {}

        for row in reader:
            cell = {
                "id": int(row["id"]),
                "type": row["type"].strip(),
                "station": row["station"].strip(),
                "x": int(row["x"]),
                "y": int(row["y"]),
                "w_north": _parse_weight(row["weight_to_NORTH"]),
                "w_west": _parse_weight(row["weight_to_WEST"]),
                "w_south": _parse_weight(row["weight_to_SOUTH"]),
                "w_east": _parse_weight(row["weight_to_EAST"]),
                "w_wait": _parse_weight(row["weight_for_WAIT"]),
            }
            cells.append(cell)
            cells_by_coord[(cell["x"], cell["y"])] = cell

    total_cells = x_size * y_size
    obstacle_cells = sum(1 for c in cells if c["type"] == "Obstacle")
    obstacle_ratio = (obstacle_cells / total_cells) * 100 if total_cells > 0 else 0.0

    return {
        "file_path": file_path,
        "x_size": x_size,
        "y_size": y_size,
        "cells": cells,
        "cells_by_coord": cells_by_coord,
        "total_cells": total_cells,
        "obstacle_cells": obstacle_cells,
        "obstacle_ratio": obstacle_ratio,
    }


def build_graph(grid_data: dict) -> nx.DiGraph:
    """
    Costruisce il grafo diretto pesato G=(V,E) dalla mappa.

    Regole:
    - nodo per ogni cella con type != Obstacle
    - nodo identificato da (x, y)
    - arco direzionale se peso della direzione è finito
    - self-loop per WAIT con peso weight_for_WAIT (se finito)
    """
    G = nx.DiGraph()
    cells_by_coord = grid_data["cells_by_coord"]

    # 1) Nodi
    for cell in grid_data["cells"]:
        if cell["type"] == "Obstacle":
            continue
        node = (cell["x"], cell["y"])
        G.add_node(
            node,
            cell_type=cell["type"],
            station=cell["station"],
            id=cell["id"],
        )

    # 2) Archi direzionali + wait
    directions = {
        "NORTH": (0, -1, "w_north"),
        "WEST": (-1, 0, "w_west"),
        "SOUTH": (0, 1, "w_south"),
        "EAST": (1, 0, "w_east"),
    }

    for cell in grid_data["cells"]:
        if cell["type"] == "Obstacle":
            continue

        src = (cell["x"], cell["y"])

        # Archi di movimento
        for direction_name, (dx, dy, weight_key) in directions.items():
            w = cell[weight_key]
            if np.isinf(w):
                continue

            dst = (cell["x"] + dx, cell["y"] + dy)
            dst_cell = cells_by_coord.get(dst)

            if dst_cell is None:
                continue
            if dst_cell["type"] == "Obstacle":
                continue

            G.add_edge(src, dst, weight=float(w), direction=direction_name)

        # Self-loop WAIT
        if not np.isinf(cell["w_wait"]):
            G.add_edge(src, src, weight=float(cell["w_wait"]), direction="WAIT")

    return G


def plot_grid(grid_data: dict, out_path: str, title: str) -> None:
    """Visualizza la mappa a celle colorate per tipo."""
    x_size = grid_data["x_size"]
    y_size = grid_data["y_size"]

    # Default: Obstacle
    arr = np.zeros((y_size, x_size), dtype=np.int8)

    type_to_code = {
        "Obstacle": 0,
        "Travel": 1,
        "Induct": 2,
        "Eject": 3,
    }

    for cell in grid_data["cells"]:
        x, y = cell["x"], cell["y"]
        arr[y, x] = type_to_code.get(cell["type"], 1)

    cmap = mcolors.ListedColormap(["black", "white", "green", "red"])
    norm = mcolors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], cmap.N)

    plt.figure(figsize=(10, 5))
    plt.imshow(arr, cmap=cmap, norm=norm, origin="upper", interpolation="nearest")
    plt.title(title)
    plt.xlabel("x")
    plt.ylabel("y")

    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor="black", edgecolor="black", label="Obstacle"),
        Patch(facecolor="white", edgecolor="black", label="Travel"),
        Patch(facecolor="green", edgecolor="black", label="Induct"),
        Patch(facecolor="red", edgecolor="black", label="Eject"),
    ]
    plt.legend(handles=legend_handles, loc="upper right", fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def _auto_node_size(num_nodes: int) -> float:
    """Riduce automaticamente la dimensione nodi quando la mappa è grande."""
    if num_nodes <= 5000:
        return 6.0
    # Decadimento dolce con limite minimo
    return max(0.6, 6.0 * (5000.0 / float(num_nodes)))


def plot_graph(G: nx.DiGraph, out_path: str, title: str) -> None:
    """Visualizzazione del grafo completo con frecce e nodi piccoli."""
    pos = {n: (n[0], -n[1]) for n in G.nodes()}
    num_nodes = G.number_of_nodes()
    node_size = _auto_node_size(num_nodes)

    node_colors = []
    for n in G.nodes():
        t = G.nodes[n].get("cell_type", "Travel")
        if t == "Induct":
            node_colors.append("green")
        elif t == "Eject":
            node_colors.append("red")
        else:
            node_colors.append("white")

    plt.figure(figsize=(12, 8))
    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=node_size,
        node_color=node_colors,
        edgecolors="black",
        linewidths=0.05,
    )
    nx.draw_networkx_edges(
        G,
        pos,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=4,
        width=0.15,
        alpha=0.45,
        edge_color="steelblue",
    )
    plt.title(f"{title} (|V|={num_nodes}, |E|={G.number_of_edges()})")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=220)
    plt.close()


def plot_zoom_graph(G: nx.DiGraph, grid_data: dict, out_path: str, title: str) -> None:
    """
    Visualizzazione locale 15x15 centrata nella mappa.
    Mostra sotto-grafo e direzionalità.
    """
    x_center = grid_data["x_size"] // 2
    y_center = grid_data["y_size"] // 2

    half = 7  # 15x15 => centro +/- 7
    x_min, x_max = x_center - half, x_center + half
    y_min, y_max = y_center - half, y_center + half

    local_nodes = [
        n for n in G.nodes()
        if x_min <= n[0] <= x_max and y_min <= n[1] <= y_max
    ]
    H = G.subgraph(local_nodes).copy()

    pos = {n: (n[0], -n[1]) for n in H.nodes()}

    node_colors = []
    for n in H.nodes():
        t = H.nodes[n].get("cell_type", "Travel")
        if t == "Induct":
            node_colors.append("green")
        elif t == "Eject":
            node_colors.append("red")
        else:
            node_colors.append("white")

    plt.figure(figsize=(8, 8))
    nx.draw_networkx_nodes(
        H,
        pos,
        node_size=80,
        node_color=node_colors,
        edgecolors="black",
        linewidths=0.4,
    )
    nx.draw_networkx_edges(
        H,
        pos,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=12,
        width=0.8,
        alpha=0.8,
        edge_color="tab:blue",
        connectionstyle="arc3,rad=0.05",
    )

    plt.title(
        f"{title} — Zoom 15x15 centro ({x_center}, {y_center})\n"
        f"|V_local|={H.number_of_nodes()}, |E_local|={H.number_of_edges()}"
    )
    plt.gca().set_aspect("equal", adjustable="box")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=220)
    plt.close()


def analyze_graph(G: nx.DiGraph, grid_data: dict, map_name: str) -> dict:
    """Calcola metriche principali del grafo e le stampa."""
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()

    avg_degree = (sum(dict(G.degree()).values()) / num_nodes) if num_nodes > 0 else 0.0
    scc_count = nx.number_strongly_connected_components(G)

    stats = {
        "map": map_name,
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "avg_degree": avg_degree,
        "obstacle_ratio_percent": grid_data["obstacle_ratio"],
        "num_scc": scc_count,
    }

    print("=" * 70)
    print(f"Analisi mappa: {map_name}")
    print("=" * 70)
    print(f"Numero nodi:                      {stats['num_nodes']}")
    print(f"Numero archi:                     {stats['num_edges']}")
    print(f"Grado medio:                      {stats['avg_degree']:.4f}")
    print(f"Percentuale ostacoli:             {stats['obstacle_ratio_percent']:.2f}%")
    print(f"Numero SCC (fortemente connesse): {stats['num_scc']}")

    return stats


def _export_graphml(G: nx.DiGraph, out_path: str) -> None:
    """
    Esporta GraphML.
    GraphML non gestisce in modo robusto tuple come node-id: si converte l'id
    in stringa 'x,y', preservando x e y come attributi numerici.
    """
    H = nx.DiGraph()

    for n, attrs in G.nodes(data=True):
        node_id = f"{n[0]},{n[1]}"
        H.add_node(node_id, x=int(n[0]), y=int(n[1]), **attrs)

    for u, v, attrs in G.edges(data=True):
        u_id = f"{u[0]},{u[1]}"
        v_id = f"{v[0]},{v[1]}"
        H.add_edge(u_id, v_id, **attrs)

    nx.write_graphml(H, out_path)


def main() -> None:
    maps_to_process = [
        ("warehouse", "warehouse_map.grid"),
        ("warehouse_optimized", "warehouse_optimized.grid"),
        ("sorting", "sorting_map.grid"),
    ]

    for map_label, base_name in maps_to_process:
        # Fallback: prova prima in cwd, poi in maps/
        candidate_paths = [base_name, f"../maps/{base_name}"]

        selected_path = None
        for p in candidate_paths:
            try:
                with open(p, "r"):
                    selected_path = p
                    break
            except OSError:
                continue

        if selected_path is None:
            raise FileNotFoundError(
                f"Impossibile trovare '{base_name}' né in cwd né in maps/"
            )

        grid_data = parse_custom_grid(selected_path)
        G = build_graph(grid_data)

        analyze_graph(G, grid_data, map_label)

        plot_grid(
            grid_data,
            out_path=f"{map_label}_grid.png",
            title=f"{map_label} — Grid view",
        )
        plot_graph(
            G,
            out_path=f"{map_label}_graph.png",
            title=f"{map_label} — Directed weighted graph",
        )
        plot_zoom_graph(
            G,
            grid_data,
            out_path=f"{map_label}_zoom.png",
            title=f"{map_label}",
        )
        _export_graphml(G, out_path=f"{map_label}.graphml")

        print(f"Output salvati per {map_label}:")
        print(f"  - {map_label}_grid.png")
        print(f"  - {map_label}_graph.png")
        print(f"  - {map_label}_zoom.png")
        print(f"  - {map_label}.graphml")


if __name__ == "__main__":
    main()
