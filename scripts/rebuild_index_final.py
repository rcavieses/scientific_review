#!/usr/bin/env python3
"""
Reconstruye índice FAISS con GROBID + chunking semántico.

Pipeline completo:
  1. Extrae PDFs con GROBID
  2. Aplica chunking semántico (mantiene contexto)
  3. Genera embeddings con BERT
  4. Indexa en FAISS

Uso:
    python3 scripts/rebuild_index_final.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pipeline.rag.semantic_chunker import SemanticChunker
from pipeline.rag.pdf_extractor import GrobidPDFExtractor
from pipeline.embeddings.embedding_generator import get_embedding_generator


def main():
    pdf_dir = Path("outputs/PDF_GOC/PDF")
    index_dir = Path("outputs/rag_index_goc")

    print(f"\n{'='*70}")
    print("🚀 PIPELINE FINAL: GROBID + CHUNKING SEMÁNTICO + INDEXACIÓN")
    print(f"{'='*70}\n")

    print(f"📋 Configuración:")
    print(f"   PDFs: {pdf_dir} ({len(list(pdf_dir.glob('*.pdf')))} archivos)")
    print(f"   Índice: {index_dir}")
    print(f"   Extractor: GROBID")
    print(f"   Chunking: Semántico (BERT)")
    print(f"   Modelo: all-MiniLM-L6-v2 (384 dims)\n")

    # Limpiar índice anterior
    print("🧹 Limpiando índice anterior...")
    for f in index_dir.glob("*"):
        f.unlink()
    print("   ✓ Limpiado\n")

    # Crear componentes
    print("🔧 Inicializando componentes...")

    # 1. Extractor: GROBID
    extractor = GrobidPDFExtractor(verbose=False)
    print("   ✓ GROBID extractor")

    # 2. Embedding generator
    embedding_gen = get_embedding_generator(provider="local", verbose=False)
    print("   ✓ Embedding generator (BERT)")

    # 3. Chunker: Semántico
    chunker = SemanticChunker(
        embedding_generator=embedding_gen,
        similarity_threshold=0.4,
        min_chunk_size=50,
        max_chunk_size=800,
        verbose=False,
    )
    print("   ✓ Semantic chunker")

    # Crear orchestrator con componentes personalizados
    print("\n🔄 Iniciando pipeline...")
    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=pdf_dir,
        index_dir=index_dir,
        extractor=extractor,
        chunker=chunker,
        embedding_generator=embedding_gen,
        skip_indexed=False,
        verbose=True,
    )

    print(f"\n{'='*70}\n")

    # Ejecutar
    result = orchestrator.run()

    # Resultados
    print(f"\n\n{'='*70}")
    print("✅ INDEXACIÓN COMPLETADA")
    print(f"{'='*70}\n")

    print(f"📊 Resultados:")
    print(f"   PDFs procesados: {result['processed']}")
    print(f"   PDFs saltados:   {result['skipped']}")
    print(f"   PDFs con error:  {len(result['failed'])}")
    print(f"   Total chunks:    {result['total_chunks']:,}")

    if result["total_chunks"] > 0 and result["processed"] > 0:
        avg_chunks = result["total_chunks"] / result["processed"]
        print(f"   Promedio:        {avg_chunks:.1f} chunks/PDF")

    print(f"\n💾 Índice guardado en: {index_dir}")
    print(f"   • index.faiss")
    print(f"   • metadata_store.json")
    print(f"   • index_config.json")

    if result["failed"]:
        print(f"\n⚠️  Errores ({len(result['failed'])} PDFs):")
        for pdf_path, error in result["failed"][:5]:
            print(f"   • {pdf_path.name}: {str(error)[:60]}...")

    print(f"\n{'='*70}")
    print("✨ Listo para probar el RAG")
    print(f"{'='*70}\n")

    return result["total_chunks"] > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
