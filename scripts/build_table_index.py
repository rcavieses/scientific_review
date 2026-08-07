#!/usr/bin/env python3
"""
Construye un sub-índice (FAISS + BM25) restringido solo a chunks que
parecen tablas de datos, filtrados de metadata_store.json con
table_detector.py. No re-extrae ni re-chunkea PDFs — reutiliza el texto
ya validado del índice principal, solo re-genera embeddings para el
subconjunto filtrado (rápido: ~1000 chunks).
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.table_detector import filter_table_chunks, table_score
from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.bm25_index import BM25IndexManager
from pipeline.rag.models import ChunkData, ChunkVector
from pipeline.embeddings.embedding_generator import get_embedding_generator

MAIN_INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
TABLE_INDEX_DIR = MAIN_INDEX_DIR / "table_index"
THRESHOLD = 1.0


def main():
    print("📂 Cargando metadata_store principal...")
    with open(MAIN_INDEX_DIR / "metadata_store.json", encoding="utf-8") as f:
        metadata_store = json.load(f)
    print(f"   {len(metadata_store)} chunks totales")

    print(f"\n🔍 Filtrando candidatos a tabla (umbral={THRESHOLD})...")
    table_chunks = filter_table_chunks(metadata_store, threshold=THRESHOLD)
    print(f"   {len(table_chunks)} chunks candidatos ({len(table_chunks)/len(metadata_store)*100:.1f}% del total)")

    if not table_chunks:
        print("❌ No se encontraron chunks candidatos a tabla. Abortando.")
        return

    print("\n📦 Inicializando embedding generator...")
    eg = get_embedding_generator(
        provider="local", model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )

    print("\n🔨 Re-generando embeddings para el subconjunto...")
    t0 = time.time()
    records = list(table_chunks.values())
    texts = [r["text"] for r in records]
    vectors = eg.batch_generate(texts, batch_size=64, show_progress=False)
    model_name = eg.get_model_name()
    print(f"   ✓ {len(records)} embeddings generados en {time.time()-t0:.1f}s")

    print("\n💾 Construyendo sub-índice FAISS...")
    if TABLE_INDEX_DIR.exists():
        import shutil
        shutil.rmtree(TABLE_INDEX_DIR)

    db = VectorDBManager(index_dir=TABLE_INDEX_DIR, embedding_dim=384)
    chunk_vectors = []
    for rec, vec in zip(records, vectors):
        chunk_data = ChunkData(
            chunk_id=rec["chunk_id"],
            paper_id=rec["paper_id"],
            text=rec["text"],
            chunk_index=rec["chunk_index"],
            page_number=rec["page_number"],
            char_start=rec.get("char_start", -1),
            char_end=rec.get("char_end", -1),
            total_chunks=rec.get("total_chunks", 0),
            source_pdf=rec["source_pdf"],
            title=rec.get("title"),
            authors=rec.get("authors"),
            year=rec.get("year"),
            doi=rec.get("doi"),
        )
        chunk_vectors.append(ChunkVector(chunk=chunk_data, vector=vec, embedding_model=model_name))

    db.add_chunks(chunk_vectors)
    db.save()
    stats = db.get_stats()
    print(f"   ✓ FAISS: {stats.total_chunks} chunks, {stats.total_papers} papers")

    print("\n🔨 Construyendo sub-índice BM25...")
    bm25 = BM25IndexManager(index_dir=TABLE_INDEX_DIR)
    n = bm25.build_from_metadata_store(table_chunks)
    bm25.save()
    print(f"   ✓ BM25: {n} chunks indexados")

    print(f"\n✅ Sub-índice de tablas guardado en {TABLE_INDEX_DIR}")


if __name__ == "__main__":
    main()
