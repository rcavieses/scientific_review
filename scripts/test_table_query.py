#!/usr/bin/env python3
"""Consulta dirigida a validar que los datos de tablas antes corruptas ahora se recuperan."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.embeddings.embedding_generator import get_embedding_generator

IDX = PROJECT_ROOT / "outputs" / "test_idx_semantic_large"
MODEL = "claude-haiku-4-5-20251001"

QUERIES = [
    "What transect and density data were recorded for Lutjanus argentiventris across different habitats and years?",
    "What relative abundance and biomass values were recorded for the most important fish species caught by different fishing gears?",
]


def main():
    embedding_generator = get_embedding_generator(
        provider="local", model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )
    db = VectorDBManager(index_dir=IDX, embedding_dim=384)
    db.load()
    engine = RAGQueryEngine(
        vector_db=db, embedding_generator=embedding_generator,
        model=MODEL, top_k=5, max_tokens=700, min_score=0.15, verbose=False,
    )

    for qi, q in enumerate(QUERIES, 1):
        print("=" * 100)
        print(f"QUESTION {qi}: {q}")
        print("=" * 100)
        r = engine.query(q)
        print(f"Chunks used: {r.chunks_used} | Scores: {[round(s.score,3) for s in r.sources]}")
        print(f"Source papers: {[s.paper_id for s in r.sources]}")
        print(f"\nANSWER:\n{r.answer}\n")


if __name__ == "__main__":
    main()
