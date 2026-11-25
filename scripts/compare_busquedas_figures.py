#!/usr/bin/env python3
"""Genera las tablas y figuras de comparación de las 5 búsquedas de parámetros.

Salidas en outputs/reports/comparacion_busquedas/
"""
import itertools
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
OUT = ROOT / "outputs" / "reports" / "comparacion_busquedas"
OUT.mkdir(parents=True, exist_ok=True)

FILES = {
    "B1": "BUSQUEDA1",
    "B3": "BUSQUEDA_3",
    "B4": "BUSQUEDA_4",
    "B5": "BUSQUEDA_5",
}
PARAMS = [
    "biomass_mt", "abundance_numbers", "mean_body_size", "max_age",
    "natural_mortality", "Lmax", "Von_bertalanffy_a", "Von_bertalanffy_b",
    "growth_rate", "age_first_maturity", "larval_duration",
    "StartSpawnDayOfYear", "EndSpawnDayOfYear", "IsMigratory",
]

# Paleta categórica validada (light mode), asignada en orden fijo
SERIES = {"B1": "#2a78d6", "B3": "#eb6834", "B4": "#1baf7a", "B5": "#eda100"}
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e3e2de"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "font.size": 10,
    "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": GRID,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
})


def load():
    d = {}
    for k, v in FILES.items():
        df = pd.read_csv(ROOT / "data" / "output" / f"Atlantis_GOC_parametros_biologicos_{v}.csv")
        d[k] = df
    return d


def cells(df):
    m = df[PARAMS].notna().values
    return {(i, PARAMS[j]) for i, j in zip(*np.where(m))}


def bare(ax):
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)


D = load()
C = {k: cells(df) for k, df in D.items()}

# ---------------------------------------------------------------- Figura 1
fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
ks = list(FILES)
vals_cells = [len(C[k]) for k in ks]
vals_sp = [len({i for i, _ in C[k]}) for k in ks]
for ax, vals, title in [
    (axes[0], vals_cells, "Valores extraídos (celdas con dato)"),
    (axes[1], vals_sp, "Especies con ≥1 parámetro (de 1 122)"),
]:
    y = np.arange(len(ks))[::-1]
    ax.barh(y, vals, height=0.62, color=[SERIES[k] for k in ks])
    for yy, v in zip(y, vals):
        ax.text(v + max(vals) * 0.02, yy, f"{v:,}".replace(",", " "), va="center",
                color=INK, fontsize=10, fontweight="bold")
    ax.set_yticks(y, ks)
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=10)
    bare(ax)
fig.suptitle("Rendimiento global por búsqueda", x=0.005, ha="left",
             fontsize=13, fontweight="bold", color=INK)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(OUT / "fig1_rendimiento_global.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- Figura 2
mat = pd.DataFrame({k: D[k][PARAMS].notna().sum() for k in ks}).loc[PARAMS]
fig, ax = plt.subplots(figsize=(7.2, 6.4))
cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq", SEQ)
im = ax.imshow(mat.values, cmap=cmap, aspect="auto", vmin=0, vmax=mat.values.max())
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = mat.values[i, j]
        ax.text(j, i, str(v), ha="center", va="center", fontsize=9,
                color="#ffffff" if v > mat.values.max() * 0.55 else INK)
ax.set_xticks(range(len(ks)), ks)
ax.set_yticks(range(len(PARAMS)), PARAMS)
ax.set_title("Especies con dato, por parámetro y búsqueda", color=INK,
             fontsize=12, fontweight="bold", loc="left", pad=12)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)
fig.colorbar(im, ax=ax, shrink=0.55, label="nº de especies")
fig.tight_layout()
fig.savefig(OUT / "fig2_heatmap_parametros.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- Figura 3
pairs, jac, agree = [], [], []
for a, b in itertools.combinations(ks, 2):
    inter, uni = C[a] & C[b], C[a] | C[b]
    ident = sum(1 for (i, p) in inter
                if str(D[a].at[i, p]).strip() == str(D[b].at[i, p]).strip())
    pairs.append(f"{a}–{b}")
    jac.append(100 * len(inter) / len(uni))
    agree.append(100 * ident / len(inter))
fig, ax = plt.subplots(figsize=(8.4, 3.8))
x = np.arange(len(pairs))
w = 0.38
b1 = ax.bar(x - w / 2, jac, w, color=SERIES["B1"], label="Solapamiento (Jaccard)")
b2 = ax.bar(x + w / 2, agree, w, color=SERIES["B3"], label="Valor idéntico (celdas comunes)")
for bars in (b1, b2):
    ax.bar_label(bars, fmt="%.0f%%", padding=3, fontsize=9, color=INK)
ax.set_xticks(x, pairs)
ax.set_ylim(0, 105)
ax.set_ylabel("%")
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper left", fontsize=9, ncols=2)
ax.set_title("Reproducibilidad entre pares de búsquedas", color=INK,
             fontsize=12, fontweight="bold", loc="left", pad=12)
fig.tight_layout()
fig.savefig(OUT / "fig3_reproducibilidad.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- Figura 4
cov = pd.DataFrame({k: (D[k][PARAMS].notna().sum(axis=1) > 0)
                    .groupby(D[k]["Group"]).sum() for k in ks})
cov["n"] = D["B1"].groupby("Group").size()
cov = cov.sort_values("B5", ascending=False).head(12)
fig, ax = plt.subplots(figsize=(9, 5.4))
y = np.arange(len(cov))[::-1]
h = 0.2
for n, k in enumerate(ks):
    ax.barh(y + (1.5 - n) * h, cov[k].values, height=h * 0.9,
            color=SERIES[k], label=k)
ax.set_yticks(y, [f"{g}  (n={cov['n'][g]})" for g in cov.index], fontsize=9)
ax.set_xlabel("especies con ≥1 parámetro")
ax.legend(frameon=False, ncols=4, fontsize=9, loc="lower right")
ax.set_title("Cobertura por grupo funcional (12 mayores)", color=INK,
             fontsize=12, fontweight="bold", loc="left", pad=12)
bare(ax)
fig.tight_layout()
fig.savefig(OUT / "fig4_grupos_funcionales.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- Figura 5
core = set.intersection(*C.values())
excl = {k: len(C[k] - set().union(*[C[o] for o in ks if o != k])) for k in ks}
union = set().union(*C.values())
shared = len(union) - len(core) - sum(excl.values())
fig, ax = plt.subplots(figsize=(8.4, 3.2))
labels = ["Núcleo\n(en las 4)", "Parcial\n(2–3 búsquedas)"] + [f"Solo {k}" for k in ks]
vals = [len(core), shared] + [excl[k] for k in ks]
colors = ["#184f95", "#9ec5f4"] + [SERIES[k] for k in ks]
bars = ax.bar(labels, vals, color=colors, width=0.6)
ax.bar_label(bars, fontsize=10, color=INK, fontweight="bold", padding=3)
ax.set_ylabel("valores extraídos")
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.set_title(f"Composición de la unión de las 4 búsquedas ({len(union)} valores)",
             color=INK, fontsize=12, fontweight="bold", loc="left", pad=12)
fig.tight_layout()
fig.savefig(OUT / "fig5_union_valores.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- Tablas CSV
mat.to_csv(OUT / "cobertura_por_parametro.csv")
cov.to_csv(OUT / "cobertura_por_grupo_top12.csv")
pd.DataFrame({"par": pairs, "jaccard_%": np.round(jac, 1),
              "valor_identico_%": np.round(agree, 1)}).to_csv(
    OUT / "reproducibilidad.csv", index=False)
print("Figuras y tablas escritas en", OUT)
