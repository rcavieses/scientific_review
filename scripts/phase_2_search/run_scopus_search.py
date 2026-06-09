"""
Búsqueda paralela SOLO con Scopus API para las nuevas especies.

Guarda resultados en scopus_results/ (directorio separado para no
sobreescribir los resultados multi-fuente del pipeline principal).

Ejecutar en background:
    nohup python run_scopus_search.py > scopus_search.log 2>&1 &

Monitoreo:
    tail -f scopus_search.log
    cat scopus_search_state.json
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from scripts.phase_2_search.search_articles import search_scopus, _load_api_key

# ── Logging ───────────────────────────────────────────────────────────────────

STATE_DIR = Path(__file__).resolve().parent / "outputs" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path(__file__).parent / "scopus_search.log"
STATE_FILE = STATE_DIR / "scopus_search_state.json"
PROGRESS_FILE = STATE_DIR / "scopus_search_progress.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── Constants ─────────────────────────────────────────────────────────────────

TAXONOMY_CSV = PROJECT_ROOT / "data/input/final_taxonomy_occ.csv"
SEARCH_PROGRESS = STATE_DIR / "search_progress.json"  # pipeline principal
SCOPUS_RESULTS_DIR = PROJECT_ROOT / "outputs" / "scopus_results"
SCOPUS_BASE = "https://api.elsevier.com/content/search/scopus"
MAX_RESULTS = 20
TIMEOUT = 15
SLEEP_BETWEEN = 0.15  # respeta rate-limit de Elsevier (6 req/s máx.)




# ── State management ──────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "start_time": datetime.now().isoformat(),
        "status": "pending",
        "total": 0,
        "processed": 0,
        "found": 0,
        "errors": 0,
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


# ── Species list ──────────────────────────────────────────────────────────────

def load_all_species() -> list[str]:
    """Todas las especies limpias de final_taxonomy_occ.csv (sin híbridos/inciertas)."""
    new_species: list[str] = []
    with TAXONOMY_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sp = (row.get("species") or "").strip()
            if sp and "/" not in sp and " sp." not in sp and " spp." not in sp:
                new_species.append(sp)

    # Deduplicar manteniendo orden
    seen: set[str] = set()
    unique: list[str] = []
    for sp in new_species:
        if sp.lower() not in seen:
            seen.add(sp.lower())
            unique.append(sp)

    return unique


# ── Scopus search ─────────────────────────────────────────────────────────────



def save_articles(species_name: str, articles: list[dict], output_dir: Path) -> None:
    """Guarda artículos en CSV. Añade a archivo existente si ya tiene resultados."""
    if not articles:
        return

    safe_name = species_name.replace(" ", "_").replace("/", "_")
    csv_path = output_dir / f"{safe_name}.csv"

    fieldnames = ["source", "title", "authors", "year", "journal", "doi", "url", "pubmed_id", "arxiv_id"]

    # Si ya existe, cargar títulos existentes para deduplicar
    existing_titles: set[str] = set()
    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t = (row.get("title") or "").strip().lower()
                    if t:
                        existing_titles.add(t)
        except Exception:
            pass

    new_articles = [a for a in articles if a.get("title", "").strip().lower() not in existing_titles]
    if not new_articles:
        return

    write_header = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for article in new_articles:
            writer.writerow(article)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 70)
    logger.info("SCOPUS PARALLEL SEARCH — START")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 70)

    api_key = _load_api_key("SCOPUS_API_KEY", "scopus_apikey.txt")
    if not api_key:
        logger.error("No Scopus API key found. Set SCOPUS_API_KEY env var or secrets/scopus_apikey.txt")
        sys.exit(1)

    logger.info(f"Scopus API key: {api_key[:8]}***")

    SCOPUS_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    species_list = load_all_species()
    logger.info(f"Total species to search with Scopus: {len(species_list)}")

    # Load prior Scopus-specific progress
    progress = load_progress()
    already_done = {k.lower() for k in progress.keys()}

    # Filter out already done in this Scopus pass
    todo = [sp for sp in species_list if sp.lower() not in already_done]
    logger.info(f"Remaining (not yet in scopus_search_progress.json): {len(todo)}")

    state = load_state()
    state["status"] = "running"
    state["total"] = len(todo)
    state["processed"] = 0
    state["found"] = 0
    state["errors"] = 0
    save_state(state)

    for idx, species in enumerate(todo, 1):
        articles = search_scopus(species, api_key)
        count = len(articles)

        if articles:
            save_articles(species, articles, SCOPUS_RESULTS_DIR)
            state["found"] += 1

        progress[species] = count
        state["processed"] = idx

        if idx % 50 == 0 or idx == len(todo):
            save_progress(progress)
            save_state(state)
            pct = idx / len(todo) * 100
            logger.info(
                f"[{idx}/{len(todo)}] {pct:.1f}% | "
                f"Con artículos: {state['found']} | "
                f"Errores: {state['errors']}"
            )
        else:
            logger.debug(f"[{idx}/{len(todo)}] {species} → {count} artículos")

        # Log each 100
        if idx % 100 == 0:
            logger.info(
                f"Progreso: {idx}/{len(todo)} ({pct:.1f}%) — "
                f"Encontrados: {state['found']}"
            )

    save_progress(progress)
    state["status"] = "completed"
    state["end_time"] = datetime.now().isoformat()
    save_state(state)

    logger.info("=" * 70)
    logger.info("SCOPUS PARALLEL SEARCH — COMPLETED")
    logger.info(
        f"Total: {state['total']} | "
        f"Con artículos: {state['found']} | "
        f"Errores: {state['errors']}"
    )
    logger.info(f"Resultados en: {SCOPUS_RESULTS_DIR}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
