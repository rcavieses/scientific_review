#!/usr/bin/env python3
"""Valida la fusión híbrida contra el caso diagnosticado: chunk con datos
de tabla real de Amezcua2006, enterrado en rank 42 en búsqueda puramente
semántica."""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.bm25_index import BM25IndexManager
from pipeline.rag.hybrid_query_engine import HybridRAGQueryEngine
from pipeline.embeddings.embedding_generator import get_embedding_generator

INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"

QUERY = "What relative abundance and biomass values were recorded for the most important fish species caught by different fishing gears?"


def main():
    print("Cargando índices...")
    with open(INDEX_DIR / "metadata_store.json", encoding="utf-8") as f:
        metadata_store = json.load(f)

    db = VectorDBManager(index_dir=INDEX_DIR, embedding_dim=384)
    db.load()

    bm25 = BM25IndexManager(index_dir=INDEX_DIR)
    bm25.load()

    # Identificar dinámicamente el chunk_id real con los datos de la tabla
    # (contiene nombres de especies + valores numéricos de Amezcua2006)
    target_chunk_id = None
    for rec in metadata_store.values():
        if rec.get("paper_id") == "Amezcua2006" and "Eucinostomus" in rec.get("text", ""):
            target_chunk_id = rec["chunk_id"]
            break
    print(f"Chunk objetivo (datos reales de la tabla): {target_chunk_id}")

    eg = get_embedding_generator(provider="local", model="all-MiniLM-L6-v2", verbose=False)

    # Primero: ¿en qué rank encuentra BM25 solo el chunk correcto?
    bm25_hits = bm25.search(QUERY, top_k=20)
    print("\n=== Top 10 BM25 puro ===")
    for i, (chunk_id, score) in enumerate(bm25_hits[:10], 1):
        marker = "  <<<< chunk con los datos reales" if chunk_id == target_chunk_id else ""
        print(f"[{i:2d}] score={score:.2f}  {chunk_id}{marker}")

    # Ahora: motor híbrido completo
    engine = HybridRAGQueryEngine(
        vector_db=db,
        bm25_index=bm25,
        metadata_store=metadata_store,
        embedding_generator=eg,
        model="claude-haiku-4-5-20251001",
        top_k=5,
        candidate_k=30,
        verbose=True,
    )

    print("\n=== Consulta híbrida completa ===")
    result = engine.query(QUERY)
    print(f"\nChunks usados: {result.chunks_used}")
    for i, s in enumerate(result.sources, 1):
        marker = "  <<<< chunk con los datos reales" if s.chunk_id == target_chunk_id else ""
        print(f"  [{i}] {s.paper_id:20s} p.{s.page_number}  score={s.score:.3f}{marker}")

    print(f"\nRESPUESTA:\n{result.answer}")


if __name__ == "__main__":
    main()
