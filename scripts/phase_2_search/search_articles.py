"""
PASO 3: Buscar artículos científicos para especies MARINE.

Consulta múltiples bases de datos científicas:
- PubMed (NCBI) - Gratuito
- CrossRef (DOIs) - Gratuito
- Scopus (si tiene API key) - Requiere subscripción
- ScienceDirect (si tiene API key) - Requiere subscripción
- ArXiv (preprints) - Gratuito

Genera CSV por especie con: DOI, URL, título, año, journal

Configuración:
  - Copiar .env.example a .env
  - Agregar SCOPUS_API_KEY y SCIENCEDIRECT_API_KEY si tienes acceso
"""

from __future__ import annotations

import csv
import json
import logging
import os
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
BIORXIV_BASE = "https://api.biorxiv.org/details"
PLOS_BASE = "https://api.plos.org/search"

# Configuración
MAX_RESULTS = 20  # máximo de artículos por especie
TIMEOUT = 15
SLEEP_PUBMED = 0.3  # segundos entre peticiones PubMed
SLEEP_CROSSREF = 0.1
SLEEP_ARXIV = 0.1


def _load_api_key(env_var: str, secret_file: str) -> str:
	"""Carga API key desde variable de entorno o archivo secrets/.

	Args:
	    env_var: nombre de la variable de entorno (ej. SCOPUS_API_KEY)
	    secret_file: nombre del archivo en secrets/ (ej. scopus_apikey.txt)

	Returns:
	    API key si existe, string vacío si no se encuentra
	"""
	key = os.getenv(env_var, "").strip()
	if not key:
		secret_path = Path(__file__).resolve().parents[2] / "secrets" / secret_file
		if secret_path.exists():
			key = secret_path.read_text().strip()
	return key


