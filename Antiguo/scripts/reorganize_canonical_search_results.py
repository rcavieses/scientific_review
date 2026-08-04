#!/usr/bin/env python3
"""Reorganiza resultados de búsqueda canónicos para el pipeline de PDFs.

Acciones:
  1. Lee especies canónicas de final_taxonomy_occ.csv.
  2. Recorre search_results/ y conserva solo CSVs que correspondan a la lista.
  3. Resuelve duplicados por diferencias de mayúsculas/minúsculas con una regla
     determinista, sin modificar los archivos originales.
  4. Copia la versión canónica a search_results_canonical/.
  5. Genera reportes JSON/CSV con seleccionados, faltantes, no canónicos y duplicados.

Uso:
  ./venv/bin/python scripts/reorganize_canonical_search_results.py
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_CSV = PROJECT_ROOT / "data/input/final_taxonomy_occ.csv"
SEARCH_RESULTS_DIR = PROJECT_ROOT / "outputs" / "search_results"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "search_results_canonical"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"


def normalize_canonical_species(value: str) -> str:
    return " ".join(value.strip().lower().replace("/", " ").split())


def normalize_search_stem(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("/", " ").split())


def safe_csv_name(species_name: str) -> str:
    return species_name.replace(" ", "_").replace("/", "_") + ".csv"


def load_canonical_species() -> dict[str, str]:
    canonical: dict[str, str] = {}
    with CANONICAL_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            species_name = (row.get("species") or "").strip()
            if not species_name:
                continue
            canonical.setdefault(normalize_canonical_species(species_name), species_name)
    return canonical


def choose_preferred_file(species_name: str, candidates: list[Path]) -> Path:
    preferred_name = safe_csv_name(species_name)
    exact_matches = [candidate for candidate in candidates if candidate.name == preferred_name]
    if exact_matches:
        return sorted(exact_matches, key=lambda path: path.name)[0]
    return sorted(candidates, key=lambda path: (path.name.lower(), path.name))[0]


def write_csv_report(file_path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with file_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    canonical = load_canonical_species()
    grouped: dict[str, list[Path]] = defaultdict(list)
    non_canonical: list[Path] = []

    for csv_file in sorted(SEARCH_RESULTS_DIR.glob("*.csv")):
        normalized = normalize_search_stem(csv_file.stem)
        if normalized in canonical:
            grouped[normalized].append(csv_file)
        else:
            non_canonical.append(csv_file)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    selected_rows: list[dict[str, str]] = []
    duplicate_rows: list[dict[str, str]] = []
    missing_rows: list[dict[str, str]] = []
    non_canonical_rows: list[dict[str, str]] = []

    for existing in OUTPUT_DIR.glob("*.csv"):
        existing.unlink()

    for normalized_name, species_name in sorted(canonical.items()):
        candidates = grouped.get(normalized_name, [])
        if not candidates:
            missing_rows.append({
                "normalized_species": normalized_name,
                "canonical_species": species_name,
            })
            continue

        selected = choose_preferred_file(species_name, candidates)
        target = OUTPUT_DIR / safe_csv_name(species_name)
        shutil.copy2(selected, target)

        selected_rows.append({
            "normalized_species": normalized_name,
            "canonical_species": species_name,
            "selected_file": selected.name,
            "output_file": target.name,
            "candidate_count": str(len(candidates)),
        })

        for duplicate in sorted(candidates, key=lambda path: (path.name.lower(), path.name)):
            if duplicate == selected:
                continue
            duplicate_rows.append({
                "normalized_species": normalized_name,
                "canonical_species": species_name,
                "selected_file": selected.name,
                "ignored_duplicate": duplicate.name,
            })

    for csv_file in non_canonical:
        non_canonical_rows.append({
            "normalized_species": normalize_search_stem(csv_file.stem),
            "source_file": csv_file.name,
        })

    summary = {
        "canonical_species_total": len(canonical),
        "canonical_species_with_file": len(selected_rows),
        "canonical_species_missing_file": len(missing_rows),
        "search_result_files_total": sum(1 for _ in SEARCH_RESULTS_DIR.glob("*.csv")),
        "search_result_files_non_canonical": len(non_canonical_rows),
        "duplicate_candidates_ignored": len(duplicate_rows),
        "canonical_output_dir": str(OUTPUT_DIR.relative_to(PROJECT_ROOT)),
    }

    (REPORT_DIR / "canonical_search_results_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORT_DIR / "canonical_search_results_selected.json").write_text(
        json.dumps(selected_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORT_DIR / "canonical_search_results_duplicates.json").write_text(
        json.dumps(duplicate_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORT_DIR / "canonical_search_results_missing.json").write_text(
        json.dumps(missing_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORT_DIR / "canonical_search_results_non_canonical.json").write_text(
        json.dumps(non_canonical_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_csv_report(
        REPORT_DIR / "canonical_search_results_selected.csv",
        selected_rows,
        ["normalized_species", "canonical_species", "selected_file", "output_file", "candidate_count"],
    )
    write_csv_report(
        REPORT_DIR / "canonical_search_results_duplicates.csv",
        duplicate_rows,
        ["normalized_species", "canonical_species", "selected_file", "ignored_duplicate"],
    )
    write_csv_report(
        REPORT_DIR / "canonical_search_results_missing.csv",
        missing_rows,
        ["normalized_species", "canonical_species"],
    )
    write_csv_report(
        REPORT_DIR / "canonical_search_results_non_canonical.csv",
        non_canonical_rows,
        ["normalized_species", "source_file"],
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()