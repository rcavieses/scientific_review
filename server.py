"""
Servidor API para el pipeline de procesamiento de especies.

Uso:
    python server.py [--host 0.0.0.0] [--port 8000] [--reload]

Endpoints:
    GET  /health           - Estado del servidor
    GET  /status           - Estado actual del pipeline
    POST /start            - Iniciar pipeline
    POST /stop             - Detener pipeline (cuando esté implementado)
    GET  /results          - Resultados/archivos procesados
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Agregar el directorio del proyecto al path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_manager import (
    PipelineManager,
    PipelineStatus,
    create_default_manager,
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "server.log"),
    ],
)
logger = logging.getLogger(__name__)

# --- Inicialización ---
manager: PipelineManager | None = None


def get_manager() -> PipelineManager:
    """Obtiene la instancia global del manager."""
    global manager
    if manager is None:
        manager = create_default_manager(PROJECT_ROOT)
    return manager


# --- FastAPI app ---
app = FastAPI(
    title="Scientific Review Pipeline",
    description="API para orquestar el procesamiento de especies",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Modelos ---
class StartPipelineRequest(BaseModel):
    """Solicitud para iniciar el pipeline."""

    force_restart: bool = False


class StartPipelineResponse(BaseModel):
    """Respuesta cuando se inicia el pipeline."""

    status: str
    message: str


class HealthResponse(BaseModel):
    """Respuesta del health check."""

    status: str
    pipeline_stage: str


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check del servidor."""
    mgr = get_manager()
    return HealthResponse(
        status="ok",
        pipeline_stage=mgr.status.stage.value,
    )


@app.get("/status", response_model=PipelineStatus)
async def get_status() -> PipelineStatus:
    """Obtiene el estado actual del pipeline."""
    mgr = get_manager()
    return mgr.get_status()


@app.post("/start", response_model=StartPipelineResponse)
async def start_pipeline(req: StartPipelineRequest) -> StartPipelineResponse:
    """Inicia la ejecución del pipeline."""
    mgr = get_manager()

    current_stage = mgr.status.stage.value
    if current_stage not in ("idle", "completed", "failed"):
        if not req.force_restart:
            raise HTTPException(
                status_code=409,
                detail=f"Pipeline ya está en ejecución (etapa: {current_stage}). "
                "Use force_restart=true para reiniciar.",
            )
        logger.info("Reiniciando pipeline (force_restart=true)")

    mgr.run_pipeline()

    return StartPipelineResponse(
        status="started",
        message="Pipeline iniciado en segundo plano",
    )


@app.get("/results")
async def get_results():
    """Lista los archivos/resultados disponibles."""
    mgr = get_manager()
    results = {
        "analysis_files": [],
        "search_results": [],
        "pdfs": [],
        "rag_index": None,
        "report": None,
    }

    # Archivos de análisis
    if mgr.config.analysis_dir.exists():
        results["analysis_files"] = [
            f.name
            for f in mgr.config.analysis_dir.glob("*.csv")
            if f.is_file()
        ]

    # Búsquedas
    if mgr.config.search_results_dir.exists():
        results["search_results"] = [
            f.name
            for f in mgr.config.search_results_dir.glob("*.csv")
            if f.is_file()
        ]

    # PDFs
    if mgr.config.pdfs_dir.exists():
        results["pdfs"] = [
            f.name
            for f in mgr.config.pdfs_dir.glob("*.pdf")
            if f.is_file()
        ]

    # Índice RAG
    rag_faiss = mgr.config.rag_index_dir / "index.faiss"
    if rag_faiss.exists():
        results["rag_index"] = "index.faiss"

    # Reporte
    report_file = mgr.config.project_root / "reporte.md"
    if report_file.exists():
        results["report"] = "reporte.md"

    return results


@app.get("/download/{file_type}/{filename}")
async def download_file(file_type: str, filename: str):
    """Descarga un archivo de resultados."""
    allowed_dirs = {
        "analysis": "analysis_species",
        "search": "search_results",
        "pdf": "pdfs",
        "report": ".",
    }

    if file_type not in allowed_dirs:
        raise HTTPException(status_code=400, detail="Tipo de archivo inválido")

    base_dir = Path(allowed_dirs[file_type])
    if not base_dir.is_absolute():
        base_dir = PROJECT_ROOT / base_dir

    file_path = base_dir / filename

    # Validar que no haya directory traversal
    try:
        file_path.resolve().relative_to(base_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/log")
async def get_log():
    """Obtiene las últimas líneas del log del servidor."""
    log_file = PROJECT_ROOT / "server.log"
    if not log_file.exists():
        return {"log": []}

    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()
        return {"log": lines[-100:]}  # últimas 100 líneas
    except Exception as e:
        return {"error": str(e)}


@app.on_event("startup")
async def startup_event():
    """Evento al iniciar el servidor."""
    logger.info("="*60)
    logger.info("Servidor iniciado")
    logger.info(f"Project root: {PROJECT_ROOT}")
    mgr = get_manager()
    logger.info(f"Pipeline stage: {mgr.status.stage.value}")
    logger.info("="*60)


@app.on_event("shutdown")
async def shutdown_event():
    """Evento al cerrar el servidor."""
    logger.info("Servidor cerrando...")


def main():
    """Punto de entrada."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Puerto (default: 8000)")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Habilitar hot-reload (solo desarrollo)",
    )
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
