#!/usr/bin/env python3
"""
Test del pipeline Fase 2 con búsqueda ESPECÍFICA del Golfo de California.
Compara con el test global anterior.
"""

import csv
import sys
import time
import argparse
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase_2_search.search_gulf_california import search_articles_batch_region

REGION_TERMS = [
    "Gulf of California",
    "Golfo de California",
    "Baja California Gulf",
    "California Gulf",
    "Mexican Pacific",
    "Pacífico mexicano",
    "Pacifico mexicano",
    "Mexico Pacific",
    "Sea of Cortez",
    "Sea of Cortés",
]

def get_sample_species(csv_path: Path, sample_percent: float = 0.02) -> list[str]:
    """Extrae muestra de especies del CSV."""
    species_list = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            species = (row.get('Especie') or row.get('species') or "").strip()
            if species:
                species_list.append(species)
    
    sample_size = max(1, int(len(species_list) * sample_percent))
    sample = species_list[:sample_size]
    
    logger.info(f"Total especies en archivo: {len(species_list)}")
    logger.info(f"Muestra ({sample_percent*100:.0f}%): {len(sample)} especies")
    logger.info(f"Términos de región GOC: {len(REGION_TERMS)} términos")
    
    return sample

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample-percent', type=float, default=0.02)
    args = parser.parse_args()
    
    csv_path = PROJECT_ROOT / "data/input/final_taxonomy_occ.csv"
    output_file = PROJECT_ROOT / "outputs/goc_articles_test.csv"
    progress_file = PROJECT_ROOT / "outputs/state/goc_test_search_progress.json"

    if not csv_path.exists():
        logger.error(f"Archivo no encontrado: {csv_path}")
        sys.exit(1)

    species_list = get_sample_species(csv_path, args.sample_percent)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    progress_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info("")
    logger.info("=" * 80)
    logger.info("BÚSQUEDA ESPECÍFICA GOLFO DE CALIFORNIA - 2% DE ESPECIES")
    logger.info("=" * 80)
    logger.info(f"Salida: {output_file}")
    logger.info(f"Progreso: {progress_file}")
    logger.info(f"Región: GOC + Pacífico Mexicano")
    logger.info("")

    inicio = time.time()
    results = search_articles_batch_region(
        species_list=species_list,
        output_file=output_file,
        progress_file=progress_file
    )
    tiempo_total = time.time() - inicio
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("RESUMEN DE RESULTADOS GOC-ESPECÍFICOS")
    logger.info("=" * 80)
    logger.info(f"Total procesadas: {results['processed']}")
    logger.info(f"Con artículos de GOC: {results['found']}")
    logger.info(f"Éxito: {results['found']/max(1, results['processed'])*100:.1f}%")
    logger.info(f"Tiempo total: {tiempo_total/60:.1f} minutos")
    logger.info(f"Tiempo promedio por especie: {tiempo_total/results['processed']:.1f}s")
    logger.info("=" * 80)
    logger.info("")

    if output_file.exists():
        size = output_file.stat().st_size / 1024
        logger.info(f"Archivo consolidado generado: {output_file.name} ({size:.1f} KB)")

if __name__ == "__main__":
    main()
