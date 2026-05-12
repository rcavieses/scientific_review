"""Extrae valores unicos de la columna 'species' y los exporta a un CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def extraer_species_unicas(input_csv: Path, output_csv: Path, column_name: str = "species") -> int:
    """Lee un CSV, obtiene los valores unicos de una columna y los guarda en otro CSV.

    Args:
        input_csv: Ruta del archivo CSV de entrada.
        output_csv: Ruta del archivo CSV de salida.
        column_name: Nombre de la columna de la que se extraeran valores unicos.

    Returns:
        Cantidad de valores unicos exportados.
    """
    unique_values: set[str] = set()

    with input_csv.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)

        if reader.fieldnames is None or column_name not in reader.fieldnames:
            raise ValueError(
                f"La columna '{column_name}' no existe en el archivo. "
                f"Columnas disponibles: {reader.fieldnames}"
            )

        for row in reader:
            value = (row.get(column_name) or "").strip()
            if value:
                unique_values.add(value)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    sorted_values = sorted(unique_values)

    with output_csv.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow([column_name])
        for value in sorted_values:
            writer.writerow([value])

    return len(sorted_values)


def parse_args() -> argparse.Namespace:
    """Parsea argumentos de linea de comandos."""
    project_root = Path(__file__).resolve().parents[1]

    default_input = project_root / "biodiversity_integrated_conabio_2025-09-19.csv"
    default_output = project_root / "analysis_species" / "species_unicas.csv"

    parser = argparse.ArgumentParser(
        description="Extrae valores unicos de una columna CSV y los exporta a un CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help=f"Ruta al CSV de entrada (default: {default_input})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=f"Ruta al CSV de salida (default: {default_output})",
    )
    parser.add_argument(
        "--column",
        default="species",
        help="Nombre de la columna a procesar (default: species)",
    )

    return parser.parse_args()


def main() -> None:
    """Punto de entrada del script."""
    args = parse_args()
    total = extraer_species_unicas(args.input, args.output, args.column)
    print(f"Se exportaron {total} valores unicos a: {args.output}")


if __name__ == "__main__":
    main()
