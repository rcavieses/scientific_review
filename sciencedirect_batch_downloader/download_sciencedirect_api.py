#!/usr/bin/env python3
"""
Script para descargar artículos en lote desde ScienceDirect usando su API.

Uso:
    python3 download_sciencedirect_api.py --config config.json --articles articles_to_download.csv

Requisitos:
    - API key válida de ScienceDirect (requiere acceso institucional)
    - Archivo CSV con los artículos a descargar
    - pip install requests pyyaml

Notas:
    - Las instituciones con suscripción a ScienceDirect pueden usar esta API
    - Sin costo adicional si la institución ya tiene acceso
    - Requiere que la IP sea reconocida por ScienceDirect
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# Configuración
DEFAULT_CONFIG = {
    "api_key": "",
    "output_dir": "downloaded_pdfs",
    "sleep_between_requests": 1.0,
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 5,
}

SCIENCEDIRECT_API_BASE = "https://api.elsevier.com/content"


class ScienceDirectDownloader:
    """Gestor de descargas desde ScienceDirect API."""

    def __init__(self, config: dict[str, Any]):
        """Inicializar con configuración."""
        self.api_key = config.get("api_key", "")
        self.output_dir = Path(config.get("output_dir", "downloaded_pdfs"))
        self.sleep_between = config.get("sleep_between_requests", 1.0)
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 5)

        if not self.api_key:
            raise ValueError("API key no configurada. Editar config.json")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-ELS-APIKey": self.api_key,
                "Accept": "application/pdf",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )

        logger.info(f"✓ Directorio de salida: {self.output_dir}")
        logger.info(f"✓ Timeout: {self.timeout}s")
        logger.info(f"✓ Reintentos máximos: {self.max_retries}")

    def _build_filename(self, article: dict[str, Any]) -> str:
        """Construir nombre de archivo seguro."""
        doi = article.get("doi", "").replace("/", "_").strip()
        title = article.get("title", "unknown")[:40].replace("/", "_").replace(" ", "_")
        species = article.get("species", "unknown").replace(" ", "_").replace("/", "_")

        if doi:
            filename = f"{species}_{doi}.pdf"
        else:
            filename = f"{species}_{title}.pdf"

        return filename

    def _download_by_doi(self, doi: str, output_path: Path) -> bool:
        """Descargar usando DOI."""
        try:
            url = f"{SCIENCEDIRECT_API_BASE}/article/doi/{doi}"
            logger.debug(f"  GET {url}")

            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)

            if response.status_code == 200:
                if b"%PDF" in response.content[:20]:
                    with output_path.open("wb") as f:
                        f.write(response.content)
                    return True
                else:
                    logger.debug(f"    ⚠ No es PDF válido (tamaño: {len(response.content)})")
                    return False
            elif response.status_code == 403:
                logger.debug(f"    ✗ Acceso denegado (403)")
                return False
            elif response.status_code == 404:
                logger.debug(f"    ✗ No encontrado (404)")
                return False
            else:
                logger.debug(f"    ✗ Error HTTP {response.status_code}")
                return False

        except requests.Timeout:
            logger.debug(f"    ✗ Timeout")
            return False
        except Exception as e:
            logger.debug(f"    ✗ Error: {str(e)[:60]}")
            return False

    def _download_by_pii(self, pii: str, output_path: Path) -> bool:
        """Descargar usando PII (Publication Identifier)."""
        try:
            url = f"{SCIENCEDIRECT_API_BASE}/article/pii/{pii}"
            logger.debug(f"  GET {url}")

            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)

            if response.status_code == 200:
                if b"%PDF" in response.content[:20]:
                    with output_path.open("wb") as f:
                        f.write(response.content)
                    return True

        except Exception as e:
            logger.debug(f"    ✗ Error PII: {str(e)[:60]}")

        return False

    def _download_by_url(self, url: str, output_path: Path) -> bool:
        """Descargar desde URL directa."""
        if not url or not url.startswith("http"):
            return False

        try:
            logger.debug(f"  GET {url[:60]}...")

            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)

            if response.status_code == 200:
                if b"%PDF" in response.content[:20]:
                    with output_path.open("wb") as f:
                        f.write(response.content)
                    return True

        except Exception as e:
            logger.debug(f"    ✗ Error URL: {str(e)[:60]}")

        return False

    def download_article(self, article: dict[str, Any], index: int, total: int) -> dict[str, Any]:
        """Descargar un artículo con reintentos."""
        filename = self._build_filename(article)
        output_path = self.output_dir / filename

        # Saltar si ya existe
        if output_path.exists():
            logger.info(f"[{index}/{total}] ⊘ Existe: {filename}")
            return {
                "status": "skipped",
                "species": article.get("species"),
                "doi": article.get("doi"),
                "filename": filename,
            }

        logger.info(
            f"[{index}/{total}] Descargando: {article.get('species')} "
            f"({article.get('source', 'unknown')})"
        )

        # Intentar con diferentes métodos
        methods = [
            ("DOI", lambda: self._download_by_doi(article.get("doi", ""), output_path)),
            ("URL", lambda: self._download_by_url(article.get("url", ""), output_path)),
        ]

        for attempt in range(self.max_retries):
            for method_name, method_func in methods:
                try:
                    if method_func():
                        logger.info(f"  ✓ Éxito ({method_name}): {filename}")
                        time.sleep(self.sleep_between)
                        return {
                            "status": "downloaded",
                            "species": article.get("species"),
                            "doi": article.get("doi"),
                            "source": article.get("source"),
                            "method": method_name,
                            "filename": filename,
                            "size": output_path.stat().st_size,
                        }
                except Exception as e:
                    logger.debug(f"    Error en {method_name}: {e}")

            if attempt < self.max_retries - 1:
                logger.debug(f"  Reintentando en {self.retry_delay}s...")
                time.sleep(self.retry_delay)

        # Fallo final
        logger.warning(f"  ✗ Fallo: No se pudo descargar")
        return {
            "status": "failed",
            "species": article.get("species"),
            "doi": article.get("doi"),
            "title": article.get("title"),
            "source": article.get("source"),
            "url": article.get("url"),
            "reason": "Acceso denegado o archivo no disponible",
        }

    def download_batch(self, articles_csv: Path) -> dict[str, Any]:
        """Descargar lote de artículos."""
        if not articles_csv.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {articles_csv}")

        # Leer artículos
        articles = []
        with articles_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            articles = list(reader)

        logger.info(f"Leyendo {len(articles)} artículos de {articles_csv.name}")
        logger.info("Iniciando descarga...")
        logger.info("")

        results = {
            "total": len(articles),
            "downloaded": 0,
            "failed": 0,
            "skipped": 0,
            "failed_articles": [],
            "start_time": datetime.now(),
        }

        for idx, article in enumerate(articles, 1):
            result = self.download_article(article, idx, len(articles))

            if result["status"] == "downloaded":
                results["downloaded"] += 1
            elif result["status"] == "failed":
                results["failed"] += 1
                results["failed_articles"].append(result)
            elif result["status"] == "skipped":
                results["skipped"] += 1

            # Mostrar progreso cada 25 descargas
            if idx % 25 == 0:
                elapsed = (datetime.now() - results["start_time"]).total_seconds()
                rate = idx / elapsed if elapsed > 0 else 0
                remaining = (len(articles) - idx) / rate if rate > 0 else 0
                logger.info(
                    f"Progreso: {idx}/{len(articles)} | "
                    f"✓ {results['downloaded']} | "
                    f"✗ {results['failed']} | "
                    f"ETA: {int(remaining/60)}m"
                )

        results["end_time"] = datetime.now()
        results["duration"] = (results["end_time"] - results["start_time"]).total_seconds()

        return results


def save_results(results: dict[str, Any], output_dir: Path) -> None:
    """Guardar resumen de resultados."""
    # Resumen JSON
    summary_file = output_dir / "descarga_resumen.json"
    summary = {
        "fecha": datetime.now().isoformat(),
        "total_articulos": results["total"],
        "descargados": results["downloaded"],
        "fallidos": results["failed"],
        "saltados": results["skipped"],
        "porcentaje_exito": f"{(results['downloaded'] / max(1, results['total'])) * 100:.1f}%",
        "duracion_segundos": int(results.get("duration", 0)),
        "duracion_minutos": f"{int(results.get('duration', 0) / 60)}m",
    }

    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"✓ Resumen: {summary_file}")

    # Artículos fallidos
    if results["failed_articles"]:
        failed_file = output_dir / "articulos_fallidos.csv"
        fieldnames = [
            "species",
            "title",
            "source",
            "doi",
            "url",
            "reason",
        ]

        with failed_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for article in results["failed_articles"]:
                writer.writerow(
                    {
                        "species": article.get("species", ""),
                        "title": article.get("title", ""),
                        "source": article.get("source", ""),
                        "doi": article.get("doi", ""),
                        "url": article.get("url", ""),
                        "reason": article.get("reason", ""),
                    }
                )

        logger.info(f"✓ Artículos fallidos: {failed_file} ({len(results['failed_articles'])})")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.json",
        help="Archivo de configuración JSON",
    )
    parser.add_argument(
        "--articles",
        type=Path,
        default=Path(__file__).parent / "articles_to_download.csv",
        help="CSV con artículos a descargar",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Directorio de salida (sobrescribe config)",
    )

    args = parser.parse_args()

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Cargar configuración
    config = DEFAULT_CONFIG.copy()
    if args.config.exists():
        try:
            with args.config.open("r") as f:
                config.update(json.load(f))
            logger.info(f"✓ Configuración cargada: {args.config}")
        except Exception as e:
            logger.error(f"Error al cargar config: {e}")
            return 1
    else:
        logger.warning(f"Config no encontrada: {args.config}")
        logger.warning("Usando valores por defecto")

    if args.output:
        config["output_dir"] = str(args.output)

    # Crear descargador
    try:
        downloader = ScienceDirectDownloader(config)
    except ValueError as e:
        logger.error(f"✗ Error de configuración: {e}")
        return 1

    # Descargar
    try:
        results = downloader.download_batch(args.articles)
    except FileNotFoundError as e:
        logger.error(f"✗ {e}")
        return 1
    except KeyboardInterrupt:
        logger.warning("Descarga cancelada por usuario")
        return 1
    except Exception as e:
        logger.error(f"✗ Error durante la descarga: {e}")
        return 1

    # Guardar resultados
    output_dir = Path(config["output_dir"])
    save_results(results, output_dir)

    # Resumen final
    logger.info("")
    logger.info("=" * 70)
    logger.info("RESUMEN FINAL")
    logger.info("=" * 70)
    logger.info(f"Total de artículos: {results['total']}")
    logger.info(f"✓ Descargados: {results['downloaded']}")
    logger.info(f"✗ Fallidos: {results['failed']}")
    logger.info(f"⊘ Saltados: {results['skipped']}")
    logger.info(
        f"Éxito: {(results['downloaded'] / max(1, results['total'])) * 100:.1f}%"
    )
    logger.info(f"Tiempo total: {int(results.get('duration', 0) / 60)}m")
    logger.info(f"Carpeta de PDFs: {output_dir}")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    exit(main())
