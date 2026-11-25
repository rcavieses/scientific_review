#!/usr/bin/env python3
"""
Construye un grafo de conocimiento SIN llamadas a LLM, a partir de datos ya
estructurados del proyecto:

  - Los 4 CSV de búsquedas de parámetros (B1, B3, B4, B5)
  - Los metadatos del índice FAISS (paper_id, year, authors)  [solo lectura]
  - Las citas extraídas por el RAG en la columna `citations`

Nodos:  Species | FunctionalGroup | Taxon | Parameter | Paper
Aristas: belongs_to_group | classified_as | has_parameter | cited_in

El grafo se escribe en formato KnowledgeGraphStore, de modo que
`visualizar_grafo.py` y `GraphQueryEngine` puedan consumirlo directamente.
NO toca el índice FAISS ni su metadata_store.json (se abren en modo lectura).

Uso:
    python scripts/build_parameter_graph.py
    python scripts/build_parameter_graph.py --graph-dir outputs/graph_index_parametros
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.graph import Entity, KnowledgeGraphStore, Relation, normalize_entity_id

ROOT = Path(__file__).parent.parent

SEARCHES = {
    "B1": "Atlantis_GOC_parametros_biologicos_BUSQUEDA1.csv",
    "B3": "Atlantis_GOC_parametros_biologicos_BUSQUEDA_3.csv",
    "B4": "Atlantis_GOC_parametros_biologicos_BUSQUEDA_4.csv",
    "B5": "Atlantis_GOC_parametros_biologicos_BUSQUEDA_5.csv",
}

PARAMS = [
    "biomass_mt", "abundance_numbers", "mean_body_size", "max_age",
    "natural_mortality", "Lmax", "Von_bertalanffy_a", "Von_bertalanffy_b",
    "growth_rate", "age_first_maturity", "larval_duration",
    "StartSpawnDayOfYear", "EndSpawnDayOfYear", "IsMigratory",
]

# Cadena taxonómica: cada rango apunta al siguiente
RANKS = ["Genus", "Family", "Order", "Class", "Phylum"]


def norm_key(s: str) -> str:
    """Normaliza un identificador de paper para poder emparejar citas."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_paper_metadata(index_dir: Path) -> dict:
    """Lee (solo lectura) el metadata_store del índice FAISS y agrega por paper."""
    meta_file = index_dir / "metadata_store.json"
    if not meta_file.exists():
        print(f"[warn] No se encontró {meta_file}; el grafo no tendrá nodos Paper.")
        return {}

    with open(meta_file, encoding="utf-8") as f:
        store = json.load(f)

    papers: dict = {}
    for chunk in store.values():
        pid = chunk.get("paper_id")
        if not pid:
            continue
        p = papers.setdefault(pid, {"n_chunks": 0, "year": None, "authors": []})
        p["n_chunks"] += 1
        if p["year"] is None and chunk.get("year"):
            p["year"] = chunk["year"]
        if not p["authors"] and chunk.get("authors"):
            p["authors"] = chunk["authors"][:5]
    return papers


def citation_sources(raw: str) -> list:
    """Devuelve las cadenas `"source": "..."` de una celda `citations`."""
    return re.findall(r'"source"\s*:\s*"([^"]+)"', str(raw))


