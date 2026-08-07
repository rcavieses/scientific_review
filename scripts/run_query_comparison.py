#!/usr/bin/env python3
"""
Corre las mismas queries contra el índice TextChunker y el índice
SemanticChunker (ambos sobre el mismo corpus de 30 PDFs) para comparar
calidad de respuesta.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.embeddings.embedding_generator import get_embedding_generator

IDX_TEXT = PROJECT_ROOT / "outputs" / "test_idx_textchunker"
IDX_SEMANTIC = PROJECT_ROOT / "outputs" / "test_idx_semantic"
IDX_SEMANTIC_LARGE = PROJECT_ROOT / "outputs" / "test_idx_semantic_large"
IDX_SEMANTIC_XL = PROJECT_ROOT / "outputs" / "test_idx_semantic_xl"

QUERIES = [
    "What growth rates have been reported for fish species in the Gulf of California?",
    "What is known about recruitment of reef fish species in the region?",
    "What abundance and biomass patterns have been documented for the species studied?",
    "What information is available about the spawning season of marine species in the Gulf?",
]

MODEL = "claude-haiku-4-5-20251001"


def run_engine(index_dir: Path, embedding_generator):
    db = VectorDBManager(index_dir=index_dir, embedding_dim=384)
    db.load()
    engine = RAGQueryEngine(
        vector_db=db,
        embedding_generator=embedding_generator,
        model=MODEL,
        top_k=5,
        max_tokens=600,
        min_score=0.15,
        verbose=False,
    )
    return engine


def main():
    print("📦 Cargando embeddings + índices...\n")
    embedding_generator = get_embedding_generator(
        provider="local", model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )

    engine_text = run_engine(IDX_TEXT, embedding_generator)
    engine_semantic = run_engine(IDX_SEMANTIC, embedding_generator)
    engine_semantic_large = run_engine(IDX_SEMANTIC_LARGE, embedding_generator)
    engine_semantic_xl = run_engine(IDX_SEMANTIC_XL, embedding_generator)

    results = []

    for qi, question in enumerate(QUERIES, 1):
        print("=" * 100)
        print(f"QUESTION {qi}: {question}")
        print("=" * 100)

        print("\n🔹 TextChunker (chunks ~2000 chars, character-based cuts):")
        try:
            r1 = engine_text.query(question)
            print(f"   Chunks used: {r1.chunks_used} | Scores: {[round(s.score,3) for s in r1.sources]}")
            print(f"\n   ANSWER:\n   {r1.answer}\n")
        except Exception as e:
            r1 = None
            print(f"   ✗ ERROR: {type(e).__name__}: {e}\n")

        print("🔸 SemanticChunker SMALL (300-1000 chars, topic-change cuts):")
        try:
            r2 = engine_semantic.query(question)
            print(f"   Chunks used: {r2.chunks_used} | Scores: {[round(s.score,3) for s in r2.sources]}")
            print(f"\n   ANSWER:\n   {r2.answer}\n")
        except Exception as e:
            r2 = None
            print(f"   ✗ ERROR: {type(e).__name__}: {e}\n")

        print("🔶 SemanticChunker LARGE (1200-2200 chars, topic-change cuts):")
        try:
            r3 = engine_semantic_large.query(question)
            print(f"   Chunks used: {r3.chunks_used} | Scores: {[round(s.score,3) for s in r3.sources]}")
            print(f"\n   ANSWER:\n   {r3.answer}\n")
        except Exception as e:
            r3 = None
            print(f"   ✗ ERROR: {type(e).__name__}: {e}\n")

        print("🔷 SemanticChunker XL (2000-3500 chars, topic-change cuts):")
        try:
            r4 = engine_semantic_xl.query(question)
            print(f"   Chunks used: {r4.chunks_used} | Scores: {[round(s.score,3) for s in r4.sources]}")
            print(f"\n   ANSWER:\n   {r4.answer}\n")
        except Exception as e:
            r4 = None
            print(f"   ✗ ERROR: {type(e).__name__}: {e}\n")

        results.append((question, r1, r2, r3, r4))
        print()

    print("=" * 100)
    print("✅ Comparison complete")
    print("=" * 100)


if __name__ == "__main__":
    main()
