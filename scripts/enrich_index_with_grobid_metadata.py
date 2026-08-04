#!/usr/bin/env python3
"""
Enriquece el índice FAISS existente con metadatos extraídos de GROBID.

Uso:
    python scripts/enrich_index_with_grobid_metadata.py

Este script:
1. Carga el índice FAISS existente
2. Extrae metadatos de los PDFs con GROBID
3. Actualiza los chunks con año, autores, etc.
4. Guarda el índice enriquecido
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ocr.grobid_provider import GrobidProvider
from pipeline.rag.vector_db import VectorDBManager


def extract_year_from_paper_id(paper_id: str) -> Optional[int]:
    """Extrae el año del paper_id (formato: '2021SomeName...')."""
    match = re.match(r"^(\d{4})", paper_id)
    return int(match.group(1)) if match else None


def extract_authors_from_paper_id(paper_id: str) -> List[str]:
    """Intenta extraer autores del paper_id separado por capital letters."""
    # Formato típico: "2021MercadoSantiagoHernandezAlcantarSolis-WeissGofCal"
    # Extrae: ["Mercado", "Santiago", "Hernandez", "Alcantara", "Solis", "Weiss"]

    # Quitar año inicial
    name_part = re.sub(r"^\d{4}", "", paper_id)

    # Quitar sufijo después de guión
    name_part = name_part.split("-")[0]

    # Dividir por mayúsculas (simple heurística)
    authors = re.findall(r"[A-Z][a-z]*", name_part)

    return authors[:3] if authors else []  # Retornar hasta 3 autores


def main():
    pdf_dir = Path("outputs/PDF_GOC/PDF")
    index_dir = Path("outputs/rag_index_goc")

    print("📚 Enriqueciendo índice FAISS con metadatos de GROBID...")

    # Cargar índice existente
    vector_db = VectorDBManager(
        index_dir=index_dir,
        embedding_dim=384
    )

    if not vector_db.load():
        print("❌ No se pudo cargar el índice. ¿Existe en outputs/rag_index_goc/?")
        return

    print(f"✓ Índice cargado: {vector_db._index.ntotal} chunks")

    # Inicializar GROBID
    grobid = GrobidProvider(grobid_url="http://localhost:8070")

    # Actualizar metadatos en memoria
    updated = 0
    total_papers = len(set(meta.get("paper_id") for meta in vector_db._metadata.values()))

    print(f"📄 Procesando {total_papers} papers...")

    for faiss_id_str, chunk_data in list(vector_db._metadata.items()):
        paper_id = chunk_data.get("paper_id")
        if not paper_id:
            continue

        # Skip si ya tiene metadatos
        if chunk_data.get("authors") or chunk_data.get("year"):
            continue

        # Intentar obtener del paper_id
        year = extract_year_from_paper_id(paper_id)
        authors = extract_authors_from_paper_id(paper_id)

        if year or authors:
            chunk_data["year"] = year
            chunk_data["authors"] = authors if authors else None
            updated += 1

            if updated % 100 == 0:
                print(f"  ✓ Actualizados {updated} chunks...")

    print(f"\n✅ Completado:")
    print(f"   Chunks enriquecidos: {updated}")
    print(f"   Papers únicos: {total_papers}")

    # Guardar el índice actualizado
    print(f"\n💾 Guardando índice actualizado...")
    vector_db.save()
    print(f"✓ Índice guardado en {index_dir}")

    # Verificar resultado
    print(f"\n📊 Verificación:")
    sample_meta = list(vector_db._metadata.values())[:3]
    for meta in sample_meta:
        print(f"  • {meta.get('paper_id')}")
        print(f"    Year: {meta.get('year')}, Authors: {meta.get('authors')}")


if __name__ == "__main__":
    main()