def resolve_source(src: str, paper_index: dict):
    """
    Resuelve una cadena de cita a un paper_id del índice, o None.

    El RAG escribe cosas como:
        "Herrera2016 - Ciencias Marinas, vol. 37"
        "Anderson2017 / eScholarship_UC_item_0tv9z4fp"
    Se prueban los fragmentos en orden y se devuelve el primero que exista
    en el índice (una misma cita puede nombrar el paper de dos formas).
    """
    head = src.split(" - ")[0]
    for frag in re.split(r"[/,;]| — |[()]", head):
        frag = frag.strip()
        if len(frag) < 4 or frag.isdigit():
            continue
        pid = paper_index.get(norm_key(frag))
        if pid:
            return pid

    # Fallback estilo "Pondella et al. (2001)" → "pondella2001"
    m = re.match(r"\s*([A-Za-zÁ-ÿ\-']{3,})\b.*?\((\d{4})\)", src)
    if m:
        pid = paper_index.get(norm_key(m.group(1) + m.group(2)))
        if pid:
            return pid
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index-dir", default="outputs/rag_index_goc_full",
                    help="Índice FAISS del que leer metadatos de papers (solo lectura)")
    ap.add_argument("--graph-dir", default="outputs/graph_index_parametros",
                    help="Directorio destino del grafo")
    ap.add_argument("--csv-dir", default="data/output")
    args = ap.parse_args()

    graph_dir = ROOT / args.graph_dir
    csv_dir = ROOT / args.csv_dir

    # ── Cargar las búsquedas ──────────────────────────────────────────────
    frames = {}
    for tag, fname in SEARCHES.items():
        path = csv_dir / fname
        if path.exists():
            frames[tag] = pd.read_csv(path)
        else:
            print(f"[warn] Falta {path}; se omite {tag}.")
    if not frames:
        print("[error] No se encontró ningún CSV de búsquedas.")
        return 1

    base = frames[sorted(frames)[0]]
    print(f"Búsquedas cargadas: {', '.join(sorted(frames))}")
    print(f"Especies en el padrón: {len(base)}")

    papers_meta = load_paper_metadata(ROOT / args.index_dir)
    print(f"Papers en el índice   : {len(papers_meta)}")
    paper_index = {norm_key(p): p for p in papers_meta}

    store = KnowledgeGraphStore(graph_dir=graph_dir, verbose=True)

    # ── Nodos de parámetros ───────────────────────────────────────────────
    for p in PARAMS:
        store.add_entity(Entity(
            entity_id=normalize_entity_id("Parameter", p),
            entity_type="Parameter",
            name=p,
            properties={"rol": "parámetro poblacional Atlantis"},
        ))

    # ── Especies, grupos funcionales y taxonomía ──────────────────────────
    n_group_edges = n_taxon_edges = 0
    for _, row in base.iterrows():
        sp_id = normalize_entity_id("Species", row["Species"])
        store.add_entity(Entity(
            entity_id=sp_id,
            entity_type="Species",
            name=row["Species"],
            properties={
                "code": row.get("Code"),
                "group": row.get("Group"),
                **{r.lower(): row.get(r) for r in RANKS if pd.notna(row.get(r))},
            },
        ))

        if pd.notna(row.get("Group")):
            g_id = normalize_entity_id("FunctionalGroup", row["Group"])
            store.add_entity(Entity(
                entity_id=g_id, entity_type="FunctionalGroup", name=row["Group"],
            ))
            store.add_relation(Relation(
                relation_id=f"{sp_id}::belongs_to_group::{g_id}",
                subject_id=sp_id, relation_type="belongs_to_group", object_id=g_id,
            ))
            n_group_edges += 1

        # Cadena taxonómica: Species → Genus → Family → Order → Class → Phylum
        chain = [(sp_id, None)]
        for rank in RANKS:
            val = row.get(rank)
            if pd.isna(val):
                continue
            t_id = normalize_entity_id("Taxon", f"{rank}:{val}")
            store.add_entity(Entity(
                entity_id=t_id, entity_type="Taxon", name=str(val),
                properties={"rank": rank},
            ))
            chain.append((t_id, rank))
        for (a, _), (b, _) in zip(chain, chain[1:]):
            store.add_relation(Relation(
                relation_id=f"{a}::classified_as::{b}",
                subject_id=a, relation_type="classified_as", object_id=b,
            ))
            n_taxon_edges += 1

    # ── Aristas Species → Parameter, con consenso entre búsquedas ─────────
    # values[(species, param)][tag] = valor
    values: dict = defaultdict(dict)
    for tag, df in frames.items():
        for i, row in df.iterrows():
            for p in PARAMS:
                v = row.get(p)
                if pd.notna(v):
                    values[(row["Species"], p)][tag] = str(v).strip()

    n_searches_total = len(frames)
    consensus_counter = Counter()
    for (species, param), by_tag in values.items():
        sp_id = normalize_entity_id("Species", species)
        p_id = normalize_entity_id("Parameter", param)
        n = len(by_tag)
        distinct = len(set(by_tag.values()))
        if n == n_searches_total and distinct == 1:
            consenso = "nucleo_unanime"
        elif n == n_searches_total:
            consenso = "nucleo_discrepante"
        elif n == 1:
            consenso = "unico"
        else:
            consenso = "parcial"
        consensus_counter[consenso] += 1

        store.add_relation(Relation(
            relation_id=f"{sp_id}::has_parameter::{p_id}",
            subject_id=sp_id, relation_type="has_parameter", object_id=p_id,
            confidence=round(n / n_searches_total, 3),
            context_snippet="; ".join(f"{t}={v}" for t, v in sorted(by_tag.items()))[:200],
        ))

    # ── Aristas Species → Paper, desde las citas del RAG ───────────────────
    cited = Counter()
    unmatched = Counter()
    sp_paper = Counter()
    for tag, df in frames.items():
        if "citations" not in df.columns:
            continue
        for _, row in df[df["citations"].notna()].iterrows():
            for src in citation_sources(row["citations"]):
                pid = resolve_source(src, paper_index)
                if pid:
                    sp_paper[(row["Species"], pid)] += 1
                    cited[pid] += 1
                else:
                    unmatched[src.split(" - ")[0].strip()] += 1

    for pid in cited:
        meta = papers_meta.get(pid, {})
        store.add_entity(Entity(
            entity_id=normalize_entity_id("Paper", pid),
            entity_type="Paper", name=pid,
            source_paper_ids=[pid],
            properties={
                "year": meta.get("year"),
                "n_chunks": meta.get("n_chunks"),
                "authors": meta.get("authors", []),
                "n_menciones": cited[pid],
            },
        ))

    for (species, pid), n in sp_paper.items():
        sp_id = normalize_entity_id("Species", species)
        pa_id = normalize_entity_id("Paper", pid)
        store.add_relation(Relation(
            relation_id=f"{sp_id}::cited_in::{pa_id}",
            subject_id=sp_id, relation_type="cited_in", object_id=pa_id,
            source_paper_ids=[pid],
            confidence=1.0,
            context_snippet=f"{n} menciones en las citas del RAG",
        ))

    store.save()

    # ── Reporte ───────────────────────────────────────────────────────────
    stats = store.get_stats()
    print("\n" + "=" * 62)
    print("  GRAFO DE PARÁMETROS (sin LLM)")
    print("=" * 62)
    print(f"  Entidades : {stats.total_entities}")
    for t, c in sorted(stats.entity_type_counts.items()):
        print(f"    {t:<16}: {c}")
    print(f"  Relaciones: {stats.total_relations}")
    for t, c in sorted(stats.relation_type_counts.items()):
        print(f"    {t:<16}: {c}")
    print(f"\n  Aristas especie–parámetro por consenso:")
    for k, v in consensus_counter.most_common():
        print(f"    {k:<20}: {v}")
    total_cit = sum(sp_paper.values()) + sum(unmatched.values())
    if total_cit:
        print(f"\n  Citas resueltas a papers del índice: "
              f"{sum(sp_paper.values())}/{total_cit} "
              f"({100*sum(sp_paper.values())/total_cit:.1f}%)")
        print(f"  Papers citados: {len(cited)} de {len(papers_meta)} indexados")
        if unmatched:
            print(f"  Claves de cita sin match ({len(unmatched)} únicas), top 5:")
            for k, v in unmatched.most_common(5):
                print(f"    - {k[:70]} ({v})")
    print(f"\n  Grafo → {graph_dir}/")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
