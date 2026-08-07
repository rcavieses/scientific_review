#!/usr/bin/env python3
"""
Comparación rápida: TextChunker vs SemanticChunker en 50 PDFs
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List
import statistics

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.text_chunker import TextChunker
from pipeline.rag.semantic_chunker import SemanticChunker
from pipeline.rag.pdf_extractor import PdfPlumberExtractor
from pipeline.embeddings.embedding_generator import get_embedding_generator

PDF_DIR = PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"

def compare_chunkers():
    """Compara TextChunker vs SemanticChunker"""

    # Seleccionar 50 PDFs
    all_pdfs = sorted(PDF_DIR.glob("*.pdf"))
    test_pdfs = all_pdfs[:50]

    print("🔀 COMPARACIÓN: TextChunker vs SemanticChunker")
    print("=" * 80)
    print(f"\nPDFs a procesar: {len(test_pdfs)}")
    print(f"Primero: {test_pdfs[0].name}")
    print(f"Último: {test_pdfs[-1].name}\n")

    # Inicializar componentes
    print("📦 Inicializando componentes...")
    extractor = PdfPlumberExtractor(verbose=False)

    print("  ⏳ Cargando embedding model (para SemanticChunker)...")
    embedding_generator = get_embedding_generator(
        provider="local",
        model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False
    )
    print("  ✓ Embeddings cargados")

    # Crear chunkers
    text_chunker = TextChunker(
        chunk_size=2000,
        overlap=200,
        min_chunk_size=100,
        split_on_paragraph=True,
        verbose=False
    )

    semantic_chunker = SemanticChunker(
        embedding_generator=embedding_generator,
        similarity_threshold=0.5,
        min_chunk_size=300,
        max_chunk_size=1000,
        verbose=False
    )

    print("\n" + "=" * 80)
    print("🚀 PROCESANDO 50 PDFs")
    print("=" * 80 + "\n")

    results = {
        "text_chunker": [],
        "semantic_chunker": [],
        "errors": []
    }

    for i, pdf_path in enumerate(test_pdfs, 1):
        try:
            # Extraer
            pages = extractor.extract_by_pages(pdf_path)
            paper_id = pdf_path.stem

            # TextChunker
            start_time = time.time()
            text_chunks = text_chunker.chunk_pages(pages, paper_id, str(pdf_path))
            text_time = time.time() - start_time

            # SemanticChunker
            start_time = time.time()
            semantic_chunks = semantic_chunker.chunk_pages(pages, paper_id, str(pdf_path))
            semantic_time = time.time() - start_time

            results["text_chunker"].append({
                "pdf": pdf_path.name,
                "chunk_count": len(text_chunks),
                "time": text_time,
                "sizes": [len(c.text) for c in text_chunks] if text_chunks else []
            })

            results["semantic_chunker"].append({
                "pdf": pdf_path.name,
                "chunk_count": len(semantic_chunks),
                "time": semantic_time,
                "sizes": [len(c.text) for c in semantic_chunks] if semantic_chunks else []
            })

            if i % 10 == 0:
                print(f"  [{i}/50] {pdf_path.name}")
                print(f"    TextChunker: {len(text_chunks)} chunks ({text_time:.2f}s)")
                print(f"    SemanticChunker: {len(semantic_chunks)} chunks ({semantic_time:.2f}s)")

        except Exception as e:
            results["errors"].append({
                "pdf": pdf_path.name,
                "error": str(e)
            })
            print(f"  ✗ [{i}/50] {pdf_path.name}: {type(e).__name__}")

    # Análisis
    print("\n" + "=" * 80)
    print("📊 ANÁLISIS COMPARATIVO")
    print("=" * 80 + "\n")

    text_results = results["text_chunker"]
    semantic_results = results["semantic_chunker"]

    # Estadísticas TextChunker
    text_chunk_counts = [r["chunk_count"] for r in text_results if r["chunk_count"] > 0]
    text_times = [r["time"] for r in text_results]
    text_all_sizes = []
    for r in text_results:
        text_all_sizes.extend(r["sizes"])

    # Estadísticas SemanticChunker
    semantic_chunk_counts = [r["chunk_count"] for r in semantic_results if r["chunk_count"] > 0]
    semantic_times = [r["time"] for r in semantic_results]
    semantic_all_sizes = []
    for r in semantic_results:
        semantic_all_sizes.extend(r["sizes"])

    print("TextChunker:")
    print(f"  Chunks totales: {sum(text_chunk_counts)}")
    print(f"  Chunks por PDF: min={min(text_chunk_counts)}, max={max(text_chunk_counts)}, promedio={statistics.mean(text_chunk_counts):.1f}")
    if text_all_sizes:
        print(f"  Tamaño chunks: min={min(text_all_sizes)}, max={max(text_all_sizes)}, promedio={statistics.mean(text_all_sizes):.0f}")
    print(f"  Tiempo total: {sum(text_times):.2f}s")
    print(f"  Tiempo promedio/PDF: {statistics.mean(text_times):.3f}s")

    print("\nSemanticChunker:")
    print(f"  Chunks totales: {sum(semantic_chunk_counts)}")
    print(f"  Chunks por PDF: min={min(semantic_chunk_counts)}, max={max(semantic_chunk_counts)}, promedio={statistics.mean(semantic_chunk_counts):.1f}")
    if semantic_all_sizes:
        print(f"  Tamaño chunks: min={min(semantic_all_sizes)}, max={max(semantic_all_sizes)}, promedio={statistics.mean(semantic_all_sizes):.0f}")
    print(f"  Tiempo total: {sum(semantic_times):.2f}s")
    print(f"  Tiempo promedio/PDF: {statistics.mean(semantic_times):.3f}s")

    # Comparación
    print("\n" + "-" * 80)
    print("📈 COMPARACIÓN:")
    print("-" * 80)

    time_ratio = sum(semantic_times) / sum(text_times)
    chunk_ratio = sum(semantic_chunk_counts) / sum(text_chunk_counts)

    print(f"Ratio de tiempo: SemanticChunker es {time_ratio:.1f}x más lento")
    print(f"Ratio de chunks: SemanticChunker genera {chunk_ratio:.2f}x chunks")

    # Extrapolación a 430 PDFs
    print("\n" + "=" * 80)
    print("🔮 EXTRAPOLACIÓN A 430 PDFs")
    print("=" * 80)

    text_time_total = (sum(text_times) / 50) * 430
    semantic_time_total = (sum(semantic_times) / 50) * 430

    print(f"\nTextChunker:")
    print(f"  Tiempo estimado: {text_time_total/60:.1f} minutos")
    print(f"  Chunks esperados: {(sum(text_chunk_counts)/50)*430:,.0f}")

    print(f"\nSemanticChunker:")
    print(f"  Tiempo estimado: {semantic_time_total/60:.1f} minutos")
    print(f"  Chunks esperados: {(sum(semantic_chunk_counts)/50)*430:,.0f}")

    # Recomendación
    print("\n" + "=" * 80)
    print("💡 ANÁLISIS Y RECOMENDACIÓN")
    print("=" * 80 + "\n")

    if semantic_chunk_counts and len(semantic_chunk_counts) > 0:
        print("✓ SemanticChunker FUNCIONA (no tiene el bug de 433 chunks)")
        print(f"  Genera {statistics.mean(semantic_chunk_counts):.1f} chunks/PDF vs {statistics.mean(text_chunk_counts):.1f}")

        if time_ratio < 3:
            print(f"\n✓ RECOMENDACIÓN: Cambiar a SemanticChunker")
            print(f"  - Solo {time_ratio:.1f}x más lento (aceptable)")
            print(f"  - Chunks más coherentes semánticamente")
        else:
            print(f"\n⚠️  SemanticChunker es {time_ratio:.1f}x más lento")
            print(f"   - {semantic_time_total/60:.1f} min vs {text_time_total/60:.1f} min para 430 PDFs")
            print(f"   - No vale la pena a menos que calidad sea significativamente mejor")
    else:
        print("✗ SemanticChunker FALLA: No genera chunks (como antes)")
        print("  Recomendación: Mantener TextChunker, investigar bug de SemanticChunker después")

    # Errores
    if results["errors"]:
        print(f"\n⚠️  Errores: {len(results['errors'])} PDFs fallidos")
        for error in results["errors"][:3]:
            print(f"   - {error['pdf']}: {error['error'][:60]}...")

if __name__ == "__main__":
    compare_chunkers()
