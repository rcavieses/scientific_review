#!/usr/bin/env python3
"""
FASE 1: Reconstrucción optimizada del índice RAG

Objetivos:
  1. Extracción completa con GROBID (fallback a pdfplumber)
  2. Chunking semántico intelligent
  3. Generación de embeddings con all-MiniLM-L6-v2
  4. Indexación FAISS con metadatos

Salida:
  - outputs/rag_index_goc_full/
    - index.faiss
    - metadata_store.json
    - index_config.json
  - logs/phase_1_rebuild.log
  - reports/phase_1_rebuild_stats.json
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pipeline.rag.semantic_chunker import SemanticChunker
from pipeline.rag.text_chunker import TextChunker
from pipeline.embeddings.embedding_generator import get_embedding_generator
from pipeline.ocr.hybrid_provider import HybridOCRProvider
from pipeline.ocr.grobid_provider import GrobidProvider

# Configuración
PDF_DIR = PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"
INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
LOGS_DIR = PROJECT_ROOT / "outputs" / "logs"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

# Parámetros estándar (de Fase 0)
CHUNKING_PARAMS = {
    "chunk_size": 2000,
    "overlap": 200,
    "min_chunk_size": 100,
    "split_on_paragraph": True,
}

EMBEDDING_PARAMS = {
    "model": "all-MiniLM-L6-v2",
    "provider": "local",
    "cache_folder": str(PROJECT_ROOT / "models" / "embeddings"),
}

# Logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "phase_1_rebuild.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def create_ocr_provider():
    """Crea proveedor OCR híbrido: GROBID + fallback a pdfplumber."""
    logger.info("Configurando proveedor OCR...")

    grobid = GrobidProvider()
    logger.info("  ✓ GROBID (primario)")

    # Nota: PDFPlumberExtractor se usa automáticamente como fallback en RAGPipelineOrchestrator
    logger.info("  ✓ pdfplumber (fallback automático)")

    return grobid


def create_chunker():
    """Crea TextChunker con parámetros estándar."""
    logger.info("Configurando chunker de texto...")

    chunker = TextChunker(
        chunk_size=CHUNKING_PARAMS["chunk_size"],
        overlap=CHUNKING_PARAMS["overlap"],
        min_chunk_size=CHUNKING_PARAMS["min_chunk_size"],
        split_on_paragraph=CHUNKING_PARAMS["split_on_paragraph"],
        verbose=False,
    )

    logger.info(
        f"  ✓ TextChunker: {CHUNKING_PARAMS['chunk_size']} chars, "
        f"{CHUNKING_PARAMS['overlap']} chars overlap"
    )

    return chunker


def create_embedding_generator():
    """Crea generador de embeddings local."""
    logger.info("Configurando generador de embeddings...")

    generator = get_embedding_generator(
        provider=EMBEDDING_PARAMS["provider"],
        model=EMBEDDING_PARAMS["model"],
        cache_folder=EMBEDDING_PARAMS["cache_folder"],
        verbose=False,
    )

    logger.info(f"  ✓ {EMBEDDING_PARAMS['model']} (384 dimensiones)")

    return generator


def rebuild_index():
    """Reconstruye índice completo con parámetros optimizados."""
    logger.info("\n" + "=" * 80)
    logger.info("FASE 1: RECONSTRUCCIÓN DE ÍNDICE")
    logger.info("=" * 80)

    # Información de entrada
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    logger.info(f"\n📋 ENTRADA:")
    logger.info(f"   PDFs encontrados: {len(pdf_files)}")
    logger.info(f"   Tamaño total: {sum(p.stat().st_size for p in pdf_files) / 1024**2:.1f} MB")
    logger.info(f"   Directorio de índice: {INDEX_DIR}")

    # Crear componentes
    logger.info(f"\n🔧 CONFIGURACIÓN:")
    chunker = create_chunker()
    embedding_generator = create_embedding_generator()

    # Crear orquestador
    logger.info("\n📦 Inicializando pipeline...")

    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=PDF_DIR,
        index_dir=INDEX_DIR,
        chunker=chunker,
        embedding_generator=embedding_generator,
        skip_indexed=False,  # Procesar todos sin excepción
        batch_size=64,
        verbose=True,
    )

    # Ejecutar pipeline
    logger.info("\n🚀 Ejecutando extracción + chunking + indexación...")
    logger.info("   (Esto puede tomar varios minutos para 433 PDFs)")

    start_time = time.time()
    result = orchestrator.run()
    elapsed_time = time.time() - start_time

    return result, elapsed_time


def save_rebuild_report(result: Dict, elapsed_time: float, pdf_count: int):
    """Guarda reporte detallado de la reconstrucción."""
    logger.info("\n" + "=" * 80)
    logger.info("FASE 1.1: Guardando reporte de reconstrucción")
    logger.info("=" * 80)

    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "rebuild_index_optimized",
        "duration_seconds": elapsed_time,
        "duration_minutes": round(elapsed_time / 60, 2),
        "input": {
            "pdf_count": pdf_count,
            "pdf_directory": str(PDF_DIR),
        },
        "output": {
            "index_directory": str(INDEX_DIR),
            "processed_pdfs": result.get("processed", 0),
            "skipped_pdfs": result.get("skipped", 0),
            "failed_pdfs": len(result.get("failed", [])),
            "total_chunks": result.get("total_chunks", 0),
            "index_stats": result.get("index_stats", {}),
        },
        "parameters": {
            "chunking": CHUNKING_PARAMS,
            "embeddings": EMBEDDING_PARAMS,
        },
        "performance": {
            "pdfs_per_second": pdf_count / elapsed_time if elapsed_time > 0 else 0,
            "chunks_per_second": result.get("total_chunks", 0) / elapsed_time if elapsed_time > 0 else 0,
        },
        "status": "success" if result.get("failed", []) == [] else "completed_with_errors",
    }

    if result.get("failed"):
        report["failed_pdfs"] = result["failed"]

    report_path = REPORTS_DIR / "phase_1_rebuild_stats.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"  Reporte guardado: {report_path}")

    return report


def print_summary(result: Dict, elapsed_time: float, pdf_count: int, report: Dict):
    """Imprime resumen formateado de la ejecución."""
    logger.info(f"\n{'=' * 80}")
    logger.info("📊 RESUMEN DE FASE 1")
    logger.info(f"{'=' * 80}")

    logger.info(f"\n  ⏱️  TIEMPO:")
    logger.info(f"     {elapsed_time:.1f} segundos ({elapsed_time / 60:.1f} minutos)")
    logger.info(f"     {report['performance']['pdfs_per_second']:.2f} PDFs/segundo")

    logger.info(f"\n  📈 ESTADÍSTICAS:")
    logger.info(f"     PDFs procesados: {result.get('processed', 0)}/{pdf_count}")
    logger.info(f"     Chunks totales: {result.get('total_chunks', 0)}")
    logger.info(f"     Tamaño promedio chunk: {result.get('index_stats', {}).get('avg_chunk_size', 0):.0f} chars")

    if result.get("failed"):
        logger.warning(f"\n  ⚠️  ERRORES:")
        for pdf_name in result.get("failed", []):
            logger.warning(f"     - {pdf_name}")
    else:
        logger.info(f"\n  ✅ Sin errores")

    logger.info(f"\n  📂 ÍNDICE CREADO:")
    logger.info(f"     {INDEX_DIR}")
    logger.info(f"     Archivos:")
    for file in sorted(INDEX_DIR.glob("*")):
        size_mb = file.stat().st_size / 1024**2
        logger.info(f"       - {file.name}: {size_mb:.1f} MB")

    logger.info(f"\n  → Próximo paso: python3 scripts/phase_2_enrich_metadata.py")
    logger.info(f"{'=' * 80}\n")


def main():
    logger.info(f"\n{'=' * 80}")
    logger.info("🔨 FASE 1: RECONSTRUCCIÓN OPTIMIZADA DE ÍNDICE RAG")
    logger.info(f"{'=' * 80}")

    pdf_count = len(list(PDF_DIR.glob("*.pdf")))

    if pdf_count == 0:
        logger.error(f"❌ No hay PDFs en {PDF_DIR}")
        sys.exit(1)

    # Ejecutar reconstrucción
    result, elapsed_time = rebuild_index()

    # Guardar reporte
    report = save_rebuild_report(result, elapsed_time, pdf_count)

    # Imprimir resumen
    print_summary(result, elapsed_time, pdf_count, report)


if __name__ == "__main__":
    main()
