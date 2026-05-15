"""
PASO 3: Buscar artículos científicos para especies MARINE.

Consulta múltiples bases de datos científicas:
- PubMed (NCBI)
- CrossRef (DOIs)
- ArXiv (preprints)

Genera CSV por especie con: DOI, URL, título, año, journal
"""

from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# URLs de APIs
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF_BASE = "https://api.crossref.org/works"
ARXIV_BASE = "http://export.arxiv.org/api/query"

# Configuración
MAX_RESULTS = 20  # máximo de artículos por especie
TIMEOUT = 15
SLEEP_PUBMED = 0.3  # segundos entre peticiones PubMed
SLEEP_CROSSREF = 0.1
SLEEP_ARXIV = 0.1


def search_pubmed(species_name: str) -> list[dict[str, Any]]:
    """Busca artículos en PubMed por nombre de especie."""
    results = []
    try:
        # Búsqueda en PubMed
        search_url = f"{PUBMED_BASE}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": f'"{species_name}"[Organism]',
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
                    results.append(
                        {
                            "source": "PubMed",
                            "pubmed_id": uid,
                            "title": article.get("title", ""),
                            "authors": ", ".join(
                                [a.get("name", "") for a in article.get("authors", [])][:3]
                            ),
                            "year": article.get("pub_date", "")[:4],
                            "journal": article.get("source", ""),
                            "doi": article.get("doi", ""),
                            "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                        }
                    )

    except Exception as e:
        logger.debug(f"Error en PubMed para {species_name}: {e}")

    return results


def search_crossref(species_name: str) -> list[dict[str, Any]]:
    """Busca artículos en CrossRef por nombre de especie."""
    results = []
    try:
        params = {
            "query": species_name,
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
            results.append(
                {
                    "source": "CrossRef",
                    "doi": doi,
                    "title": "".join(item.get("title", [])),
                    "authors": ", ".join(
                        [
                            f"{a.get('given', '')} {a.get('family', '')}"
                            for a in item.get("author", [])[:3]
                        ]
                    ),
                    "year": str(item.get("published", {}).get("date-parts", [[""]])[0][0]),
                    "journal": item.get("container-title", ""),
                    "url": f"https://doi.org/{doi}" if doi else "",
                }
            )

    except Exception as e:
        logger.debug(f"Error en CrossRef para {species_name}: {e}")

    return results


def search_arxiv(species_name: str) -> list[dict[str, Any]]:
    """Busca artículos en ArXiv por nombre de especie."""
    results = []
    try:
        # Búsqueda en ArXiv (solo si tiene "fish" o "marine" en el nombre)
        if "fish" not in species_name.lower() and "marine" not in species_name.lower():
            return results

        params = {
            "search_query": f"all:{species_name}",
            "max_results": MAX_RESULTS,
            "sort_by": "submittedDate",
            "sort_order": "descending",
        }

        time.sleep(SLEEP_ARXIV)
        resp = requests.get(ARXIV_BASE, params=params, timeout=TIMEOUT)

        if resp.status_code != 200:
            return results

        # Parsear XML (respuesta de ArXiv es XML)
        import xml.etree.ElementTree as ET

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title_elem = entry.find("atom:title", ns)
            published_elem = entry.find("atom:published", ns)
            id_elem = entry.find("atom:id", ns)
            authors_elems = entry.findall("atom:author/atom:name", ns)

            if title_elem is not None and id_elem is not None:
                arxiv_id = id_elem.text.split("/abs/")[-1] if id_elem.text else ""
                results.append(
                    {
                        "source": "ArXiv",
                        "arxiv_id": arxiv_id,
                        "title": title_elem.text or "",
                        "authors": ", ".join(
                            [a.text for a in authors_elems[:3] if a.text]
                        ),
                        "year": published_elem.text[:4] if published_elem is not None else "",
                        "journal": "ArXiv",
                        "url": f"https://arxiv.org/abs/{arxiv_id}",
                    }
                )

    except Exception as e:
        logger.debug(f"Error en ArXiv para {species_name}: {e}")

    return results


def search_articles_for_species(species_name: str) -> list[dict[str, Any]]:
    """Busca artículos en todas las bases de datos para una especie."""
    logger.debug(f"Buscando artículos para: {species_name}")

    all_results = []

    # Buscar en cada base de datos
    all_results.extend(search_pubmed(species_name))
    all_results.extend(search_crossref(species_name))
    all_results.extend(search_arxiv(species_name))

    # Remover duplicados por título
    seen_titles = set()
    unique_results = []
    for result in all_results:
        title = result.get("title", "").lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_results.append(result)

    return unique_results[:MAX_RESULTS]


def save_species_articles(
    species_name: str,
    articles: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    """Guarda artículos en CSV por especie."""
    if not articles:
        return

    # Sanitizar nombre de archivo
    safe_name = species_name.replace(" ", "_").replace("/", "_")
    csv_path = output_dir / f"{safe_name}.csv"

    fieldnames = [
        "source",
        "title",
        "authors",
        "year",
        "journal",
        "doi",
        "url",
        "pubmed_id",
        "arxiv_id",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for article in articles:
            writer.writerow(
                {
                    "source": article.get("source", ""),
                    "title": article.get("title", ""),
                    "authors": article.get("authors", ""),
                    "year": article.get("year", ""),
                    "journal": article.get("journal", ""),
                    "doi": article.get("doi", ""),
                    "url": article.get("url", ""),
                    "pubmed_id": article.get("pubmed_id", ""),
                    "arxiv_id": article.get("arxiv_id", ""),
                }
            )


def search_articles_batch(
    species_list: list[str],
    output_dir: Path,
    progress_file: Path | None = None,
) -> dict[str, int]:
    """Busca artículos para un lote de especies."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Cargar progreso previo
    progress = {}
    if progress_file and progress_file.exists():
        try:
            progress = json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    results_summary = {"total": len(species_list), "found": 0, "processed": 0}

    for idx, species_name in enumerate(species_list, 1):
        # Saltar si ya fue procesado
        safe_name = species_name.replace(" ", "_").replace("/", "_")
        csv_path = output_dir / f"{safe_name}.csv"
        if csv_path.exists() and species_name in progress:
            logger.debug(f"[{idx}/{len(species_list)}] Saltando (ya procesada): {species_name}")
            results_summary["processed"] += 1
            continue

        logger.info(f"[{idx}/{len(species_list)}] Buscando: {species_name}")

        articles = search_articles_for_species(species_name)
        if articles:
            save_species_articles(species_name, articles, output_dir)
            results_summary["found"] += 1
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
            avg = results_summary["found"] / results_summary["processed"]
            logger.info(
                f"Progreso: {idx}/{len(species_list)} | "
                f"Encontrados: {results_summary['found']} | "
                f"Promedio: {avg:.1%}"
            )

    logger.info(
        f"✓ Búsqueda completada: {results_summary['found']}/{results_summary['processed']} "
        f"con artículos ({results_summary['found']/max(1, results_summary['processed']):.1%})"
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
        default=Path(__file__).parent / "analysis_species" / "species_acuaticas.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "search_results",
    )
    args = parser.parse_args()

    # Leer especies acuáticas
    species_list = []
    with args.input.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            species = (row.get("species") or "").strip()
            if species:
                species_list.append(species)

    logger.info(f"Buscando artículos para {len(species_list)} especies...")

    progress_file = Path(__file__).parent / "search_progress.json"
    results = search_articles_batch(species_list, args.output, progress_file)

    logger.info(f"\nResumen: {results}")
