#!/usr/bin/env python3
"""
Script para buscar artículos en Scopus API de forma individual.

Scopus es la base de datos científica más grande (>24 millones de artículos).

Requisitos:
  1. Tener cuenta en https://dev.elsevier.com
  2. Crear una aplicación y obtener API key
  3. Crear archivo .env con: SCOPUS_API_KEY=tu_key_aqui

Uso:
  python3 search_scopus.py "nombre de especie"
  python3 search_scopus.py "Acanthaster planci"
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Constantes
SCOPUS_API = "https://api.elsevier.com/content/search/scopus"
MAX_RESULTS = 100


class ScopusSearcher:
    """Cliente para búsqueda en Scopus API."""

    def __init__(self, api_key: str | None = None):
        """Inicializa el buscador."""
        self.api_key = api_key or os.getenv("SCOPUS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "SCOPUS_API_KEY no configurada. "
                "Edita .env o usa: export SCOPUS_API_KEY=tu_key"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json",
        })

    def search(self, query: str, max_results: int = MAX_RESULTS) -> list[dict[str, Any]]:
        """Busca artículos en Scopus."""
        logger.info(f"Buscando en Scopus: '{query}'")

        results = []
        page_size = min(25, max_results)  # Scopus permite máx 25 por página

        try:
            for start in range(0, max_results, page_size):
                params = {
                    "query": f'TITLE-ABS-KEY("{query}")',
                    "start": start,
                    "count": page_size,
                    "sort": "citedby-count",
                    "view": "COMPLETE",
                }

                logger.debug(f"  Página {start // page_size + 1}...")
                response = self.session.get(SCOPUS_API, params=params, timeout=30)

                if response.status_code == 401:
                    raise ValueError("API key inválida o expirada")
                if response.status_code == 429:
                    raise RuntimeError("Rate limit excedido. Intenta más tarde.")
                if response.status_code != 200:
                    logger.warning(f"Status {response.status_code}: {response.text}")
                    continue

                data = response.json()
                entries = data.get("search-results", {}).get("entry", [])

                if not entries:
                    logger.info(f"  No hay más resultados")
                    break

                for entry in entries:
                    results.append(self._parse_entry(entry))

                # Verificar si hay más resultados
                total_results = int(
                    data.get("search-results", {}).get("opensearch:totalResults", 0)
                )
                logger.info(f"  Encontrados {len(results)}/{total_results} artículos")

                if len(results) >= max_results:
                    break

        except requests.RequestException as e:
            logger.error(f"Error en API: {e}")
            raise

        return results[:max_results]

    def _parse_entry(self, entry: dict) -> dict[str, Any]:
        """Parsea una entrada de Scopus."""
        return {
            "source": "Scopus",
            "eid": entry.get("eid", ""),
            "doi": entry.get("prism:doi", ""),
            "title": entry.get("dc:title", ""),
            "authors": ", ".join([
                f"{a.get('surname', '')} {a.get('given-name', '')}"
                for a in entry.get("author", [])[:3]
            ]),
            "year": entry.get("prism:coverDate", "")[:4],
            "journal": entry.get("prism:publicationName", ""),
            "cited_by": entry.get("citedby-count", "0"),
            "url": entry.get("link", [{}])[0].get("@href", ""),
            "abstract": entry.get("dc:description", "")[:200] if entry.get("dc:description") else "",
        }


def display_results(results: list[dict[str, Any]]) -> None:
    """Muestra resultados en formato tabla."""
    if not results:
        print("❌ No se encontraron resultados")
        return

    print(f"\n✅ Encontrados {len(results)} artículos\n")

    for i, article in enumerate(results, 1):
        print(f"{i}. {article['title']}")
        print(f"   Autores: {article['authors']}")
        print(f"   Journal: {article['journal']} ({article['year']})")
        print(f"   Citaciones: {article['cited_by']}")
        print(f"   DOI: {article['doi']}")
        if article["abstract"]:
            print(f"   Resumen: {article['abstract']}...")
        print()


def save_results(results: list[dict[str, Any]], output_file: Path) -> None:
    """Guarda resultados en CSV."""
    if not results:
        return

    fieldnames = [
        "source",
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "eid",
        "cited_by",
        "url",
        "abstract",
    ]

    with output_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n💾 Resultados guardados en: {output_file}")


def main():
    """Punto de entrada."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "species",
        nargs="?",
        help="Nombre de la especie a buscar",
    )
    parser.add_argument(
        "--api-key",
        help="API key de Scopus (o usar variable de entorno SCOPUS_API_KEY)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=50,
        help="Máximo de artículos a obtener (default: 50)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Guardar resultados en CSV",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Mostrar resultados en JSON",
    )

    args = parser.parse_args()

    if not args.species:
        parser.print_help()
        print("\n📋 Ejemplos:")
        print("  python3 search_scopus.py 'Acanthaster planci'")
        print("  python3 search_scopus.py 'Coral reef biodiversity' --max 100")
        print("  python3 search_scopus.py 'fish diseases' -o resultados.csv")
        return

    try:
        # Crear buscador
        searcher = ScopusSearcher(args.api_key)

        # Buscar
        results = searcher.search(args.species, max_results=args.max)

        # Mostrar resultados
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            display_results(results)

        # Guardar si se solicita
        if args.output:
            save_results(results, args.output)

    except ValueError as e:
        logger.error(f"❌ Error de configuración: {e}")
        print("\n📝 Para usar Scopus API:")
        print("  1. Ir a https://dev.elsevier.com")
        print("  2. Crear cuenta y aplicación")
        print("  3. Copiar API key a .env: SCOPUS_API_KEY=tu_key")
        print("\n  O usa variable de entorno:")
        print("     export SCOPUS_API_KEY=tu_key_aqui")
        return 1

    except RuntimeError as e:
        logger.error(f"❌ {e}")
        return 1


if __name__ == "__main__":
    exit(main())
