"""
PASO 4: Descargar PDFs basado en DOIs y URLs de artículos.

Intenta descargar desde:
- DOI con resolución de acceso abierto
- URLs directas
- ArXiv PDFs

Almacena en: pdfs/{species}/
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

# URLs de resolvers
DOI_RESOLVER = "https://doi.org"
ARXIV_PDF = "https://arxiv.org/pdf"
UNPAYWALL_API = "https://api.unpaywall.org/v2/{doi}"
UNPAYWALL_EMAIL = "research@scientific-review.local"

# Configuración
TIMEOUT = 30
MAX_RETRIES = 2
SLEEP_BETWEEN = 0.5

# Headers para evitar bloqueos
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Scientific research bot)"
}


def build_progress_key(species_name: str, article: dict[str, Any]) -> str:
    """Construye una clave de progreso estable por especie y artículo."""
    source = article.get("source", "").strip().lower()
    title = article.get("title", "").strip().lower()
    return f"{species_name.strip().lower()}::{source}::{title}"


def download_file(url: str, output_path: Path, max_size: int = 50 * 1024 * 1024) -> bool:
    """Descarga un archivo desde URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        response.raise_for_status()

        # Verificar tamaño
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            logger.debug(f"Archivo muy grande ({content_length} bytes): {url}")
            return False

        # Verificar Content-Type: rechazar HTML (páginas de paywall)
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type or "text/xml" in content_type:
            logger.debug(f"Rechazado (Content-Type={content_type}, probable paywall): {url}")
            return False

        # Descargar en buffer para validar header antes de guardar
        output_path.parent.mkdir(parents=True, exist_ok=True)
        buf = b""
        header_checked = False
        tmp_path = output_path.with_suffix(".tmp")
        with tmp_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    if not header_checked:
                        buf += chunk
                        if len(buf) >= 5:
                            if not buf[:5].startswith(b"%PDF"):
                                tmp_path.unlink(missing_ok=True)
                                logger.debug(f"Rechazado (no es PDF real): {url}")
                                return False
                            header_checked = True
                    f.write(chunk)

        tmp_path.rename(output_path)
        file_size = output_path.stat().st_size
        logger.info(f"✓ Descargado: {output_path.name} ({file_size / 1024:.1f} KB)")
        return True

    except Exception as e:
        logger.debug(f"Error descargando {url}: {e}")
        return False


def download_from_doi(doi: str, output_path: Path) -> bool:
    """Intenta descargar desde un DOI."""
    if not doi:
        return False

    try:
        oa_url = resolve_oa_url_from_doi(doi)
        if oa_url and download_file(oa_url, output_path):
            return True

        # Resolver DOI a URL
        doi_url = f"{DOI_RESOLVER}/{doi}"
        response = requests.head(doi_url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)

        if response.status_code == 200:
            final_url = response.url
            return download_file(final_url, output_path)

    except Exception as e:
        logger.debug(f"Error con DOI {doi}: {e}")

    return False


