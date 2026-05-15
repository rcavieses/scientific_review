"""Gestor centralizado del pipeline de procesamiento de especies."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import subprocess
import sys
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    IDLE = "idle"
    CLASSIFYING_HABITATS = "classifying_habitats"
    FILTERING_MARINE = "filtering_marine"
    SEARCHING_ARTICLES = "searching_articles"
    DOWNLOADING_PDFS = "downloading_pdfs"
    INDEXING_RAG = "indexing_rag"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStatus(BaseModel):
    stage: PipelineStage
    progress: dict[str, Any]
    start_time: str | None = None
    end_time: str | None = None
    error: str | None = None


class PipelineConfig(BaseModel):
    project_root: Path
    analysis_dir: Path
    search_results_dir: Path
    pdfs_dir: Path
    rag_index_dir: Path


class PipelineManager:
    """Orquesta la ejecución del pipeline en segundo plano."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.status_file = config.project_root / "pipeline_status.json"
        self.state_file = config.project_root / ".pipeline_state.json"
        self.lock = threading.RLock()

        # Crear directorios necesarios
        for directory in [
            config.analysis_dir,
            config.search_results_dir,
            config.pdfs_dir,
            config.rag_index_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        # Cargar estado previo o inicializar
        self._load_state()

    def _load_state(self) -> None:
        """Carga el estado del pipeline desde archivo."""
        with self.lock:
            if self.state_file.exists():
                try:
                    state = json.loads(self.state_file.read_text(encoding="utf-8"))
                    self.status = PipelineStatus(**state)
                except Exception as e:
                    logger.warning(f"No se pudo cargar estado previo: {e}")
                    self.status = PipelineStatus(
                        stage=PipelineStage.IDLE,
                        progress={},
                    )
            else:
                self.status = PipelineStatus(stage=PipelineStage.IDLE, progress={})

    def _save_state(self) -> None:
        """Persiste el estado actual a disco."""
        with self.lock:
            data = self.status.model_dump(mode="json")
            self.state_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def _update_progress(
        self,
        stage: PipelineStage,
        progress: dict[str, Any],
        error: str | None = None,
    ) -> None:
        """Actualiza el estado del pipeline."""
        with self.lock:
            self.status.stage = stage
            self.status.progress = progress
            self.status.error = error

            if stage != PipelineStage.IDLE and not self.status.start_time:
                self.status.start_time = datetime.now().isoformat()

            if stage in (PipelineStage.COMPLETED, PipelineStage.FAILED):
                self.status.end_time = datetime.now().isoformat()

            self._save_state()
            logger.info(f"[{stage.value}] {progress}")

    def get_status(self) -> PipelineStatus:
        """Obtiene el estado actual del pipeline."""
        with self.lock:
            return self.status.model_copy()

    def run_pipeline(self) -> None:
        """Ejecuta el pipeline completo en un thread separado."""
        thread = threading.Thread(target=self._run_pipeline_internal, daemon=False)
        thread.start()

    def _run_pipeline_internal(self) -> None:
        """Implementación interna del pipeline."""
        try:
            # Paso 1: Clasificar hábitats
            self._run_step(
                "Clasificar hábitats",
                PipelineStage.CLASSIFYING_HABITATS,
                self._step_classify_habitats,
            )

            # Paso 2: Filtrar MARINE
            self._run_step(
                "Filtrar MARINE",
                PipelineStage.FILTERING_MARINE,
                self._step_filter_marine,
            )

            # Paso 3: Buscar artículos
            self._run_step(
                "Buscar artículos científicos",
                PipelineStage.SEARCHING_ARTICLES,
                self._step_search_articles,
            )

            # Paso 4: Descargar PDFs
            self._run_step(
                "Descargar PDFs",
                PipelineStage.DOWNLOADING_PDFS,
                self._step_download_pdfs,
            )

            # Paso 5: Indexar RAG
            self._run_step(
                "Indexar RAG",
                PipelineStage.INDEXING_RAG,
                self._step_index_rag,
            )

            # Paso 6: Crear reporte
            self._run_step(
                "Generar reporte",
                PipelineStage.GENERATING_REPORT,
                self._step_generate_report,
            )

            self._update_progress(
                PipelineStage.COMPLETED,
                {"message": "Pipeline completado exitosamente"},
            )
            logger.info("✓ Pipeline completado exitosamente")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._update_progress(
                PipelineStage.FAILED,
                {"error": str(e)},
                error=error_msg,
            )
            logger.error(f"✗ Pipeline falló: {error_msg}")

    def _run_step(
        self,
        name: str,
        stage: PipelineStage,
        step_func,
    ) -> None:
        """Ejecuta un paso del pipeline con manejo de errores."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Iniciando: {name}")
        logger.info(f"{'='*60}")

        self._update_progress(stage, {"status": "iniciando"})

        try:
            result = step_func()
            self._update_progress(stage, result)
            logger.info(f"✓ {name} completado")
        except Exception as e:
            logger.error(f"✗ {name} falló: {e}")
            raise

    def _step_classify_habitats(self) -> dict[str, Any]:
        """Paso 1: Clasificar hábitats."""
        script = self.config.project_root / "analysis_species" / "clasificar_habitats.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=self.config.project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Error ejecutando clasificar_habitats: {result.stderr}"
            )

        return {
            "status": "completado",
            "output": result.stdout[-500:] if result.stdout else "",
        }

    def _step_filter_marine(self) -> dict[str, Any]:
        """Paso 2: Filtrar especies MARINE."""
        acuaticas_csv = self.config.analysis_dir / "species_acuaticas.csv"

        if not acuaticas_csv.exists():
            raise FileNotFoundError(f"No encontrado: {acuaticas_csv}")

        import csv

        marine_species = []
        with acuaticas_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                habitat = (row.get("habitat") or "").upper()
                if habitat == "MARINE":
                    marine_species.append(row.get("species", ""))

        return {
            "status": "completado",
            "total_acuaticas": None,
            "marine_count": len(marine_species),
            "sample": marine_species[:5],
        }

    def _step_search_articles(self) -> dict[str, Any]:
        """Paso 3: Buscar artículos en bases de datos científicas."""
        from search_articles import search_articles_batch

        acuaticas_csv = self.config.analysis_dir / "species_acuaticas.csv"

        if not acuaticas_csv.exists():
            raise FileNotFoundError(f"No encontrado: {acuaticas_csv}")

        import csv

        species_list = []
        with acuaticas_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                species = (row.get("species") or "").strip()
                if species:
                    species_list.append(species)

        logger.info(f"Buscando artículos para {len(species_list)} especies...")

        progress_file = self.config.project_root / "search_progress.json"
        results = search_articles_batch(species_list, self.config.search_results_dir, progress_file)

        return {
            "status": "completado",
            "total_especies": results["total"],
            "con_articulos": results["found"],
            "procesadas": results["processed"],
            "promedio": f"{(results['found']/max(1, results['processed'])*100):.1f}%",
        }

    def _step_download_pdfs(self) -> dict[str, Any]:
        """Paso 4: Descargar PDFs de artículos."""
        from download_pdfs import download_all_articles

        logger.info(f"Descargando PDFs desde {self.config.search_results_dir}...")

        progress_file = self.config.project_root / "download_progress.json"
        results = download_all_articles(
            self.config.search_results_dir,
            self.config.pdfs_dir,
            progress_file,
        )

        return {
            "status": "completado",
            "total_especies": results["total_species"],
            "total_articulos": results["total_articles"],
            "pdfs_descargados": results["total_downloaded"],
            "tasa_descarga": f"{(results['total_downloaded']/max(1, results['total_articles'])*100):.1f}%",
        }

    def _step_index_rag(self) -> dict[str, Any]:
        """Paso 5: Indexar RAG (stub)."""
        return {
            "status": "pendiente_implementacion",
            "message": "Este paso indexará PDFs con FAISS",
        }

    def _step_generate_report(self) -> dict[str, Any]:
        """Paso 6: Generar reporte."""
        report_path = self.config.project_root / "reporte.md"

        report_content = f"""# Reporte de Procesamiento de Especies

**Fecha**: {datetime.now().isoformat()}
**Estado**: Completado

## Resumen

El pipeline ha procesado especies acuáticas y terrestres.

## Detalles

- **Etapa actual**: {self.status.stage.value}
- **Inicio**: {self.status.start_time}
- **Fin**: {self.status.end_time}

## Próximos pasos

- Implementar búsqueda de artículos científicos
- Descargar PDFs asociados
- Construir índice RAG con FAISS

"""

        report_path.write_text(report_content, encoding="utf-8")

        return {
            "status": "completado",
            "report_path": str(report_path),
        }


def create_default_manager(project_root: str | Path | None = None) -> PipelineManager:
    """Factory para crear un PipelineManager con configuración por defecto."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent
    else:
        project_root = Path(project_root)

    config = PipelineConfig(
        project_root=project_root,
        analysis_dir=project_root / "analysis_species",
        search_results_dir=project_root / "search_results",
        pdfs_dir=project_root / "pdfs",
        rag_index_dir=project_root / "rag_index",
    )

    return PipelineManager(config)
