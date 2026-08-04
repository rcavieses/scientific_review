#!/usr/bin/env python3
"""
Script para hacer consultas al sistema RAG del Golfo de California.

Uso:
  python scripts/query_rag.py "Your question here"

Ejemplo:
  python scripts/query_rag.py "What is the size range of Huachinango?"
"""

import sys
import os
from pathlib import Path

# Agregar directorio padre al path para importar pipeline
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/query_rag.py \"Tu pregunta aquí\"")
        print("\nEjemplos:")
        print("  python scripts/query_rag.py \"What is the size range of Huachinango?\"")
        print("  python scripts/query_rag.py \"¿Qué especies de arrecifes hay en el GOC?\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    from pipeline.rag.query_engine import RAGQueryEngine
    from pipeline.rag.vector_db import VectorDBManager
    from pipeline.embeddings.embedding_generator import get_embedding_generator

    # Load index
    vdb = VectorDBManager(index_dir=Path("outputs/rag_index_goc"), embedding_dim=384)
    vdb.load()

    # Initialize query engine
    qe = RAGQueryEngine(
        vector_db=vdb,
        embedding_generator=get_embedding_generator(provider="local", verbose=False),
        model="claude-haiku-4-5-20251001"
    )

    # Execute query
    result = qe.query(query)

    print(f"\n{'='*80}")
    print(f"Q: {query}\n")
    print(f"A:\n{result.answer}\n")
    print(f"Sources ({result.chunks_used} chunks):")
    for i, source in enumerate(result.sources, 1):
        authors = ", ".join(source.authors[:2]) if source.authors else "Unknown"
        if source.authors and len(source.authors) > 2:
            authors += " et al."
        print(f"  [{i}] {authors} ({source.year or 'N/A'}) - score: {source.score:.1%}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