def resolve_oa_url_from_doi(doi: str) -> str:
    """Obtiene una URL OA para el DOI usando Unpaywall si existe."""
    try:
        response = requests.get(
            UNPAYWALL_API.format(doi=doi),
            params={"email": UNPAYWALL_EMAIL},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if response.status_code == 404:
            return ""
        response.raise_for_status()

        data = response.json()
        best = data.get("best_oa_location") or {}
        candidates = []

        for location in [best, *(data.get("oa_locations") or [])]:
            pdf_url = (location or {}).get("url_for_pdf") or (location or {}).get("url")
            if pdf_url and pdf_url not in candidates:
                candidates.append(pdf_url)

        for candidate in candidates:
            if url_looks_like_pdf(candidate):
                return candidate

        return candidates[0] if candidates else ""

    except Exception as e:
        logger.debug(f"Error resolviendo OA para DOI {doi}: {e}")
        return ""


def url_looks_like_pdf(url: str) -> bool:
    """Verifica rápido si una URL parece servir un PDF."""
    try:
        response = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        content_type = response.headers.get("content-type", "").lower()
        return "application/pdf" in content_type
    except Exception:
        return False


def download_from_arxiv(arxiv_id: str, output_path: Path) -> bool:
    """Descarga PDF desde ArXiv."""
    if not arxiv_id:
        return False

    pdf_url = f"{ARXIV_PDF}/{arxiv_id}.pdf"
    return download_file(pdf_url, output_path)


def download_from_url(url: str, output_path: Path) -> bool:
    """Descarga desde URL directa."""
    if not url or not url.startswith("http"):
        return False

    return download_file(url, output_path)


def download_article_pdf(
    article: dict[str, Any],
    output_dir: Path,
    species_name: str = "",
) -> bool:
    """Intenta descargar PDF de un artículo usando varias estrategias."""
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    # Generar nombre del archivo
    title = article.get("title", "article")[:50].replace(" ", "_").replace("/", "_")
    source = article.get("source", "unknown")
    base_filename = f"{source}_{title}.pdf"
    output_path = output_dir / base_filename

    # Si ya existe, saltar
    if output_path.exists():
        logger.debug(f"Ya existe: {output_path.name}")
        return True

    # Estrategia 1: DOI
    doi = article.get("doi", "")
    if doi and download_from_doi(doi, output_path):
        return True

    # Estrategia 2: ArXiv
    arxiv_id = article.get("arxiv_id", "")
    if arxiv_id and download_from_arxiv(arxiv_id, output_path):
        return True

    # Estrategia 3: URL directa
    url = article.get("url", "")
    if url and download_from_url(url, output_path):
        return True

    # Estrategia 4: PubMed full text (si tiene ID)
    pubmed_id = article.get("pubmed_id", "")
    if pubmed_id:
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
        if download_file(pubmed_url, output_path):
            return True

    logger.debug(f"No se pudo descargar: {article.get('title', '')}")
    return False


def process_species_articles(
    species_csv: Path,
    output_dir: Path,
    progress_file: Path | None = None,
    source_filter: str | None = None,
) -> dict[str, int]:
    """Procesa artículos de una especie y descarga PDFs."""
    # source_filter: si se indica, solo descarga filas con ese valor en 'source'
    if not species_csv.exists():
        return {"processed": 0, "downloaded": 0}

    species_name = species_csv.stem.replace("_", " ")
    species_output_dir = output_dir / species_name

    # Cargar progreso
    progress = {}
    if progress_file and progress_file.exists():
        try:
            progress = json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    results = {"processed": 0, "downloaded": 0}

    with species_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filtrar por fuente si se indica
            if source_filter and row.get("source", "").strip() != source_filter:
                continue

            article_id = build_progress_key(species_name, row)

            # Saltar si ya fue procesado
            if article_id in progress:
                results["processed"] += 1
                continue

            if download_article_pdf(row, species_output_dir, species_name):
                results["downloaded"] += 1

            results["processed"] += 1

            # Guardar progreso
            progress[article_id] = True
            if progress_file:
                progress_file.write_text(
                    json.dumps(progress, ensure_ascii=False),
                    encoding="utf-8",
                )

            # Rate limiting
            time.sleep(SLEEP_BETWEEN)

    return results


def download_all_articles(
    search_results_dir: Path,
    output_dir: Path,
    progress_file: Path | None = None,
    source_filter: str | None = None,
) -> dict[str, Any]:
    """Descarga PDFs para todas las especies."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not search_results_dir.exists():
        logger.warning(f"Directorio no encontrado: {search_results_dir}")
        return {"total_species": 0, "total_articles": 0, "total_downloaded": 0}

    # Obtener CSVs de búsqueda
    csv_files = list(search_results_dir.glob("*.csv"))
    logger.info(f"Encontrados {len(csv_files)} archivos de búsqueda")

    # Cargar progreso global
    progress = {}
    if progress_file and progress_file.exists():
        try:
            progress = json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    summary = {
        "total_species": len(csv_files),
        "total_articles": 0,
        "total_downloaded": 0,
    }

    for idx, csv_file in enumerate(csv_files, 1):
        species_name = csv_file.stem.replace("_", " ")

        # Contar artículos en CSV (con filtro si aplica)
        with csv_file.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if not source_filter or r.get("source", "").strip() == source_filter]
            num_articles = len(rows)

        if num_articles == 0:
            continue

        summary["total_articles"] += num_articles

        logger.info(
            f"[{idx}/{len(csv_files)}] {species_name} "
            f"({num_articles} artículos)"
        )

        # Procesar
        results = process_species_articles(csv_file, output_dir, progress_file, source_filter)
        summary["total_downloaded"] += results["downloaded"]

        logger.info(f"  → Descargados: {results['downloaded']}/{results['processed']}")

        # Actualizar progreso
        progress[species_name] = results
        if progress_file:
            progress_file.write_text(
                json.dumps(progress, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    logger.info(
        f"✓ Descarga completada: {summary['total_downloaded']}/{summary['total_articles']} "
        f"PDFs ({summary['total_downloaded']/max(1, summary['total_articles']):.1%})"
    )

    return summary


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--search-results",
        type=Path,
        default=Path(__file__).parent / "outputs" / "search_results",
        help="Directorio con resultados de búsqueda",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "pdfs",
        help="Directorio de salida para PDFs",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Filtrar por fuente (ej: Scopus, CrossRef, PubMed). Si no se indica, descarga todas.",
    )
    args = parser.parse_args()

    logger.info(f"Descargando artículos de {args.search_results}...")

    if args.source:
        logger.info(f"Filtrando por fuente: {args.source}")

    progress_file = Path(__file__).parent / "outputs" / "state" / "download_progress.json"
    results = download_all_articles(args.search_results, args.output, progress_file, args.source)

    logger.info(f"\nResumen: {results}")
