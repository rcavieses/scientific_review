#!/usr/bin/env python3
"""
Búsqueda de artículos científicos en fuentes de acceso abierto.

Utiliza el sistema unificado de scientific_search para:
- PubMed (biomédico)
- bioRxiv/medRxiv (preprints)
- PLOS ONE (multidisciplinario)

Para todas las especies del Golfo de California y Pacífico Mexicano.

Uso:
    python search_species_open_access.py
    python search_species_open_access.py --sources pubmed,biorxiv,plos
    python search_species_open_access.py --test  # Prueba con 5 especies
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import time
from pathlib import Path
from typing import Optional

from scientific_search import ScientificArticleSearcher

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
DEFAULT_SPECIES_CSV = PROJECT_ROOT / "data/input/occurrence_data_revised_taxonomy.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "open_access_results"
DEFAULT_PROGRESS_FILE = DEFAULT_OUTPUT_DIR / "search_progress.json"


def load_species_from_csv(csv_path: Path) -> list[str]:
    """Carga lista única de especies del CSV."""
    species_set = set()

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                species = row.get('species', '').strip()
                if species:
                    species_set.add(species)
    except Exception as e:
        logger.error(f"Error cargando especies: {e}")
        return []

    return sorted(list(species_set))


def search_species(
    species_list: list[str],
    sources: list[str] = None,
    output_dir: Path = None,
    max_results_per_source: int = 10,
) -> dict:
    """
    Busca artículos para cada especie en múltiples fuentes.

    Args:
        species_list: Lista de nombres de especies
        sources: Fuentes a buscar ['pubmed', 'biorxiv', 'plos']
        output_dir: Directorio para guardar resultados
        max_results_per_source: Máximo de artículos por fuente/especie

    Returns:
        Diccionario con estadísticas
    """
    if sources is None:
        sources = ['pubmed', 'biorxiv', 'plos']

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Inicializar searcher
    searcher = ScientificArticleSearcher(verbose=False)

    # Estadísticas
    stats = {source: 0 for source in sources}
    stats['total_species'] = len(species_list)
    stats['processed'] = 0

    logger.info(f"Buscando para {len(species_list)} especies en {len(sources)} fuentes")
    logger.info(f"Fuentes: {', '.join(sources)}")

    # Búsqueda por especie
    for idx, species in enumerate(species_list, 1):
        all_results = []

        # Buscar en cada fuente
        try:
            logger.debug(f"[{idx}/{len(species_list)}] Buscando {species}")

            search_result = searcher.search(
                query=species,
                max_results=max_results_per_source,
                specific_sources=sources,
                min_relevance=0.0,  # Sin filtro de relevancia
            )

            # SearchResult retorna un objeto con .articles
            if hasattr(search_result, 'articles'):
                all_results.extend(search_result.articles)
            else:
                all_results.extend(search_result)

            # Actualizar estadísticas por fuente
            for article in all_results:
                source_name = article.source if hasattr(article, 'source') else 'unknown'
                if source_name in stats:
                    stats[source_name] += 1

        except Exception as e:
            logger.warning(f"Error buscando {species}: {e}")

        # Guardar resultados
        if all_results:
            safe_name = species.replace(" ", "_").replace("/", "_")
            csv_path = output_dir / f"{safe_name}.csv"

            try:
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['source', 'title', 'authors', 'year', 'journal', 'doi', 'url']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for article in all_results:
                        writer.writerow({
                            'source': article.source,
                            'title': article.title,
                            'authors': ', '.join(article.authors) if article.authors else '',
                            'year': article.year or '',
                            'journal': article.journal or '',
                            'doi': article.doi or '',
                            'url': article.url or '',
                        })
            except Exception as e:
                logger.error(f"Error guardando {species}: {e}")

        stats['processed'] += 1

        # Log de progreso cada 20 especies
        if idx % 20 == 0:
            logger.info(
                f"Progreso: {stats['processed']}/{stats['total_species']} | "
                f"PubMed: {stats.get('pubmed', 0)}, "
                f"bioRxiv: {stats.get('biorxiv', 0)}, "
                f"PLOS: {stats.get('plos', 0)}"
            )

        # Rate limiting
        if idx % 5 == 0:
            time.sleep(1)

    logger.info("Búsqueda completada")
    return stats


def main():
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description='Búsqueda de artículos en fuentes de acceso abierto'
    )
    parser.add_argument(
        '--species-csv',
        type=Path,
        default=DEFAULT_SPECIES_CSV,
        help='CSV con especies (default: occurrence_data_revised_taxonomy.csv)',
    )
    parser.add_argument(
        '--sources',
        type=str,
        default='pubmed,biorxiv,plos',
        help='Fuentes a buscar (comma-separated)',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help='Directorio para resultados',
    )
    parser.add_argument(
        '--max-results',
        type=int,
        default=10,
        help='Máximo de artículos por fuente/especie (default: 10)',
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Modo prueba con 5 especies',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Logging detallado',
    )

    args = parser.parse_args()

    # Configurar logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # Cargar especies
    if args.test:
        species_list = [
            "Dosidicus gigas",
            "Prionace glauca",
            "Callinectes sapidus",
            "Mugil cephalus",
            "Lutjanus peru",
        ]
        print(f"Modo PRUEBA: {len(species_list)} especies")
    else:
        species_list = load_species_from_csv(args.species_csv)
        if not species_list:
            logger.error("No se encontraron especies")
            return

    # Parsear fuentes
    sources = [s.strip() for s in args.sources.split(',')]
    valid_sources = {'pubmed', 'biorxiv', 'plos'}
    sources = [s for s in sources if s in valid_sources]

    if not sources:
        logger.error("Fuentes inválidas")
        return

    # Ejecutar búsqueda
    print("\n" + "=" * 70)
    print("BÚSQUEDA DE ARTÍCULOS EN FUENTES ABIERTAS")
    print("=" * 70)

    start_time = time.time()
    stats = search_species(
        species_list,
        sources=sources,
        output_dir=args.output_dir,
        max_results_per_source=args.max_results,
    )
    elapsed = time.time() - start_time

    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"Especies procesadas: {stats['processed']}/{stats['total_species']}")
    print(f"Tiempo total: {elapsed:.1f}s")
    print()

    for source in sources:
        count = stats.get(source, 0)
        avg = count / len(species_list) if species_list else 0
        print(f"  {source.upper():10} {count:5} artículos ({avg:.1f} por especie)")

    total = sum(stats.get(s, 0) for s in sources)
    print()
    print(f"TOTAL: {total} artículos encontrados")
    print(f"Directorio: {args.output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
