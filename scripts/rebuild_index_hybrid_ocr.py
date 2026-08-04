#!/usr/bin/env python3
"""
Reconstruye índice FAISS usando OCR híbrido + chunking semántico.

Estrategia OCR en cascada:
  1. Claude Vision (mejor calidad, puede fallar por API/costo)
  2. PaddleOCR (gratuito, confiable, buen balance)
  3. GROBID (fallback rápido)

Uso:
    # Con Claude Vision
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 scripts/rebuild_index_hybrid_ocr.py

    # Sin Claude Vision (PaddleOCR + GROBID)
    pip install paddleocr
    python3 scripts/rebuild_index_hybrid_ocr.py

    # Solo PaddleOCR (más rápido, menos API calls)
    python3 scripts/rebuild_index_hybrid_ocr.py --provider paddle_only
"""

import sys
import os
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pipeline.ocr.hybrid_provider import HybridOCRProvider
from pipeline.ocr.grobid_provider import GrobidProvider
from pipeline.rag.pdf_extractor import GrobidPDFExtractor

# Variables de entorno para semantic chunking
os.environ["CHUNKER_TYPE"] = "semantic"
os.environ["SEMANTIC_THRESHOLD"] = "0.4"
os.environ["MIN_CHUNK_SIZE"] = "50"
os.environ["MAX_CHUNK_SIZE"] = "800"


def create_hybrid_ocr_provider(strategy: str = "full"):
    """
    Crea proveedor OCR híbrido con fallback en cascada.

    Args:
        strategy: "full" (Claude→Paddle→GROBID), "paddle_only" (Paddle→GROBID), etc.
    """
    providers = []

    if strategy in ["full", "claude_first"]:
        try:
            from pipeline.ocr.claude_vision_provider import ClaudeVisionOCRProvider

            if os.getenv("ANTHROPIC_API_KEY"):
                providers.append(("Claude Vision", ClaudeVisionOCRProvider()))
                print("  ✓ Claude Vision disponible (prioridad 1)")
            else:
                print("  ⚠️  Claude Vision sin ANTHROPIC_API_KEY, omitido")
        except Exception as e:
            print(f"  ⚠️  Claude Vision no disponible: {e}")

    if strategy in ["full", "paddle_only", "paddle_first"]:
        try:
            from pipeline.ocr.paddle_provider import PaddleOCRProvider

            providers.append(("PaddleOCR", PaddleOCRProvider(use_gpu=False)))
            priority = "prioridad 2" if providers else "prioridad 1"
            print(f"  ✓ PaddleOCR disponible ({priority})")
        except Exception as e:
            print(f"  ⚠️  PaddleOCR no disponible: {e}")

    # GROBID como fallback siempre
    providers.append(("GROBID", GrobidProvider()))
    priority = f"prioridad {len(providers)}" if len(providers) > 1 else "prioridad 1"
    print(f"  ✓ GROBID disponible ({priority})")

    if not providers:
        raise RuntimeError("No OCR providers disponibles")

    return HybridOCRProvider(
        providers=providers,
        min_chars_threshold=300,  # Al menos 300 chars para considerar éxito
        verbose=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Reconstruir índice FAISS con OCR híbrido + chunking semántico"
    )
    parser.add_argument(
        "--strategy",
        choices=["full", "paddle_only", "claude_first"],
        default="full",
        help="Estrategia de OCR: full (Claude→Paddle→GROBID), paddle_only (Paddle→GROBID), etc.",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="No limpiar índice anterior (continuar indexación)",
    )
    args = parser.parse_args()

    pdf_dir = Path("outputs/PDF_GOC/PDF")
    index_dir = Path("outputs/rag_index_goc")

    print(f"\n{'='*70}")
    print("🚀 RECONSTRUCCIÓN DE ÍNDICE CON OCR HÍBRIDO + CHUNKING SEMÁNTICO")
    print(f"{'='*70}")

    print(f"\n📋 Configuración:")
    print(f"   PDF dir: {pdf_dir}")
    print(f"   Index dir: {index_dir}")
    print(f"   Estrategia OCR: {args.strategy}")
    print(f"   Chunking: semántico (threshold=0.4, 50-800 chars)")

    # Crear proveedor OCR híbrido
    print(f"\n🔧 Inicializando OCR...")
    try:
        hybrid_ocr = create_hybrid_ocr_provider(strategy=args.strategy)
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Crear extractor que usa OCR híbrido
    extractor = GrobidPDFExtractor(grobid_provider=hybrid_ocr)

    # Limpiar índice anterior si es necesario
    if not args.skip_cleanup:
        print(f"\n🧹 Limpiando índice anterior...")
        for f in index_dir.glob("*"):
            f.unlink()
            print(f"   Eliminado: {f.name}")

    # Crear orchestrator
    print(f"\n🔄 Inicializando pipeline...")
    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=pdf_dir,
        index_dir=index_dir,
        extractor=extractor,
        skip_indexed=False,
        verbose=True,
    )

    # Ejecutar pipeline
    print(f"\n{'='*70}")
    print("⏳ PROCESANDO PDFs...")
    print(f"{'='*70}\n")

    result = orchestrator.run()

    # Mostrar resultados
    print(f"\n\n{'='*70}")
    print("✅ COMPLETADO")
    print(f"{'='*70}")

    print(f"\n📊 Resultados:")
    print(f"   Procesados: {result['processed']}")
    print(f"   Saltados: {result['skipped']}")
    print(f"   Fallidos: {len(result['failed'])}")
    print(f"   Total chunks: {result['total_chunks']}")

    if result['total_chunks'] > 0:
        avg_chunk_size = (
            result.get('total_chars', 0) // result['total_chunks']
            if result['total_chunks'] > 0
            else 0
        )
        print(f"   Tamaño promedio chunk: {avg_chunk_size} chars")
        print(f"   Chunks por PDF: {result['total_chunks'] / max(result['processed'], 1):.1f}")

    # Mostrar estadísticas de OCR
    print(f"\n📋 Estadísticas de OCR:")
    hybrid_ocr.print_statistics()

    # Mostrar errores si los hay
    if result['failed']:
        print(f"\n⚠️  PDFs con error:")
        for pdf_path, error in result['failed'][:5]:
            print(f"   • {pdf_path.name}")
            error_str = str(error)[:70]
            print(f"     {error_str}...")

        if len(result['failed']) > 5:
            print(f"   ... y {len(result['failed']) - 5} más")

    print(f"\n{'='*70}")
    print(f"✨ Índice listo en {index_dir}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
