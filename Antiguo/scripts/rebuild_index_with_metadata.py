#!/usr/bin/env python3
"""
Reconstruye el índice FAISS extrayendo metadatos de los PDFs con GROBID.

Uso:
    python scripts/rebuild_index_with_metadata.py

Este script:
1. Carga los PDFs
2. Extrae metadatos (título, autores, año) con GROBID
3. Recrea el índice con los metadatos enriquecidos
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ocr.grobid_provider import GrobidProvider
from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator


def main():
    pdf_dir = Path("outputs/PDF_GOC/PDF")
    index_dir = Path("outputs/rag_index_goc")

    print(f"📄 Reconstruyendo índice con metadatos de GROBID...")
    print(f"   PDF dir: {pdf_dir}")
    print(f"   Index dir: {index_dir}")

    # Inicializar GROBID
    grobid = GrobidProvider(grobid_url="http://localhost:8070", verbose=False)

    # Crear orchestrator con GROBID
    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=pdf_dir,
        index_dir=index_dir,
        skip_indexed=False,  # Reindexar todos
        verbose=True
    )

    # Usar GrobidPDFExtractor
    from pipeline.rag.pdf_extractor import GrobidPDFExtractor
    orchestrator._extractor = GrobidPDFExtractor(grobid_provider=grobid, verbose=False)

    # Limpiar índice anterior
    index_path = index_dir / "index.faiss"
    if index_path.exists():
        print(f"  Eliminando índice anterior en {index_dir}...")
        for f in index_dir.glob("*"):
            f.unlink()

    # Ejecutar pipeline
    result = orchestrator.run()

    print(f"\n✅ Índice reconstruido:")
    print(f"   Procesados: {result['processed']}")
    print(f"   Fallidos: {len(result['failed'])}")
    print(f"   Total chunks: {result['total_chunks']}")

    if result['failed']:
        print(f"\n⚠️  PDFs con error:")
        for pdf_path, error in result['failed'][:5]:
            print(f"   - {pdf_path.name}: {error}")


if __name__ == "__main__":
    main()
