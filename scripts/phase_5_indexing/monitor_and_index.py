#!/usr/bin/env python3
"""
Monitorea las descargas de PDFs y ejecuta la indexación RAG automáticamente
cuando todas las descargas estén completas.
"""

import json
import subprocess
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("monitor_and_index.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path.cwd()
STATE_DIR = PROJECT_ROOT / "outputs" / "state"
DOWNLOAD_PROGRESS_FILE = STATE_DIR / "download_progress.json"
RAG_INDEXING_SCRIPT = PROJECT_ROOT / "run_rag_indexing.py"
MONITOR_STATE_FILE = STATE_DIR / ".monitor_state.json"
PDF_DIR = PROJECT_ROOT / "pdfs"  # O "PDF" si es en mayúscula

POLL_INTERVAL = 60  # Revisar cada 60 segundos
MAX_WAIT_TIME = 7 * 24 * 3600  # 7 días máximo
MIN_PDFS_TO_INDEX = 1000  # Cantidad mínima de PDFs para iniciar indexación


def count_available_pdfs() -> int:
    """Cuenta cuántos PDFs hay disponibles para indexación."""
    if not PDF_DIR.exists():
        return 0
    return len(list(PDF_DIR.rglob("*.pdf")))


def is_download_complete() -> bool:
    """
    Verifica si todas las descargas están completadas.
    Las descargas están completas cuando:
    - El archivo de progreso existe
    - Para cada especie: processed == downloaded (todos los artículos encontrados fueron descargados)
    """
    if not DOWNLOAD_PROGRESS_FILE.exists():
        logger.info("Archivo de progreso no encontrado aún")
        return False

    try:
        with open(DOWNLOAD_PROGRESS_FILE) as f:
            progress = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error al leer JSON de progreso: {e}")
        return False

    if not progress:
        logger.warning("Archivo de progreso vacío")
        return False

    # Revisar si alguna especie aún está descargando
    incomplete_species = []
    for species, stats in progress.items():
        # Ignorar entradas que no sean diccionarios
        if not isinstance(stats, dict):
            continue

        processed = stats.get("processed", 0)
        downloaded = stats.get("downloaded", 0)

        # Si processed > downloaded, aún hay descargas pendientes
        if processed > downloaded:
            incomplete_species.append(f"{species} ({downloaded}/{processed})")

    if incomplete_species:
        logger.info(f"Descargas pendientes ({len(incomplete_species)} especies):")
        for species in incomplete_species[:5]:  # Mostrar solo las primeras 5
            logger.info(f"  - {species}")
        if len(incomplete_species) > 5:
            logger.info(f"  ... y {len(incomplete_species) - 5} más")
        return False

    logger.info(f"✅ Todas las descargas completadas ({len(progress)} especies)")
    return True


def run_indexing() -> bool:
    """Ejecuta el script de indexación RAG."""
    if not RAG_INDEXING_SCRIPT.exists():
        logger.error(f"Script de indexación no encontrado: {RAG_INDEXING_SCRIPT}")
        return False

    logger.info("=" * 70)
    logger.info("Iniciando indexación RAG...")
    logger.info("=" * 70)

    try:
        result = subprocess.run(
            [sys.executable, str(RAG_INDEXING_SCRIPT)],
            timeout=14400,  # 4 horas máximo
            check=False
        )

        if result.returncode == 0:
            logger.info("✅ Indexación completada exitosamente")
            return True
        else:
            logger.error(f"❌ Indexación fallida (código {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        logger.error("❌ Timeout en indexación (4h)")
        return False
    except Exception as e:
        logger.error(f"❌ Error al ejecutar indexación: {e}", exc_info=True)
        return False


def load_monitor_state() -> dict:
    """Carga el estado previo del monitoreo."""
    if MONITOR_STATE_FILE.exists():
        try:
            with open(MONITOR_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"started": datetime.now().isoformat(), "indexing_completed": False}


def save_monitor_state(state: dict):
    """Guarda el estado del monitoreo."""
    with open(MONITOR_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def main():
    """Loop principal de monitoreo."""
    logger.info("Iniciando monitor de descargas e indexación")
    logger.info(f"Archivo de progreso: {DOWNLOAD_PROGRESS_FILE}")
    logger.info(f"Directorio de PDFs: {PDF_DIR}")
    logger.info(f"Mínimo de PDFs para iniciar indexación: {MIN_PDFS_TO_INDEX}")
    logger.info(f"Intervalo de revisión: {POLL_INTERVAL}s")

    state = load_monitor_state()
    start_time = time.time()

    # Si ya se completó la indexación, no hacer nada
    if state.get("indexing_completed"):
        logger.info("Indexación ya completada en ejecución anterior")
        return 0

    while True:
        elapsed = time.time() - start_time

        # Timeout de seguridad
        if elapsed > MAX_WAIT_TIME:
            logger.error(f"❌ Timeout: esperando descargas por {MAX_WAIT_TIME/3600:.1f} horas")
            return 1

        # Contar PDFs disponibles
        pdf_count = count_available_pdfs()
        logger.info(f"PDFs disponibles: {pdf_count}")

        # Condición 1: Si hay suficientes PDFs, lanzar indexación
        # (aunque descargas no estén 100% completas)
        if pdf_count >= MIN_PDFS_TO_INDEX:
            logger.info(f"✅ {pdf_count} PDFs disponibles (mínimo requerido: {MIN_PDFS_TO_INDEX})")
            logger.info("Iniciando indexación en paralelo con descargas...")
            success = run_indexing()

            state["indexing_completed"] = success
            state["completion_time"] = datetime.now().isoformat()
            state["pdfs_indexed"] = pdf_count
            save_monitor_state(state)

            return 0 if success else 1

        # Condición 2: Todas las descargas completas (fallback)
        if is_download_complete():
            logger.info("✅ Todas las descargas completadas")
            logger.info(f"Ejecutando indexación con {pdf_count} PDFs...")

            success = run_indexing()

            state["indexing_completed"] = success
            state["completion_time"] = datetime.now().isoformat()
            state["pdfs_indexed"] = pdf_count
            save_monitor_state(state)

            return 0 if success else 1

        # Aún no hay suficientes PDFs
        logger.info(f"Esperando más PDFs... ({pdf_count}/{MIN_PDFS_TO_INDEX})")
        logger.info(f"Siguiente revisión en {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Monitor interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)
