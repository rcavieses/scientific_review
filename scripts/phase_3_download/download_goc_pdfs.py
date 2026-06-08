#!/usr/bin/env python3
"""
Descargar PDFs de artículos del Golfo de California.
Intenta descargar con URL directa, luego con doi2pdf como fallback.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Configuración
OUTPUT_DIR = Path(__file__).parent / "outputs" / "PDF_GOC"
PDF_DIR = OUTPUT_DIR / "pdfs"
TIMEOUT = 30
SLEEP_BETWEEN_DOWNLOADS = 0.5  # segundos entre descargas

# User agent para evitar bloqueos
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def ensure_directories():
    """Crear directorios necesarios."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"✓ Directorio de salida: {PDF_DIR}")


def try_direct_download(url: str, output_path: Path) -> bool:
    """Intenta descargar directamente desde la URL."""
    if not url or not url.startswith("http"):
        return False

    try:
        logger.debug(f"Intentando descarga directa: {url[:60]}...")
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)

        if resp.status_code == 200:
            # Verificar que sea un PDF
            if "application/pdf" in resp.headers.get("content-type", ""):
                with output_path.open("wb") as f:
                    f.write(resp.content)
                logger.debug(f"  ✓ Descargado: {output_path.name}")
                return True
        elif resp.status_code == 403 or resp.status_code == 401:
            logger.debug(f"  ⚠ Acceso denegado ({resp.status_code})")
            return False
        else:
            logger.debug(f"  ✗ Error HTTP {resp.status_code}")
            return False
    except Exception as e:
        logger.debug(f"  ✗ Error en descarga directa: {str(e)[:50]}")
        return False

    return False


def try_doi2pdf(doi: str, output_path: Path) -> bool:
    """Intenta usar doi2pdf para descargar el artículo."""
    if not doi or not doi.strip():
        return False

    try:
        logger.debug(f"Intentando doi2pdf para: {doi}")

        # Instalar doi2pdf si no está disponible
        try:
            import doi2pdf
        except ImportError:
            logger.debug("  Instalando doi2pdf...")
            subprocess.run(
                ["pip", "install", "-q", "doi2pdf"],
                capture_output=True,
                timeout=60,
            )

        # Intentar descargar
        cmd = [
            "python3",
            "-m",
            "doi2pdf.core",
            "--doi",
            doi,
            "--output-file",
            str(output_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=TIMEOUT,
            text=True,
        )

        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
            logger.debug(f"  ✓ Descargado con doi2pdf: {output_path.name}")
            return True
        else:
            logger.debug(f"  ✗ doi2pdf falló")
            return False

    except subprocess.TimeoutExpired:
        logger.debug(f"  ✗ doi2pdf timeout")
        return False
    except Exception as e:
        logger.debug(f"  ✗ Error en doi2pdf: {str(e)[:50]}")
        return False

    return False


def try_pubmed_download(pubmed_id: str, output_path: Path) -> bool:
    """Intenta descargar desde PubMed Central."""
    if not pubmed_id or not pubmed_id.strip():
        return False

    try:
        logger.debug(f"Intentando PubMed Central para: {pubmed_id}")

        # Construir URL de PMC
        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pubmed_id}/"
        resp = requests.get(pmc_url, headers=HEADERS, timeout=TIMEOUT)

        if resp.status_code == 200:
            # Buscar enlace PDF
            if "pdf" in resp.text.lower():
                # Intentar con el patrón común de PMC
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pubmed_id}/pdf/"
                resp = requests.get(pdf_url, headers=HEADERS, timeout=TIMEOUT)
                if resp.status_code == 200 and b"PDF" in resp.content[:100]:
                    with output_path.open("wb") as f:
                        f.write(resp.content)
                    logger.debug(f"  ✓ Descargado desde PMC: {output_path.name}")
                    return True

    except Exception as e:
        logger.debug(f"  ✗ Error en PubMed: {str(e)[:50]}")

    return False


