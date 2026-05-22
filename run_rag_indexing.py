#!/usr/bin/env python3
"""
Indexa TODOS los PDFs (nuevos + previos) en FAISS para RAG.
Esto incluye:
- pdfs/ → archivos descargados recientemente
- Todos sus subdirectorios recursivamente
"""

import subprocess
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path.cwd()
PDFS_DIR = PROJECT_ROOT / "pdfs"
RAG_INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index"

print("=" * 70)
print("FASE 3: Indexación RAG con FAISS")
print("=" * 70)

# Contar PDFs disponibles
pdfs = list(PDFS_DIR.rglob("*.pdf"))
logger.info(f"PDFs encontrados para indexar: {len(pdfs)}")

if not pdfs:
    logger.warning("❌ No hay PDFs para indexar")
    sys.exit(1)

RAG_INDEX_DIR.mkdir(parents=True, exist_ok=True)

# Ejecutar indexar.py
cmd = [
    sys.executable, 
    str(PROJECT_ROOT / "indexar.py"),
    "--pdf-dir", str(PDFS_DIR),
    "--index-dir", str(RAG_INDEX_DIR),
    "--provider", "local",
    "--chunk-size", "2000",
    "--overlap", "200",
]

logger.info(f"Ejecutando: {' '.join(cmd)}")
logger.info("Esto puede tomar 2-4 horas dependiendo de la cantidad de PDFs...")

try:
    result = subprocess.run(cmd, timeout=7200, check=False)
    
    if result.returncode == 0:
        logger.info("✅ Indexación RAG completada")
        
        # Verificar config
        config_file = RAG_INDEX_DIR / "index_config.json"
        if config_file.exists():
            with config_file.open() as f:
                config = json.load(f)
                logger.info(f"Índice RAG info: {config}")
    else:
        logger.error(f"❌ Error en indexación: código {result.returncode}")
        sys.exit(1)
        
except subprocess.TimeoutExpired:
    logger.error("❌ Timeout en indexación (2h)")
    sys.exit(1)
except Exception as e:
    logger.error(f"❌ Error: {e}", exc_info=True)
    sys.exit(1)

