#!/usr/bin/env python3
"""
Buscar artículos científicos para especies con criterios geográficos específicos:
- Golfo de California / Baja California Gulf
- Pacífico mexicano / Mexican Pacific

Filtra resultados donde título, resumen o palabras clave mencionen la región.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Cargar variables de entorno
_project_root = Path(__file__).parent
_env_file = _project_root / ".env"
load_dotenv(_env_file)

logger = logging.getLogger(__name__)

# URLs de APIs
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF_BASE = "https://api.crossref.org/works"
ARXIV_BASE = "http://export.arxiv.org/api/query"
SCIENCEDIRECT_BASE = "https://api.elsevier.com/content/search/sciencedirect"
SCOPUS_BASE = "https://api.elsevier.com/content/search/scopus"

# Configuración
MAX_RESULTS = 20  # máximo de artículos por especie
TIMEOUT = 15
SLEEP_PUBMED = 0.3  # segundos entre peticiones PubMed
SLEEP_CROSSREF = 0.1
SLEEP_ARXIV = 0.1

# Términos de búsqueda para la región
REGION_TERMS = [
    "Gulf of California",
    "Golfo de California",
    "Baja California Gulf",
    "California Gulf",
    "Mexican Pacific",
    "Pacífico mexicano",
    "Pacifico mexicano",
    "Mexico Pacific",
]


def _contains_region_terms(text: str) -> bool:
    """Verifica si el texto contiene referencias a la región."""
    if not text:
        return False
    text_lower = text.lower()
    return any(term.lower() in text_lower for term in REGION_TERMS)


def search_pubmed_region(species_name: str) -> list[dict[str, Any]]:
    """Busca artículos en PubMed con criterio geográfico."""
    results = []
    try:
        # Agregar términos de región a la búsqueda
        region_query = " OR ".join([f'"{term}"' for term in REGION_TERMS])
        search_url = f"{PUBMED_BASE}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": f'("{species_name}"[Organism] OR "{species_name}"[Title/Abstract]) AND ({region_query}[Title/Abstract])',
            "retmax": MAX_RESULTS,
            "rettype": "json",
        }

        search_resp = requests.get(search_url, params=search_params, timeout=TIMEOUT)
        if search_resp.status_code != 200:
            return results

        search_data = search_resp.json()
        pubmed_ids = search_data.get("esearchresult", {}).get("idlist", [])

        if not pubmed_ids:
            return results

        # Obtener detalles de cada artículo
        fetch_url = f"{PUBMED_BASE}/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pubmed_ids),
            "rettype": "json",
        }

        time.sleep(SLEEP_PUBMED)
        fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=TIMEOUT)

        if fetch_resp.status_code == 200:
            fetch_data = fetch_resp.json()
            articles = fetch_data.get("result", {}).get("uids", [])

            for uid in articles:
                if uid == "uids":
                    continue
                article = fetch_data.get("result", {}).get(uid, {})
                if article:
                    # Verificar que tenga referencias regionales
                    title = article.get("title", "")
                    abstract = article.get("abstract", "")

                    if _contains_region_terms(title) or _contains_region_terms(abstract):
                        results.append(
                            {
                                "source": "PubMed",
                                "pubmed_id": uid,
                                "title": title,
                                "authors": ", ".join(
                                    [a.get("name", "") for a in article.get("authors", [])][:3]
                                ),
                                "year": article.get("pub_date", "")[:4],
                                "journal": article.get("source", ""),
                                "doi": article.get("doi", ""),
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                                "species": species_name,
                                "abstract": abstract[:500] if abstract else "",
                            }
                        )

    except Exception as e:
        logger.debug(f"Error en PubMed para {species_name}: {e}")

    return results


def search_crossref_region(species_name: str) -> list[dict[str, Any]]:
    """Busca en CrossRef con criterio geográfico."""
    results = []
    try:
        # Búsqueda con términos de región
        region_query = " ".join(REGION_TERMS[:4])  # Usar los primeros 4 términos

        params = {
            "query.bibliographic": f'"{species_name}" AND ({region_query})',
            "rows": MAX_RESULTS,
            "sort": "published",
            "order": "desc",
        }

        time.sleep(SLEEP_CROSSREF)
        resp = requests.get(CROSSREF_BASE, params=params, timeout=TIMEOUT)

        if resp.status_code != 200:
            return results

        data = resp.json()
        items = data.get("message", {}).get("items", [])

        for item in items:
            doi = item.get("DOI", "")
            title = "".join(item.get("title", []))
            abstract = item.get("abstract", "")

            # Filtrar por región
            if _contains_region_terms(title) or _contains_region_terms(abstract):
                results.append(
                    {
                        "source": "CrossRef",
                        "doi": doi,
                        "title": title,
                        "authors": ", ".join(
                            [
                                f"{a.get('given', '')} {a.get('family', '')}"
                                for a in item.get("author", [])[:3]
                            ]
                        ),
                        "year": str(item.get("published", {}).get("date-parts", [[""]])[0][0]),
                        "journal": item.get("container-title", ""),
                        "url": f"https://doi.org/{doi}" if doi else "",
                        "species": species_name,
                        "abstract": abstract[:500] if abstract else "",
                    }
                )

    except Exception as e:
        logger.debug(f"Error en CrossRef para {species_name}: {e}")

    return results


def search_sciencedirect_region(species_name: str) -> list[dict[str, Any]]:
    """Busca en ScienceDirect con criterio geográfico."""
    import os

    api_key = os.getenv("SCIENCEDIRECT_API_KEY", "")
    if not api_key:
        return []

    results = []
    try:
        region_query = " OR ".join(REGION_TERMS[:4])

        params = {
            "query": f'{species_name} AND ({region_query})',
            "count": MAX_RESULTS,
            "sort": "date",
            "apiKey": api_key,
        }

        time.sleep(SLEEP_CROSSREF)
        resp = requests.get(SCIENCEDIRECT_BASE, params=params, timeout=TIMEOUT)

        if resp.status_code == 401:
            logger.warning("ScienceDirect no autorizado")
            return results

        if resp.status_code != 200:
            return results

        data = resp.json()
        items = data.get("search-results", {}).get("entry", [])

        for item in items:
            doi = item.get("prism:doi", "")
            title = item.get("dc:title", "")
            abstract = item.get("dc:description", "")

            if _contains_region_terms(title) or _contains_region_terms(abstract):
                results.append(
                    {
                        "source": "ScienceDirect",
                        "doi": doi,
                        "title": title,
                        "authors": item.get("dc:creator", ""),
                        "year": item.get("prism:coverDate", "")[:4],
                        "journal": item.get("prism:publicationName", ""),
                        "url": item.get("link", [{"@href": ""}])[0].get("@href", "") if item.get("link") else "",
                        "species": species_name,
                        "abstract": abstract[:500] if abstract else "",
                    }
                )

    except Exception as e:
        logger.debug(f"Error en ScienceDirect para {species_name}: {e}")

    return results


def search_scopus_region(species_name: str) -> list[dict[str, Any]]:
    """Busca en Scopus con criterio geográfico."""
    import os

    api_key = os.getenv("SCOPUS_API_KEY", "")
    if not api_key:
        return []

    results = []
    try:
        headers = {
            "X-ELS-APIKey": api_key,
            "Accept": "application/json",
        }

        # Construir búsqueda con criterios geográficos
        region_query = " OR ".join([f'TITLE-ABS-KEY("{term}")' for term in REGION_TERMS[:4]])

        params = {
            "query": f'(TITLE-ABS-KEY("{species_name}") AND ({region_query}))',
            "count": MAX_RESULTS,
            "sort": "date",
        }

        time.sleep(SLEEP_CROSSREF)
        resp = requests.get(SCOPUS_BASE, params=params, headers=headers, timeout=TIMEOUT)

        if resp.status_code != 200:
            return results

        data = resp.json()
        items = data.get("search-results", {}).get("entry", [])

        for item in items:
            eid = item.get("eid", "")
            doi = item.get("prism:doi", "")
            title = item.get("dc:title", "")
            abstract = item.get("dc:description", "")

            results.append(
                {
                    "source": "Scopus",
                    "doi": doi,
                    "title": title,
                    "authors": ", ".join(
                        [a.get("authname", "") for a in item.get("author", [])][:3]
                    ),
                    "year": item.get("prism:coverDate", "")[:4],
                    "journal": item.get("prism:publicationName", ""),
                    "url": f"https://www.scopus.com/inward/record.uri?eid={eid}" if eid else "",
                    "scopus_id": eid,
                    "species": species_name,
                    "abstract": abstract[:500] if abstract else "",
                }
            )

    except Exception as e:
        logger.debug(f"Error en Scopus para {species_name}: {e}")

    return results


def search_articles_for_species_region(species_name: str) -> list[dict[str, Any]]:
    """Busca artículos para una especie con criterios geográficos."""
    logger.debug(f"Buscando artículos para: {species_name} (región: Golfo de California)")

    all_results = []

    # Buscar en cada base de datos
    all_results.extend(search_pubmed_region(species_name))
    all_results.extend(search_crossref_region(species_name))
    all_results.extend(search_scopus_region(species_name))  # Si está configurado
    all_results.extend(search_sciencedirect_region(species_name))  # Si está configurado

    # Remover duplicados por título
    seen_titles = set()
    unique_results = []
    for result in all_results:
        title = result.get("title", "").lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_results.append(result)

    return unique_results[:MAX_RESULTS]


def search_articles_batch_region(
    species_list: list[str],
    output_file: Path,
    progress_file: Path | None = None,
) -> dict[str, int]:
    """Busca artículos para un lote de especies con criterios geográficos."""

    # Cargar progreso previo
    progress = {}
    if progress_file and progress_file.exists():
        try:
            progress = json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    results_summary = {"total": len(species_list), "found": 0, "processed": 0, "total_articles": 0}
    all_articles = []

    for idx, species_name in enumerate(species_list, 1):
        # Saltar si ya fue procesado
        if species_name in progress:
            logger.debug(f"[{idx}/{len(species_list)}] Saltando (ya procesada): {species_name}")
            results_summary["processed"] += 1
            continue

        logger.info(f"[{idx}/{len(species_list)}] Buscando: {species_name}")

        articles = search_articles_for_species_region(species_name)
        if articles:
            all_articles.extend(articles)
            results_summary["found"] += 1
            results_summary["total_articles"] += len(articles)
            logger.info(f"  → {len(articles)} artículos encontrados")

        results_summary["processed"] += 1

        # Guardar progreso
        progress[species_name] = len(articles)
        if progress_file:
            progress_file.write_text(
                json.dumps(progress, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # Mostrar progreso cada 10 especies
        if idx % 10 == 0:
            pct = results_summary["found"] / results_summary["processed"]
            logger.info(
                f"Progreso: {idx}/{len(species_list)} | "
                f"Especies con artículos: {results_summary['found']} | "
                f"Total artículos: {results_summary['total_articles']} | "
                f"Porcentaje: {pct:.1%}"
            )

    # Guardar todos los artículos en un archivo consolidado
    if all_articles:
        fieldnames = [
            "species",
            "source",
            "title",
            "authors",
            "year",
            "journal",
            "doi",
            "url",
            "pubmed_id",
            "scopus_id",
            "abstract",
        ]

        with output_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for article in all_articles:
                writer.writerow(
                    {
                        "species": article.get("species", ""),
                        "source": article.get("source", ""),
                        "title": article.get("title", ""),
                        "authors": article.get("authors", ""),
                        "year": article.get("year", ""),
                        "journal": article.get("journal", ""),
                        "doi": article.get("doi", ""),
                        "url": article.get("url", ""),
                        "pubmed_id": article.get("pubmed_id", ""),
                        "scopus_id": article.get("scopus_id", ""),
                        "abstract": article.get("abstract", ""),
                    }
                )

    logger.info(
        f"✓ Búsqueda completada: {results_summary['found']} especies con artículos "
        f"({results_summary['found']/max(1, results_summary['processed']):.1%}) | "
        f"Total: {results_summary['total_articles']} artículos"
    )

    return results_summary


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent / "data/input/final_taxonomy_occ.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "gulf_california_articles.csv",
    )
    args = parser.parse_args()

    # Leer especies del archivo
    species_list = []
    with args.input.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            species = (row.get("species") or "").strip()
            if species:
                species_list.append(species)

    logger.info(f"Leyendo {len(species_list)} especies de {args.input}")
    logger.info(f"Buscando artículos con criterios: Golfo de California, Pacífico mexicano")

    progress_file = Path(__file__).parent / "outputs" / "state" / "gulf_california_search_progress.json"
    results = search_articles_batch_region(species_list, args.output, progress_file)

    logger.info(f"\nResumen final:")
    logger.info(f"  Especies procesadas: {results['processed']}/{results['total']}")
    logger.info(f"  Especies con artículos: {results['found']}")
    logger.info(f"  Total de artículos encontrados: {results['total_articles']}")
    logger.info(f"  Archivo de salida: {args.output}")
