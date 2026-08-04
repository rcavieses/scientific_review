#!/usr/bin/env python3
"""
Pipeline COMPLETO de extracción + chunking + indexación.

Estrategia de máxima extracción:
  1. OCR Híbrido (Claude Vision → GROBID con fallback)
  2. Chunking Semántico (mantiene contexto)
  3. Embeddings BERT (384 dims)
  4. Indexación FAISS

Uso:
    # Con Claude Vision (máxima calidad)
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 scripts/full_extraction_pipeline.py --mode full

    # Solo GROBID (rápido, confiable)
    python3 scripts/full_extraction_pipeline.py --mode grobid

    # Continuación de indexación anterior
    python3 scripts/full_extraction_pipeline.py --mode full --continue
"""

import sys
import os
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pipeline.rag.semantic_chunker import SemanticChunker
from pipeline.rag.generic_ocr_extractor import GenericOCRExtractor
from pipeline.ocr.hybrid_provider import HybridOCRProvider
from pipeline.ocr.grobid_provider import GrobidProvider
from pipeline.ocr.claude_vision_provider import ClaudeVisionOCRProvider
from pipeline.embeddings.embedding_generator import get_embedding_generator


def create_ocr_provider(mode: str = "full"):
    """Crea el proveedor OCR según el modo."""
    providers = []

    # Modo full: Claude Vision + GROBID
    if mode == "full":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                providers.append(("Claude Vision", ClaudeVisionOCRProvider()))
                print("  ✓ Claude Vision (1ª opción)")
            except Exception as e:
                print(f"  ⚠️  Claude Vision: {e}")
        else:
            print("  ⚠️  ANTHROPIC_API_KEY no configurada, omitiendo Claude Vision")

    # GROBID siempre como fallback
    providers.append(("GROBID", GrobidProvider()))
    priority = "2ª opción" if len(providers) > 1 else "1ª opción"
    print(f"  ✓ GROBID ({priority})")

    if not providers:
        raise RuntimeError("No OCR providers disponibles")

    return HybridOCRProvider(
        providers=providers,
        min_chars_threshold=200,
        verbose=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline completo: OCR + Chunking Semántico + Indexación"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "grobid"],
        default="full",
        help="full: Claude Vision + GROBID, grobid: solo GROBID",
    )
    parser.add_argument(
        "--continue",
        action="store_true",
        dest="continue_indexing",
        help="Continuar sin limpiar índice anterior",
    )
    args = parser.parse_args()

    pdf_dir = Path("outputs/PDF_GOC/PDF")
    index_dir = Path("outputs/rag_index_goc")

    print(f"\n{'='*80}")
    print("🚀 PIPELINE COMPLETO: EXTRACCIÓN + CHUNKING SEMÁNTICO + INDEXACIÓN FAISS")
    print(f"{'='*80}\n")

    print(f"📋 CONFIGURACIÓN:")
    print(f"   Directorio de PDFs:  {pdf_dir}")
    print(f"   Número de PDFs:      {len(list(pdf_dir.glob('*.pdf')))}")
    print(f"   Índice FAISS:        {index_dir}")
    print(f"   Modo OCR:            {args.mode}")
    print(f"   Estrategia chunking: Semántico (BERT)")
    print(f"   Modelo embeddings:   all-MiniLM-L6-v2 (384 dims)")

    # Crear OCR
    print(f"\n🔧 PROVEEDORES OCR:")
    ocr_provider = create_ocr_provider(args.mode)

    # Limpiar índice si es necesario
    if not args.continue_indexing:
        print(f"\n🧹 Limpiando índice anterior...")
        for f in index_dir.glob("*"):
            f.unlink()
        print("   ✓ Limpiado")

    # Crear componentes
    print(f"\n⚙️  INICIALIZANDO COMPONENTES:")

    # Extractor genérico con OCR híbrido
    extractor = GenericOCRExtractor(
        ocr_provider=ocr_provider,
        min_page_chars=50,
        verbose=False,
    )
    print("   ✓ Extractor genérico con OCR híbrido")

    # Embedding generator
    embedding_gen = get_embedding_generator(provider="local", verbose=False)
    print("   ✓ Embedding generator (all-MiniLM-L6-v2)")

    # Chunker semántico
    chunker = SemanticChunker(
        embedding_generator=embedding_gen,
        similarity_threshold=0.4,
        min_chunk_size=50,
        max_chunk_size=800,
        verbose=False,
    )
    print("   ✓ Semantic chunker (threshold=0.4)")

    # Orchestrator
    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=pdf_dir,
        index_dir=index_dir,
        extractor=extractor,
        chunker=chunker,
        embedding_generator=embedding_gen,
        skip_indexed=args.continue_indexing,
        verbose=True,
    )
    print("   ✓ Pipeline orchestrator\n")

    # Ejecutar
    print(f"{'='*80}")
    print("⏳ PROCESANDO PDFs...")
    print(f"{'='*80}\n")

    result = orchestrator.run()

    # Mostrar resultados
    print(f"\n\n{'='*80}")
    print("✅ PIPELINE COMPLETADO")
    print(f"{'='*80}\n")

    print(f"📊 RESULTADOS DE INDEXACIÓN:")
    print(f"   PDFs procesados:    {result['processed']:>5}")
    print(f"   PDFs saltados:      {result['skipped']:>5}")
    print(f"   PDFs con error:     {len(result['failed']):>5}")
    print(f"   ───────────────────────────")
    print(f"   Total chunks:       {result['total_chunks']:>5,}")

    if result["total_chunks"] > 0 and result["processed"] > 0:
        avg_chunks = result["total_chunks"] / result["processed"]
        total_chars = result.get("total_chars", 0)
        avg_chunk_size = total_chars / result["total_chunks"] if result["total_chunks"] > 0 else 0

        print(f"\n📈 ESTADÍSTICAS:")
        print(f"   Chunks/PDF:         {avg_chunks:>5.1f}")
        if total_chars:
            print(f"   Total caracteres:   {total_chars:>5,}")
            print(f"   Chars/chunk:        {avg_chunk_size:>5.0f}")

    # Estadísticas de OCR
    print(f"\n🔍 ESTADÍSTICAS DE OCR:")
    ocr_provider.print_statistics()

    # Errores
    if result["failed"]:
        print(f"\n⚠️  PDFS CON ERROR ({len(result['failed'])}):")
        for pdf_path, error in result["failed"][:10]:
            error_str = str(error)[:70]
            print(f"   • {pdf_path.name}")
            print(f"     {error_str}...")

    print(f"\n{'='*80}")
    print(f"✨ ÍNDICE LISTO EN: {index_dir}")
    print(f"   • index.faiss          (índice binario)")
    print(f"   • metadata_store.json  (metadatos + texto)")
    print(f"   • index_config.json    (configuración)")
    print(f"{'='*80}\n")

    print("🧪 PRÓXIMO PASO:")
    print(f"   Reinicia el servidor: python3 scripts/server_rag.py --host 0.0.0.0 --port 8000")
    print(f"   Y prueba en: http://localhost:8000\n")

    return result["total_chunks"] > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