def download_article_pdf(
    article: dict[str, Any],
    index: int,
    total: int,
) -> dict[str, Any]:
    """Descarga el PDF de un artículo con múltiples intentos."""
    species = article.get("species", "Unknown").replace("/", "_").replace(" ", "_")
    title = article.get("title", "unknown")[:50].replace("/", "_").replace(" ", "_")
    doi = article.get("doi", "").strip()
    url = article.get("url", "").strip()
    pubmed_id = article.get("pubmed_id", "").strip()
    source = article.get("source", "")

    # Nombre del archivo
    safe_species = species.replace(" ", "_")
    filename = f"{safe_species}_{index}.pdf"
    output_path = PDF_DIR / filename

    # Saltar si ya existe
    if output_path.exists():
        logger.debug(f"[{index}/{total}] Ya existe: {filename}")
        return {
            "status": "skipped",
            "species": article.get("species"),
            "title": title,
            "source": source,
            "filename": filename,
        }

    logger.info(f"[{index}/{total}] Descargando: {species}")

    # Intentar diferentes métodos
    methods = [
        ("URL directa", lambda: try_direct_download(url, output_path)),
        ("doi2pdf", lambda: try_doi2pdf(doi, output_path)),
        ("PubMed", lambda: try_pubmed_download(pubmed_id, output_path)),
    ]

    for method_name, method_func in methods:
        if method_func():
            logger.info(f"  ✓ Éxito ({method_name}): {filename}")
            time.sleep(SLEEP_BETWEEN_DOWNLOADS)
            return {
                "status": "downloaded",
                "species": article.get("species"),
                "title": title,
                "source": source,
                "method": method_name,
                "filename": filename,
                "doi": doi,
                "url": url,
            }

    # Si todos fallan
    logger.warning(f"  ✗ FALLO: No se pudo descargar")
    return {
        "status": "failed",
        "species": article.get("species"),
        "title": title,
        "source": source,
        "doi": doi,
        "url": url,
        "pubmed_id": pubmed_id,
        "reason": "Acceso denegado o archivo no disponible",
    }


def download_all_pdfs(csv_file: Path) -> dict[str, Any]:
    """Descarga todos los PDFs del archivo CSV."""
    ensure_directories()

    # Leer artículos
    articles = []
    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        articles = list(reader)

    logger.info(f"Descargando {len(articles)} artículos...")

    results = {
        "total": len(articles),
        "downloaded": 0,
        "failed": 0,
        "skipped": 0,
        "failed_articles": [],
    }

    for idx, article in enumerate(articles, 1):
        result = download_article_pdf(article, idx, len(articles))

        if result["status"] == "downloaded":
            results["downloaded"] += 1
        elif result["status"] == "failed":
            results["failed"] += 1
            results["failed_articles"].append(result)
        elif result["status"] == "skipped":
            results["skipped"] += 1

        # Mostrar progreso cada 50 descargas
        if idx % 50 == 0:
            logger.info(
                f"Progreso: {idx}/{len(articles)} | "
                f"Descargados: {results['downloaded']} | "
                f"Fallidos: {results['failed']}"
            )

    return results


def save_failed_articles(failed_articles: list[dict[str, Any]]) -> Path:
    """Guarda lista de artículos fallidos."""
    if not failed_articles:
        return None

    failed_file = OUTPUT_DIR / "articulos_fallidos.csv"

    fieldnames = [
        "species",
        "title",
        "source",
        "doi",
        "url",
        "pubmed_id",
        "reason",
    ]

    with failed_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for article in failed_articles:
            writer.writerow(
                {
                    "species": article.get("species", ""),
                    "title": article.get("title", ""),
                    "source": article.get("source", ""),
                    "doi": article.get("doi", ""),
                    "url": article.get("url", ""),
                    "pubmed_id": article.get("pubmed_id", ""),
                    "reason": article.get("reason", ""),
                }
            )

    logger.info(f"✓ Artículos fallidos guardados en: {failed_file}")
    return failed_file


def save_summary(results: dict[str, Any]) -> Path:
    """Guarda resumen de la descarga."""
    summary_file = OUTPUT_DIR / "resumen_descarga.json"

    summary = {
        "total_articulos": results["total"],
        "descargados": results["downloaded"],
        "fallidos": results["failed"],
        "saltados": results["skipped"],
        "porcentaje_exito": f"{(results['downloaded'] / max(1, results['total'])) * 100:.1f}%",
        "directorio_pdfs": str(PDF_DIR),
        "fecha": __import__("datetime").datetime.now().isoformat(),
    }

    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"✓ Resumen guardado en: {summary_file}")
    return summary_file


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
        default=Path(__file__).parent / "gulf_california_articles.csv",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Archivo no encontrado: {args.input}")
        exit(1)

    logger.info(f"Iniciando descarga de PDFs...")
    logger.info(f"Archivo de entrada: {args.input}")

    results = download_all_pdfs(args.input)

    # Guardar resultados
    save_summary(results)
    if results["failed_articles"]:
        save_failed_articles(results["failed_articles"])

    logger.info("")
    logger.info("=" * 70)
    logger.info("RESUMEN FINAL")
    logger.info("=" * 70)
    logger.info(f"Total de artículos: {results['total']}")
    logger.info(f"✓ Descargados: {results['downloaded']}")
    logger.info(f"✗ Fallidos: {results['failed']}")
    logger.info(f"⊘ Saltados (ya existentes): {results['skipped']}")
    logger.info(f"Éxito: {(results['downloaded'] / max(1, results['total'])) * 100:.1f}%")
    logger.info("")
    logger.info(f"Carpeta de PDFs: {PDF_DIR}")
    if results["failed_articles"]:
        logger.info(f"Artículos fallidos: {len(results['failed_articles'])}")
    logger.info("=" * 70)
