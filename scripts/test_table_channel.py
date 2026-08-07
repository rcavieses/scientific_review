#!/usr/bin/env python3
"""Valida el canal de tablas: (1) la query objetivo debe subir al top-8,
(2) una query no relacionada con tablas NO debe contaminarse."""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.bm25_index import BM25IndexManager
from pipeline.rag.hybrid_query_engine import HybridRAGQueryEngine
from pipeline.embeddings.embedding_generator import get_embedding_generator

MAIN_INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
TABLE_INDEX_DIR = MAIN_INDEX_DIR / "table_index"

TARGET_CHUNK = "Amezcua2006_chunk_019"
TARGET_QUERY = "What relative abundance and biomass values were recorded for the most important fish species caught by different fishing gears?"
UNRELATED_QUERY = "What is known about the spawning season of marine species in the Gulf of California?"


def main():
    print("Cargando índices...")
    with open(MAIN_INDEX_DIR / "metadata_store.json", encoding="utf-8") as f:
        metadata_store = json.load(f)

    db = VectorDBManager(index_dir=MAIN_INDEX_DIR, embedding_dim=384)
    db.load()
    bm25 = BM25IndexManager(index_dir=MAIN_INDEX_DIR)
    bm25.load()

    table_db = VectorDBManager(index_dir=TABLE_INDEX_DIR, embedding_dim=384)
    table_db.load()
    table_bm25 = BM25IndexManager(index_dir=TABLE_INDEX_DIR)
    table_bm25.load()

    eg = get_embedding_generator(provider="local", model="all-MiniLM-L6-v2", verbose=False)

    engine = HybridRAGQueryEngine(
        vector_db=db,
        bm25_index=bm25,
        metadata_store=metadata_store,
        embedding_generator=eg,
        model="claude-haiku-4-5-20251001",
        top_k=8,
        candidate_k=30,
        table_vector_db=table_db,
        table_bm25_index=table_bm25,
        table_candidate_k=10,
        verbose=True,
    )

    print("\n" + "=" * 90)
    print("TEST 1: Query objetivo (debe subir el chunk de tabla al top-8)")
    print("=" * 90)
    result1 = engine.query(TARGET_QUERY)
    found = any(s.chunk_id == TARGET_CHUNK for s in result1.sources)
    print(f"\n¿{TARGET_CHUNK} está en el top-8? {'✅ SÍ' if found else '❌ NO'}")
    for i, s in enumerate(result1.sources, 1):
        marker = "  <<<< objetivo" if s.chunk_id == TARGET_CHUNK else ""
        print(f"  [{i}] {s.chunk_id:25s} score={s.score:.3f}{marker}")
    print(f"\nRESPUESTA:\n{result1.answer}\n")

    print("=" * 90)
    print("TEST 2: Query NO relacionada con tablas (no debe contaminarse)")
    print("=" * 90)
    result2 = engine.query(UNRELATED_QUERY)
    table_chunk_ids = set()
    with open(TABLE_INDEX_DIR / "metadata_store.json", encoding="utf-8") as f:
        table_meta = json.load(f)
    table_chunk_ids = {r["chunk_id"] for r in table_meta.values()}

    injected_tables = [s.chunk_id for s in result2.sources if s.chunk_id in table_chunk_ids]
    print(f"\nChunks de tabla inyectados en esta query no-tabular: {len(injected_tables)}")
    for i, s in enumerate(result2.sources, 1):
        is_table = "  [ES CANDIDATO A TABLA]" if s.chunk_id in table_chunk_ids else ""
        print(f"  [{i}] {s.chunk_id:25s} score={s.score:.3f}{is_table}")
    print(f"\nRESPUESTA:\n{result2.answer}")


if __name__ == "__main__":
    main()
