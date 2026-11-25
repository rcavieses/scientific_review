#!/usr/bin/env python3
"""
Renderiza el grafo de parámetros (outputs/graph_index_parametros) a PNG estático.

Genera dos figuras:
  fig_grafo_red.png       — red Especie–Parámetro–Paper–Grupo funcional
  fig_grafo_taxonomia.png — árbol taxonómico de las especies con dato

Uso:
    ./venv/bin/python scripts/render_parameter_graph_png.py
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

ROOT = Path(__file__).parent.parent

# Paleta categórica validada: los 3 primeros slots pasan el gate all-pairs
# (necesario en un diagrama nodo-enlace, donde todos los tipos se ven a la vez).
# Los tipos estructurales van en neutros para no competir por identidad.
COLORS = {
    "Species": "#2a78d6",
    "Parameter": "#eb6834",
    "Paper": "#1baf7a",
    "FunctionalGroup": "#6f6e6a",
    "Taxon": "#a8a7a1",
}
MARKERS = {
    "Species": "o", "Parameter": "s", "Paper": "D",
    "FunctionalGroup": "^", "Taxon": "o",
}
SURFACE, INK, INK2, EDGE = "#fcfcfb", "#0b0b0b", "#52514e", "#d8d7d2"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK, "font.size": 10,
})


def load_graph(graph_dir: Path):
    with open(graph_dir / "knowledge_graph.json", encoding="utf-8") as f:
        g = json.load(f)
    return g["entities"], g["relations"]


def legend(ax, types, title):
    handles = [
        Line2D([], [], marker=MARKERS[t], color="none", markerfacecolor=COLORS[t],
               markeredgecolor="white", markeredgewidth=0.8, markersize=9, label=lab)
        for t, lab in types
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False,
              fontsize=9, labelcolor=INK2, title=title,
              title_fontproperties={"size": 9, "weight": "bold"})


def place_labels(ax, labels: dict, pos: dict, fontsize=8.5):
    """
    Coloca etiquetas fuera del núcleo del grafo con línea guía.

    Los nodos más conectados caen en el centro del layout, así que etiquetarlos
    in situ produce solapamientos. Cada etiqueta se empuja radialmente hacia
    afuera y luego se separa de las ya colocadas.
    """
    import numpy as np

    cx = np.mean([p[0] for p in pos.values()])
    cy = np.mean([p[1] for p in pos.values()])
    order = sorted(labels, key=lambda n: -((pos[n][0] - cx) ** 2 + (pos[n][1] - cy) ** 2))

    placed = []  # (x, y, w, h)
    for n in order:
        x, y = pos[n]
        dx, dy = x - cx, y - cy
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-6
        ux, uy = dx / norm, dy / norm
        w, h = 0.0125 * len(labels[n]) + 0.02, 0.052
        lx, ly = x + ux * 0.06, y + uy * 0.06
        for _ in range(160):                       # empujar hasta no solapar
            if not any(abs(lx - px) < (w + pw) / 2 and abs(ly - py) < (h + ph) / 2
                       for px, py, pw, ph in placed):
                break
            lx += ux * 0.022
            ly += uy * 0.022
        placed.append((lx, ly, w, h))
        ax.annotate(
            labels[n], xy=(x, y), xytext=(lx, ly), ha="center", va="center",
            fontsize=fontsize, color=INK, zorder=7,
            bbox=dict(boxstyle="round,pad=0.22", fc=SURFACE, ec="none", alpha=0.9),
            arrowprops=dict(arrowstyle="-", color="#b9b8b3", lw=0.7,
                            shrinkA=0, shrinkB=4),
        )


def figure_network(E, R, out: Path, n_species=70, n_papers=45):
    """Red Especie–Parámetro–Paper–Grupo. La taxonomía va en la otra figura."""
    keep_rel = {"has_parameter", "cited_in", "belongs_to_group"}
    deg = Counter()
    for r in R.values():
        if r["relation_type"] in keep_rel:
            deg[r["subject_id"]] += 1
            deg[r["object_id"]] += 1

    def top(t, n):
        return [i for i, _ in sorted(
            ((i, d) for i, d in deg.items() if E[i]["entity_type"] == t),
            key=lambda x: -x[1])[:n]]

    nodes = set(i for i in deg if E[i]["entity_type"] == "Parameter")
    nodes |= set(top("Species", n_species)) | set(top("Paper", n_papers))
    nodes |= set(top("FunctionalGroup", 12))

    G = nx.Graph()
    for i in nodes:
        G.add_node(i, t=E[i]["entity_type"])
    for r in R.values():
        s, o = r["subject_id"], r["object_id"]
        if r["relation_type"] in keep_rel and s in nodes and o in nodes:
            G.add_edge(s, o, rel=r["relation_type"])
    G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])

    pos = nx.spring_layout(G, k=0.75, iterations=450, seed=7)

    fig, ax = plt.subplots(figsize=(15, 11))
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=EDGE, width=0.8, alpha=0.9)

    for t in ["Taxon", "FunctionalGroup", "Paper", "Species", "Parameter"]:
        sub = [n for n in G if G.nodes[n]["t"] == t]
        if not sub:
            continue
        sizes = [70 + 26 * G.degree(n) for n in sub]
        if t == "Parameter":
            sizes = [min(s, 620) for s in sizes]
        nx.draw_networkx_nodes(G, pos, nodelist=sub, node_size=sizes,
                               node_color=COLORS[t], node_shape=MARKERS[t],
                               edgecolors="white", linewidths=0.9, ax=ax)

    # Etiquetas selectivas: los 14 parámetros, los grupos funcionales y solo los
    # papers/especies mejor conectados (etiquetar todo produce colisiones).
    def top_by_degree(t, n):
        return {i for i, _ in sorted(((i, G.degree(i)) for i in G
                                      if G.nodes[i]["t"] == t), key=lambda x: -x[1])[:n]}

    labeled = {n for n in G if G.nodes[n]["t"] in ("Parameter", "FunctionalGroup")}
    labeled |= top_by_degree("Paper", 6) | top_by_degree("Species", 5)
    place_labels(ax, {n: E[n]["name"] for n in labeled}, pos)

    fig.text(0.01, 0.985, "Grafo de parámetros ATLANTIS GOC — evidencia por especie",
             fontsize=16, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 0.951,
             f"{G.number_of_nodes()} nodos · {G.number_of_edges()} aristas · "
             "tamaño del nodo = número de conexiones · "
             "solo se etiquetan los nodos más conectados",
             fontsize=10, color=INK2, va="top")
    legend(ax, [("Species", "Especie"), ("Parameter", "Parámetro"),
                ("Paper", "Paper"), ("FunctionalGroup", "Grupo funcional")],
           "Tipo de nodo")
    ax.axis("off")
    fig.tight_layout(rect=[0, 0, 1, 0.935])
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  {out}  ({G.number_of_nodes()} nodos, {G.number_of_edges()} aristas)")


def figure_taxonomy(E, R, out: Path):
    """Árbol Phylum→Class→Order→Family de las especies con parámetros."""
    with_param = {r["subject_id"] for r in R.values()
                  if r["relation_type"] == "has_parameter"}
    parent = {r["subject_id"]: r["object_id"] for r in R.values()
              if r["relation_type"] == "classified_as"}

    # Ascender de cada especie con dato hasta Phylum, contando especies por taxón
    count = Counter()
    edges = set()
    for sp in with_param:
        node, seen = parent.get(sp), 0
        while node and seen < 6:
            count[node] += 1
            nxt = parent.get(node)
            if nxt:
                edges.add((nxt, node))
            node, seen = nxt, seen + 1

    keep = {n for n in count if E[n]["properties"].get("rank") != "Genus"}
    keep = {n for n in keep if count[n] >= 2}
    G = nx.DiGraph()
    for a, b in edges:
        if a in keep and b in keep:
            G.add_edge(a, b)
    G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])

    rank_y = {"Phylum": 3, "Class": 2, "Order": 1, "Family": 0}
    layers = defaultdict(list)
    for n in G:
        layers[E[n]["properties"].get("rank", "Family")].append(n)
    pos = {}
    for rank, y in rank_y.items():
        row = sorted(layers.get(rank, []), key=lambda n: -count[n])
        for i, n in enumerate(row):
            pos[n] = ((i + 0.5) / max(len(row), 1), y)

    fig, ax = plt.subplots(figsize=(15, 7.5))
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=EDGE, width=0.9,
                           arrows=False, alpha=0.95)
    # Rampa ordinal de un solo tono: cuanto más profundo el rango, más claro
    rank_color = {"Phylum": "#184f95", "Class": "#256abf",
                  "Order": "#3987e5", "Family": "#86b6ef"}
    sizes = [60 + 22 * count[n] for n in G]
    colors = [rank_color.get(E[n]["properties"].get("rank"), COLORS["Taxon"]) for n in G]
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=colors,
                           edgecolors="white", linewidths=0.9, ax=ax)
    for n, (x, y) in pos.items():
        rank = E[n]["properties"].get("rank")
        if count[n] >= 6 or rank in ("Phylum", "Class"):
            ax.text(x, y + 0.11, f"{E[n]['name']} ({count[n]})", ha="center",
                    va="bottom", fontsize=8, color=INK, rotation=28)
    for rank, y in rank_y.items():
        ax.text(-0.035, y, rank, ha="right", va="center",
                fontsize=10, fontweight="bold", color=INK2)

    fig.text(0.01, 0.985, "Cobertura taxonómica de las especies con parámetros",
             fontsize=16, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 0.945,
             f"{len(with_param)} especies con ≥1 parámetro · "
             "el número entre paréntesis es cuántas caen bajo ese taxón · "
             "se omiten taxones con una sola especie",
             fontsize=10, color=INK2, va="top")
    ax.set_xlim(-0.09, 1.05)
    ax.set_ylim(-0.55, 3.9)
    ax.axis("off")
    fig.tight_layout(rect=[0, 0, 1, 0.925])
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  {out}  ({G.number_of_nodes()} taxones)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-dir", default="outputs/graph_index_parametros")
    ap.add_argument("--out-dir", default="outputs/reports/comparacion_busquedas")
    args = ap.parse_args()

    E, R = load_graph(ROOT / args.graph_dir)
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Grafo: {len(E)} entidades, {len(R)} relaciones")
    figure_network(E, R, out_dir / "fig_grafo_red.png")
    figure_taxonomy(E, R, out_dir / "fig_grafo_taxonomia.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
