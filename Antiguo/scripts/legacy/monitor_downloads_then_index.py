#!/usr/bin/env python3
"""
Monitorea el progreso de descargas y ejecuta la indexación paralela
1 hora después de que todas las descargas estén completas.
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
        logging.FileHandler("monitor_downloads_then_index.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path.cwd()
DOWNLOAD_PROGRESS_FILE = PROJECT_ROOT / "download_progress.json"
INDEXING_SCRIPT = PROJECT_ROOT / "indexar_paralelo.py"
MONITOR_STATE_FILE = PROJECT_ROOT / ".monitor_index_state.json"

POLL_INTERVAL = 120  # Revisar cada 2 minutos
WAIT_AFTER_DOWNLOAD = 3600  # 1 hora después de que terminen las descargas
MAX_TOTAL_WAIT = 30 * 24 * 3600  # 30 días máximo


def is_download_complete() -> bool:
    """
    Verifica si todas las descargas están completadas.
    Las descargas están completas cuando processed == downloaded para todas las especies.
    """
    if not DOWNLOAD_PROGRESS_FILE.exists():
        logger.info("Archivo de progreso no encontrado")
        return False

    try:
        with open(DOWNLOAD_PROGRESS_FILE) as f:
            progress = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error al leer progreso: {e}")
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
            incomplete_species.append(species)

    if incomplete_species:
        logger.info(f"⏳ Descargas pendientes: {len(incomplete_species)} especies")
        if len(incomplete_species) <= 5:
            for species in incomplete_species:
                logger.info(f"  - {species}")
        return False

    logger.info(f"✅ Todas las descargas completadas ({len(progress)} especies)")
    return True


def run_parallel_indexing() -> bool:
    """Ejecuta el script de indexación paralela."""
    if not INDEXING_SCRIPT.exists():
        logger.error(f"Script de indexación no encontrado: {INDEXING_SCRIPT}")
        return False

    logger.info("=" * 70)
    logger.info("Iniciando indexación paralela...")
    logger.info("=" * 70)

    try:
        result = subprocess.run(
            [sys.executable, str(INDEXING_SCRIPT)],
            check=False
        )

        if result.returncode == 0:
            logger.info("✅ Indexación completada exitosamente")
            return True
        else:
            logger.error(f"❌ Indexación fallida (código {result.returncode})")
            return False

    except Exception as e:
        logger.error(f"❌ Error al ejecutar indexación: {e}", exc_info=True)
        return False


def load_state() -> dict:
    """Carga estado previo."""
    if MONITOR_STATE_FILE.exists():
        try:
            with open(MONITOR_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "started": datetime.now().isoformat(),
        "download_completed_at": None,
        "indexing_started_at": None,
        "indexing_completed": False
    }


def save_state(state: dict):
    """Guarda estado."""
    with open(MONITOR_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def main():
    """Loop principal."""
    logger.info("Iniciando monitor de descargas e indexación...")

    state = load_state()
    start_time = time.time()

    # Si ya se completó la indexación, no hacer nada
    if state.get("indexing_completed"):
        logger.info("Indexación ya completada en ejecución anterior")
        return 0

    # Fase 1: Esperar 1 hora inicial
    logger.info("\n=== FASE 1: Esperando 1 hora ===")
    remaining = WAIT_AFTER_DOWNLOAD

    while remaining > 0:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        logger.info(f"Esperando: {hours}h {minutes}m")

        # Revisar cada 5 minutos
        sleep_time = min(300, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time

    logger.info("✅ Tiempo de espera completado. Comenzando a monitorear descargas...")

    # Fase 2: Monitorear hasta que terminen las descargas
    logger.info("\n=== FASE 2: Monitoreando descargas ===")

    while True:
        elapsed = time.time() - start_time
        if elapsed > MAX_TOTAL_WAIT:
            logger.error(f"❌ Timeout total ({MAX_TOTAL_WAIT/3600:.0f}h)")
            return 1

        if is_download_complete():
            logger.info(f"✅ Descargas completadas a las {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            state["download_completed_at"] = datetime.now().isoformat()
            save_state(state)
            break

        logger.info(f"Siguiente revisión en {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

    # Fase 3: Ejecutar indexación inmediatamente
    logger.info("\n=== FASE 3: Iniciando indexación paralela ===")
    state["indexing_started_at"] = datetime.now().isoformat()
    save_state(state)

    success = run_parallel_indexing()

    state["indexing_completed"] = success
    if success:
        state["indexing_completed_at"] = datetime.now().isoformat()
    save_state(state)

    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Monitoreo interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)