def search_pubmed(species_name: str, region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca artículos en PubMed por nombre de especie.

    Args:
        species_name: nombre de la especie a buscar
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados
    """
    results = []
    try:
        # Búsqueda en PubMed
        search_url = f"{PUBMED_BASE}/esearch.fcgi"

        # Construir query con filtro geográfico opcional
        query = f'"{species_name}"[Organism]'
        if region_terms:
            region_query = " OR ".join([f'"{term}"[Title/Abstract]' for term in region_terms])
            query = f'{query} AND ({region_query})'

        search_params = {
            "db": "pubmed",
            "term": query,
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


def search_crossref(species_name: str, region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca artículos en CrossRef por nombre de especie.

    Args:
        species_name: nombre de la especie a buscar
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados
    """
    results = []
    try:
        # query.bibliographic restringe la búsqueda al título, abstract y palabras clave.
        # Las comillas obligan a Crossref a tratar el nombre como frase exacta,
        # evitando que devuelva artículos donde la palabra aparece en apellidos de autores
        # o en contextos no relacionados (ej. "Pinus nigra", "Alberto Nigra").
        query = f'"{species_name}"'
        if region_terms:
            region_query = " OR ".join(f'"{term}"' for term in region_terms)
            query = f'{query} AND ({region_query})'

        params = {
            "query.bibliographic": query,
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


def search_sciencedirect(species_name: str, api_key: str = "", region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca en ScienceDirect (requiere API key en env var SCIENCEDIRECT_API_KEY o secrets/sciencedirect_apikey.txt).

    Args:
        species_name: nombre de la especie a buscar
        api_key: API key opcional. Si no se proporciona, se carga desde env/secrets
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados
    """
    if not api_key:
        api_key = _load_api_key("SCIENCEDIRECT_API_KEY", "sciencedirect_apikey.txt")
    if not api_key:
        return []

    results = []
    try:
        query = species_name
        if region_terms:
            region_query = " OR ".join(region_terms)
            query = f'{query} AND ({region_query})'

        params = {
            "query": query,
            "count": MAX_RESULTS,
            "sort": "date",
            "apiKey": api_key,
        }

        time.sleep(SLEEP_CROSSREF)
        resp = requests.get(SCIENCEDIRECT_BASE, params=params, timeout=TIMEOUT)

        if resp.status_code == 401:
            logger.warning("ScienceDirect no autorizado para esta API key")
            return results

        if resp.status_code != 200:
            return results

        data = resp.json()
        items = data.get("search-results", {}).get("entry", [])

        for item in items:
            doi = item.get("prism:doi", "")
            results.append(
                {
                    "source": "ScienceDirect",
                    "doi": doi,
                    "title": item.get("dc:title", ""),
                    "authors": item.get("dc:creator", ""),
                    "year": item.get("prism:coverDate", "")[:4],
                    "journal": item.get("prism:publicationName", ""),
                    "url": item.get("link", [{"@href": ""}])[0].get("@href", "") if item.get("link") else "",
                }
            )

    except Exception as e:
        logger.debug(f"Error en ScienceDirect para {species_name}: {e}")

    return results


def search_scopus(species_name: str, api_key: str = "", region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca en Scopus (requiere API key en env var SCOPUS_API_KEY o secrets/scopus_apikey.txt).

    Args:
        species_name: nombre de la especie a buscar
        api_key: API key opcional. Si no se proporciona, se carga desde env/secrets
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados
    """
    if not api_key:
        api_key = _load_api_key("SCOPUS_API_KEY", "scopus_apikey.txt")
    if not api_key:
        return []

    results = []
    try:
        headers = {
            "X-ELS-APIKey": api_key,
            "Accept": "application/json",
        }

        query = f'TITLE-ABS-KEY("{species_name}")'
        if region_terms:
            region_query = ' AND '.join([f'TITLE-ABS-KEY("{term}")' for term in region_terms])
            query = f'{query} AND {region_query}'

        params = {
            "query": query,
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
            results.append(
                {
                    "source": "Scopus",
                    "doi": doi,
                    "title": item.get("dc:title", ""),
                    "authors": ", ".join(
                        [a.get("authname", "") for a in item.get("author", [])][:3]
                    ),
                    "year": item.get("prism:coverDate", "")[:4],
                    "journal": item.get("prism:publicationName", ""),
                    "url": f"https://www.scopus.com/inward/record.uri?eid={eid}" if eid else "",
                    "scopus_id": eid,
                }
            )

    except Exception as e:
        logger.debug(f"Error en Scopus para {species_name}: {e}")

    return results


def search_arxiv(species_name: str, region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca artículos en ArXiv por nombre de especie.

    Args:
        species_name: nombre de la especie a buscar
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados
    """
    results = []
    try:
        # ti: restringe la búsqueda al título del paper.
        # Las comillas obligan a arXiv a buscar la frase exacta,
        # evitando coincidencias parciales donde solo aparece el género o el epíteto.
        # Nota: arXiv tiene poca cobertura de biología/ecología marina;
        # se mantiene la búsqueda pero los resultados serán pocos.
        escaped = species_name.replace('"', '')
        search_query = f'ti:"{escaped}"'
        if region_terms:
            region_query = ' OR '.join([f'ti:"{term}"' for term in region_terms])
            search_query = f'{search_query} AND ({region_query})'

        params = {
            "search_query": search_query,
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


def search_biorxiv(species_name: str, region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca preprints en BioRxiv/MedRxiv por nombre de especie.

    Args:
        species_name: nombre de la especie a buscar
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados
    """
    results = []
    try:
        import datetime

        # BioRxiv API busca en últimos 365 días
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=365)

        search_url = f"{BIORXIV_BASE}/biorxiv/{start_date.isoformat()}/{today.isoformat()}"
        params = {"sort": "date", "direction": "descending"}

        time.sleep(0.2)
        resp = requests.get(search_url, params=params, timeout=TIMEOUT)

        if resp.status_code != 200:
            return results

        data = resp.json()
        query_lower = species_name.lower()

        for preprint in data.get("collection", []):
            title = preprint.get("title", "").lower()
            abstract = preprint.get("abstract", "").lower()

            # Buscar especie en título o abstract
            if query_lower not in title and query_lower not in abstract:
                continue

            # Filtrar por región si se proporciona
            if region_terms:
                region_str = " ".join([t.lower() for t in region_terms])
                if region_str not in title and region_str not in abstract:
                    continue

            doi = preprint.get("doi", "")
            date_str = preprint.get("date", "")
            year = int(date_str[:4]) if date_str else None

            authors = preprint.get("authors", "")
            if isinstance(authors, list):
                author_list = authors[:3]
            else:
                author_list = [a.strip() for a in str(authors).split(",")[:3] if a.strip()]

            results.append({
                "source": "BioRxiv",
                "doi": doi,
                "title": preprint.get("title", ""),
                "authors": ", ".join(author_list),
                "year": str(year) if year else "",
                "journal": "BioRxiv/MedRxiv",
                "url": f"https://doi.org/{doi}" if doi else "",
            })

            if len(results) >= MAX_RESULTS:
                break

    except Exception as e:
        logger.debug(f"Error en BioRxiv para {species_name}: {e}")

    return results


def search_plos(species_name: str, region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca artículos en PLOS (open access) por nombre de especie.

    Args:
        species_name: nombre de la especie a buscar
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados
    """
    results = []
    try:
        query = f'"{species_name}"'
        if region_terms:
            region_query = ' OR '.join([f'"{term}"' for term in region_terms])
            query = f'{query} AND ({region_query})'

        params = {
            "q": query,
            "wt": "json",
            "rows": MAX_RESULTS,
            "sort": "publication_date desc",
        }

        time.sleep(0.2)
        resp = requests.get(PLOS_BASE, params=params, timeout=TIMEOUT)

        if resp.status_code != 200:
            return results

        data = resp.json()
        docs = data.get("response", {}).get("docs", [])

        for doc in docs:
            doi = doc.get("id", "")
            publication_date = doc.get("publication_date", "")
            year = int(publication_date[:4]) if publication_date else None

            authors_list = doc.get("author_display", [])
            authors = authors_list[:3] if authors_list else []

            results.append({
                "source": "PLOS",
                "doi": doi,
                "title": doc.get("title_display", ""),
                "authors": ", ".join(authors),
                "year": str(year) if year else "",
                "journal": doc.get("journal_name", "PLOS"),
                "url": f"https://doi.org/{doi}" if doi else "",
            })

    except Exception as e:
        logger.debug(f"Error en PLOS para {species_name}: {e}")

    return results


def _title_contains_species(title: str, species_name: str) -> bool:
    """
    Verifica que el título del artículo contenga al menos una de las dos
    palabras del nombre de la especie (género o epíteto específico).

    Esto descarta artículos que solo coinciden por apellido de autor u otras
    fuentes de ruido en la búsqueda (ej. "Alberto Nigra" para "Aaptos nigra").
    PubMed y Scopus ya filtran por campo, así que se aplica solo a CrossRef/ArXiv.
    """
    title_lower = title.lower()
    parts = species_name.lower().split()
    # Para ser incluido, el título debe contener ambas palabras del binomio
    # (género + epíteto). Si la especie tiene solo una palabra, basta con que aparezca.
    if len(parts) >= 2:
        return parts[0] in title_lower and parts[1] in title_lower
    return parts[0] in title_lower if parts else False


def search_articles_for_species(species_name: str, region_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Busca artículos en todas las bases de datos para una especie.

    Args:
        species_name: nombre de la especie a buscar
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Lista de artículos encontrados de todas las fuentes
    """
    logger.debug(f"Buscando artículos para: {species_name}")

    all_results = []

    # Buscar en cada base de datos (en orden de relevancia)
    all_results.extend(search_pubmed(species_name, region_terms=region_terms))
    all_results.extend(search_crossref(species_name, region_terms=region_terms))
    all_results.extend(search_scopus(species_name, region_terms=region_terms))  # Si está configurado
    all_results.extend(search_sciencedirect(species_name, region_terms=region_terms))  # Si está configurado
    all_results.extend(search_arxiv(species_name, region_terms=region_terms))
    all_results.extend(search_biorxiv(species_name, region_terms=region_terms))
    all_results.extend(search_plos(species_name, region_terms=region_terms))

    # Filtro de relevancia: el título debe mencionar el nombre de la especie.
    # PubMed y Scopus ya son semánticamente precisos; CrossRef y ArXiv no.
    noisy_sources = {"CrossRef", "ArXiv"}
    all_results = [
        r for r in all_results
        if r.get("source") not in noisy_sources
        or _title_contains_species(r.get("title", ""), species_name)
    ]

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
    region_terms: list[str] | None = None,
) -> dict[str, int]:
    """Busca artículos para un lote de especies.

    Args:
        species_list: lista de nombres de especies a buscar
        output_dir: directorio para guardar resultados CSV
        progress_file: archivo para guardar/cargar progreso (JSON)
        region_terms: términos geográficos opcionales para filtrar resultados

    Returns:
        Resumen de búsqueda con total, encontrados y procesados
    """
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

        articles = search_articles_for_species(species_name, region_terms=region_terms)
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
        default=Path(__file__).parent / "outputs" / "search_results",
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

    progress_file = Path(__file__).parent / "outputs" / "state" / "search_progress.json"
    results = search_articles_batch(species_list, args.output, progress_file)

    logger.info(f"\nResumen: {results}")
