#!/usr/bin/env python3
"""
Re-genera los embeddings y el índice BM25 (principal + sub-índice de
tablas) usando texto contextualizado (ver pipeline/rag/contextual_text.py):
cada chunk se busca con "<contexto del paper> <texto original>" antepuesto,
pero el texto mostrado al usuario/LLM (ChunkData.text) permanece intacto.

No re-extrae ni re-chunkea PDFs — reutiliza el metadata_store.json ya
validado, solo re-calcula vectores/índice de búsqueda.
"""

import sys
import json
import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.contextual_text import build_search_texts
from pipeline.rag.table_detector import filter_table_chunks
from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.bm25_index import BM25IndexManager
from pipeline.rag.models import ChunkData, ChunkVector
from pipeline.embeddings.embedding_generator import get_embedding_generator

MAIN_INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
TABLE_INDEX_DIR = MAIN_INDEX_DIR / "table_index"
TABLE_THRESHOLD = 1.0


def chunk_data_from_record(rec: dict) -> ChunkData:
    """Reconstruye ChunkData preservando el texto ORIGINAL (para display/citas)."""
    return ChunkData(
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


def rebuild_index(index_dir: Path, records: list, search_texts: dict, eg, label: str):
    print(f"\n🔨 Reconstruyendo índice: {label} ({len(records)} chunks)")
    t0 = time.time()

    texts_to_embed = [search_texts[r["chunk_id"]] for r in records]
    vectors = eg.batch_generate(texts_to_embed, batch_size=64, show_progress=False)
    model_name = eg.get_model_name()
    print(f"   ✓ Embeddings generados en {time.time()-t0:.1f}s")

    if index_dir.exists():
        shutil.rmtree(index_dir)

    db = VectorDBManager(index_dir=index_dir, embedding_dim=384)
    chunk_vectors = [
        ChunkVector(chunk=chunk_data_from_record(r), vector=vec, embedding_model=model_name)
        for r, vec in zip(records, vectors)
    ]
    db.add_chunks(chunk_vectors)
    db.save()
    stats = db.get_stats()
    print(f"   ✓ FAISS: {stats.total_chunks} chunks, {stats.total_papers} papers")

    bm25 = BM25IndexManager(index_dir=index_dir)
    texts_by_id = {r["chunk_id"]: search_texts[r["chunk_id"]] for r in records}
    n = bm25.build_from_texts(texts_by_id)
    bm25.save()
    print(f"   ✓ BM25: {n} chunks indexados")


def main():
    print("📂 Cargando metadata_store principal...")
    with open(MAIN_INDEX_DIR / "metadata_store.json", encoding="utf-8") as f:
        metadata_store = json.load(f)
    print(f"   {len(metadata_store)} chunks totales")

    print("\n🧩 Construyendo textos contextualizados...")
    search_texts = build_search_texts(metadata_store)
    # Muestra de verificación
    sample = next(iter(search_texts.items()))
    print(f"   Ejemplo (chunk_id={sample[0]}):")
    print(f"   {sample[1][:150]}...")

    print("\n📦 Inicializando embedding generator...")
    eg = get_embedding_generator(
        provider="local", model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )

    all_records = list(metadata_store.values())
    rebuild_index(MAIN_INDEX_DIR, all_records, search_texts, eg, "principal")

    print("\n🔍 Filtrando candidatos a tabla para el sub-índice...")
    table_chunks = filter_table_chunks(metadata_store, threshold=TABLE_THRESHOLD)
    table_records = list(table_chunks.values())
    print(f"   {len(table_records)} chunks candidatos")
    rebuild_index(TABLE_INDEX_DIR, table_records, search_texts, eg, "tablas")

    print("\n✅ Reconstrucción con contexto completada.")


if __name__ == "__main__":
    main()
