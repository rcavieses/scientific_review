#!/usr/bin/env python3
"""
CLI interactivo para consultas RAG.

Uso:
    python3 rag_cli.py "tu pregunta aquí"

O modo interactivo:
    python3 rag_cli.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager
from pipeline.embeddings.embedding_generator import get_embedding_generator


def init_rag():
    """Inicializa el motor RAG."""
    print("📚 Cargando índice FAISS...")
    vector_db = VectorDBManager(
        index_dir=Path("outputs/rag_index_goc"),
        embedding_dim=384
    )
    vector_db.load()
    print(f"✓ Índice: {vector_db._index.ntotal} chunks\n")

    embedding_gen = get_embedding_generator(provider="local", verbose=False)
    query_engine = RAGQueryEngine(
        vector_db=vector_db,
        embedding_generator=embedding_gen,
        model="claude-haiku-4-5-20251001",
        top_k=5,
        verbose=False
    )
    return query_engine


def format_result(result):
    """Formatea y muestra el resultado."""
    print(f"\n{'='*70}")
    print("💬 RESPUESTA:\n")
    print(result.answer)

    print(f"\n{'='*70}")
    print(f"📊 FUENTES ({result.chunks_used} chunks):\n")

    for i, source in enumerate(result.sources, 1):
        authors = ", ".join(source.authors[:2]) if source.authors else "Unknown"
        if source.authors and len(source.authors) > 2:
            authors += " et al."

        print(f"[{i}] {authors} ({source.year or 'N/A'})")
        print(f"    {source.paper_id} | Score: {source.score*100:.1f}%")
        if source.text:
            preview = source.text[:120].replace('\n', ' ')
            print(f"    \"{preview}...\"")
        print()

    print(f"{'='*70}\n")


def main():
    print("🚀 RAG CLI - Consultas sobre Golfo de California\n")

    query_engine = init_rag()

    # Si hay argumento en línea de comandos, usarlo
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"❓ Consulta: {question}\n")
        try:
            result = query_engine.query(question)
            format_result(result)
        except Exception as e:
            print(f"❌ Error: {e}")
        return

    # Modo interactivo
    print("📝 Modo interactivo (escribe 'exit' para salir)\n")
    while True:
        try:
            question = input("❓ Pregunta: ").strip()

            if question.lower() in ["exit", "quit", "q"]:
                print("👋 Adiós!")
                break

            if not question:
                print("Por favor ingresa una pregunta.\n")
                continue

            print("\n⏳ Procesando...\n")
            result = query_engine.query(question)
            format_result(result)

        except KeyboardInterrupt:
            print("\n👋 Adiós!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


if __name__ == "__main__":
    main()
