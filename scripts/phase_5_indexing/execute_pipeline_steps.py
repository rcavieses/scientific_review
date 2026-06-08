"""
Orquestador de pasos 3, 4 y 6 (reporte final).

Ejecuta secuencialmente:
1. PASO 3: Buscar artículos científicos
2. PASO 4: Descargar PDFs
3. PASO 6: Generar reporte de resultados

Puede desconectarse la terminal - todo corre en background.

Uso:
    python3 execute_pipeline_steps.py [--start-from {3|4|6}]

Monitoreo:
    python3 cli.py status
    tail -f pipeline_execution.log
    ls -la search_results/*.csv | wc -l
    find pdfs -name "*.pdf" | wc -l
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline_execution.log"),
    ],
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "outputs" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_progress(step: int) -> dict[str, Any]:
    """Carga el progreso previo de un paso."""
    progress_files = {
        3: "search_progress.json",
        4: "download_progress.json",
    }

    progress_file = STATE_DIR / progress_files.get(step, "")
    if progress_file and progress_file.exists():
        try:
            return json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"No se pudo cargar progreso anterior: {e}")

    return {}


def save_execution_state(state: dict[str, Any]) -> None:
    """Guarda el estado de ejecución."""
    state_file = STATE_DIR / "pipeline_execution_state.json"
    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_execution_state() -> dict[str, Any]:
    """Obtiene el estado de ejecución."""
    state_file = STATE_DIR / "pipeline_execution_state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "start_time": datetime.now().isoformat(),
        "steps": {3: "pending", 4: "pending", 6: "pending"},
        "results": {},
    }


def execute_step_3() -> dict[str, Any]:
    """Ejecuta PASO 3: Buscar artículos."""
    logger.info("="*70)
    logger.info("INICIANDO PASO 3: Buscar artículos científicos")
    logger.info("="*70)

    from scripts.phase_2_search.search_articles import search_articles_batch
    import csv

    try:
        # Leer especies
        acuaticas_csv = PROJECT_ROOT / "analysis_species" / "species_acuaticas.csv"
        species_list = []
        with acuaticas_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                species = (row.get("species") or "").strip()
                if species:
                    species_list.append(species)

        logger.info(f"Buscando artículos para {len(species_list)} especies...")

        # Ejecutar búsqueda
        progress_file = STATE_DIR / "search_progress.json"
        results = search_articles_batch(species_list, PROJECT_ROOT / "outputs" / "search_results", progress_file)

        logger.info("="*70)
        logger.info(f"✓ PASO 3 COMPLETADO")
        logger.info(f"  Total especies: {results['total']}")
        logger.info(f"  Con artículos: {results['found']}")
        logger.info(f"  Procesadas: {results['processed']}")
        logger.info(f"  Promedio: {(results['found']/max(1, results['processed'])*100):.1f}%")
        logger.info("="*70)

        return {"status": "completado", **results}

    except Exception as e:
        logger.error(f"✗ PASO 3 FALLÓ: {e}", exc_info=True)
        return {"status": "fallido", "error": str(e)}


def execute_step_4() -> dict[str, Any]:
    """Ejecuta PASO 4: Descargar PDFs."""
    logger.info("="*70)
    logger.info("INICIANDO PASO 4: Descargar PDFs")
    logger.info("="*70)

    from scripts.phase_3_download.download_pdfs import download_all_articles

    try:
        logger.info("Descargando artículos desde search_results/...")

        progress_file = STATE_DIR / "download_progress.json"
        results = download_all_articles(
            PROJECT_ROOT / "outputs" / "search_results",
            PROJECT_ROOT / "pdfs",
            progress_file,
        )

        logger.info("="*70)
        logger.info(f"✓ PASO 4 COMPLETADO")
        logger.info(f"  Especies procesadas: {results['total_species']}")
        logger.info(f"  Artículos encontrados: {results['total_articles']}")
        logger.info(f"  PDFs descargados: {results['total_downloaded']}")
        logger.info(f"  Tasa de descarga: {(results['total_downloaded']/max(1, results['total_articles'])*100):.1f}%")
        logger.info("="*70)

        return {"status": "completado", **results}

    except Exception as e:
        logger.error(f"✗ PASO 4 FALLÓ: {e}", exc_info=True)
        return {"status": "fallido", "error": str(e)}


def execute_step_6_report(step3_results: dict, step4_results: dict) -> dict[str, Any]:
    """Ejecuta PASO 6: Generar reporte detallado."""
    logger.info("="*70)
    logger.info("INICIANDO PASO 6: Generar reporte detallado")
    logger.info("="*70)

    import csv

    try:
        # Leer datos
        search_results_dir = PROJECT_ROOT / "outputs" / "search_results"
        pdfs_dir = PROJECT_ROOT / "pdfs"

        # Contar artículos por especie
        species_articles = {}
        species_pdfs = {}

        if search_results_dir.exists():
            for csv_file in search_results_dir.glob("*.csv"):
                species_name = csv_file.stem.replace("_", " ")
                with csv_file.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    count = sum(1 for _ in reader) - 1  # Restar encabezado
                    species_articles[species_name] = max(0, count)

        # Contar PDFs por especie
        if pdfs_dir.exists():
            for species_dir in pdfs_dir.iterdir():
                if species_dir.is_dir():
                    pdf_count = len(list(species_dir.glob("*.pdf")))
                    species_pdfs[species_dir.name] = pdf_count

        # Leer especies MARINE
        acuaticas_csv = PROJECT_ROOT / "analysis_species" / "species_acuaticas.csv"
        total_species = 0
        with acuaticas_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            total_species = sum(1 for _ in reader)

        # Calcular estadísticas
        species_con_articulos = len([s for s, c in species_articles.items() if c > 0])
        species_sin_articulos = len(species_articles) - species_con_articulos
        total_articulos = sum(species_articles.values())
        total_pdfs = sum(species_pdfs.values())

        # Generar reporte
        report_path = PROJECT_ROOT / "REPORTE_PASOS_3_4.md"

        report_content = f"""# Reporte de Ejecución - Pasos 3 y 4

