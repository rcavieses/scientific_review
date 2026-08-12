#!/usr/bin/env python3
"""
Script de debug para ver exactamente qué contexto se le pasa a Claude.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager
from pipeline.embeddings.embedding_generator import get_embedding_generator

RAG_INDEX_DIR = Path(__file__).parent.parent / "outputs" / "rag_index_goc_full"

# Cargar índice
print("Cargando índice...")
vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
vector_db.load()

print("Cargando embedding generator...")
embedding_gen = get_embedding_generator(provider="local")

# Hacer consulta general
species = "Seriola lalandi"
query_text = f"¿Qué información hay disponible sobre {species} en el Golfo de California?"

print(f"\nConsulta: {query_text}")
print("=" * 80)

# Generar embedding
query_vector = embedding_gen.generate(query_text)
print(f"Embedding generado: {query_vector.shape}")

# Buscar en FAISS
print(f"\nBuscando en índice (top_k=15)...")
results = vector_db.search(query_vector, top_k=15)

print(f"Chunks encontrados: {len(results)}\n")

# Mostrar cada chunk
for i, result in enumerate(results, 1):
    print(f"\n{'='*80}")
    print(f"CHUNK {i}")
    print(f"{'='*80}")
    print(f"Score: {result.score:.4f}")
    print(f"Paper: {result.title or result.paper_id}")
    print(f"Year: {result.year}")
    print(f"Authors: {', '.join(result.authors[:3]) if result.authors else 'N/A'}")
    print(f"Page: {result.page_number}")
    print(f"\nTexto (primeros 500 caracteres):")
    print("-" * 80)
    print(result.text[:500])
    if len(result.text) > 500:
        print(f"... [total: {len(result.text)} caracteres]")

print(f"\n{'='*80}")
print("FIN DEBUG")
