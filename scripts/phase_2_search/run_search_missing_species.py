#!/usr/bin/env python3
"""
Búsqueda de artículos para las especies canónicas (final_taxonomy_occ.csv)
que aún no tienen CSV en search_results/.

- Usa TODAS las fuentes: PubMed, CrossRef, Scopus, ScienceDirect, ArXiv.
- Guarda resultados en search_results/ (mismo directorio canónico).
- Progreso en missing_search_progress.json (reanudable).
- Al finalizar, genera paywall_articles.json con los artículos que NO
  pudieron descargarse por estar detrás de barrera de pago.

Uso:
    nohup python run_search_missing_species.py > missing_search.log 2>&1 &
    tail -f missing_search.log
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("missing_search.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── CLI args ──────────────────────────────────────────────────────────────────
import argparse
parser = argparse.ArgumentParser(description="Busca artículos para especies sin CSV")
parser.add_argument("--no-scopus", action="store_true", help="Omitir Scopus (cuota agotada)")
parser.add_argument("--no-sciencedirect", action="store_true", help="Omitir ScienceDirect")
args, _ = parser.parse_known_args()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "outputs" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
SEARCH_RESULTS_DIR = PROJECT_ROOT / "outputs" / "search_results"
PROGRESS_FILE = STATE_DIR / "missing_search_progress.json"
PAYWALL_FILE = STATE_DIR / "paywall_articles.json"

# Fuentes que tienen el artículo pero requieren suscripción para descargar el PDF
PAYWALLED_SOURCES = {"Scopus", "ScienceDirect"}

# Fuentes de acceso abierto donde sí se puede descargar el PDF
OPEN_SOURCES = {"PubMed", "ArXiv"}


# ── Configuración de env vars para las API keys ───────────────────────────────

def _load_key(env_var: str, secret_file: str) -> str:
    key = os.getenv(env_var, "").strip()
    if key:
        return key
    p = PROJECT_ROOT / "secrets" / secret_file
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""


os.environ.setdefault("SCOPUS_API_KEY", _load_key("SCOPUS_API_KEY", "scopus_apikey.txt"))
os.environ.setdefault("SCIENCEDIRECT_API_KEY", _load_key("SCIENCEDIRECT_API_KEY", "sciencedirect_apikey.txt"))


# ── Importar funciones de búsqueda ────────────────────────────────────────────

from scripts.phase_2_search.search_articles import (
    search_pubmed,
    search_crossref,
    search_scopus,
    search_sciencedirect,
    search_arxiv,
    _title_contains_species,
    save_species_articles,
)

FIELDNAMES = ["source", "title", "authors", "year", "journal", "doi", "url", "pubmed_id", "arxiv_id"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_canonical() -> list[str]:
    with open(PROJECT_ROOT / "data/input/final_taxonomy_occ.csv", newline="", encoding="utf-8") as f:
        return sorted({
            r["species"].strip()
            for r in csv.DictReader(f)
            if r.get("species", "").strip()
        })


def has_csv(sp: str) -> bool:
    return (SEARCH_RESULTS_DIR / f'{sp.replace(" ", "_")}.csv').exists()


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def load_paywall() -> list:
    if PAYWALL_FILE.exists():
        try:
            return json.loads(PAYWALL_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_paywall(records: list) -> None:
    PAYWALL_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def search_all_sources(species_name: str) -> list[dict]:
    """Busca en todas las fuentes disponibles y devuelve resultados filtrados."""
    all_results = []
    all_results.extend(search_pubmed(species_name))
    all_results.extend(search_crossref(species_name))
    if not args.no_scopus:
        all_results.extend(search_scopus(species_name))
    if not args.no_sciencedirect:
        all_results.extend(search_sciencedirect(species_name))
    all_results.extend(search_arxiv(species_name))

    # Filtro de relevancia para fuentes ruidosas
    noisy = {"CrossRef", "ArXiv"}
    all_results = [
        r for r in all_results
        if r.get("source") not in noisy
        or _title_contains_species(r.get("title", ""), species_name)
    ]

    # Deduplicar por título (case-insensitive)
    seen: set[str] = set()
    unique = []
    for r in all_results:
        t = r.get("title", "").lower().strip()
        if t and t not in seen:
            seen.add(t)
            unique.append(r)

    return unique


def classify_paywall(species_name: str, articles: list[dict]) -> list[dict]:
    """
    Devuelve los artículos que están detrás de paywall (sin PDF descargable).
    Estos tienen DOI/URL pero no son Open Access directos.
    """
    records = []
    for a in articles:
        source = a.get("source", "")
        if source in PAYWALLED_SOURCES:
            records.append({
                "species": species_name,
                "source": source,
                "title": a.get("title", ""),
                "doi": a.get("doi", ""),
                "url": a.get("url", ""),
                "year": a.get("year", ""),
                "journal": a.get("journal", ""),
            })
    return records


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 70)
    logger.info("  BÚSQUEDA ESPECIES SIN CSV  —  todas las editoriales")
    logger.info("  Fuentes: PubMed · CrossRef · Scopus · ScienceDirect · ArXiv")
    logger.info("=" * 70)

    scopus_key = os.environ.get("SCOPUS_API_KEY", "")
    sd_key = os.environ.get("SCIENCEDIRECT_API_KEY", "")
    logger.info(f"  Scopus API key:        {'OK (' + scopus_key[:8] + '...)' if scopus_key else 'NO DISPONIBLE'}" + (" [DESACTIVADO --no-scopus]" if args.no_scopus else ""))
    logger.info(f"  ScienceDirect API key: {'OK (' + sd_key[:8] + '...)' if sd_key else 'NO DISPONIBLE'}" + (" [DESACTIVADO --no-sciencedirect]" if args.no_sciencedirect else ""))
    logger.info(f"  Fuentes activas: PubMed · CrossRef · ArXiv" + (" · Scopus" if not args.no_scopus else "") + (" · ScienceDirect" if not args.no_sciencedirect else ""))
    logger.info("")

    canonical = load_canonical()
    missing = [sp for sp in canonical if not has_csv(sp)]
    logger.info(f"Especies canónicas totales: {len(canonical):,}")
    logger.info(f"Sin CSV (a buscar):         {len(missing):,}")

    if not missing:
        logger.info("Todas las especies canónicas ya tienen CSV. Nada que hacer.")
        return

    progress = load_progress()
    already = sum(1 for sp in missing if sp in progress)
    logger.info(f"Ya procesadas (sesión anterior): {already:,}")
    logger.info(f"Pendientes: {len(missing) - already:,}")
    logger.info("")

    paywall_records = load_paywall()
    found_total = 0
    processed = 0
    start = time.time()

    for idx, species_name in enumerate(missing, 1):
        # Saltar si ya procesada y el CSV ya existe con contenido
        if species_name in progress and has_csv(species_name):
            continue

        articles = search_all_sources(species_name)
        processed += 1

        if articles:
            save_species_articles(species_name, articles, SEARCH_RESULTS_DIR)
            found_total += 1

            # Clasificar artículos de paywall
            pw = classify_paywall(species_name, articles)
            if pw:
                paywall_records.extend(pw)

        # Guardar progreso
        progress[species_name] = len(articles)
        save_progress(progress)

        # Guardar lista de paywall cada 100 especies
        if processed % 100 == 0:
            save_paywall(paywall_records)

        # Log
        if processed % 50 == 0:
            elapsed = time.time() - start
            rate = processed / elapsed * 60
            remaining = (len(missing) - idx) / (rate / 60) / 60 if rate > 0 else 0
            logger.info(
                f"[{idx:,}/{len(missing):,}] "
                f"Con artículos: {found_total} | "
                f"Velocidad: {rate:.0f} esp/min | "
                f"ETA: {remaining:.1f}h | "
                f"Paywall acumulados: {len(paywall_records):,}"
            )
        elif articles:
            open_count = sum(1 for a in articles if a.get("source") in OPEN_SOURCES)
            pw_count = sum(1 for a in articles if a.get("source") in PAYWALLED_SOURCES)
            logger.info(
                f"  [{idx:,}] {species_name}: "
                f"{len(articles)} artículos "
                f"(OA:{open_count} · paywall:{pw_count})"
            )

    # Guardar paywall final
    save_paywall(paywall_records)

    elapsed_total = time.time() - start
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"Búsqueda completada en {elapsed_total/3600:.1f}h")
    logger.info(f"Especies con artículos: {found_total:,} / {processed:,}")
    logger.info(f"Artículos tras paywall: {len(paywall_records):,}  → {PAYWALL_FILE.name}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