**Fecha**: {datetime.now().isoformat()}

---

## 📊 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total de especies MARINE** | {total_species:,} |
| **Especies procesadas** | {len(species_articles):,} |
| **Total de artículos encontrados** | {total_articulos:,} |
| **Total de PDFs descargados** | {total_pdfs:,} |
| **Especies con artículos** | {species_con_articulos:,} ({(species_con_articulos/max(1,len(species_articles))*100):.1f}%) |
| **Especies sin artículos** | {species_sin_articulos:,} ({(species_sin_articulos/max(1,len(species_articles))*100):.1f}%) |

---

## 📈 Detalles por Paso

### PASO 3: Búsqueda de Artículos
- **Estado**: ✅ Completado
- **Especies buscadas**: {step3_results.get('processed', 'N/A')}
- **Especies con resultados**: {step3_results.get('found', 'N/A')}
- **Promedio**: {step3_results.get('promedio', 'N/A')}
- **Bases de datos**: PubMed, CrossRef, ArXiv (+ Scopus/ScienceDirect si config)

### PASO 4: Descarga de PDFs
- **Estado**: ✅ Completado
- **Especies procesadas**: {step4_results.get('total_species', 'N/A')}
- **Artículos disponibles**: {step4_results.get('total_articles', 'N/A')}
- **PDFs descargados**: {step4_results.get('total_downloaded', 'N/A')}
- **Tasa de descarga**: {step4_results.get('tasa_descarga', 'N/A')}

---

## 🔍 Análisis Detallado

### Especies CON Información

**Total**: {species_con_articulos} especies

| Especie | Artículos | PDFs |
|---------|-----------|------|
"""

        # Agregar top 20 especies con más artículos
        top_species = sorted(
            species_articles.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        for species_name, article_count in top_species:
            pdf_count = species_pdfs.get(species_name, 0)
            report_content += f"| {species_name} | {article_count} | {pdf_count} |\n"

        report_content += f"""
**... y {species_con_articulos - 20} especies más**

---

### Especies SIN Información

**Total**: {species_sin_articulos} especies

Las siguientes especies no tuvieron resultados en las bases de datos consultadas:

"""

        # Agregar especies sin artículos (primeras 50)
        species_sin_info = [s for s in species_articles if species_articles[s] == 0][:50]
        for species_name in sorted(species_sin_info):
            report_content += f"- {species_name}\n"

        if len(species_sin_info) < len([s for s in species_articles if species_articles[s] == 0]):
            report_content += f"\n**... y {len([s for s in species_articles if species_articles[s] == 0]) - 50} especies más sin información**\n"

        report_content += f"""

---

## 📁 Archivos Generados

### Resultados de Búsqueda
- **Directorio**: `search_results/`
- **Formato**: CSV con columnas: source, title, authors, year, journal, doi, url
- **Cantidad**: {len(species_articles)} archivos

### PDFs Descargados
- **Directorio**: `pdfs/`
- **Estructura**: `pdfs/{{especie}}/`
- **Total**: {total_pdfs} archivos

### Archivos de Tracking
- `search_progress.json` - Progreso de búsqueda
- `download_progress.json` - Progreso de descargas
- `REPORTE_PASOS_3_4.md` - Este reporte

