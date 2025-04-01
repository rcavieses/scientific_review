#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script principal que integra todo el flujo de trabajo para buscar artículos académicos,
integrar resultados y clasificarlos usando Anthropic Claude.

Este script:
1. Carga términos de dominio desde archivos CSV
2. Ejecuta búsquedas en Crossref, Science Direct y Semantic Scholar
3. Integra los resultados
4. Analiza los dominios
5. Clasifica los artículos usando Anthropic Claude
"""

import os
import csv
import sys
import time
import argparse
from typing import List, Dict, Any, Optional, Tuple

# Importar los módulos de búsqueda, integración y análisis
from crossref_search import run_crossref_search
from science_direct_search import run_science_direct_search
from semantic_scholar_search import run_semantic_scholar_search
from integrated_search import integrate_search_results
from domain_analysis import run_domain_analysis
from nlp_classifier_anthropic import classify_articles
import argparse

# Verificar que los scripts de módulo existen antes de importarlos
required_scripts = [
    "crossref_search.py",
    "science_direct_search.py",
    "semantic_scholar_search.py",
    "integrated_search.py",
    "domain_analysis.py",
    "nlp_classifier_anthropic.py",
    "google_scholar_scraper.py"  # Add this line
]

def check_required_files(files_list: List[str]) -> None:
    """
    Verifica que todos los archivos requeridos existan.
    
    Args:
        files_list: Lista de nombres de archivos a verificar.
    """
    missing_files = []
    for file in files_list:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"ERROR: Los siguientes archivos requeridos no se encontraron: {', '.join(missing_files)}")
        sys.exit(1)


def load_domain_terms_from_csv(filepath: str) -> List[str]:
    """
    Carga términos de dominio desde un archivo CSV.
    
    Args:
        filepath: Ruta al archivo CSV con los términos.
        
    Returns:
        Lista de términos cargados.
    """
    terms = []
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0].strip():  # Verificar que no sea una fila vacía
                    terms.append(row[0].strip())
            
        print(f"Se cargaron {len(terms)} términos desde {filepath}")
        return terms
    except Exception as e:
        print(f"Error al cargar términos desde {filepath}: {str(e)}")
        return []


def create_output_directory() -> None:
    """
    Crea la carpeta de outputs si no existe.
    """
    os.makedirs("outputs", exist_ok=True)
    print("Se verificó la carpeta de outputs.")


def run_search_pipeline(
    domain1_terms: List[str],
    domain2_terms: List[str],
    domain3_terms: Optional[List[str]] = None,
    domain_names: Optional[List[str]] = None,
    max_results: int = 100,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    email: Optional[str] = None,
    sciencedirect_apikey_file: str = "secrets/sciencedirect_apikey.txt",
    anthropic_apikey_file: str = "secrets/anthropic-apikey",
    questions_file: str = "questions.json",
    sequential_classification: bool = True,
    skip_searches: bool = False,
    skip_integration: bool = False,
    skip_domain_analysis: bool = False,
    skip_classification: bool = False,
    skip_google_scholar: bool = False
) -> None:
    """
    Ejecuta el pipeline completo de búsqueda, integración, análisis y clasificación.
    
    Args:
        domain1_terms: Lista de términos del primer dominio.
        domain2_terms: Lista de términos del segundo dominio.
        domain3_terms: Lista de términos del tercer dominio (opcional).
        domain_names: Nombres de los dominios para el análisis.
        max_results: Número máximo de resultados a buscar en cada fuente.
        year_start: Año inicial para filtrar resultados.
        year_end: Año final para filtrar resultados.
        email: Email para identificarse con Crossref.
        sciencedirect_apikey_file: Archivo con la API key de Science Direct.
        anthropic_apikey_file: Archivo con la API key de Anthropic.
        questions_file: Archivo con las preguntas para la clasificación.
        sequential_classification: Si es True, clasifica artículos secuencialmente.
        skip_searches: Si es True, omite la ejecución de las búsquedas.
        skip_integration: Si es True, omite la integración de resultados.
        skip_domain_analysis: Si es True, omite el análisis de dominios.
        skip_classification: Si es True, omite la clasificación con Claude.
        skip_google_scholar: Si es True, omite la búsqueda en Google Scholar.
    """
    start_time = time.time()
    
    # 1. Crear archivos de salida
    create_output_directory()
    
    # 2. Ejecutar búsquedas en las tres fuentes
    if not skip_searches:
        print("\n====== INICIANDO BÚSQUEDAS EN FUENTES ACADÉMICAS ======\n")
        
        # 2.1 Crossref
        print("\n----- Búsqueda en Crossref -----\n")
        run_crossref_search(
            domain1_terms=domain1_terms,
            domain2_terms=domain2_terms,
            domain3_terms=domain3_terms,
            results_file="crossref_results.json",
            abstracts_file="crossref_abstracts.json",
            max_results=max_results,
            email=email,
            year_start=year_start,
            year_end=year_end
        )
        
        # 2.2 Science Direct (si existe el archivo de API key)
        if os.path.exists(sciencedirect_apikey_file):
            print("\n----- Búsqueda en Science Direct -----\n")
            run_science_direct_search(
                domain1_terms=domain1_terms,
                domain2_terms=domain2_terms,
                domain3_terms=domain3_terms,
                apikey_file=sciencedirect_apikey_file,
                results_file="sciencedirect_results.json",
                abstracts_file="sciencedirect_abstracts.json",
                max_results=max_results,
                fetch_details=True,
                year_range=(year_start, year_end) if year_start or year_end else None
            )
        else:
            print(f"\nArchivo de API key de Science Direct no encontrado ({sciencedirect_apikey_file}).")
            print("Se omitirá la búsqueda en Science Direct.")
        
        # 2.3 Semantic Scholar
        print("\n----- Búsqueda en Semantic Scholar -----\n")
        run_semantic_scholar_search(
            domain1_terms=domain1_terms,
            domain2_terms=domain2_terms,
            domain3_terms=domain3_terms,
            results_file="semanticscholar_results.json",
            abstracts_file="semanticscholar_abstracts.json",
            max_results=max_results,
            year_start=year_start,
            year_end=year_end
        )

        # 2.4 Google Scholar
        if not skip_searches and not skip_google_scholar:
            print("\n----- Búsqueda en Google Scholar -----\n")
            try:
                from google_scholar_scraper import run_google_scholar_search
                run_google_scholar_search(
                    domain1_terms=domain1_terms,
                    domain2_terms=domain2_terms,
                    domain3_terms=domain3_terms,
                    output_file="google_scholar_results.json",  # Fix path
                    integrated_results_file=None,
                    max_results=max_results,
                    year_start=year_start,
                    year_end=year_end,
                    always_integrate=False,
                    use_proxy=True  # Add proxy parameter
                )
            except Exception as e:
                print(f"ERROR: No se pudo ejecutar la búsqueda en Google Scholar: {str(e)}")
                print("Se continuará con el resto del proceso.")
    else:
        print("\nSe omitió la ejecución de búsquedas por indicación del usuario.")
    
    # 3. Integrar resultados
    if not skip_integration:
        print("\n====== INICIANDO INTEGRACIÓN DE RESULTADOS ======\n")
        integrate_search_results(
            sciencedirect_results="outputs/sciencedirect_results.json",
            crossref_results="outputs/crossref_results.json",
            semanticscholar_results="outputs/semanticscholar_results.json",
            google_scholar_results="outputs/google_scholar_results.json" if not skip_google_scholar else None,
            sciencedirect_abstracts="outputs/sciencedirect_abstracts.json",
            crossref_abstracts="outputs/crossref_abstracts.json",
            semanticscholar_abstracts="outputs/semanticscholar_abstracts.json",
            output_results="outputs/integrated_results.json",
            output_abstracts="outputs/integrated_abstracts.json"
        )
    else:
        print("\nSe omitió la integración de resultados por indicación del usuario.")

    
    # 4. Analizar dominios
    if not skip_searches and not skip_google_scholar:
        print("\n----- Búsqueda en Google Scholar -----\n")
        try:
            from google_scholar_scraper import run_google_scholar_search
            run_google_scholar_search(
                domain1_terms=domain1_terms,
                domain2_terms=domain2_terms,
                domain3_terms=domain3_terms,
                output_file="outputs/google_scholar_results.json",
                integrated_results_file=None,  # No integrar aquí, lo haremos después con todas las fuentes
                max_results=max_results,
                year_start=year_start,
                year_end=year_end,
                always_integrate=False,  # No integrar dentro de la función, sino después con el resto
                use_proxy=True
            )
        except Exception as e:
            print(f"ERROR: No se pudo ejecutar la búsqueda en Google Scholar: {str(e)}")
            print("Se continuará con el resto del proceso.")
        
    # 5. Clasificar con Anthropic Claude
    if not skip_classification:
        print("\n====== INICIANDO CLASIFICACIÓN CON ANTHROPIC CLAUDE ======\n")
        
        # Verificar que existe el archivo de API key de Anthropic
        if not os.path.exists(anthropic_apikey_file):
            print(f"ERROR: No se encontró el archivo de API key de Anthropic ({anthropic_apikey_file}).")
            print("La clasificación no puede continuar sin la API key.")
            return
        
        # Verificar que existe el archivo de preguntas
        if not os.path.exists(questions_file):
            print(f"ERROR: No se encontró el archivo de preguntas ({questions_file}).")
            print("La clasificación no puede continuar sin las preguntas.")
            return
        
        # Ejecutar clasificación
        success, summary = classify_articles(
            input_file="outputs/domain_analyzed_results.json",
            questions_file=questions_file,
            output_file="outputs/classified_results.json",
            api_key_file=anthropic_apikey_file,
            batch_size=5,
            sequential=sequential_classification
        )
        
        if not success:
            print(f"ERROR durante la clasificación: {summary.get('error', 'Error desconocido')}")
    else:
        print("\nSe omitió la clasificación con Anthropic Claude por indicación del usuario.")
    
    # Finalización
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n====== PIPELINE COMPLETADO ======")
    print(f"Tiempo total de ejecución: {total_time:.2f} segundos ({total_time/60:.2f} minutos)")
    print(f"Todos los resultados se guardaron en la carpeta 'outputs'")


def main():
    """
    Función principal que parsea argumentos y ejecuta el pipeline.
    """
    # Configurar parser de argumentos
    parser = argparse.ArgumentParser(description='Script principal para búsqueda académica y clasificación')
    
    # Argumentos para archivos de dominio
    parser.add_argument('--domain1', type=str, default='Domain1.csv',
                        help='Archivo CSV con términos del primer dominio (default: Domain1.csv)')
    parser.add_argument('--domain2', type=str, default='Domain2.csv',
                        help='Archivo CSV con términos del segundo dominio (default: Domain2.csv)')
    parser.add_argument('--domain3', type=str, default='Domain3.csv',
                        help='Archivo CSV con términos del tercer dominio (default: Domain3.csv)')
    
    # Nombres de dominio
    parser.add_argument('--domain1-name', type=str, default='IA',
                        help='Nombre del primer dominio (default: IA)')
    parser.add_argument('--domain2-name', type=str, default='Pronóstico',
                        help='Nombre del segundo dominio (default: Pronóstico)')
    parser.add_argument('--domain3-name', type=str, default='Pesquerías',
                        help='Nombre del tercer dominio (default: Pesquerías)')
    
    # Filtros de búsqueda
    parser.add_argument('--max-results', type=int, default=100,
                        help='Número máximo de resultados por fuente (default: 100)')
    parser.add_argument('--year-start', type=int, default=2008,
                        help='Año inicial para filtrar resultados (default: 2008)')
    parser.add_argument('--year-end', type=int, default=None,
                        help='Año final para filtrar resultados (default: None)')
    
    # Configuración de APIs
    parser.add_argument('--email', type=str, default=None,
                        help='Email para API de Crossref (default: None)')
    parser.add_argument('--science-direct-key', type=str, default='sciencedirect_apikey.txt',
                        help='Archivo con API key de Science Direct (default: sciencedirect_apikey.txt)')
    parser.add_argument('--anthropic-key', type=str, default='anthropic-apikey',
                        help='Archivo con API key de Anthropic (default: anthropic-apikey)')
    parser.add_argument('--questions', type=str, default='questions.json',
                        help='Archivo JSON con preguntas para clasificación (default: questions.json)')
    
    # Opciones de control de flujo
    parser.add_argument('--skip-searches', action='store_true',
                        help='Omitir la ejecución de búsquedas')
    parser.add_argument('--skip-integration', action='store_true',
                        help='Omitir la integración de resultados')
    parser.add_argument('--skip-domain-analysis', action='store_true',
                        help='Omitir el análisis de dominios')
    parser.add_argument('--skip-classification', action='store_true',
                        help='Omitir la clasificación con Claude')
    parser.add_argument('--parallel-classification', action='store_true',
                        help='Usar clasificación en paralelo en lugar de secuencial')
    parser.add_argument('--skip-google-scholar', action='store_true',
                        help='Omitir la búsqueda en Google Scholar')
    
    # Parsear argumentos
    args = parser.parse_args()
    
    # Verificar archivos requeridos
    check_required_files(required_scripts)
    
    # Cargar términos de dominio desde archivos CSV
    domain1_terms = load_domain_terms_from_csv(args.domain1)
    domain2_terms = load_domain_terms_from_csv(args.domain2)
    domain3_terms = load_domain_terms_from_csv(args.domain3) if os.path.exists(args.domain3) else None
    
    # Verificar que tenemos suficientes términos
    if not domain1_terms or not domain2_terms:
        print("ERROR: Se requiere al menos un término en los dominios 1 y 2.")
        sys.exit(1)
    
    # Configurar nombres de dominio
    domain_names = [args.domain1_name, args.domain2_name]
    if domain3_terms:
        domain_names.append(args.domain3_name)
    
    # Mostrar configuración
    print("\n=== CONFIGURACIÓN ===")
    print(f"Dominio 1 ({args.domain1_name}): {len(domain1_terms)} términos")
    print(f"Dominio 2 ({args.domain2_name}): {len(domain2_terms)} términos")
    if domain3_terms:
        print(f"Dominio 3 ({args.domain3_name}): {len(domain3_terms)} términos")
    print(f"Años: {args.year_start}-{args.year_end if args.year_end else 'presente'}")
    print(f"Máx. resultados por fuente: {args.max_results}")
    print(f"Clasificación: {'paralela' if args.parallel_classification else 'secuencial'}")
    print("===================\n")
    
    # Ejecutar pipeline
    run_search_pipeline(
        domain1_terms=domain1_terms,
        domain2_terms=domain2_terms,
        domain3_terms=domain3_terms,
        domain_names=domain_names,
        max_results=args.max_results,
        year_start=args.year_start,
        year_end=args.year_end,
        email=args.email,
        sciencedirect_apikey_file=args.science_direct_key,
        anthropic_apikey_file=args.anthropic_key,
        questions_file=args.questions,
        sequential_classification=not args.parallel_classification,
        skip_searches=args.skip_searches,
        skip_integration=args.skip_integration,
        skip_domain_analysis=args.skip_domain_analysis,
        skip_classification=args.skip_classification,
        skip_google_scholar=args.skip_google_scholar
    )


if __name__ == "__main__":
    main()