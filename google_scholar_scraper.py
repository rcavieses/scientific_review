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
import argparse
import re
from typing import List, Dict, Any, Optional
from scholarly import scholarly, ProxyGenerator
import csv
import logging
import traceback

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
            
        logger.info(f"Se cargaron {len(terms)} términos desde {filepath}")
        return terms
    except Exception as e:
        logger.error(f"Error al cargar términos desde {filepath}: {str(e)}")
        return []


def construct_search_query(domain_terms_list: List[List[str]], num_terms_per_domain: int = 2) -> str:
    """
    Construye una query para Google Scholar a partir de los términos de dominio.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        num_terms_per_domain: Número máximo de términos a usar por dominio para evitar queries muy largas.
        
    Returns:
        Query estructurada para Google Scholar.
    """
    domain_queries = []
    
    for domain_terms in domain_terms_list:
        if domain_terms:  # Solo procesamos dominios con términos
            # Limitar el número de términos por dominio para evitar queries muy largas
            limited_terms = domain_terms[:num_terms_per_domain]
            
            # Formatear los términos del dominio actual
            domain_query = " OR ".join([f'"{term}"' for term in limited_terms])
            domain_queries.append(f"({domain_query})")
    
    # Construir la query completa uniendo todos los dominios con AND
    full_query = " AND ".join(domain_queries)
    
    return full_query


def setup_scholarly(use_proxy: bool = True) -> None:
    """
    Configura scholarly para usar proxies y evitar bloqueos.
    
    Args:
        use_proxy: Si es True, utiliza proxies para las solicitudes.
    """
    if use_proxy:
        # Configurar generador de proxies
        pg = ProxyGenerator()
        
        # Intentar diferentes métodos de configuración de proxy
        try:
            # Método 1: Usar proxies gratuitos
            logger.info("Intentando configurar con proxies gratuitos...")
            proxy_success = pg.FreeProxies()
            
            if proxy_success:
                logger.info("Proxy gratuito configurado correctamente")
            else:
                # Método alternativo: Intentar usar un proxy de rotación de IPs
                logger.warning("No se pudo configurar FreeProxies, intentando con proxy local...")
                proxy_success = pg.LocalProxy()
                
                if not proxy_success:
                    logger.warning("No se pudieron configurar proxies, usando configuración predeterminada")
            
            # Aplicar el generador de proxies a scholarly
            scholarly.use_proxy(pg)
            
        except Exception as e:
            logger.error(f"Error configurando proxies: {str(e)}. Usando configuración predeterminada.")
    
    # Configurar scholarly para comportarse como un navegador
    scholarly.set_timeout(5)