---

## 🎯 Próximos Pasos

1. **PASO 5**: Indexación RAG (Pendiente)
   - Crear índice FAISS con PDFs descargados
   - Embeddings de documentos

2. **Análisis de Resultados**:
   - Verificar especies sin información
   - Investigar motivos de fallos de descarga
   - Mejorar estrategia de búsqueda si es necesario

3. **Integración**:
   - Usar PDFs indexados para búsquedas RAG
   - Conectar con modelos de lenguaje

---

## 📋 Configuración Utilizada

- **Bases de datos de búsqueda**: PubMed, CrossRef, ArXiv
- **Rate limits**: Respetados (0.1-0.3 seg entre peticiones)
- **Máximo artículos por especie**: 20
- **Tamaño máximo PDF**: 50 MB
- **Fecha de ejecución**: {datetime.now().isoformat()}

---

**Reporte generado automáticamente por execute_pipeline_steps.py**
"""

        report_path.write_text(report_content, encoding="utf-8")

        logger.info(f"✓ Reporte guardado en: {report_path}")
        logger.info("="*70)

        return {
            "status": "completado",
            "report_path": str(report_path),
            "total_species": total_species,
            "species_con_articulos": species_con_articulos,
            "species_sin_articulos": species_sin_articulos,
            "total_articulos": total_articulos,
            "total_pdfs": total_pdfs,
        }

    except Exception as e:
        logger.error(f"✗ PASO 6 FALLÓ: {e}", exc_info=True)
        return {"status": "fallido", "error": str(e)}


def main(start_from: int = 3) -> None:
    """Ejecuta la secuencia de pasos."""
    logger.info("\n\n")
    logger.info("╔" + "="*68 + "╗")
    logger.info("║" + " "*20 + "ORQUESTADOR DE PIPELINE" + " "*26 + "║")
    logger.info("╚" + "="*68 + "╝")
    logger.info(f"\nInicio: {datetime.now().isoformat()}")
    logger.info(f"Empezando desde PASO {start_from}\n")

    # Cargar/crear estado
    state = get_execution_state()

    try:
        # PASO 3
        if start_from <= 3:
            logger.info("\n" + "─"*70)
            logger.info("PASO 3: Buscar artículos científicos")
            logger.info("─"*70 + "\n")

            step3_results = execute_step_3()
            state["steps"][3] = step3_results.get("status", "desconocido")
            state["results"][3] = step3_results
            save_execution_state(state)

            if step3_results.get("status") != "completado":
                logger.error("PASO 3 falló. Deteniendo ejecución.")
                return
        else:
            logger.info("Saltando PASO 3 (ya completado)")
            step3_results = load_progress(3) or {}

        # PASO 4
        if start_from <= 4:
            logger.info("\n" + "─"*70)
            logger.info("PASO 4: Descargar PDFs")
            logger.info("─"*70 + "\n")

            step4_results = execute_step_4()
            state["steps"][4] = step4_results.get("status", "desconocido")
            state["results"][4] = step4_results
            save_execution_state(state)

            if step4_results.get("status") != "completado":
                logger.error("PASO 4 falló. Continuando con reporte...")
        else:
            logger.info("Saltando PASO 4 (ya completado)")
            step4_results = load_progress(4) or {}

        # PASO 6 (Reporte)
        if start_from <= 6:
            logger.info("\n" + "─"*70)
            logger.info("PASO 6: Generar Reporte")
            logger.info("─"*70 + "\n")

            step6_results = execute_step_6_report(step3_results, step4_results)
            state["steps"][6] = step6_results.get("status", "desconocido")
            state["results"][6] = step6_results
            state["end_time"] = datetime.now().isoformat()
            save_execution_state(state)

        logger.info("\n" + "╔" + "="*68 + "╗")
        logger.info("║" + " "*25 + "✅ EJECUCIÓN COMPLETADA" + " "*21 + "║")
        logger.info("╚" + "="*68 + "╝\n")

        logger.info(f"Fin: {datetime.now().isoformat()}")
        logger.info(f"\nReporte disponible en: REPORTE_PASOS_3_4.md")
        logger.info("Resultados en: search_results/ y pdfs/\n")

    except Exception as e:
        logger.error(f"\n✗ ERROR FATAL: {e}", exc_info=True)
        state["error"] = str(e)
        save_execution_state(state)
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-from",
        type=int,
        choices=[3, 4, 6],
        default=3,
        help="Paso desde el cual continuar (default: 3)",
    )
    args = parser.parse_args()

    main(start_from=args.start_from)
