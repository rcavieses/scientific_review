#!/usr/bin/env python3
"""Busca artículos en ScienceDirect para especies canónicas y descarga PDFs OA."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import requests

from scripts.phase_3_download.download_pdfs import download_all_articles
from scripts.phase_2_search.search_articles import save_species_articles, search_sciencedirect


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "outputs" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SPECIES_DIR = PROJECT_ROOT / "outputs" / "search_results_canonical"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "outputs" / "sciencedirect_results"
DEFAULT_PDFS_DIR = PROJECT_ROOT / "outputs" / "pdfs" / "sciencedirect"
DEFAULT_SEARCH_PROGRESS = STATE_DIR / "sciencedirect_search_progress.json"
DEFAULT_DOWNLOAD_PROGRESS = STATE_DIR / "sciencedirect_download_progress.json"
DEFAULT_STATE_FILE = STATE_DIR / "sciencedirect_download_state.json"
SCIENCEDIRECT_BASE = "https://api.elsevier.com/content/search/sciencedirect"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_sciencedirect_key() -> str:
    key = os.getenv("SCIENCEDIRECT_API_KEY", "").strip()
    if key:
        return key

    secret_path = PROJECT_ROOT / "secrets" / "sciencedirect_apikey.txt"
    if secret_path.exists():
        key = secret_path.read_text(encoding="utf-8").strip()
        if key:
            os.environ["SCIENCEDIRECT_API_KEY"] = key
            return key

    return ""


def iter_species(species_dir: Path) -> list[str]:
    return sorted(path.stem.replace("_", " ") for path in species_dir.glob("*.csv"))


def load_search_progress(progress_file: Path) -> dict[str, int]:
    if progress_file.exists():
        try:
            return json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_search_progress(progress_file: Path, progress: dict[str, int]) -> None:
    progress_file.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def search_sciencedirect_batch(
    species_names: list[str],
    results_dir: Path,
    progress_file: Path,
    resume: bool = True,
) -> dict[str, int]:
    results_dir.mkdir(parents=True, exist_ok=True)
    progress = load_search_progress(progress_file) if resume else {}

    summary = {
        "species_total": len(species_names),
        "species_processed": 0,
        "species_with_results": 0,
        "articles_found": 0,
    }

    for idx, species_name in enumerate(species_names, 1):
        csv_path = results_dir / f"{species_name.replace(' ', '_').replace('/', '_')}.csv"
        if resume and species_name in progress and csv_path.exists():
            summary["species_processed"] += 1
            if progress[species_name] > 0:
                summary["species_with_results"] += 1
                summary["articles_found"] += progress[species_name]
            continue

        logger.info(f"[{idx}/{len(species_names)}] ScienceDirect: {species_name}")
        articles = search_sciencedirect(species_name)
        if articles:
            save_species_articles(species_name, articles, results_dir)
            summary["species_with_results"] += 1
            summary["articles_found"] += len(articles)
            logger.info(f"  -> {len(articles)} artículos")

        progress[species_name] = len(articles)
        save_search_progress(progress_file, progress)
        summary["species_processed"] += 1

    return summary


def save_state(state_file: Path, state: dict) -> None:
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_sciencedirect_access() -> tuple[bool, str]:
    key = os.getenv("SCIENCEDIRECT_API_KEY", "").strip()
    if not key:
        return False, "SCIENCEDIRECT_API_KEY no configurada"

    try:
        response = requests.get(
            SCIENCEDIRECT_BASE,
            params={"query": "Danio rerio", "count": 1, "sort": "date", "apiKey": key},
            timeout=30,
        )
    except Exception as exc:
        return False, f"Error consultando ScienceDirect: {exc}"

    if response.status_code == 401:
        return False, "ScienceDirect devolvió AUTHORIZATION_ERROR para la API key configurada"
    if response.status_code != 200:
        return False, f"ScienceDirect devolvió status {response.status_code}"

    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--species-dir",
        type=Path,
        default=DEFAULT_SPECIES_DIR,
        help="Directorio que define el universo de especies a consultar",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directorio donde guardar CSVs de ScienceDirect",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDFS_DIR,
        help="Directorio donde guardar PDFs descargados",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Procesar solo las primeras N especies",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Solo buscar en ScienceDirect, sin descargar PDFs",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignorar progreso previo y reprocesar especies",
    )
    args = parser.parse_args()

    key = load_sciencedirect_key()
    if not key:
        logger.error("SCIENCEDIRECT_API_KEY no configurada y no existe secrets/sciencedirect_apikey.txt")
        return 1

    access_ok, access_message = check_sciencedirect_access()
    if not access_ok:
        logger.error(access_message)
        return 1

    if not args.species_dir.exists():
        logger.error(f"No existe el directorio de especies: {args.species_dir}")
        return 1

    species_names = iter_species(args.species_dir)
    if args.limit is not None:
        species_names = species_names[:args.limit]

    logger.info(f"Especies a consultar: {len(species_names)}")
    logger.info(f"Resultados ScienceDirect: {args.results_dir}")
    logger.info(f"PDFs destino: {args.pdf_dir}")

    state = {
        "search": {"status": "running"},
        "download": {"status": "pending"},
    }
    save_state(DEFAULT_STATE_FILE, state)

    search_summary = search_sciencedirect_batch(
        species_names,
        args.results_dir,
        DEFAULT_SEARCH_PROGRESS,
        resume=not args.force,
    )
    state["search"] = {"status": "completed", **search_summary}
    save_state(DEFAULT_STATE_FILE, state)

    logger.info(
        "Búsqueda ScienceDirect: "
        f"{search_summary['articles_found']} artículos en "
        f"{search_summary['species_with_results']} especies"
    )

    if args.no_download:
        return 0

    state["download"] = {"status": "running"}
    save_state(DEFAULT_STATE_FILE, state)

    download_summary = download_all_articles(
        args.results_dir,
        args.pdf_dir,
        DEFAULT_DOWNLOAD_PROGRESS,
        source_filter="ScienceDirect",
    )
    state["download"] = {"status": "completed", **download_summary}
    save_state(DEFAULT_STATE_FILE, state)

    logger.info(
        "Descarga ScienceDirect: "
        f"{download_summary.get('total_downloaded', 0)}/"
        f"{download_summary.get('total_articles', 0)} PDFs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())