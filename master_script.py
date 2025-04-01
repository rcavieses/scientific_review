#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script maestro que ejecuta todo el flujo de trabajo para el análisis bibliométrico:
1. Búsqueda de artículos en bases de datos académicas
2. Integración de resultados
3. Análisis de dominios
4. Clasificación de artículos con Anthropic Claude
5. Generación de análisis y visualizaciones
6. Creación de informe en Markdown/PDF

Este script coordina todo el proceso y permite ejecutarlo de manera secuencial,
con opciones para omitir pasos ya completados o enfocarse en fases específicas.
"""

import os
import sys
import time
import argparse
import subprocess
from datetime import datetime


def check_prerequisites():
    """Verifica que todos los scripts y dependencias necesarios estén presentes."""
    required_scripts = [
        "main_script.py",  # Script principal de búsqueda
        "analysis_generator.py",  # Generador de análisis y figuras
        "report_generator.py"     # Generador de informes
    ]
    
    missing = []
    for script in required_scripts:
        if not os.path.exists(script):
            missing.append(script)
    
    if missing:
        print(f"ERROR: Faltan los siguientes scripts necesarios: {', '.join(missing)}")
        print("Asegúrese de que todos los scripts requeridos estén en el directorio actual.")
        return False
    
    return True


def execute_command(cmd, desc):
    """
    Ejecuta un comando y maneja los posibles errores.
    
    Args:
        cmd: Lista con el comando a ejecutar
        desc: Descripción de la operación
        
    Returns:
        bool: True si la ejecución fue exitosa, False en caso contrario
    """
    print(f"\n===== EJECUTANDO: {desc} =====")
    print(f"Comando: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        start_time = time.time()
        process = subprocess.run(cmd, check=True)
        end_time = time.time()
        
        print(f"\nComando completado exitosamente en {end_time - start_time:.2f} segundos.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: El comando falló con código de salida {e.returncode}")
        return False
    except Exception as e:
        print(f"\nERROR: Ocurrió una excepción al ejecutar el comando: {str(e)}")
        return False


def run_search_phase(args):
    """Ejecuta la fase de búsqueda e integración de artículos."""
    # Determinar opciones para omitir pasos
    skip_options = []
    
    if args.skip_searches:
        skip_options.append("--skip-searches")
    if args.skip_integration:
        skip_options.append("--skip-integration")
    if args.skip_domain_analysis:
        skip_options.append("--skip-domain-analysis")
    if args.skip_classification:
        skip_options.append("--skip-classification")
    
    # Construir comando
    cmd = [
        sys.executable,
        "main_script.py",
        "--domain1", args.domain1,
        "--domain2", args.domain2,
        "--domain3", args.domain3,
        "--max-results", str(args.max_results),
        "--year-start", str(args.year_start)
    ]
    
    # Agregar opciones condicionales
    if args.year_end:
        cmd.extend(["--year-end", str(args.year_end)])
    if args.email:
        cmd.extend(["--email", args.email])
    
    # Agregar opciones para omitir pasos
    cmd.extend(skip_options)
    
    # Ejecutar búsqueda
    return execute_command(cmd, "Búsqueda e integración de artículos")


def run_analysis_phase(args):
    """Ejecuta la fase de análisis y generación de visualizaciones."""
    # Construir comando
    cmd = [
        sys.executable,
        "analysis_generator.py",
        "--classified-file", os.path.join("outputs", "classified_results.json"),
        "--abstracts-file", os.path.join("outputs", "integrated_abstracts.json"),
        "--domain-stats-file", os.path.join("outputs", "domain_statistics.csv"),
        "--figures-dir", args.figures_dir
    ]
    
    # Ejecutar análisis
    return execute_command(cmd, "Análisis y generación de visualizaciones")


def run_report_phase(args):
    """Ejecuta la fase de generación de informes."""
    # Construir comando
    cmd = [
        sys.executable,
        "report_generator.py",
        "--stats-file", os.path.join(args.figures_dir, "statistics.json"),
        "--figures-dir", args.figures_dir,
        "--output-file", args.report_file
    ]
    
    # Agregar opción para PDF si se solicita
    if args.generate_pdf:
        cmd.append("--convert-to-pdf")
        if args.pandoc_path:
            cmd.extend(["--pandoc-path", args.pandoc_path])
    
    # Ejecutar generación de informe
    return execute_command(cmd, "Generación de informe")


def main():
    """Función principal que coordina todo el proceso."""
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description='Ejecuta el flujo de trabajo completo para análisis bibliométrico.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # Grupos de argumentos para mejor organización
    search_group = parser.add_argument_group('Opciones de búsqueda')
    search_group.add_argument('--domain1', type=str, default='Domain1.csv',
                        help='Archivo CSV con términos del primer dominio (default: Domain1.csv)')
    search_group.add_argument('--domain2', type=str, default='Domain2.csv',
                        help='Archivo CSV con términos del segundo dominio (default: Domain2.csv)')
    search_group.add_argument('--domain3', type=str, default='Domain3.csv',
                        help='Archivo CSV con términos del tercer dominio (default: Domain3.csv)')
    search_group.add_argument('--max-results', type=int, default=100,
                        help='Número máximo de resultados por fuente (default: 100)')
    search_group.add_argument('--year-start', type=int, default=2008,
                        help='Año inicial para filtrar resultados (default: 2008)')
    search_group.add_argument('--year-end', type=int, default=None,
                        help='Año final para filtrar resultados (default: None)')
    search_group.add_argument('--email', type=str, default=None,
                        help='Email para API de Crossref (default: None)')
    
    output_group = parser.add_argument_group('Opciones de salida')
    output_group.add_argument('--figures-dir', type=str, default='figures',
                        help='Carpeta donde guardar/buscar las figuras (default: figures)')
    output_group.add_argument('--report-file', type=str, default='report.md',
                        help='Nombre del archivo de informe (default: report.md)')
    output_group.add_argument('--generate-pdf', action='store_true',
                        help='Generar versión PDF del informe usando Pandoc')
    output_group.add_argument('--pandoc-path', type=str, default=None,
                        help='Ruta al ejecutable de Pandoc (opcional)')
    
    flow_group = parser.add_argument_group('Control de flujo de trabajo')
    flow_group.add_argument('--skip-searches', action='store_true',
                        help='Omitir la ejecución de búsquedas')
    flow_group.add_argument('--skip-integration', action='store_true',
                        help='Omitir la integración de resultados')
    flow_group.add_argument('--skip-domain-analysis', action='store_true',
                        help='Omitir el análisis de dominios')
    flow_group.add_argument('--skip-classification', action='store_true',
                        help='Omitir la clasificación con Claude')
    flow_group.add_argument('--only-search', action='store_true',
                        help='Ejecutar solo la fase de búsqueda')
    flow_group.add_argument('--only-analysis', action='store_true',
                        help='Ejecutar solo la fase de análisis')
    flow_group.add_argument('--only-report', action='store_true',
                        help='Ejecutar solo la fase de informe')
    
    args = parser.parse_args()
    
    # Verificar prerrequisitos
    if not check_prerequisites():
        sys.exit(1)
    
    # Registrar inicio del proceso
    start_time = time.time()
    print(f"\n====== INICIANDO FLUJO DE TRABAJO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ======\n")
    
    # Determinar qué fases ejecutar
    run_search = not (args.only_analysis or args.only_report)
    run_analysis = not (args.only_search or args.only_report)
    run_report = not (args.only_search or args.only_analysis)
    
    # Si no se especificó ninguna restricción, ejecutar todo
    if not (run_search or run_analysis or run_report):
        run_search = run_analysis = run_report = True
    
    # Ejecutar fases según lo indicado
    success = True
    
    if run_search:
        print("\n----- FASE 1: BÚSQUEDA E INTEGRACIÓN DE ARTÍCULOS -----\n")
        success = run_search_phase(args)
        if not success and not args.skip_searches:
            print("ERROR: La fase de búsqueda falló. Deteniendo el proceso.")
            sys.exit(1)
    
    if run_analysis and success:
        print("\n----- FASE 2: ANÁLISIS Y VISUALIZACIONES -----\n")
        success = run_analysis_phase(args)
        if not success:
            print("ERROR: La fase de análisis falló. Deteniendo el proceso.")
            sys.exit(1)
    
    if run_report and success:
        print("\n----- FASE 3: GENERACIÓN DE INFORMES -----\n")
        success = run_report_phase(args)
        if not success:
            print("ERROR: La fase de informes falló.")
            sys.exit(1)
    
    # Registrar fin del proceso
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n====== PROCESO COMPLETADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ======")
    print(f"Tiempo total de ejecución: {total_time:.2f} segundos ({total_time/60:.2f} minutos)")
    
    # Mostrar resumen de archivos generados
    if os.path.exists("outputs"):
        output_files = os.listdir("outputs")
        print(f"\nArchivos generados en 'outputs': {len(output_files)}")
    
    if os.path.exists(args.figures_dir):
        figure_files = os.listdir(args.figures_dir)
        print(f"Figuras generadas en '{args.figures_dir}': {len(figure_files)}")
    
    if os.path.exists(args.report_file):
        report_size = os.path.getsize(args.report_file) / 1024  # KB
        print(f"Informe generado: {args.report_file} ({report_size:.1f} KB)")
    
    if args.generate_pdf and os.path.exists(args.report_file.replace(".md", ".pdf")):
        pdf_file = args.report_file.replace(".md", ".pdf")
        pdf_size = os.path.getsize(pdf_file) / 1024  # KB
        print(f"PDF generado: {pdf_file} ({pdf_size:.1f} KB)")
    
    print("\n¡Proceso completado con éxito!")


if __name__ == "__main__":
    main()