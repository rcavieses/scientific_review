#!/usr/bin/env python3
"""
🚀 SCRIPT MAESTRO: Reconstrucción Exhaustiva del Sistema RAG

Ejecuta las 4 fases de limpieza, validación, reconstrucción y optimización:

  FASE 0: Limpieza y Validación
    → Elimina índices viejos
    → Valida colección de PDFs
    → Prueba GROBID en muestra
    → Genera reporte de validación

  FASE 1: Reconstrucción de Índice
    → Extracción GROBID + fallback pdfplumber
    → Chunking semántico inteligente
    → Embeddings con all-MiniLM-L6-v2
    → Indexación FAISS
    → Genera reporte de estadísticas

  FASE 2: Enriquecimiento de Metadatos
    → Extrae título, autores, año de GROBID XML
    → Extrae o infiere DOI
    → Valida completitud de metadatos
    → Genera reporte de enriquecimiento

  FASE 3: Optimización de Retrieval
    → Detecta chunks duplicados
    → Implementa re-ranking de resultados
    → Prueba queries de ejemplo
    → Valida integridad del índice

Salida:
  - outputs/rag_index_goc_full/ (índice final optimizado)
  - outputs/reports/ (reportes de cada fase)
  - outputs/logs/ (logs detallados)

Uso:
    python3 scripts/run_exhaustive_rebuild.py [--phase <N>] [--skip-phase <N>] [--dry-run]

Ejemplos:
    # Ejecutar todas las fases
    python3 scripts/run_exhaustive_rebuild.py

    # Ejecutar solo fase 1
    python3 scripts/run_exhaustive_rebuild.py --phase 1

    # Saltar fase 2
    python3 scripts/run_exhaustive_rebuild.py --skip-phase 2
"""

import sys
import time
import subprocess
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PHASES = {
    0: {
        "name": "Limpieza y Validación",
        "script": "scripts/phase_0_cleanup_and_validate.py",
        "description": "Elimina índices viejos, valida PDFs y GROBID",
        "required": True,
    },
    1: {
        "name": "Reconstrucción de Índice",
        "script": "scripts/phase_1_rebuild_index_optimized.py",
        "description": "Extracción, chunking, embeddings, indexación FAISS",
        "required": True,
    },
    2: {
        "name": "Enriquecimiento de Metadatos",
        "script": "scripts/phase_2_enrich_metadata.py",
        "description": "Extrae título, autores, año, DOI de cada PDF",
        "required": True,
    },
    3: {
        "name": "Optimización de Retrieval",
        "script": "scripts/phase_3_optimize_retrieval.py",
        "description": "Re-ranking, deduplicación, pruebas de queries",
        "required": True,
    },
}


def print_header():
    """Imprime encabezado del programa."""
    print("\n" + "=" * 90)
    print("🚀 RECONSTRUCCIÓN EXHAUSTIVA DEL SISTEMA RAG - GOLFO DE CALIFORNIA")
    print("=" * 90)
    print("\nEste script ejecuta 4 fases de optimización:")
    for phase_num, phase_info in PHASES.items():
        print(f"  [{phase_num}] {phase_info['name']}: {phase_info['description']}")
    print("\n" + "=" * 90)


def parse_arguments():
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Reconstrucción exhaustiva del sistema RAG con validación en cada fase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s                    # Ejecutar todas las fases (recomendado)
  %(prog)s --phase 1          # Ejecutar solo fase 1
  %(prog)s --skip-phase 2     # Saltar fase 2
  %(prog)s --dry-run          # Mostrar qué se va a hacer sin ejecutar
        """,
    )

    parser.add_argument(
        "--phase",
        type=int,
        help="Ejecutar solo una fase específica (0-3)",
    )
    parser.add_argument(
        "--skip-phase",
        type=int,
        help="Saltar una fase específica",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué se va a hacer sin ejecutar",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar output completo de cada script",
    )

    return parser.parse_args()


def should_run_phase(phase_num: int, args) -> bool:
    """Determina si una fase debe ejecutarse."""
    if args.phase is not None:
        return phase_num == args.phase

    if args.skip_phase is not None:
        return phase_num != args.skip_phase

    return True


def run_phase(phase_num: int, phase_info: dict, dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Ejecuta una fase individual.

    Retorna:
        True si éxito, False si error
    """
    script_path = PROJECT_ROOT / phase_info["script"]

    if not script_path.exists():
        print(f"❌ Script no encontrado: {script_path}")
        return False

    print(f"\n{'=' * 90}")
    print(f"[FASE {phase_num}] {phase_info['name']}")
    print(f"{'=' * 90}")
    print(f"Script: {script_path.name}")

    if dry_run:
        print("(DRY-RUN: no se ejecutará)")
        return True

    try:
        start_time = time.time()
        print(f"\n⏱️  Iniciando... {datetime.now().strftime('%H:%M:%S')}")

        # Ejecutar script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=not verbose,
            text=True,
            timeout=3600,  # 1 hora máximo por fase
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            print(f"✅ Fase {phase_num} completada en {elapsed/60:.1f} minutos")
            return True
        else:
            print(f"❌ Fase {phase_num} falló")
            if not verbose and result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ Fase {phase_num} excedió timeout (1 hora)")
        return False
    except Exception as e:
        print(f"❌ Error ejecutando fase {phase_num}: {e}")
        return False


