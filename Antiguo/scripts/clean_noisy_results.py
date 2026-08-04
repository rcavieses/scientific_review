#!/usr/bin/env python3
"""
Limpia los resultados de búsqueda y PDFs descargados con el método anterior
(CrossRef sin comillas, ArXiv con all:).

Acciones:
  1. Reescribe los CSVs en search_results/ eliminando filas de CrossRef/ArXiv
     donde el título NO contiene el nombre de la especie (binomio completo).
  2. Elimina PDFs en outputs/pdfs/pdfs2/<especie>/ descargados desde esas
     filas ruidosas (identificados por prefijo CrossRef_/ArXiv_ en el nombre
     del archivo y ausencia del nombre de especie en el filename).
  3. Elimina carpetas de especie que quedan vacías tras la limpieza.
  4. Resetea download_progress.json para permitir re-descarga limpia.

Uso:
  python scripts/clean_noisy_results.py [--dry-run]
"""

import argparse
import csv
import io
import json
import logging
import shutil
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
SEARCH_RESULTS_DIR = PROJECT_ROOT / "outputs" / "search_results"
PDFS2_DIR = PROJECT_ROOT / "outputs" / "pdfs" / "pdfs2"
PROGRESS_FILE = PROJECT_ROOT / "outputs" / "state" / "download_progress.json"

NOISY_SOURCES = {"CrossRef", "ArXiv"}


def title_contains_species(title: str, species_name: str) -> bool:
    """Devuelve True si el título contiene el binomio completo de la especie."""
    title_lower = title.lower()
    parts = species_name.lower().split()
    if len(parts) >= 2:
        return parts[0] in title_lower and parts[1] in title_lower
    return parts[0] in title_lower if parts else False


def clean_csv(csv_file: Path, dry_run: bool) -> tuple[int, int]:
    """
    Reescribe el CSV eliminando filas ruidosas.

    Returns:
        (filas_totales, filas_eliminadas)
    """
    species_name = csv_file.stem.replace("_", " ")
    kept_rows = []
    removed = 0
    total = 0

    try:
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            for row in reader:
                total += 1
                src = row.get("source", "")
                title = row.get("title", "")
                if src in NOISY_SOURCES and not title_contains_species(title, species_name):
                    removed += 1
                else:
                    kept_rows.append(row)
    except Exception as e:
        logger.warning(f"Error leyendo {csv_file.name}: {e}")
        return 0, 0

    if removed == 0:
        return total, 0

    if not dry_run:
        if kept_rows:
            # Reescribir con solo las filas relevantes
            tmp = csv_file.with_suffix(".tmp")
            with open(tmp, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(kept_rows)
            tmp.replace(csv_file)
        else:
            # Sin filas relevantes: dejar el CSV solo con el header
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

    return total, removed


def is_noisy_pdf(pdf_path: Path, species_parts: list[str]) -> bool:
    """
    True si el PDF fue descargado de una fuente ruidosa y no corresponde a la especie.
    Solo aplica a archivos que empiezan con CrossRef_ o ArXiv_.
    """
    fname = pdf_path.name
    if not (fname.startswith("CrossRef_") or fname.startswith("ArXiv_")):
        return False
    fname_lower = fname.lower()
    # Si alguna parte significativa del nombre de especie aparece en el filename, es legítimo
    return not any(p in fname_lower for p in species_parts if len(p) > 3)


def clean_pdfs(dry_run: bool) -> tuple[int, int, float]:
    """
    Elimina PDFs ruidosos de pdfs2.

    Returns:
        (pdfs_eliminados, carpetas_eliminadas, mb_liberados)
    """
    deleted_pdfs = 0
    deleted_dirs = 0
    freed_bytes = 0

    if not PDFS2_DIR.exists():
        return 0, 0, 0.0

    for species_dir in sorted(PDFS2_DIR.iterdir()):
        if not species_dir.is_dir():
            continue

        species_parts = species_dir.name.lower().split()

        for pdf in list(species_dir.glob("*.pdf")):
            if is_noisy_pdf(pdf, species_parts):
                freed_bytes += pdf.stat().st_size
                if not dry_run:
                    pdf.unlink()
                deleted_pdfs += 1

        # Si la carpeta quedó vacía, eliminarla
        if not dry_run and species_dir.exists():
            remaining = list(species_dir.iterdir())
            if not remaining:
                species_dir.rmdir()
                deleted_dirs += 1

    return deleted_pdfs, deleted_dirs, freed_bytes / 1024 / 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo reportar sin modificar archivos",
    )
    args = parser.parse_args()

    mode = "DRY-RUN (sin cambios)" if args.dry_run else "LIMPIEZA REAL"
    logger.info(f"{'='*60}")
    logger.info(f"  LIMPIEZA DE RESULTADOS RUIDOSOS — {mode}")
    logger.info(f"{'='*60}")

    # ── 1. Limpiar CSVs ──────────────────────────────────────────
    logger.info("Paso 1: Limpiando CSVs de search_results/...")
    csv_files = sorted(SEARCH_RESULTS_DIR.glob("*.csv"))
    total_csv_rows = 0
    total_removed_rows = 0
    empty_species = 0

    for i, csv_file in enumerate(csv_files, 1):
        total, removed = clean_csv(csv_file, args.dry_run)
        total_csv_rows += total
        total_removed_rows += removed
        if total - removed == 0:
            empty_species += 1
        if i % 2000 == 0:
            logger.info(f"  Procesados {i}/{len(csv_files)} CSVs...")

    logger.info(
        f"  CSVs procesados:   {len(csv_files):,}\n"
        f"  Filas totales:     {total_csv_rows:,}\n"
        f"  Filas eliminadas:  {total_removed_rows:,} ({total_removed_rows/max(1,total_csv_rows)*100:.1f}%)\n"
        f"  Filas conservadas: {total_csv_rows - total_removed_rows:,}\n"
        f"  Especies sin art.: {empty_species:,}"
    )

    # ── 2. Limpiar PDFs ──────────────────────────────────────────
    logger.info("Paso 2: Eliminando PDFs ruidosos de outputs/pdfs/pdfs2/...")
    del_pdfs, del_dirs, freed_mb = clean_pdfs(args.dry_run)
    logger.info(
        f"  PDFs eliminados:   {del_pdfs:,}\n"
        f"  Carpetas vacías:   {del_dirs:,}\n"
        f"  Espacio liberado:  {freed_mb:.1f} MB"
    )

    # ── 3. Reset download_progress.json ─────────────────────────
    if not args.dry_run:
        logger.info("Paso 3: Reseteando download_progress.json...")
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.write_text("{}", encoding="utf-8")
            logger.info("  download_progress.json reseteado a {}")
    else:
        logger.info("Paso 3: [DRY-RUN] download_progress.json no modificado")

    logger.info("=" * 60)
    if args.dry_run:
        logger.info("DRY-RUN completado. Ejecuta sin --dry-run para aplicar cambios.")
    else:
        logger.info("Limpieza completada.")


if __name__ == "__main__":
    main()
