#!/usr/bin/env python3
"""
Construye el índice BM25 a partir del metadata_store.json ya existente
(no re-extrae ni re-chunkea PDFs: reutiliza los chunks ya validados del
índice FAISS de producción).
"""

import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.bm25_index import BM25IndexManager

INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"


def main():
    print("📂 Cargando metadata_store...")
    with open(INDEX_DIR / "metadata_store.json", encoding="utf-8") as f:
        metadata_store = json.load(f)
    print(f"   {len(metadata_store)} chunks cargados")

    print("\n🔨 Construyendo índice BM25...")
    t0 = time.time()
    bm25 = BM25IndexManager(index_dir=INDEX_DIR)
    n = bm25.build_from_metadata_store(metadata_store)
    elapsed = time.time() - t0
    print(f"   ✓ {n} chunks indexados en {elapsed:.1f}s")

    bm25.save()
    print(f"   ✓ Guardado en {INDEX_DIR / BM25IndexManager.BM25_FILE}")


if __name__ == "__main__":
    main()
