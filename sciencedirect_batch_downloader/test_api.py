#!/usr/bin/env python3
"""
Script para validar la configuración y el API key de ScienceDirect.

Uso:
    python3 test_api.py
    python3 test_api.py --config config.json
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

SCIENCEDIRECT_API_BASE = "https://api.elsevier.com/content"


def test_api_key(api_key: str, verbose: bool = False) -> bool:
    """Probar si el API key es válido."""
    if not api_key or not api_key.strip():
        logger.error("✗ API key vacío")
        return False

    logger.info("Probando API key...")

    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        # Intentar una búsqueda simple
        url = f"{SCIENCEDIRECT_API_BASE}/search/query"
        params = {
            "query": "Gulf of California",
            "count": 1,
        }

        if verbose:
            logger.debug(f"GET {url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Params: {params}")

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10,
        )

        if verbose:
            logger.debug(f"Status: {response.status_code}")
            logger.debug(f"Response: {response.text[:200]}")

        if response.status_code == 200:
            logger.info("✓ API key válido")
            try:
                data = response.json()
                count = data.get("search-results", {}).get("opensearch:totalResults", "?")
                logger.info(f"  Total de resultados en ejemplo: {count}")
            except:
                pass
            return True

        elif response.status_code == 401:
            logger.error("✗ API key inválido o expirado (401)")
            logger.error("  Verificar que el API key sea correcto")
            return False

        elif response.status_code == 403:
            logger.error("✗ Acceso denegado (403)")
            logger.error("  Posibles causas:")
            logger.error("  - IP no autorizada por ScienceDirect")
            logger.error("  - Conexión fuera de la red institucional")
            logger.error("  - Necesitas VPN de la institución")
            return False

        elif response.status_code == 429:
            logger.warning("⚠ Límite de rate límit alcanzado (429)")
            logger.warning("  Esperar unos minutos antes de reintentar")
            return False

        else:
            logger.error(f"✗ Error HTTP {response.status_code}")
            if response.text:
                logger.error(f"  Respuesta: {response.text[:100]}")
            return False

    except requests.Timeout:
        logger.error("✗ Timeout - sin conexión o servidor muy lento")
        return False

    except requests.ConnectionError:
        logger.error("✗ Error de conexión")
        logger.error("  Verificar conexión a internet")
        return False

    except Exception as e:
        logger.error(f"✗ Error desconocido: {e}")
        return False


def test_config_file(config_path: Path) -> bool:
    """Probar si el archivo de configuración es válido."""
    logger.info(f"Cargando configuración desde: {config_path}")

    if not config_path.exists():
        logger.error(f"✗ Archivo no encontrado: {config_path}")
        return False

    try:
        with config_path.open("r") as f:
            config = json.load(f)
        logger.info("✓ Archivo JSON válido")

        # Verificar campos requeridos
        required = ["api_key"]
        missing = [f for f in required if f not in config]

        if missing:
            logger.error(f"✗ Campos faltantes: {missing}")
            return False

        logger.info("✓ Campos requeridos presentes")

        # Mostrar configuración (ocultando API key)
        logger.info("\nConfiguración:")
        for key, value in config.items():
            if key == "api_key":
                display = f"{value[:10]}..." if len(value) > 10 else "VACÍO"
            else:
                display = value
            logger.info(f"  {key}: {display}")

        return True

    except json.JSONDecodeError as e:
        logger.error(f"✗ JSON inválido: {e}")
        return False

    except Exception as e:
        logger.error(f"✗ Error al leer configuración: {e}")
        return False


def test_articles_file(articles_path: Path) -> bool:
    """Probar si el archivo de artículos es válido."""
    logger.info(f"Verificando archivo de artículos: {articles_path}")

    if not articles_path.exists():
        logger.error(f"✗ Archivo no encontrado: {articles_path}")
        return False

    try:
        import csv

        with articles_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            logger.error("✗ Archivo vacío")
            return False

        logger.info(f"✓ {len(rows)} artículos para descargar")

        # Verificar estructura
        required_fields = ["species", "doi", "url"]
        missing = set()
        for row in rows:
            for field in required_fields:
                if field not in row:
                    missing.add(field)

        if missing:
            logger.warning(f"⚠ Campos opcionales que faltan: {missing}")

        # Estadísticas
        with_doi = len([r for r in rows if r.get("doi", "").strip()])
        with_url = len([r for r in rows if r.get("url", "").strip()])

        logger.info(f"  - Con DOI: {with_doi}")
        logger.info(f"  - Con URL: {with_url}")

        if with_doi == 0 and with_url == 0:
            logger.error("✗ No hay artículos con DOI ni URL")
            return False

        return True

    except Exception as e:
        logger.error(f"✗ Error al leer artículos: {e}")
        return False


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.json",
        help="Archivo de configuración",
    )
    parser.add_argument(
        "--articles",
        type=Path,
        default=Path(__file__).parent / "articles_to_download.csv",
        help="Archivo de artículos",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Modo verbose",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    logger.info("=" * 70)
    logger.info("VALIDADOR DE CONFIGURACIÓN - ScienceDirect Batch Downloader")
    logger.info("=" * 70)
    logger.info("")

    all_ok = True

    # Test 1: Configuración
    logger.info("[1/3] Verificando archivo de configuración...")
    config_ok = test_config_file(args.config)
    logger.info("")

    if not config_ok:
        logger.error("Solucionar problema de configuración e intentar de nuevo")
        return 1

    # Leer API key
    with args.config.open("r") as f:
        config = json.load(f)
    api_key = config.get("api_key", "")

    # Test 2: API key
    logger.info("[2/3] Probando API key...")
    api_ok = test_api_key(api_key, verbose=args.verbose)
    logger.info("")

    if not api_ok:
        logger.error("")
        logger.error("SOLUCIÓN RÁPIDA:")
        logger.error("1. Verificar que el API key sea correcto en config.json")
        logger.error("2. Verificar que estés en la red de la institución o VPN")
        logger.error("3. Verificar que la institución tenga acceso a ScienceDirect API")
        logger.error("4. Esperar unos minutos y reintentar si hay rate limit")
        return 1

    # Test 3: Artículos
    logger.info("[3/3] Verificando archivo de artículos...")
    articles_ok = test_articles_file(args.articles)
    logger.info("")

    # Resumen
    logger.info("=" * 70)
    if config_ok and api_ok and articles_ok:
        logger.info("✓ TODO LISTO - Puedes ejecutar download_sciencedirect_api.py")
        logger.info("")
        logger.info("Próximos pasos:")
        logger.info("  python3 download_sciencedirect_api.py")
        logger.info("")
        return 0
    else:
        logger.error("✗ Hay problemas que solucionar")
        if not api_ok:
            logger.error("  - Verificar API key y conexión")
        if not articles_ok:
            logger.error("  - Verificar archivo de artículos")
        logger.error("")
        return 1


if __name__ == "__main__":
    exit(main())
