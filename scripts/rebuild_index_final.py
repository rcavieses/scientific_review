#!/usr/bin/env python3
"""
Reconstrucción FINAL del índice RAG con chunking semántico completo.

Optimizado para máxima extracción y calidad de chunks.
"""

import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.semantic_chunker import SemanticChunker
from pipeline.rag.pdf_extractor import GrobidPDFExtractor, PdfPlumberExtractor
from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.models import ChunkData, ChunkVector
from pipeline.embeddings.embedding_generator import get_embedding_generator

import logging

# Configuración
PDF_DIR = PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"
INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
LOGS_DIR = PROJECT_ROOT / "outputs" / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "rebuild_final.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 80)
    logger.info("🔨 RECONSTRUCCIÓN FINAL DE ÍNDICE CON CHUNKING SEMÁNTICO")
    logger.info("=" * 80)

    # Paso 1: Crear generador de embeddings
    logger.info("\n1️⃣  Inicializando embeddings (all-MiniLM-L6-v2)...")
    embedding_generator = get_embedding_generator(
        provider="local",
        model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )
    logger.info("   ✓ Embeddings listos (384 dimensiones)")

    # Paso 2: Crear semantic chunker
    logger.info("\n2️⃣  Configurando chunker semántico...")
    chunker = SemanticChunker(
        embedding_generator=embedding_generator,
        similarity_threshold=0.5,
        min_chunk_size=300,
        max_chunk_size=1000,
        verbose=True,
    )
    logger.info("   ✓ Chunker semántico listo")

    # Paso 3: Crear extractores
    logger.info("\n3️⃣  Configurando extractores (GROBID + pdfplumber)...")
    grobid = GrobidPDFExtractor()
    pdfplumber = PdfPlumberExtractor()
    logger.info("   ✓ Extractores listos")

    # Paso 4: Crear base de datos vectorial
    logger.info("\n4️⃣  Creando índice FAISS...")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vector_db = VectorDBManager(
        index_dir=INDEX_DIR,
        embedding_dim=384,
        index_type="FlatIP",
        verbose=True,
    )
    logger.info("   ✓ Índice creado")

    # Paso 5: Procesar todos los PDFs
    logger.info("\n5️⃣  Procesando 433 PDFs...")
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    total_chunks = 0
    failed = []

    for i, pdf_path in enumerate(pdfs, 1):
        try:
            # Intentar con GROBID primero
            try:
                pages = grobid.extract_pdf(pdf_path)
            except Exception as e:
                logger.warning(f"  GROBID falló para {pdf_path.name}, usando pdfplumber")
                pages = pdfplumber.extract_by_pages(pdf_path)

            # Chunkear semánticamente
            chunks = chunker.chunk_pages(pages, pdf_path.stem, str(pdf_path))

            if not chunks:
                continue

            # Generar embeddings
            texts = [c.text for c in chunks]
            vectors = embedding_generator.batch_generate(texts)

            # Crear ChunkVectors
            chunk_vectors = [
                ChunkVector(chunk=chunk, vector=vectors[j], embedding_model="all-MiniLM-L6-v2")
                for j, chunk in enumerate(chunks)
            ]

            # Agregar al índice
            vector_db.add_chunks(chunk_vectors)
            total_chunks += len(chunk_vectors)

            # Log cada 50 PDFs
            if i % 50 == 0:
                logger.info(f"   [{i:3d}/433] {total_chunks:5d} chunks acumulados")

        except Exception as e:
            logger.error(f"   ❌ Error con {pdf_path.name}: {e}")
            failed.append(pdf_path.name)

    # Paso 6: Guardar índice
    logger.info("\n6️⃣  Guardando índice...")
    vector_db.save()
    logger.info("   ✓ Índice guardado")

    # Resumen
    logger.info("\n" + "=" * 80)
    logger.info("📊 RESUMEN FINAL")
    logger.info("=" * 80)
    logger.info(f"  PDFs procesados: {len(pdfs) - len(failed)}/{len(pdfs)}")
    logger.info(f"  Chunks totales: {total_chunks}")
    logger.info(f"  Tamaño promedio chunk: {total_chunks / (len(pdfs) - len(failed)):.0f} chars")

    if failed:
        logger.warning(f"  PDFs fallidos: {len(failed)}")
        for pdf_name in failed:
            logger.warning(f"    - {pdf_name}")

    logger.info(f"\n✅ Índice completado en: {INDEX_DIR}")
    logger.info(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
