"""
Pipeline completo para nuevas especies de final_taxonomy_occ.csv.

1. Lee especies de final_taxonomy_occ.csv (columna 'species')
2. Compara contra search_progress.json - solo procesa especies nuevas
3. Busca artículos con todas las APIs disponibles (crossref, pubmed, arxiv, scopus)
4. Descarga PDFs en acceso abierto
5. Indexa todo en FAISS para RAG

Diseñado para correr en background (nohup):
    nohup python run_new_species_pipeline.py > pipeline_new_species.log 2>&1 &

Monitoreo:
    tail -f pipeline_new_species.log
    cat pipeline_new_species_state.json
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Project structure ───────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Logging ──────────────────────────────────────────────────────────────────

STATE_DIR = PROJECT_ROOT / "outputs" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = PROJECT_ROOT / "outputs" / "logs" / "pipeline_new_species.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "pipeline_new_species_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

TAXONOMY_CSV = PROJECT_ROOT / "data" / "input" / "final_taxonomy_occ.csv"
SEARCH_PROGRESS = STATE_DIR / "search_progress.json"
DOWNLOAD_PROGRESS = STATE_DIR / "download_progress.json"
SEARCH_RESULTS_DIR = PROJECT_ROOT / "outputs" / "search_results"
PDFS_DIR = PROJECT_ROOT / "pdfs"
RAG_INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index"
OUTPUTS_PDFS_DIR = PROJECT_ROOT / "outputs" / "pdfs"


# ── State management ─────────────────────────────────────────────────────────

def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "start_time": datetime.now().isoformat(),
        "phase": "pending",
        "search": {"status": "pending", "total": 0, "processed": 0, "found": 0},
        "download": {"status": "pending"},
        "index": {"status": "pending"},
    }


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Species helpers ──────────────────────────────────────────────────────────

def load_new_species() -> list[str]:
    """Returns species from final_taxonomy_occ.csv not yet in search_progress.json."""
    # Load new species list
    new_species: list[str] = []
    with TAXONOMY_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sp = (row.get("species") or "").strip()
            # Skip empty, uncertain or hybrid species names
            if sp and "/" not in sp and " sp." not in sp and " spp." not in sp:
                new_species.append(sp)

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_species: list[str] = []
    for sp in new_species:
        key = sp.lower()
        if key not in seen:
            seen.add(key)
            unique_species.append(sp)

    # Load previously searched species
    prev_species: set[str] = set()
    if SEARCH_PROGRESS.exists():
        try:
            progress = json.loads(SEARCH_PROGRESS.read_text(encoding="utf-8"))
            prev_species = {k.lower() for k in progress.keys()}
        except Exception as e:
            logger.warning(f"Could not load search_progress.json: {e}")

    # Filter to only new species
    to_search = [sp for sp in unique_species if sp.lower() not in prev_species]

    logger.info(f"Total unique species in CSV (clean): {len(unique_species)}")
    logger.info(f"Previously searched: {len(prev_species)}")
    logger.info(f"New species to search: {len(to_search)}")

    return to_search


# ── Phase 1: Search ──────────────────────────────────────────────────────────

def run_search_phase(species_list: list[str], state: dict[str, Any]) -> None:
    """Search articles for all new species using all available APIs."""
    logger.info("=" * 70)
    logger.info("PHASE 1: Searching articles for new species")
    logger.info("=" * 70)

    # Import here to respect virtualenv
    from scripts.phase_2_search.search_articles import search_articles_batch

    state["phase"] = "search"
    state["search"]["status"] = "running"
    state["search"]["total"] = len(species_list)
    save_state(state)

    SEARCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = search_articles_batch(
        species_list,
        SEARCH_RESULTS_DIR,
        SEARCH_PROGRESS,
    )

    state["search"]["status"] = "completed"
    state["search"]["processed"] = results.get("processed", 0)
    state["search"]["found"] = results.get("found", 0)
    save_state(state)

    logger.info(f"Search phase complete: {results.get('found', 0)}/{results.get('processed', 0)} species with articles")


# ── Phase 2: Download ─────────────────────────────────────────────────────────

def run_download_phase(state: dict[str, Any]) -> None:
    """Download PDFs for all newly found articles."""
    logger.info("=" * 70)
    logger.info("PHASE 2: Downloading PDFs")
    logger.info("=" * 70)

    from scripts.phase_3_download.download_pdfs import download_all_articles

    state["phase"] = "download"
    state["download"]["status"] = "running"
    save_state(state)

    PDFS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        results = download_all_articles(
            SEARCH_RESULTS_DIR,
            PDFS_DIR,
            DOWNLOAD_PROGRESS,
        )

        state["download"]["status"] = "completed"
        state["download"]["total_species"] = results.get("total_species", 0)
        state["download"]["total_articles"] = results.get("total_articles", 0)
        state["download"]["total_downloaded"] = results.get("total_downloaded", 0)
        save_state(state)

        logger.info(
            f"Download phase complete: {results.get('total_downloaded', 0)} PDFs "
            f"from {results.get('total_articles', 0)} articles"
        )
    except Exception as e:
        logger.error(f"Download phase error: {e}", exc_info=True)
        state["download"]["status"] = "error"
        state["download"]["error"] = str(e)
        save_state(state)


# ── Phase 3: RAG Indexing ─────────────────────────────────────────────────────

def run_index_phase(state: dict[str, Any]) -> None:
    """Index all PDFs (both pdfs/ and outputs/pdfs/) into FAISS for RAG."""
    logger.info("=" * 70)
    logger.info("PHASE 3: Building/updating RAG index")
    logger.info("=" * 70)

    state["phase"] = "index"
    state["index"]["status"] = "running"
    save_state(state)

    RAG_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # Count PDFs available
    pdfs_to_index: list[Path] = []
    for pdf_dir in [PDFS_DIR, OUTPUTS_PDFS_DIR]:
        if pdf_dir.exists():
            pdfs_to_index.extend(pdf_dir.rglob("*.pdf"))

    logger.info(f"PDFs found to index: {len(pdfs_to_index)}")

    if not pdfs_to_index:
        logger.warning("No PDFs found to index. Skipping RAG indexing.")
        state["index"]["status"] = "skipped"
        state["index"]["reason"] = "no PDFs found"
        save_state(state)
        return

    # Run indexar.py via subprocess for the main pdfs/ directory
    # (it handles subdirectories recursively)
    errors: list[str] = []

    for pdf_dir, label in [(PDFS_DIR, "pdfs/"), (OUTPUTS_PDFS_DIR, "outputs/pdfs/")]:
        if not pdf_dir.exists():
            continue

        pdfs_in_dir = list(pdf_dir.rglob("*.pdf"))
        if not pdfs_in_dir:
            logger.info(f"No PDFs in {label}, skipping.")
            continue

        logger.info(f"Indexing {len(pdfs_in_dir)} PDFs from {label} ...")

        cmd = [
            sys.executable, str(PROJECT_ROOT / "scripts" / "phase_5_indexing" / "indexar.py"),
            "--pdf-dir", str(pdf_dir),
            "--index-dir", str(RAG_INDEX_DIR),
            "--provider", "local",
            "--chunk-size", "2000",
            "--overlap", "200",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=False,
                text=True,
                cwd=str(PROJECT_ROOT),
                timeout=7200,  # 2h max per directory
            )
            if result.returncode != 0:
                msg = f"indexar.py returned code {result.returncode} for {label}"
                logger.error(msg)
                errors.append(msg)
            else:
                logger.info(f"Indexing of {label} completed successfully.")
        except subprocess.TimeoutExpired:
            msg = f"Indexing timeout (2h) for {label}"
            logger.error(msg)
            errors.append(msg)
        except Exception as e:
            msg = f"Indexing error for {label}: {e}"
            logger.error(msg, exc_info=True)
            errors.append(msg)

    if errors:
        state["index"]["status"] = "completed_with_errors"
        state["index"]["errors"] = errors
    else:
        state["index"]["status"] = "completed"
    save_state(state)

    # Final stats
    try:
        config_path = RAG_INDEX_DIR / "index_config.json"
        if config_path.exists():
            import json as _json
            cfg = _json.loads(config_path.read_text())
            logger.info(f"RAG index config: {cfg}")
    except Exception:
        pass

    logger.info("RAG indexing phase complete.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 70)
    logger.info("NEW SPECIES PIPELINE — START")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"PID: {os.getpid()}")
    logger.info("=" * 70)

    state = load_state()
    start_phase = state.get("phase", "pending")

    # ── Step 1: Determine which species are new
    logger.info("Loading species lists...")
    species_to_search = load_new_species()

    if not species_to_search:
        logger.info("No new species found. All species have already been searched.")
        state["phase"] = "completed"
        state["end_time"] = datetime.now().isoformat()
        save_state(state)
        return

    # ── Step 2: Search phase (skip if already completed)
    if start_phase not in ("download", "index", "completed"):
        run_search_phase(species_to_search, state)
    else:
        logger.info(f"Skipping search phase (state: {start_phase})")

    # ── Step 3: Download phase (skip if already completed)
    if start_phase not in ("index", "completed"):
        run_download_phase(state)
    else:
        logger.info(f"Skipping download phase (state: {start_phase})")

    # ── Step 4: Index phase
    if start_phase != "completed":
        run_index_phase(state)

    # ── Done
    state["phase"] = "completed"
    state["end_time"] = datetime.now().isoformat()
    save_state(state)

    logger.info("=" * 70)
    logger.info("NEW SPECIES PIPELINE — COMPLETED SUCCESSFULLY")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"State saved to: {STATE_FILE}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
