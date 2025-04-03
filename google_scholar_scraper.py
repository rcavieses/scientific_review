#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script mejorado para realizar búsquedas en Google Scholar basado en los tres dominios de búsqueda.
Utiliza la biblioteca scholarly para interactuar con Google Scholar y extraer
títulos y autores de artículos académicos, guardando los resultados en formato JSON.

Este script implementa retrasos aleatorios, rotación de proxies para evitar
ser bloqueado por Google durante el scraping, y ahora incluye extracción de DOI.
"""

import os
import json
import time
import random
import requests
import argparse
import re
import logging
from typing import List, Dict, Any, Optional
from scholarly import scholarly, ProxyGenerator
import csv
import traceback

# Importar tqdm para barra de progreso
from tqdm import tqdm

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_scholar.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_domain_terms_from_csv(filepath: str) -> List[str]:
    """
    Carga términos de dominio desde un archivo CSV.
    """
    terms = []
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and row[0].strip():  # Verificar que no sea una fila vacía
                    terms.append(row[0].strip())
            
        logger.info(f"Se cargaron {len(terms)} términos desde {filepath}")
        return terms
    except Exception as e:
        logger.error(f"Error al cargar términos desde {filepath}: {str(e)}")
        return []

def construct_search_query(domain_terms_list: List[List[str]], num_terms_per_domain: int = 2) -> str:
    """
    Construye una query para Google Scholar a partir de los términos de dominio.
    """
    all_terms = []
    
    for domain_terms in domain_terms_list:
        if domain_terms:
            # Tomamos hasta 2 términos de cada dominio para no sobrecargar la consulta
            all_terms.extend(domain_terms[:2])
    
    # Unir todos los términos seleccionados con AND
    return " ".join(all_terms)

def setup_scholarly(use_proxy: bool = True) -> None:
    """
    Configura scholarly para usar proxies y evitar bloqueos.
    """
    if use_proxy:
        # Configurar generador de proxies
        pg = ProxyGenerator()
        
        try:
            logger.info("Intentando configurar con proxies gratuitos...")
            proxy_success = pg.FreeProxies()
            
            if proxy_success:
                logger.info("Proxy gratuito configurado correctamente")
            else:
                logger.warning("No se pudo configurar proxies gratuitos")
            
            scholarly.use_proxy(pg)
            
        except Exception as e:
            logger.error(f"Error configurando proxies: {str(e)}")
    
    scholarly.set_timeout(5)

def search_google_scholar(
    search_query: str, 
    max_results: int = 50, 
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    max_retry: int = 3,
    max_total_errors: int = 3,
    max_search_time: int = 120
) -> List[Dict[Any, Any]]:
    """
    Realiza búsquedas en Google Scholar para extraer información de artículos con barra de progreso.
    """
    results = []
    start_time = time.time()
    total_errors = 0
    
    # Configurar barra de progreso
    progress_bar = tqdm(
        total=max_results, 
        desc="Buscando artículos", 
        unit="artículo",
        dynamic_ncols=True,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
    )
    
    retry_count = 0
    while retry_count < max_retry:
        try:
            logger.info(f"Iniciando búsqueda en Google Scholar (intento {retry_count + 1}/{max_retry}): {search_query}")
            
            search_query_gen = scholarly.search_pubs(search_query)
            
            consecutive_errors = 0
            
            for i in range(max_results):
                # Verificar tiempo total de búsqueda
                if time.time() - start_time > max_search_time:
                    logger.warning(f"Se alcanzó el límite de tiempo de búsqueda ({max_search_time} segundos)")
                    progress_bar.close()
                    return results
                
                try:
                    pub = next(search_query_gen)
                    consecutive_errors = 0
                    
                    # Verificar que haya datos básicos
                    if not pub or not pub.get('bib'):
                        progress_bar.set_description("Resultado sin datos")
                        progress_bar.update(0)
                        continue
                    
                    # Filtrar por año si es necesario
                    year = pub.get('bib', {}).get('pub_year')
                    if year:
                        try:
                            year = int(year)
                            if (year_start and year < year_start) or (year_end and year > year_end):
                                progress_bar.set_description(f"Año {year} fuera de rango")
                                continue
                        except (ValueError, TypeError):
                            pass
                    
                    # Extraer datos relevantes
                    title = pub.get('bib', {}).get('title', 'Título no disponible')
                    
                    # Actualizar barra de progreso
                    progress_bar.set_description(f"Procesando: {title[:50]}...")
                    
                    # Manejar autores
                    authors_data = pub.get('bib', {}).get('author', [])
                    authors = []
                    if isinstance(authors_data, list):
                        authors = [str(author) for author in authors_data if author]
                    elif isinstance(authors_data, str):
                        authors = [author.strip() for author in authors_data.split(",") if author.strip()]
                    
                    # Crear objeto de resultado
                    article_data = {
                        "title": title,
                        "authors": authors,
                        "year": year,
                        "journal": pub.get('bib', {}).get('venue', 'Fuente no disponible'),
                        "abstract": pub.get('bib', {}).get('abstract', ''),
                        "url": pub.get('pub_url', pub.get('url_scholarbib', '')),
                        "citations": pub.get('num_citations', 0),
                        "source": "Google Scholar"
                    }
                    
                    results.append(article_data)
                    
                    # Actualizar barra de progreso
                    progress_bar.update(1)
                    
                    # Introducir retraso aleatorio para evitar bloqueos
                    time.sleep(random.uniform(1.0, 3.0))
                    
                    # Verificar si hemos alcanzado el número máximo de resultados
                    if len(results) >= max_results:
                        progress_bar.close()
                        return results
                
                except StopIteration:
                    logger.info("No hay más resultados disponibles")
                    progress_bar.close()
                    return results
                
                except Exception as e:
                    logger.error(f"Error al procesar un resultado: {str(e)}")
                    consecutive_errors += 1
                    total_errors += 1
                    
                    # Actualizar barra de progreso con estado de error
                    progress_bar.set_description(f"Error: {str(e)}")
                    
                    # Verificar límite de errores
                    if total_errors >= max_total_errors:
                        logger.error(f"Se alcanzó el límite de errores totales ({max_total_errors})")
                        progress_bar.close()
                        return results
                    
                    # Esperar y reintentar
                    time.sleep(random.uniform(3.0, 7.0))
            
            # Salir del bucle de reintentos
            break
            
        except Exception as e:
            retry_count += 1
            total_errors += 1
            
            logger.error(f"Error en la búsqueda: {str(e)}")
            
            if retry_count >= max_retry or total_errors >= max_total_errors:
                logger.error("Se agotaron los reintentos o se alcanzó el límite de errores")
                if progress_bar:
                    progress_bar.close()
                return results
            
            # Esperar antes de reintentar
            time.sleep(random.uniform(5.0, 10.0))
    
    # Cerrar barra de progreso
    if progress_bar:
        progress_bar.close()
    
    return results

def run_google_scholar_search(
    domain1_terms: List[str],
    domain2_terms: List[str],
    domain3_terms: Optional[List[str]] = None,
    output_file: str = "outputs/google_scholar_results.json",
    integrated_results_file: str = "outputs/integrated_results.json",
    max_results: int = 50,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    use_proxy: bool = False,
    always_integrate: bool = True
) -> None:
    """
    Función principal que ejecuta la búsqueda en Google Scholar con barra de progreso.
    """
    try:
        # Configurar scholarly
        setup_scholarly(use_proxy)
        
        # Preparar lista de dominios
        domain_terms_list = [domain1_terms, domain2_terms]
        if domain3_terms:
            domain_terms_list.append(domain3_terms)
        
        # Construir la query de búsqueda
        search_query = construct_search_query(domain_terms_list)
        
        logger.info(f"Query de búsqueda: {search_query}")
        logger.info(f"Buscando un máximo de {max_results} resultados...")
        
        # Realizar la búsqueda
        results = search_google_scholar(
            search_query=search_query,
            max_results=max_results,
            year_start=year_start,
            year_end=year_end
        )
        
        # Asegurar que el directorio de salida exista
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        
        # Guardar resultados
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        
        logger.info(f"Búsqueda completada. Se encontraron {len(results)} resultados.")
        
    except Exception as e:
        logger.error(f"Error durante la búsqueda en Google Scholar: {str(e)}")
        traceback.print_exc()

# Punto de entrada para ejecución directa
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Herramienta de búsqueda en Google Scholar")
    
    # Argumentos para búsqueda
    parser.add_argument("--domain1", type=str, default="Domain1.csv",
                        help="Archivo CSV con términos del primer dominio")
    parser.add_argument("--domain2", type=str, default="Domain2.csv",
                        help="Archivo CSV con términos del segundo dominio")
    parser.add_argument("--domain3", type=str, default="Domain3.csv",
                        help="Archivo CSV con términos del tercer dominio")
    parser.add_argument("--output", type=str, default="outputs/google_scholar_results.json",
                        help="Archivo donde guardar los resultados")
    parser.add_argument("--max-results", type=int, default=50,
                        help="Número máximo de resultados a extraer")
    parser.add_argument("--year-start", type=int, default=None,
                        help="Año inicial para filtrar resultados")
    parser.add_argument("--year-end", type=int, default=None,
                        help="Año final para filtrar resultados")
    parser.add_argument("--use-proxy", action="store_true",
                        help="Utilizar proxies para las solicitudes")
    
    args = parser.parse_args()
    
    # Cargar términos de cada dominio
    domain1_terms = load_domain_terms_from_csv(args.domain1)
    domain2_terms = load_domain_terms_from_csv(args.domain2)
    domain3_terms = load_domain_terms_from_csv(args.domain3) if os.path.exists(args.domain3) else None
    
    # Ejecutar la búsqueda
    run_google_scholar_search(
        domain1_terms=domain1_terms,
        domain2_terms=domain2_terms,
        domain3_terms=domain3_terms,
        output_file=args.output,
        max_results=args.max_results,
        year_start=args.year_start,
        year_end=args.year_end,
        use_proxy=args.use_proxy
    )