#!/usr/bin/env python3
"""
Buscar artículos científicos para especies con criterios geográficos específicos.

Filtra resultados para la región del Golfo de California y Pacífico mexicano.
Las búsquedas base se realizan en search_articles.py con filtros region_terms.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from scripts.phase_2_search.search_articles import (
    search_pubmed,
    search_crossref,
    search_scopus,
    search_sciencedirect,
    search_arxiv,
    _title_contains_species,
    save_species_articles,
    search_articles_batch,
)

logger = logging.getLogger(__name__)

# Términos de búsqueda para la región del Golfo de California / Pacífico mexicano
REGION_TERMS = [
    "Gulf of California",
    "Golfo de California",
    "Baja California Gulf",
    "California Gulf",
    "Mexican Pacific",
    "Pacífico mexicano",
    "Pacifico mexicano",
    "Mexico Pacific",
]


def search_articles_for_species_region(species_name: str) -> list[dict[str, Any]]:
    """Busca artículos en todas las bases de datos con filtro geográfico."""
    all_results = []

    # Buscar en cada base de datos con región_terms como filtro
    all_results.extend(search_pubmed(species_name, region_terms=REGION_TERMS))
    all_results.extend(search_crossref(species_name, region_terms=REGION_TERMS))
    all_results.extend(search_scopus(species_name, region_terms=REGION_TERMS))
    all_results.extend(search_sciencedirect(species_name, region_terms=REGION_TERMS))
    all_results.extend(search_arxiv(species_name, region_terms=REGION_TERMS))

    # Filtro de relevancia: el título debe mencionar el nombre de la especie
    noisy_sources = {"CrossRef", "ArXiv"}
    all_results = [
        r for r in all_results
        if r.get("source") not in noisy_sources
        or _title_contains_species(r.get("title", ""), species_name)
    ]

    # Remover duplicados por título
    seen_titles = set()
    unique_results = []
    for result in all_results:
        title = result.get("title", "").lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_results.append(result)

    return unique_results


def search_articles_batch_region(
    species_list: list[str],
    output_file: Path,
    progress_file: Path | None = None,
) -> dict[str, int]:
    """Busca artículos para un lote de especies con filtro geográfico.

    Guarda resultados en un archivo CSV consolidado (no por especie).

    Args:
        species_list: lista de especies a buscar
        output_file: archivo CSV consolidado para guardar resultados
        progress_file: archivo JSON para guardar/cargar progreso

    Returns:
        Resumen de búsqueda
    """
    # Usar search_articles_batch pero con región_terms
    return search_articles_batch(
        species_list,
        output_file.parent,
        progress_file=progress_file,
        region_terms=REGION_TERMS,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Busca artículos científicos del Golfo de California/Pacífico mexicano"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent.parent.parent / "final_taxonomy_occ.csv",
        help="CSV con especies (default: final_taxonomy_occ.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent.parent / "gulf_california_articles.csv",
        help="CSV de salida consolidado (default: gulf_california_articles.csv)",
    )
    parser.add_argument(
        "--progress",
        type=Path,
        default=Path(__file__).parent.parent.parent / "outputs" / "state" / "gulf_california_search_progress.json",
        help="Archivo de progreso JSON",
    )

    args = parser.parse_args()

    # Cargar especies del CSV
    import csv
    species_list = []
    if args.input.exists():
        with open(args.input, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            species_list = [row.get("Especie", "").strip() for row in reader if row]

    logger.info(f"Buscando {len(species_list)} especies del Golfo de California...")
    results = search_articles_batch_region(species_list, args.output, args.progress)
    logger.info(f"Búsqueda completada: {results}")