def random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    """
    Introduce un retraso aleatorio para simular comportamiento humano.
    
    Args:
        min_seconds: Tiempo mínimo de espera en segundos.
        max_seconds: Tiempo máximo de espera en segundos.
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def extract_doi_from_text(text: str) -> Optional[str]:
    """
    Intenta extraer un DOI de un texto o URL.
    
    Args:
        text: El texto donde buscar el DOI.
        
    Returns:
        El DOI encontrado o None si no se encuentra.
    """
    if not text:
        return None
        
    # Patrones comunes de DOI
    doi_patterns = [
        r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',  # Patrón general de DOI
        r'doi\.org/10\.\d{4,9}/[-._;()/:A-Z0-9]+',  # DOI en URL
        r'doi:10\.\d{4,9}/[-._;()/:A-Z0-9]+'  # DOI con prefijo doi:
    ]
    
    for pattern in doi_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doi = match.group(0)
            # Limpiar el prefijo si existe
            if doi.lower().startswith('doi.org/'):
                doi = doi[8:]
            elif doi.lower().startswith('doi:'):
                doi = doi[4:]
            return doi
    
    return None


def clean_text(text: str) -> str:
    """
    Limpia el texto para eliminar caracteres no deseados.
    
    Args:
        text: Texto a limpiar.
        
    Returns:
        Texto limpio.
    """
    if not text:
        return ""
    
    # Eliminar caracteres de control
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    # Reemplazar múltiples espacios por uno solo
    text = re.sub(r'\s+', ' ', text)
    # Eliminar espacios al inicio y al final
    return text.strip()


def search_google_scholar(
    search_query: str, 
    max_results: int = 50, 
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    max_retry: int = 3
) -> List[Dict[Any, Any]]:
    """
    Realiza búsquedas en Google Scholar para extraer información de artículos.
    
    Args:
        search_query: Consulta de búsqueda para Google Scholar.
        max_results: Número máximo de resultados a extraer.
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
        max_retry: Número máximo de reintentos en caso de error.
        
    Returns:
        Lista de resultados con información de artículos.
    """
    results = []
    
    # Intentar la búsqueda con reintentos
    retry_count = 0
    while retry_count < max_retry:
        try:
            logger.info(f"Iniciando búsqueda en Google Scholar (intento {retry_count + 1}/{max_retry}): {search_query}")
            
            # Crear el generador de búsqueda de publicaciones
            search_query_gen = scholarly.search_pubs(search_query)
            
            count = 0
            consecutive_errors = 0
            
            for i in range(max_results):
                try:
                    # Recuperar el siguiente resultado
                    pub = next(search_query_gen)
                    consecutive_errors = 0  # Resetear contador de errores
                    
                    # Verificar que haya datos básicos
                    if not pub or not pub.get('bib'):
                        logger.warning("Resultado sin datos básicos, saltando...")
                        continue
                    
                    # Filtrar por año si es necesario
                    year = pub.get('bib', {}).get('pub_year')
                    if year:
                        try:
                            year = int(year)
                            if (year_start and year < year_start) or (year_end and year > year_end):
                                continue
                        except (ValueError, TypeError):
                            # Si el año no se puede convertir a entero, lo incluimos de todos modos
                            pass
                    
                    # Extraer datos relevantes
                    title = clean_text(pub.get('bib', {}).get('title', 'Título no disponible'))
                    
                    # Manejar autores: pueden venir como lista o como string
                    authors_data = pub.get('bib', {}).get('author', [])
                    if isinstance(authors_data, list):
                        authors = [clean_text(author) for author in authors_data if author]
                    elif isinstance(authors_data, str):
                        # Si ya es un string, dividirlo por comas y limpiar
                        authors = [clean_text(author) for author in authors_data.split(",") if author.strip()]
                    else:
                        authors = []
                    
                    # Extraer más información
                    venue = clean_text(pub.get('bib', {}).get('venue', 'Fuente no disponible'))
                    abstract = clean_text(pub.get('bib', {}).get('abstract', ''))
                    url = pub.get('pub_url', pub.get('url_scholarbib', ''))
                    
                    # Intentar extraer DOI de varias fuentes
                    doi = None
                    
                    # 1. Buscar en la URL
                    if url:
                        doi = extract_doi_from_text(url)
                    
                    # 2. Si no se encuentra en la URL, buscar en el abstract
                    if not doi and abstract:
                        doi = extract_doi_from_text(abstract)
                    
                    # 3. Buscar en cualquier otro campo relevante
                    if not doi:
                        # Buscar en campos de URL alternativos
                        for url_field in ['eprint_url', 'url_pdf', 'url_citations']:
                            if url_field in pub and pub[url_field]:
                                doi = extract_doi_from_text(pub[url_field])
                                if doi:
                                    break
                    
                    # 4. Buscar en el título completo por si acaso
                    if not doi and title:
                        doi = extract_doi_from_text(title)
                    
                    # 5. Como último recurso, convertir todo el objeto pub a texto y buscar
                    if not doi:
                        # Convertir el objeto pub a JSON y buscar en el texto completo
                        full_text = json.dumps(pub)
                        doi = extract_doi_from_text(full_text)
                    
                    # Crear objeto de resultado con datos limpios
                    article_data = {
                        "title": title,
                        "authors": authors,
                        "year": year,
                        "journal": venue,
                        "abstract": abstract,
                        "url": url,
                        "citations": pub.get('num_citations', 0),
                        "doi": doi or "",  # Añadir DOI si se encuentra, o cadena vacía
                        "source": "Google Scholar"
                    }
                    
                    results.append(article_data)
                    count += 1
                    
                    if count % 5 == 0:
                        logger.info(f"Recuperados {count} artículos hasta ahora...")
                    
                    # Introducir retraso aleatorio para evitar bloqueos
                    random_delay(3.0, 6.0)
                    
                except StopIteration:
                    logger.info("No hay más resultados disponibles")
                    break
                except Exception as e:
                    logger.error(f"Error al procesar un resultado: {str(e)}")
                    logger.debug(traceback.format_exc())  # Mostrar stack trace detallado en debug
                    consecutive_errors += 1
                    
                    # Esperar más tiempo si hay un error
                    random_delay(5.0, 10.0)
                    
                    # Si ocurren varios errores consecutivos, podríamos estar bloqueados
                    if consecutive_errors >= 3:
                        logger.error("Múltiples errores consecutivos detectados. Posible bloqueo.")
                        break
            
            logger.info(f"Búsqueda completa. Se obtuvieron {len(results)} artículos.")
            break  # Salir del bucle de reintentos si todo fue bien
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Error durante la búsqueda en Google Scholar (intento {retry_count}/{max_retry}): {str(e)}")
            logger.debug(traceback.format_exc())  # Log del stack trace completo
            
            if retry_count < max_retry:
                logger.info(f"Reintentando búsqueda después de una pausa...")
                random_delay(10.0, 20.0)  # Pausa más larga entre reintentos
                
                # Intentar reiniciar el estado de scholarly
                try:
                    logger.info("Reiniciando configuración de scholarly...")
                    setup_scholarly(True)
                except:
                    pass
            else:
                logger.error("Se agotaron los reintentos. Finalizando búsqueda.")
    
    return results


def save_results(results: List[Dict[Any, Any]], filepath: str) -> None:
    """
    Guarda los resultados en un archivo JSON.
    
    Args:
        results: Lista de resultados a guardar.
        filepath: Ruta del archivo donde guardar los resultados.
    """
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(results, file, ensure_ascii=False, indent=4)
        logger.info(f"Resultados guardados en {filepath}")
    except Exception as e:
        logger.error(f"Error al guardar los resultados: {str(e)}")
        # Intentar guardar con una codificación alternativa
        try:
            with open(filepath, 'w', encoding='utf-8-sig') as file:
                json.dump(results, file, ensure_ascii=True, indent=4)
            logger.info(f"Resultados guardados con codificación alternativa en {filepath}")
        except Exception as e2:
            logger.error(f"Error al guardar con codificación alternativa: {str(e2)}")


def run_google_scholar_search(
    domain1_terms: List[str],
    domain2_terms: List[str],
    domain3_terms: Optional[List[str]] = None,
    output_file: str = "outputs/google_scholar_results.json",
    integrated_results_file: str = "outputs/integrated_results.json",
    max_results: int = 50,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    use_proxy: bool = True,
    always_integrate: bool = True
) -> None:
    """
    Función principal que ejecuta la búsqueda en Google Scholar.
    
    Args:
        domain1_terms: Lista de términos del primer dominio.
        domain2_terms: Lista de términos del segundo dominio.
        domain3_terms: Lista de términos del tercer dominio (opcional).
        output_file: Ruta del archivo donde guardar los resultados de Google Scholar.
        integrated_results_file: Ruta del archivo de resultados integrados donde añadir los nuevos resultados.
        max_results: Número máximo de resultados a extraer.
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
        use_proxy: Si es True, utiliza proxies para las solicitudes.
        always_integrate: Si es True, siempre integra los resultados con el archivo de resultados integrados.
    """
    try:
        start_time = time.time()
        
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
        
        # Verificar y crear directorio de salida
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Creado directorio de salida: {output_dir}")
        
        # Guardar resultados de Google Scholar
        save_results(results, output_file)
        
        end_time = time.time()
        
        logger.info(f"Búsqueda completada en {end_time - start_time:.2f} segundos.")
        logger.info(f"Se encontraron {len(results)} resultados.")
        
        # Mostrar estadísticas sobre DOIs
        dois_count = sum(1 for item in results if item.get('doi'))
        logger.info(f"Se encontraron DOIs para {dois_count} de {len(results)} artículos ({dois_count/len(results)*100:.1f}% de cobertura)")
        
        # Integrar con resultados existentes si se solicita y el archivo existe
        if always_integrate and os.path.exists(integrated_results_file):
            logger.info(f"Integrando resultados con el archivo existente: {integrated_results_file}")
            integrate_with_existing_results(
                google_scholar_file=output_file,
                integrated_results_file=integrated_results_file,
                output_file=integrated_results_file  # Sobrescribir el archivo original
            )
        
    except Exception as e:
        logger.error(f"Error durante la búsqueda en Google Scholar: {str(e)}")
        logger.debug(traceback.format_exc())  # Log del stack trace completo


def integrate_with_existing_results(
    google_scholar_file: str,
    integrated_results_file: str,
    output_file: str
) -> None:
    """
    Integra los resultados de Google Scholar con los resultados existentes.
    
    Args:
        google_scholar_file: Ruta al archivo con resultados de Google Scholar.
        integrated_results_file: Ruta al archivo con resultados integrados existentes.
        output_file: Ruta donde guardar los resultados combinados.
    """
    try:
        # Cargar resultados de Google Scholar
        with open(google_scholar_file, 'r', encoding='utf-8') as file:
            gs_results = json.load(file)
        
        # Cargar resultados integrados existentes
        with open(integrated_results_file, 'r', encoding='utf-8') as file:
            existing_results = json.load(file)
        
        logger.info(f"Integrando {len(gs_results)} resultados de Google Scholar con {len(existing_results)} resultados existentes")
        
        # Crear conjuntos para detectar duplicados por DOI y por título
        existing_dois = {item.get('doi', '').lower(): True for item in existing_results if item.get('doi')}
        existing_titles = {normalize_title(item.get('title', '')): True for item in existing_results}
        
        # Filtrar resultados de Google Scholar para eliminar duplicados
        unique_gs_results = []
        duplicates_by_doi = 0
        duplicates_by_title = 0
        
        for item in gs_results:
            # Comprobar duplicados por DOI primero (más preciso)
            if item.get('doi') and item.get('doi').lower() in existing_dois:
                duplicates_by_doi += 1
                continue
                
            # Si no hay duplicado por DOI, comprobar por título
            normalized_title = normalize_title(item.get('title', ''))
            if normalized_title in existing_titles:
                duplicates_by_title += 1
                continue
                
            # Si no es duplicado, añadirlo a los resultados únicos
            unique_gs_results.append(item)
            
            # Actualizar los conjuntos de control para futuros duplicados
            if item.get('doi'):
                existing_dois[item.get('doi').lower()] = True
            existing_titles[normalized_title] = True
        
        # Combinar resultados
        combined_results = existing_results + unique_gs_results
        
        # Ordenar por año (descendente) y luego por citas (descendente)
        combined_results = sorted(
            combined_results, 
            key=lambda x: (
                int(x.get('year', 0)) if x.get('year') and isinstance(x.get('year'), (int, str)) and str(x.get('year')).isdigit() else 0,
                int(x.get('citations', 0)) if x.get('citations') else 0
            ), 
            reverse=True
        )
        
        # Guardar resultados combinados
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(combined_results, file, ensure_ascii=False, indent=4)
        
        logger.info(f"Eliminados {duplicates_by_doi} duplicados por DOI y {duplicates_by_title} por título")
        logger.info(f"Se añadieron {len(unique_gs_results)} nuevos resultados de Google Scholar.")
        logger.info(f"Total de resultados combinados: {len(combined_results)}")
        logger.info(f"Resultados guardados en {output_file}")
        
    except Exception as e:
        logger.error(f"Error durante la integración de resultados: {str(e)}")
        logger.debug(traceback.format_exc())


def normalize_title(title: str) -> str:
    """
    Normaliza un título para comparación y detección de duplicados.
    
    Args:
        title: El título a normalizar.
        
    Returns:
        Título normalizado.
    """
    if not title:
        return ""
    
    # Eliminar espacios extras, convertir a minúsculas y eliminar puntuación común
    title = title.lower().strip()
    for char in ['.', ',', ':', ';', '!', '?', '(', ')', '[', ']', '{', '}', '"', "'"]:
        title = title.replace(char, '')
    
    # Eliminar artículos y palabras comunes que no aportan significado para la comparación
    words_to_remove = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']
    words = title.split()
    filtered_words = [word for word in words if word not in words_to_remove]
    
    return ' '.join(filtered_words)


if __name__ == "__main__":
    # Configurar parser de argumentos
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
    parser.add_argument("--no-proxy", action="store_true",
                        help="No utilizar proxies para las solicitudes")
    
    # Argumentos para integración
    parser.add_argument("--integrate", action="store_true",
                        help="Integrar con resultados existentes")
    parser.add_argument("--integrated-file", type=str, default="outputs/integrated_results.json",
                        help="Archivo con resultados integrados existentes")
    parser.add_argument("--output-integrated", type=str, default="outputs/new_integrated_results.json",
                        help="Archivo donde guardar los resultados integrados")
    
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
        integrated_results_file=args.integrated_file,
        max_results=args.max_results,
        year_start=args.year_start,
        year_end=args.year_end,
        use_proxy=not args.no_proxy,
        always_integrate=args.integrate
    )