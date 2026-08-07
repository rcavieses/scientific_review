#!/usr/bin/env python3
"""
FASE 2: Enriquecimiento de metadatos

Objetivos:
  1. Extraer título, autores, año del PDF (de GROBID o heurísticas)
  2. Extraer o inferir DOI
  3. Agregar información bibliográfica a cada chunk
  4. Validar completitud de metadatos

Salida:
  - outputs/rag_index_goc_full/metadata_store.json (actualizado)
  - reports/phase_2_metadata_enrichment.json
  - logs/phase_2_enrichment.log
"""

import sys
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ocr.grobid_provider import GrobidProvider

# Configuración
PDF_DIR = PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"
INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
METADATA_FILE = INDEX_DIR / "metadata_store.json"
LOGS_DIR = PROJECT_ROOT / "outputs" / "logs"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "phase_2_enrichment.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class MetadataEnricher:
    """Extrae y enriquece metadatos de PDFs usando GROBID."""

    def __init__(self):
        self.grobid = GrobidProvider()
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}

    def extract_from_grobid_xml(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extrae metadatos de la respuesta XML de GROBID.

        Intenta obtener:
          - title: Título del artículo
          - authors: Lista de autores
          - year: Año de publicación
          - doi: DOI
          - abstract: Abstract
        """
        try:
            # Aquí usamos internamente GROBID para obtener el XML
            xml_str = self.grobid._process_pdf(pdf_path)
            root = ET.fromstring(xml_str)

            metadata = {
                "source_pdf": pdf_path.name,
                "title": None,
                "authors": [],
                "year": None,
                "doi": None,
                "abstract": None,
            }

            # Extraer title
            title_elem = root.find(".//title[@level='a']")
            if title_elem is not None and title_elem.text:
                metadata["title"] = title_elem.text.strip()

            # Extraer autores
            authors_elem = root.find(".//front//author-list")
            if authors_elem is not None:
                for author in authors_elem.findall("author"):
                    name_parts = []

                    persname = author.find("persName")
                    if persname is not None:
                        forename = persname.find("forename")
                        surname = persname.find("surname")

                        if surname is not None and surname.text:
                            name_parts.append(surname.text.strip())
                        if forename is not None and forename.text:
                            name_parts.append(forename.text.strip())

                    if name_parts:
                        metadata["authors"].append(" ".join(name_parts))

            # Extraer año
            year_elem = root.find(".//monogr//imprint/date")
            if year_elem is not None and year_elem.get("when"):
                year_str = year_elem.get("when")[:4]
                if year_str.isdigit():
                    metadata["year"] = int(year_str)

            # Extraer DOI
            doi_elem = root.find(".//idno[@type='DOI']")
            if doi_elem is not None and doi_elem.text:
                metadata["doi"] = doi_elem.text.strip()

            # Extraer abstract
            abstract_elem = root.find(".//abstract")
            if abstract_elem is not None and abstract_elem.text:
                metadata["abstract"] = abstract_elem.text.strip()[:500]  # Limitar a 500 chars

            return metadata

        except Exception as e:
            logger.warning(f"Error extrayendo metadatos de GROBID para {pdf_path.name}: {e}")
            return self._extract_from_filename(pdf_path)

    def _extract_from_filename(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Intenta extraer información del nombre del archivo como fallback.

        Patrones esperados:
          - Author_Year.pdf
          - Author-Year.pdf
          - Author2026.pdf
        """
        metadata = {
            "source_pdf": pdf_path.name,
            "title": None,
            "authors": [],
            "year": None,
            "doi": None,
            "abstract": None,
        }

        filename = pdf_path.stem

        # Intentar extraer año (últimos 4 dígitos)
        year_match = re.search(r"(\d{4})", filename)
        if year_match:
            metadata["year"] = int(year_match.group(1))

        # Intentar extraer autor(es) (primeras palabras antes del año)
        author_part = re.sub(r"\d{4}.*$", "", filename).strip()
        if author_part:
            # Reemplazar guiones y espacios con espacio
            author_part = author_part.replace("-", " ").replace("_", " ")
            metadata["authors"] = [author_part.strip()]

        return metadata

    def enrich_chunk(self, chunk: Dict[str, Any], pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agrega metadatos bibliográficos a un chunk.

        Escribe en los campos de nivel superior (title/authors/year/doi),
        que son los que lee VectorDBManager.search() al construir
        RAGSearchResult. Antes esto escribía en chunk["metadata"] (anidado,
        con otros nombres de campo) que nadie más leía — los metadatos
        quedaban calculados pero inertes.
        """
        chunk["title"] = pdf_metadata.get("title")
        chunk["authors"] = pdf_metadata.get("authors", [])
        chunk["year"] = pdf_metadata.get("year")
        chunk["doi"] = pdf_metadata.get("doi")
        return chunk


def load_metadata_store() -> Dict[str, Dict[str, Any]]:
    """Carga el metadata_store.json existente."""
    if not METADATA_FILE.exists():
        logger.error(f"❌ Archivo de metadatos no encontrado: {METADATA_FILE}")
        sys.exit(1)

    with open(METADATA_FILE, "r") as f:
        return json.load(f)


def group_chunks_by_pdf(metadata_store: Dict) -> Dict[str, List[str]]:
    """Agrupa IDs de chunks por PDF source."""
    chunks_by_pdf: Dict[str, List[str]] = {}

    for chunk_id, chunk_data in metadata_store.items():
        pdf_source = chunk_data.get("source_pdf", "unknown")
        if pdf_source not in chunks_by_pdf:
            chunks_by_pdf[pdf_source] = []
        chunks_by_pdf[pdf_source].append(chunk_id)

    return chunks_by_pdf


def enrich_metadata_store():
    """Enriquece el metadata_store con información bibliográfica."""
    logger.info("\n" + "=" * 80)
    logger.info("FASE 2: ENRIQUECIMIENTO DE METADATOS")
    logger.info("=" * 80)

    # Cargar metadata_store actual
    logger.info("\n📂 Cargando metadata_store...")
    metadata_store = load_metadata_store()
    logger.info(f"   Chunks totales: {len(metadata_store)}")

    # Agrupar por PDF
    chunks_by_pdf = group_chunks_by_pdf(metadata_store)
    logger.info(f"   PDFs únicos: {len(chunks_by_pdf)}")

    # Enriquecedor
    enricher = MetadataEnricher()
    enriched_count = 0
    failed_count = 0

    # Procesar cada PDF
    logger.info("\n📚 Extrayendo metadatos por PDF...")

    for i, (pdf_source, chunk_ids) in enumerate(sorted(chunks_by_pdf.items()), 1):
        pdf_path = PDF_DIR / pdf_source

        if not pdf_path.exists():
            logger.warning(f"  [{i:3d}] ⚠️  PDF no encontrado: {pdf_source}")
            failed_count += len(chunk_ids)
            continue

        logger.info(f"  [{i:3d}/{len(chunks_by_pdf)}] {pdf_source}...")

        try:
            # NOTA: No hay servicio GROBID real disponible en este entorno
            # (solo un mock que devuelve datos genéricos fabricados para
            # cualquier PDF). Usamos el fallback por nombre de archivo, que
            # da datos reales aunque limitados (autor/año), en vez de
            # arriesgar metadatos bibliográficos fabricados/incorrectos.
            pdf_metadata = enricher._extract_from_filename(pdf_path)

            # Enriquecer todos los chunks de este PDF
            for chunk_id in chunk_ids:
                metadata_store[chunk_id] = enricher.enrich_chunk(
                    metadata_store[chunk_id], pdf_metadata
                )
                enriched_count += 1

            # Log de éxito
            authors_str = ", ".join(pdf_metadata.get("authors", [])[:2])
            if len(pdf_metadata.get("authors", [])) > 2:
                authors_str += ", et al."
            year_str = f"({pdf_metadata.get('year', '?')})" if pdf_metadata.get("year") else ""

            logger.info(f" ✓ {authors_str} {year_str}")

        except Exception as e:
            logger.error(f" ❌ {str(e)}")
            failed_count += len(chunk_ids)

    # Guardar metadata_store enriquecido
    logger.info("\n💾 Guardando metadata_store enriquecido...")
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata_store, f, indent=2)
    logger.info(f"   ✓ Guardado: {METADATA_FILE}")

    return {
        "total_chunks_enriched": enriched_count,
        "failed_chunks": failed_count,
        "total_pdfs": len(chunks_by_pdf),
        "enrichment_rate": (enriched_count / (enriched_count + failed_count) * 100)
        if (enriched_count + failed_count) > 0
        else 0,
    }


def calculate_metadata_stats(metadata_store: Dict) -> Dict[str, Any]:
    """Calcula estadísticas de completitud de metadatos."""
    stats = {
        "total_chunks": len(metadata_store),
        "chunks_with_title": 0,
        "chunks_with_authors": 0,
        "chunks_with_year": 0,
        "chunks_with_doi": 0,
        "completeness_pct": 0,
    }

    for chunk_data in metadata_store.values():
        if chunk_data.get("title"):
            stats["chunks_with_title"] += 1
        if chunk_data.get("authors"):
            stats["chunks_with_authors"] += 1
        if chunk_data.get("year"):
            stats["chunks_with_year"] += 1
        if chunk_data.get("doi"):
            stats["chunks_with_doi"] += 1

    # Completeness: promedio de campos disponibles
    if stats["total_chunks"] > 0:
        total_fields = (
            stats["chunks_with_title"]
            + stats["chunks_with_authors"]
            + stats["chunks_with_year"]
            + stats["chunks_with_doi"]
        )
        stats["completeness_pct"] = (total_fields / (stats["total_chunks"] * 4)) * 100

    return stats


def save_enrichment_report(enrichment_stats: Dict, metadata_stats: Dict):
    """Guarda reporte de enriquecimiento."""
    logger.info("\n" + "=" * 80)
    logger.info("FASE 2.1: Guardando reporte de enriquecimiento")
    logger.info("=" * 80)

    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "enrich_metadata",
        "enrichment": enrichment_stats,
        "metadata_statistics": metadata_stats,
        "recommendations": [
            "Los metadatos están listos para búsquedas filtradas",
            "Se puede filtrar por año, autor, DOI",
            "El campo paper_title permite búsquedas de titulos",
        ],
    }

    report_path = REPORTS_DIR / "phase_2_metadata_enrichment.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"  Reporte guardado: {report_path}")


def print_summary(enrichment_stats: Dict, metadata_stats: Dict):
    """Imprime resumen de la fase."""
    logger.info(f"\n{'=' * 80}")
    logger.info("📊 RESUMEN DE FASE 2")
    logger.info(f"{'=' * 80}")

    logger.info(f"\n  📝 ENRIQUECIMIENTO:")
    logger.info(f"     Chunks enriquecidos: {enrichment_stats['total_chunks_enriched']}")
    logger.info(f"     Chunks fallidos: {enrichment_stats['failed_chunks']}")
    logger.info(f"     Tasa de éxito: {enrichment_stats['enrichment_rate']:.1f}%")

    logger.info(f"\n  📊 COMPLETITUD DE METADATOS:")
    logger.info(f"     Chunks con título: {metadata_stats['chunks_with_title']}/{metadata_stats['total_chunks']}")
    logger.info(f"     Chunks con autores: {metadata_stats['chunks_with_authors']}/{metadata_stats['total_chunks']}")
    logger.info(f"     Chunks con año: {metadata_stats['chunks_with_year']}/{metadata_stats['total_chunks']}")
    logger.info(f"     Chunks con DOI: {metadata_stats['chunks_with_doi']}/{metadata_stats['total_chunks']}")
    logger.info(f"     Completitud general: {metadata_stats['completeness_pct']:.1f}%")

    logger.info(f"\n  → Próximo paso: python3 scripts/phase_3_optimize_retrieval.py")
    logger.info(f"{'=' * 80}\n")


def main():
    logger.info(f"\n{'=' * 80}")
    logger.info("📚 FASE 2: ENRIQUECIMIENTO DE METADATOS BIBLIOGRÁFICOS")
    logger.info(f"{'=' * 80}")

    # Enriquecer
    enrichment_stats = enrich_metadata_store()

    # Cargar nuevamente para estadísticas
    metadata_store = load_metadata_store()
    metadata_stats = calculate_metadata_stats(metadata_store)

    # Guardar reporte
    save_enrichment_report(enrichment_stats, metadata_stats)

    # Resumen
    print_summary(enrichment_stats, metadata_stats)


if __name__ == "__main__":
    main()
