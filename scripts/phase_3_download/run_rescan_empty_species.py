#!/usr/bin/env python3
"""
Re-búsqueda con métodos corregidos para las ~14,485 especies
cuyos CSVs quedaron vacíos tras la limpieza.

- Solo procesa CSVs que tienen 0 filas de artículos.
- No toca CSVs con contenido → sin conflicto con download_pdfs.py corriendo.
- Fuentes: PubMed, CrossRef (query.bibliographic + comillas), ArXiv (ti: exacto).
- Progreso en rescan_progress.json (reanudable).

Uso:
    nohup python run_rescan_empty_species.py > rescan.log 2>&1 &
    tail -f rescan.log
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("rescan.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "outputs" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
SEARCH_RESULTS_DIR = PROJECT_ROOT / "outputs" / "search_results"
PROGRESS_FILE = STATE_DIR / "rescan_progress.json"

FIELDNAMES = ["source", "title", "authors", "year", "journal", "doi", "url", "pubmed_id", "arxiv_id"]


# ── Importar funciones de búsqueda ya corregidas ─────────────────────────────

from scripts.phase_2_search.search_articles import (
    search_pubmed,
    search_crossref,
    search_arxiv,
    search_scopus,
    _title_contains_species,
    save_species_articles,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_empty_csv(csv_file: Path) -> bool:
    """True si el CSV existe pero no tiene filas de datos (solo header o vacío)."""
    try:
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for _ in reader:
                return False  # tiene al menos una fila
        return True
    except Exception:
        return True


def get_empty_species() -> list[tuple[str, Path]]:
    """Devuelve lista de (species_name, csv_path) para CSVs vacíos."""
    result = []
    for csv_file in sorted(SEARCH_RESULTS_DIR.glob("*.csv")):
        if is_empty_csv(csv_file):
            species_name = csv_file.stem.replace("_", " ")
            result.append((species_name, csv_file))
    return result


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def search_species(species_name: str) -> list[dict]:
    """Busca en PubMed, CrossRef y ArXiv con métodos corregidos."""
    all_results = []
    all_results.extend(search_pubmed(species_name))
    all_results.extend(search_crossref(species_name))
    all_results.extend(search_arxiv(species_name))
    # Scopus también si hay API key configurada
    scopus_results = search_scopus(species_name)
    all_results.extend(scopus_results)

    # Filtro de relevancia para fuentes ruidosas
    noisy = {"CrossRef", "ArXiv"}
    all_results = [
        r for r in all_results
        if r.get("source") not in noisy
        or _title_contains_species(r.get("title", ""), species_name)
    ]

    # Deduplicar por título
    seen = set()
    unique = []
    for r in all_results:
        t = r.get("title", "").lower().strip()
        if t and t not in seen:
            seen.add(t)
            unique.append(r)

    return unique


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 65)
    logger.info("  RE-BÚSQUEDA ESPECIES SIN ARTÍCULOS (métodos corregidos)")
    logger.info("=" * 65)

    # Detectar especies con CSV vacío
    logger.info("Identificando especies con CSVs vacíos...")
    empty_species = get_empty_species()
    logger.info(f"  Total a procesar: {len(empty_species):,}")

    if not empty_species:
        logger.info("No hay especies con CSVs vacíos. Nada que hacer.")
        return

    progress = load_progress()
    already_done = sum(1 for sp, _ in empty_species if sp in progress)
    logger.info(f"  Ya procesadas (progreso anterior): {already_done:,}")
    logger.info(f"  Pendientes: {len(empty_species) - already_done:,}")

    found_total = 0
    processed = 0
    start = time.time()

    for idx, (species_name, csv_path) in enumerate(empty_species, 1):
        # Saltar si ya fue procesada en sesión anterior Y el CSV ya tiene contenido
        if species_name in progress and not is_empty_csv(csv_path):
            continue

        articles = search_species(species_name)
        processed += 1

        if articles:
            save_species_articles(species_name, articles, SEARCH_RESULTS_DIR)
            found_total += 1

        # Guardar progreso
        progress[species_name] = len(articles)
        save_progress(progress)

        # Log cada 50 especies
        if processed % 50 == 0:
            elapsed = time.time() - start
            rate = processed / elapsed * 60  # especies/min
            remaining = (len(empty_species) - idx) / (rate / 60) / 60 if rate > 0 else 0
            logger.info(
                f"[{idx:,}/{len(empty_species):,}] "
                f"Con artículos: {found_total} | "
                f"Velocidad: {rate:.0f} esp/min | "
                f"ETA: {remaining:.1f}h"
            )
        elif articles:
            logger.info(f"  [{idx:,}] {species_name}: {len(articles)} artículos")

    elapsed_total = time.time() - start
    logger.info("=" * 65)
    logger.info(f"Re-búsqueda completada en {elapsed_total/3600:.1f}h")
    logger.info(f"Especies con artículos encontrados: {found_total:,} / {processed:,}")
    logger.info("=" * 65)


if __name__ == "__main__":
    main()
