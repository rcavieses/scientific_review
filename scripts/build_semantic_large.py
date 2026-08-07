#!/usr/bin/env python3
"""
Construye un tercer índice: SemanticChunker con ventana grande (1200-2200
chars), comparable a TextChunker (2000), pero con cortes por cambio de tema
en vez de por conteo de caracteres. Mismo corpus de 30 PDFs.
"""

import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.pdf_extractor import PdfPlumberExtractor
from pipeline.rag.semantic_chunker import SemanticChunker
from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.models import ChunkVector
from pipeline.embeddings.embedding_generator import get_embedding_generator

PDF_DIR = PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"
IDX_SEMANTIC_LARGE = PROJECT_ROOT / "outputs" / "test_idx_semantic_large"

N_PDFS = 30


def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))[:N_PDFS]
    print(f"Test corpus: {len(pdfs)} PDFs\n")

    print("Initializing extractor + embeddings...")
    extractor = PdfPlumberExtractor(verbose=False)
    embedding_generator = get_embedding_generator(
        provider="local", model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )

    semantic_chunker_large = SemanticChunker(
        embedding_generator=embedding_generator,
        similarity_threshold=0.15,
        min_chunk_size=1200,
        max_chunk_size=2200,
    )

    if IDX_SEMANTIC_LARGE.exists():
        shutil.rmtree(IDX_SEMANTIC_LARGE)
    db = VectorDBManager(index_dir=IDX_SEMANTIC_LARGE, embedding_dim=384)

    total_chunks = 0
    for i, pdf_path in enumerate(pdfs, 1):
        paper_id = pdf_path.stem
        pages = extractor.extract_by_pages(pdf_path)
        chunks = semantic_chunker_large.chunk_pages(pages, paper_id, str(pdf_path))
        if not chunks:
            continue

        texts = [c.text for c in chunks]
        vectors = embedding_generator.batch_generate(texts, batch_size=64, show_progress=False)
        model_name = embedding_generator.get_model_name()

        chunk_vectors = [
            ChunkVector(chunk=c, vector=vectors[j], embedding_model=model_name)
            for j, c in enumerate(chunks)
        ]
        db.add_chunks(chunk_vectors)
        total_chunks += len(chunk_vectors)
        print(f"  [{i}/{len(pdfs)}] {pdf_path.name}: {len(chunk_vectors)} chunks (total: {total_chunks})", flush=True)

    db.save()
    stats = db.get_stats()
    print(f"\n✓ Index saved: {stats.total_chunks} chunks, {stats.total_papers} papers")


if __name__ == "__main__":
    main()
