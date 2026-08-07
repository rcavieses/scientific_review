#!/usr/bin/env python3
"""Test de reconstrucción de un solo PDF - diagnóstico"""

import sys
import os
from pathlib import Path
import logging

# Agregar project al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pipeline.rag.text_chunker import TextChunker
from pipeline.embeddings.embedding_generator import get_embedding_generator

PDF_DIR = Path(__file__).parent.parent / "outputs" / "PDF_GOC" / "PDF"
INDEX_DIR = Path(__file__).parent.parent / "outputs" / "test_single_index"

def test_single_pdf():
    """Test de un solo PDF"""
    pdfs = sorted(PDF_DIR.glob("*.pdf"))[:1]

    if not pdfs:
        print("❌ No hay PDFs")
        return

    pdf_path = pdfs[0]
    print(f"📄 Procesando: {pdf_path.name}")
    print(f"Tamaño: {pdf_path.stat().st_size / 1024**2:.1f} MB\n")

    # Limpiar índice anterior si existe
    import shutil
    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR)
        print(f"✓ Índice anterior eliminado")

    # Crear componentes
    print("🔧 Configurando componentes...")
    chunker = TextChunker(chunk_size=2000, overlap=200, min_chunk_size=100)

    print("⏳ Inicializando embedding generator...")
    try:
        embedding_generator = get_embedding_generator(
            provider="local",
            model="all-MiniLM-L6-v2",
            cache_folder=None,
            verbose=False
        )
        print("✓ Embeddings inicializados")
    except Exception as e:
        print(f"❌ Error con embeddings: {e}")
        import traceback
        traceback.print_exc()
        return

    # Crear orquestador
    print("📦 Inicializando pipeline...")
    try:
        orchestrator = RAGPipelineOrchestrator(
            pdf_dir=PDF_DIR,
            index_dir=INDEX_DIR,
            chunker=chunker,
            embedding_generator=embedding_generator,
            skip_indexed=False,
            batch_size=64,
            verbose=True,
        )
        print("✓ Pipeline inicializado")
    except Exception as e:
        print(f"❌ Error al crear orquestador: {e}")
        import traceback
        traceback.print_exc()
        return

    # Procesar un solo PDF
    print(f"\n🚀 Procesando {pdf_path.name}...")
    try:
        result = orchestrator.index_single_pdf(pdf_path)
        print(f"✓ Procesado: {len(result)} chunks creados")

        if result:
            print(f"\nPrimer chunk:")
            chunk = result[0]
            print(f"  Texto: {chunk.chunk.text[:100]}...")
            print(f"  Vector dim: {len(chunk.vector)}")
    except Exception as e:
        print(f"❌ Error al procesar PDF: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return

    # Guardar índice
    print(f"\n💾 Guardando índice a {INDEX_DIR}...")
    try:
        db = orchestrator.get_db()
        db.save()
        print("✓ Índice guardado")

        # Mostrar estadísticas
        stats = db.get_stats()
        print(f"\n📊 Estadísticas:")
        print(f"  Total chunks: {stats.total_chunks}")
        print(f"  Total papers: {stats.total_papers}")
    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_pdf()