def load_phase_reports() -> Dict[int, dict]:
    """Carga reportes de las fases ejecutadas."""
    reports = {}
    reports_dir = PROJECT_ROOT / "outputs" / "reports"

    phase_report_files = {
        0: "phase_0_validation_report.json",
        1: "phase_1_rebuild_stats.json",
        2: "phase_2_metadata_enrichment.json",
        3: "phase_3_retrieval_optimization.json",
    }

    for phase_num, filename in phase_report_files.items():
        file_path = reports_dir / filename
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    reports[phase_num] = json.load(f)
            except Exception as e:
                print(f"⚠️  No se pudo leer reporte de fase {phase_num}: {e}")

    return reports


def print_final_summary(executed_phases: list, reports: dict):
    """Imprime resumen final de la ejecución."""
    print(f"\n{'=' * 90}")
    print("📊 RESUMEN FINAL DE EJECUCIÓN")
    print(f"{'=' * 90}")

    print(f"\n✅ Fases ejecutadas: {executed_phases}")

    if 1 in reports:
        stats = reports[1].get("output", {})
        print(f"\n📈 ESTADÍSTICAS DE INDEXACIÓN:")
        print(f"   PDFs procesados: {stats.get('processed_pdfs', 0)}")
        print(f"   Chunks totales: {stats.get('total_chunks', 0)}")
        print(f"   Directorio del índice: {stats.get('index_directory', 'N/A')}")

    if 2 in reports:
        enrichment = reports[2].get("enrichment", {})
        metadata_stats = reports[2].get("metadata_statistics", {})
        print(f"\n📚 METADATOS:")
        print(f"   Chunks enriquecidos: {enrichment.get('total_chunks_enriched', 0)}")
        print(f"   Tasa de éxito: {enrichment.get('enrichment_rate', 0):.1f}%")
        print(f"   Completitud de metadatos: {metadata_stats.get('completeness_pct', 0):.1f}%")

    if 3 in reports:
        integrity = reports[3].get("integrity", {})
        test_results = reports[3].get("test_results", {})
        print(f"\n🔧 RETRIEVAL:")
        print(f"   Integridad del índice: {'✓ Válido' if integrity.get('is_valid', False) else '❌ Problemas'}")
        print(f"   Queries de prueba exitosas: {test_results.get('successful_queries', 0)}/{test_results.get('total_queries', 0)}")

    print(f"\n📁 ARCHIVOS GENERADOS:")
    print(f"   - Índice: outputs/rag_index_goc_full/")
    print(f"   - Reportes: outputs/reports/phase_*.json")
    print(f"   - Logs: outputs/logs/phase_*.log")

    print(f"\n💡 PRÓXIMOS PASOS:")
    print(f"   1. Validar calidad de resultados con tus propias queries")
    print(f"   2. Revisar reportes en outputs/reports/")
    print(f"   3. Usar el índice para consultas RAG")

    print(f"\n💻 EJEMPLO DE USO:")
    print(f"""
   from pipeline.rag.query_engine import RAGQueryEngine
   from pipeline.rag.vector_db import VectorDBManager

   # Cargar índice
   vector_db = VectorDBManager(
       index_dir="outputs/rag_index_goc_full",
       embedding_dim=384
   )
   vector_db.load()

   # Crear engine de queries
   query_engine = RAGQueryEngine(vector_db=vector_db, model="claude-haiku-4-5-20251001")

   # Hacer query
   result = query_engine.query("parámetros poblacionales del pargo rojo")
   print(result.answer)
    """)

    print(f"\n{'=' * 90}\n")


def main():
    print_header()

    args = parse_arguments()

    # Determinar fases a ejecutar
    phases_to_run = [p for p in PHASES.keys() if should_run_phase(p, args)]

    if not phases_to_run:
        print("❌ No hay fases para ejecutar")
        sys.exit(1)

    print(f"\n📋 PLAN DE EJECUCIÓN:")
    for phase_num in phases_to_run:
        phase_info = PHASES[phase_num]
        print(f"   [{phase_num}] {phase_info['name']}")

    if args.dry_run:
        print(f"\n🏃 Modo DRY-RUN: se mostrarán los pasos sin ejecutar")

    # Ejecutar fases
    executed_phases = []
    all_success = True

    for phase_num in phases_to_run:
        phase_info = PHASES[phase_num]

        success = run_phase(
            phase_num,
            phase_info,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if success:
            executed_phases.append(phase_num)
        else:
            all_success = False
            if args.phase is None:
                print(f"\n⚠️  Fase {phase_num} falló. Deteniéndose aquí.")
                break
            else:
                # Si ejecutamos una sola fase, no detenemos
                pass

    # Cargar y mostrar reportes
    print(f"\n📄 Cargando reportes...")
    reports = load_phase_reports()

    # Resumen final
    print_final_summary(executed_phases, reports)

    # Exit code
    if all_success:
        print("✅ RECONSTRUCCIÓN COMPLETADA EXITOSAMENTE")
        sys.exit(0)
    else:
        print("❌ LA RECONSTRUCCIÓN TUVO ERRORES")
        sys.exit(1)


if __name__ == "__main__":
    main()
