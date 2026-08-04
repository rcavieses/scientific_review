#!/usr/bin/env python3
"""
Reconstruye el índice FAISS usando chunking semántico en lugar de tamaño fijo.

Uso:
    python3 scripts/rebuild_index_semantic.py

Características:
- Mantiene oraciones relacionadas juntas
- Hace cortes en cambios de tema (bajo similitud semántica)
- Preserva mejor el contexto para embeddings
- Chunks más grandes pero más coherentes
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pipeline.rag.pdf_extractor import PdfPlumberExtractor


def main():
    # Configurar variables de entorno para usar SemanticChunker
    os.environ["CHUNKER_TYPE"] = "semantic"
    os.environ["SEMANTIC_THRESHOLD"] = "0.4"   # Similitud mínima antes de hacer corte (más bajo = menos cortes)
    os.environ["MIN_CHUNK_SIZE"] = "50"        # Mínimo de chars (bajado para permitir chunks pequeños)
    os.environ["MAX_CHUNK_SIZE"] = "800"       # Máximo de chars

    pdf_dir = Path("outputs/PDF_GOC/PDF")
    index_dir = Path("outputs/rag_index_goc")

    print("📚 Reconstruyendo índice con CHUNKING SEMÁNTICO...")
    print(f"   PDF dir: {pdf_dir}")
    print(f"   Index dir: {index_dir}")
    print(f"   Threshold de similitud: {os.environ['SEMANTIC_THRESHOLD']}")
    print(f"   Tamaño de chunk: {os.environ['MIN_CHUNK_SIZE']}-{os.environ['MAX_CHUNK_SIZE']} chars")
    print()

    # Crear orchestrator con configuración semántica
    # Usar PdfPlumberExtractor para mejor extracción de texto
    extractor = PdfPlumberExtractor(verbose=False)

    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=pdf_dir,
        index_dir=index_dir,
        extractor=extractor,
        skip_indexed=False,  # Reindexar todos
        verbose=True
    )

    # Limpiar índice anterior
    print("🧹 Limpiando índice anterior...")
    index_path = index_dir / "index.faiss"
    if index_path.exists():
        for f in index_dir.glob("*"):
            f.unlink()
            print(f"   Eliminado: {f.name}")

    print()

    # Ejecutar pipeline con SemanticChunker
    print("🔄 Iniciando pipeline con chunking semántico...")
    print()

    result = orchestrator.run()

    print()
    print("✅ Índice reconstruido exitosamente:")
    print(f"   Procesados: {result['processed']}")
    print(f"   Saltados: {result['skipped']}")
    print(f"   Fallidos: {len(result['failed'])}")
    print(f"   Total chunks: {result['total_chunks']}")
    print()

    # Calcular estadísticas
    if result['total_chunks'] > 0:
        avg_chunk_size = result.get('avg_chunk_size', 0)
        print(f"📊 Estadísticas de chunking:")
        print(f"   Chunks por PDF: {result['total_chunks'] / max(result['processed'], 1):.1f}")
        if avg_chunk_size:
            print(f"   Tamaño promedio: {avg_chunk_size:.0f} chars")

    if result['failed']:
        print(f"\n⚠️  PDFs con error ({len(result['failed'])}):")
        for pdf_path, error in result['failed'][:5]:
            print(f"   - {pdf_path.name}")
            print(f"     {str(error)[:80]}...")


if __name__ == "__main__":
    main()
