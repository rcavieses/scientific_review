#!/usr/bin/env python3
"""
Construye dos índices sobre el MISMO corpus de 30 PDFs (uno con TextChunker,
otro con SemanticChunker ya corregido) y corre las mismas queries contra
ambos para comparar calidad de respuesta.
"""

import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.pdf_extractor import PdfPlumberExtractor
from pipeline.rag.text_chunker import TextChunker
from pipeline.rag.semantic_chunker import SemanticChunker
from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.models import ChunkVector
from pipeline.embeddings.embedding_generator import get_embedding_generator

PDF_DIR = PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"
IDX_TEXT = PROJECT_ROOT / "outputs" / "test_idx_textchunker"
IDX_SEMANTIC = PROJECT_ROOT / "outputs" / "test_idx_semantic"

N_PDFS = 30


def build_index(index_dir: Path, chunker, extractor, embedding_generator, pdfs):
    if index_dir.exists():
        shutil.rmtree(index_dir)

    db = VectorDBManager(index_dir=index_dir, embedding_dim=384)

    total_chunks = 0
    for i, pdf_path in enumerate(pdfs, 1):
        paper_id = pdf_path.stem
        pages = extractor.extract_by_pages(pdf_path)
        chunks = chunker.chunk_pages(pages, paper_id, str(pdf_path))
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
    print(f"  ✓ Índice guardado: {stats.total_chunks} chunks, {stats.total_papers} papers\n")
    return db


def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))[:N_PDFS]
    print(f"Corpus de prueba: {len(pdfs)} PDFs\n")

    print("📦 Inicializando extractor y embeddings...")
    extractor = PdfPlumberExtractor(verbose=False)
    embedding_generator = get_embedding_generator(
        provider="local", model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )

    text_chunker = TextChunker(chunk_size=2000, overlap=200, min_chunk_size=100, split_on_paragraph=True)
    semantic_chunker = SemanticChunker(
        embedding_generator=embedding_generator,
        similarity_threshold=0.15,
        min_chunk_size=300,
        max_chunk_size=1000,
    )

    print("\n" + "=" * 80)
    print("🔨 Construyendo índice TextChunker (baseline)")
    print("=" * 80)
    build_index(IDX_TEXT, text_chunker, extractor, embedding_generator, pdfs)

    print("=" * 80)
    print("🔨 Construyendo índice SemanticChunker (corregido)")
    print("=" * 80)
    build_index(IDX_SEMANTIC, semantic_chunker, extractor, embedding_generator, pdfs)

    print("=" * 80)
    print("✅ Ambos índices construidos sobre el mismo corpus de 30 PDFs")
    print("=" * 80)


if __name__ == "__main__":
    main()
