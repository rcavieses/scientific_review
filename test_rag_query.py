#!/usr/bin/env python3
"""Test rápido del sistema RAG"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager
from pipeline.embeddings.embedding_generator import get_embedding_generator

# Cargar índice
print("📚 Cargando índice FAISS...")
vector_db = VectorDBManager(
    index_dir=Path("outputs/rag_index_goc"),
    embedding_dim=384
)
vector_db.load()
print(f"✓ Índice cargado: {vector_db._index.ntotal} chunks\n")

# Inicializar motor de consultas
print("🔧 Inicializando motor RAG...")
embedding_gen = get_embedding_generator(provider="local", verbose=False)
query_engine = RAGQueryEngine(
    vector_db=vector_db,
    embedding_generator=embedding_gen,
    model="claude-haiku-4-5-20251001",
    top_k=5,
    verbose=False
)
print("✓ Motor RAG listo\n")

# Consulta
question = "which are the population parameter for sharks?"
print(f"❓ Consulta: {question}\n")
print("=" * 70)

try:
    result = query_engine.query(question)

    print(f"\n💬 RESPUESTA:\n{result.answer}\n")

    print(f"{'='*70}")
    print(f"\n📊 FUENTES ({result.chunks_used} chunks usados):\n")

    for i, source in enumerate(result.sources, 1):
        authors = ", ".join(source.authors[:2]) if source.authors else "Unknown"
        if source.authors and len(source.authors) > 2:
            authors += " et al."

        print(f"[{i}] {authors} ({source.year or 'N/A'})")
        print(f"    {source.paper_id}")
        print(f"    Relevancia: {source.score*100:.1f}%")
        if source.text:
            preview = source.text[:150].replace('\n', ' ')
            print(f"    Texto: {preview}...")
        print()

    print(f"⏱️  Modelo: {result.model}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
