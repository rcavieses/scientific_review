"""
Descarga PDFs de resultados Scopus e indexa en RAG.

Fase 2 y 3 del pipeline Scopus paralelo:
  - Descarga PDFs desde scopus_results/
  - Indexa en outputs/rag_index/ (mismo índice que el pipeline principal)

Ejecutar en background:
    nohup python run_scopus_download_index.py > scopus_download_index.log 2>&1 &

Monitoreo:
    tail -f scopus_download_index.log
    cat scopus_download_index_state.json
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────

STATE_DIR = Path(__file__).resolve().parent / "outputs" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path(__file__).parent / "scopus_download_index.log"
STATE_FILE = STATE_DIR / "scopus_download_index_state.json"

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

SCOPUS_RESULTS_DIR = PROJECT_ROOT / "outputs" / "scopus_results"
SCOPUS_PDFS_DIR = PROJECT_ROOT / "pdfs"          # mismo dir que pipeline principal
SCOPUS_DOWNLOAD_PROGRESS = STATE_DIR / "scopus_download_progress.json"
RAG_INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index"


# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "start_time": datetime.now().isoformat(),
        "download": {"status": "pending"},
        "index": {"status": "pending"},
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Phase 1: Download ─────────────────────────────────────────────────────────

def run_download(state: dict) -> None:
    logger.info("=" * 70)
    logger.info("SCOPUS PHASE 2: Downloading PDFs from scopus_results/")
    logger.info("=" * 70)

    from scripts.phase_3_download.download_pdfs import download_all_articles

    state["download"]["status"] = "running"
    save_state(state)

    try:
        results = download_all_articles(
            SCOPUS_RESULTS_DIR,
            SCOPUS_PDFS_DIR,
            SCOPUS_DOWNLOAD_PROGRESS,
        )
        state["download"]["status"] = "completed"
        state["download"].update(results)
        save_state(state)
        logger.info(
            f"Download complete: {results.get('total_downloaded', 0)} PDFs "
            f"from {results.get('total_articles', 0)} articles"
        )
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        state["download"]["status"] = "error"
        state["download"]["error"] = str(e)
        save_state(state)


# ── Phase 2: RAG Index ────────────────────────────────────────────────────────

def run_index(state: dict) -> None:
    logger.info("=" * 70)
    logger.info("SCOPUS PHASE 3: Updating RAG index with new PDFs")
    logger.info("=" * 70)

    RAG_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = list(SCOPUS_PDFS_DIR.rglob("*.pdf"))
    logger.info(f"Total PDFs in {SCOPUS_PDFS_DIR}: {len(pdfs)}")

    if not pdfs:
        logger.warning("No PDFs found. Skipping indexing.")
        state["index"]["status"] = "skipped"
        state["index"]["reason"] = "no PDFs"
        save_state(state)
        return

    state["index"]["status"] = "running"
    save_state(state)

    cmd = [
        sys.executable, str(PROJECT_ROOT / "scripts" / "phase_5_indexing" / "indexar.py"),
        "--pdf-dir", str(SCOPUS_PDFS_DIR),
        "--index-dir", str(RAG_INDEX_DIR),
        "--provider", "local",
        "--chunk-size", "2000",
        "--overlap", "200",
    ]

    logger.info(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=14400,  # 4h max
        )
        if result.returncode == 0:
            state["index"]["status"] = "completed"
            logger.info("RAG indexing completed successfully.")
        else:
            state["index"]["status"] = "error"
            state["index"]["returncode"] = result.returncode
            logger.error(f"indexar.py exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        state["index"]["status"] = "timeout"
        logger.error("Indexing timed out after 4h.")
    except Exception as e:
        state["index"]["status"] = "error"
        state["index"]["error"] = str(e)
        logger.error(f"Indexing error: {e}", exc_info=True)

    save_state(state)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 70)
    logger.info("SCOPUS DOWNLOAD + INDEX — START")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"PID:  {os.getpid()}")
    logger.info(f"scopus_results CSVs: {len(list(SCOPUS_RESULTS_DIR.glob('*.csv')))}")
    logger.info("=" * 70)

    state = load_state()

    # Resume logic
    if state["download"]["status"] not in ("completed",):
        run_download(state)
    else:
        logger.info("Download already completed, skipping.")

    if state["index"]["status"] not in ("completed",):
        run_index(state)
    else:
        logger.info("Indexing already completed, skipping.")

    state["end_time"] = datetime.now().isoformat()
    save_state(state)

    logger.info("=" * 70)
    logger.info("SCOPUS DOWNLOAD + INDEX — COMPLETED")
    logger.info(f"State: {STATE_FILE}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
