#!/usr/bin/env python3
"""
Reconstruye índice FAISS usando OCR híbrido (Claude Vision → GROBID).

Estrategia simple pero efectiva:
  1. Claude Vision (excelente calidad si tienes API key)
  2. GROBID (fallback rápido)

Uso:
    # Con Claude Vision
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 scripts/rebuild_index_hybrid_simple.py

    # Solo GROBID (rápido)
    python3 scripts/rebuild_index_hybrid_simple.py --strategy grobid_only
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

# Configurar chunking semántico
os.environ["CHUNKER_TYPE"] = "semantic"
os.environ["SEMANTIC_THRESHOLD"] = "0.4"
os.environ["MIN_CHUNK_SIZE"] = "50"
os.environ["MAX_CHUNK_SIZE"] = "800"


def create_hybrid_ocr(strategy: str = "full"):
    """Crea proveedor OCR híbrido."""
    providers = []

    # Opción 1: Claude Vision
    if strategy in ["full", "claude_first"]:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                from pipeline.ocr.claude_vision_provider import ClaudeVisionOCRProvider
                providers.append(("Claude Vision", ClaudeVisionOCRProvider()))
                print("  ✓ Claude Vision (prioridad 1)")
            except Exception as e:
                print(f"  ⚠️  Claude Vision: {e}")
        else:
            print("  ⚠️  Claude Vision: ANTHROPIC_API_KEY no configurada")

    # Opción 2: GROBID (siempre disponible)
    providers.append(("GROBID", GrobidProvider()))
    priority = "prioridad 2" if len(providers) > 1 else "prioridad 1"
    print(f"  ✓ GROBID ({priority})")

    if not providers:
        raise RuntimeError("No OCR providers disponibles")

    return HybridOCRProvider(
        providers=providers,
        min_chars_threshold=200,  # Umbral bajo para GROBID
        verbose=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Reconstruir índice con OCR híbrido + chunking semántico"
    )
    parser.add_argument(
        "--strategy",
        choices=["full", "grobid_only"],
        default="full",
        help="full: Claude→GROBID, grobid_only: solo GROBID",
    )
    parser.add_argument(
        "--continue",
        action="store_true",
        dest="continue_indexing",
        help="Continuar indexación (no limpiar índice anterior)",
    )
    args = parser.parse_args()

    pdf_dir = Path("outputs/PDF_GOC/PDF")
    index_dir = Path("outputs/rag_index_goc")

    print(f"\n{'='*70}")
    print("🚀 RECONSTRUCCIÓN: OCR HÍBRIDO + CHUNKING SEMÁNTICO")
    print(f"{'='*70}\n")

    print(f"📋 Configuración:")
    print(f"   PDFs: {pdf_dir}")
    print(f"   Índice: {index_dir}")
    print(f"   Estrategia: {args.strategy}")
    print(f"   Chunking: semántico (0.4 threshold, 50-800 chars)\n")

    # Crear OCR híbrido
    print("🔧 OCR Providers:")
    hybrid = create_hybrid_ocr(args.strategy)

    # Limpiar índice si es necesario
    if not args.continue_indexing:
        print(f"\n🧹 Limpiando índice anterior...")
        for f in index_dir.glob("*"):
            f.unlink()

    # Crear extractor
    extractor = GrobidPDFExtractor(grobid_provider=hybrid)

    # Crear orchestrator
    print(f"\n🔄 Inicializando pipeline...")
    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=pdf_dir,
        index_dir=index_dir,
        extractor=extractor,
        skip_indexed=False,
        verbose=True,
    )

    # Ejecutar
    print(f"\n{'='*70}\n")
    result = orchestrator.run()

    # Resultados
    print(f"\n\n{'='*70}")
    print("✅ COMPLETADO")
    print(f"{'='*70}\n")

    print(f"📊 Resultados:")
    print(f"   Procesados: {result['processed']:>4}")
    print(f"   Saltados:   {result['skipped']:>4}")
    print(f"   Fallidos:   {len(result['failed']):>4}")
    print(f"   Chunks:     {result['total_chunks']:>4}")

    if result["total_chunks"] > 0:
        avg = result["total_chunks"] / max(result["processed"], 1)
        print(f"   Promedio:   {avg:>4.1f} chunks/PDF")

    # Estadísticas de OCR
    print(f"\n📊 OCR Providers usados:")
    hybrid.print_statistics()

    if result["failed"]:
        print(f"\n⚠️  Errores ({len(result['failed'])} PDFs):")
        for pdf, err in result["failed"][:3]:
            print(f"   • {pdf.name}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
