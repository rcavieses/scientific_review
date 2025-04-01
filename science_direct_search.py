#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script optimizado para realizar búsquedas en Science Direct API usando elsapy.
Permite buscar artículos usando tres dominios de términos con la estructura:
(term1_dominio1 OR term2_dominio1 OR...) AND (term1_dominio2 OR term2_dominio2 OR...) AND (term1_dominio3 OR term2_dominio3 OR...)
"""

import os
import json
import time
from typing import List, Dict, Any, Tuple, Optional
from elsapy.elsclient import ElsClient
from elsapy.elssearch import ElsSearch


def load_api_key(filepath: str = "sciencedirect_apikey.txt") -> str:
    """
    Carga la API key de Science Direct desde un archivo.
    
    Args:
        filepath: Ruta al archivo que contiene la API key.
        
    Returns:
        API key como string.
    """
    try:
        with open(filepath, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo {filepath} con la API key.")


def construct_query(domain_terms_list: List[List[str]]) -> str:
    """
    Construye la query para Science Direct según la estructura solicitada.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        
    Returns:
        Query estructurada para Science Direct.
    """
    domain_queries = []
    
    for domain_terms in domain_terms_list:
        if domain_terms:  # Solo procesamos dominios con términos
            # Formatear los términos del dominio actual
            domain_query = " OR ".join([f'"{term}"' for term in domain_terms])
            domain_queries.append(f"({domain_query})")
    
    # Construir la query completa uniendo todos los dominios con AND
    full_query = " AND ".join(domain_queries)
    
    return full_query


def search_science_direct(domain_terms_list: List[List[str]], 
                         api_key: str, 
                         max_results: int = 100,
                         search_field: str = "title-abs-key",
                         year_range: Optional[Tuple[int, int]] = None) -> Tuple[List[Dict[Any, Any]], Dict[str, str]]:
    """
    Realiza una búsqueda en Science Direct utilizando elsapy.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        api_key: API key para Science Direct.
        max_results: Número máximo de resultados a devolver.
        search_field: Campo en el que buscar (por defecto, título, resumen y palabras clave)
        year_range: Tupla opcional (año_inicio, año_fin) para filtrar por rango de años
        
    Returns:
        Tupla con (lista de resultados, diccionario de resúmenes)
    """
    # Construir la query
    query = construct_query(domain_terms_list)
    
    # Indicamos el campo de búsqueda
    query = f"{search_field}({query})"
    
    print(f"Ejecutando búsqueda con query: {query}")
    
    # Inicializar el cliente de Elsevier
    client = ElsClient(api_key)
    client.inst_token = None  # No se requiere un token institucional si tienes una API key personal
    
    # Crear el objeto de búsqueda
    # Utilizamos 'scopus' como base de datos ya que proporciona acceso a artículos de Science Direct
    search = ElsSearch(query, 'scopus')
    
    # Ejecutar la búsqueda
    search.execute(client, get_all=False)
    
    # Si no hay resultados, devolver listas vacías
    if not hasattr(search, 'results') or not search.results:
        print("No se encontraron resultados para la búsqueda.")
        return [], {}
    
    # Extraer y formatear los resultados
    results = []
    abstracts = {}
    
    # Número de resultados antes de filtrar por año
    num_results_before_filter = len(search.results)
    
    for item in search.results:
        # Extraer el año de publicación
        pub_year = None
        if "prism:coverDate" in item:
            try:
                pub_year = int(item["prism:coverDate"][:4])
            except (ValueError, TypeError):
                pub_year = None
        
        # Filtrar por año si se especifica un rango
        if year_range and len(year_range) == 2 and pub_year is not None:  # Verificar explícitamente que pub_year no es None
            year_start, year_end = year_range
            # Verificar que year_start y year_end no son None antes de comparar
            if (year_start is not None and pub_year < year_start) or (year_end is not None and pub_year > year_end):
                continue  # Saltar este artículo si está fuera del rango de años
        
        # Extraer información básica
        article = {
            "title": item.get("dc:title", ""),
            "authors": [],
            "year": pub_year,
            "journal": item.get("prism:publicationName", ""),
            "doi": item.get("prism:doi", ""),
            "url": item.get("prism:url", ""),
            "citations": item.get("citedby-count", "0"),
            "keywords": [],  # Añadimos campo para palabras clave
            "source": "Science Direct"  # Añadir etiqueta de fuente
        }
        
        # Extraer autores si están disponibles
        if "author" in item and isinstance(item["author"], list):
            for author in item["author"]:
                if "authname" in author:
                    article["authors"].append(author["authname"])
                elif "given-name" in author and "surname" in author:
                    article["authors"].append(f"{author['given-name']} {author['surname']}")
        elif "dc:creator" in item:
            article["authors"] = [item["dc:creator"]]
        
        # Extraer palabras clave (keywords) si están disponibles
        if "authkeywords" in item:
            if isinstance(item["authkeywords"], str):
                # Si es un string, lo dividimos por comas o punto y coma
                keywords = [k.strip() for k in item["authkeywords"].replace(";", ",").split(",")]
                article["keywords"] = keywords
            elif isinstance(item["authkeywords"], list):
                article["keywords"] = item["authkeywords"]
        
        # Añadir a la lista de resultados
        results.append(article)
        
        # Extraer el resumen si está disponible
        if "dc:description" in item:
            abstracts[item.get("prism:doi", "")] = item.get("dc:description", "")
        
        # Limitar al número máximo de resultados solicitados
        if len(results) >= max_results:
            break
    
    # Mostrar información sobre el filtrado por año
    if year_range and len(year_range) == 2:
        year_start, year_end = year_range
        print(f"Se filtraron los resultados por año: {year_start}-{year_end}")
        print(f"Total de resultados antes del filtro: {num_results_before_filter}")
        print(f"Total de resultados después del filtro: {len(results)}")
    
    return results, abstracts


def save_results(results: List[Dict[Any, Any]], filename: str = "sciencedirect_results.json") -> None:
    """
    Guarda los resultados en un archivo JSON en la carpeta outputs.
    
    Args:
        results: Lista de resultados a guardar.
        filename: Nombre del archivo donde guardar los resultados.
    """
    # Crear la carpeta outputs si no existe
    os.makedirs("outputs", exist_ok=True)
    
    # Ruta completa del archivo
    filepath = os.path.join("outputs", filename)
    
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(results, file, ensure_ascii=False, indent=4)
        
    print(f"Resultados guardados en {filepath}")


def save_abstracts(abstracts: Dict[str, str], filename: str = "sciencedirect_abstracts.json") -> None:
    """
    Guarda los resúmenes en un archivo JSON en la carpeta outputs.
    
    Args:
        abstracts: Diccionario de resúmenes (DOI: resumen).
        filename: Nombre del archivo donde guardar los resúmenes.
    """
    # Crear la carpeta outputs si no existe
    os.makedirs("outputs", exist_ok=True)
    
    # Ruta completa del archivo
    filepath = os.path.join("outputs", filename)
    
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(abstracts, file, ensure_ascii=False, indent=4)
        
    print(f"Resúmenes guardados en {filepath}")


def get_article_details(client: ElsClient, doi: str) -> Dict[str, Any]:
    """
    Obtiene detalles adicionales de un artículo mediante su DOI,
    incluyendo abstract y keywords que pueden no estar en los resultados de búsqueda iniciales.
    
    Args:
        client: Cliente de ElsAPI inicializado.
        doi: DOI del artículo del que queremos obtener más detalles.
        
    Returns:
        Diccionario con detalles adicionales del artículo.
    """
    from elsapy.elsdoc import FullDoc
    
    try:
        doc = FullDoc(doi=doi)
        if doc.read(client):
            return doc.data
        return {}
    except Exception as e:
        print(f"Error al obtener detalles del artículo {doi}: {str(e)}")
        return {}


def run_science_direct_search(domain1_terms: List[str], 
                             domain2_terms: List[str],
                             domain3_terms: Optional[List[str]] = None,
                             apikey_file: str = "sciencedirect_apikey.txt",
                             results_file: str = "sciencedirect_results.json",
                             abstracts_file: str = "sciencedirect_abstracts.json",
                             max_results: int = 100,
                             search_field: str = "title-abs-key",
                             fetch_details: bool = True,
                             year_range: Optional[Tuple[int, int]] = None) -> None:
    """
    Función principal que ejecuta todo el proceso de búsqueda en Science Direct.
    
    Args:
        domain1_terms: Lista de términos del primer dominio.
        domain2_terms: Lista de términos del segundo dominio.
        domain3_terms: Lista de términos del tercer dominio (opcional).
        apikey_file: Ruta al archivo con la API key.
        results_file: Nombre del archivo para guardar los resultados.
        abstracts_file: Nombre del archivo para guardar los resúmenes.
        max_results: Número máximo de resultados a devolver.
        search_field: Campo en el que buscar (por defecto, título, resumen y palabras clave)
        fetch_details: Si es True, busca detalles adicionales para cada artículo (consume más API calls)
        year_range: Tupla opcional (año_inicio, año_fin) para filtrar por rango de años
    """
    try:
        # Cargar la API key
        api_key = load_api_key(apikey_file)
        
        # Preparar la lista de dominios
        domain_terms_list = [domain1_terms, domain2_terms]
        if domain3_terms:
            domain_terms_list.append(domain3_terms)
        
        # Verificar que no haya listas vacías
        domain_terms_list = [terms for terms in domain_terms_list if terms]
        
        if not domain_terms_list:
            raise ValueError("Debe proporcionar al menos un dominio con términos.")
            
        # Realizar la búsqueda
        start_time = time.time()
        results, abstracts = search_science_direct(domain_terms_list, api_key, max_results, search_field, year_range)
        
        # Si se solicita obtener detalles adicionales
        if fetch_details and results:
            print("Obteniendo detalles adicionales para cada artículo...")
            client = ElsClient(api_key)
            
            for idx, article in enumerate(results):
                if "doi" in article and article["doi"]:
                    print(f"Procesando artículo {idx+1}/{len(results)}: {article['title']}")
                    details = get_article_details(client, article["doi"])
                    
                    # Si no tenemos keywords pero están en los detalles, las agregamos
                    if not article["keywords"] and "coredata" in details:
                        if "dc:description" in details["coredata"] and article["doi"] not in abstracts:
                            abstracts[article["doi"]] = details["coredata"]["dc:description"]
                        
                        # Buscar keywords en diferentes ubicaciones posibles
                        if "subject-areas" in details["coredata"]:
                            subject_areas = details["coredata"]["subject-areas"]
                            if "subject-area" in subject_areas:
                                areas = subject_areas["subject-area"]
                                if isinstance(areas, list):
                                    article["keywords"] = [area.get("$", "") for area in areas]
                                elif isinstance(areas, dict):
                                    article["keywords"] = [areas.get("$", "")]
                    
                    # Pausar para no superar límites de la API
                    time.sleep(1)
        
        end_time = time.time()
        
        # Guardar resultados y resúmenes
        save_results(results, results_file)
        save_abstracts(abstracts, abstracts_file)
        
        print(f"Búsqueda completada en {end_time - start_time:.2f} segundos.")
        print(f"Se encontraron {len(results)} resultados.")
        
    except Exception as e:
        print(f"Error durante la búsqueda en Science Direct: {str(e)}")


if __name__ == "__main__":
    # Ejemplo de uso con tres dominios para búsqueda de modelos de IA para pronóstico en pesquerías
    dominio1_modelos = [
        "artificial intelligence", 
        "machine learning", 
        "deep learning", 
        "neural networks", 
        "random forest",
        "support vector machine"
    ]
    
    dominio2_pronostico = [
        "forecast", 
        "prediction", 
        "forecasting", 
        "time series", 
        "predictive modeling"
    ]
    
    dominio3_pesca = [
        "fishery", 
        "fisheries", 
        "fish stock", 
        "fishing", 
        "aquaculture",
        "marine resources"
    ]
    
    # Ejecutar la búsqueda con los tres dominios
    run_science_direct_search(
        domain1_terms=dominio1_modelos,
        domain2_terms=dominio2_pronostico,
        domain3_terms=dominio3_pesca,
        results_file="sciencedirect_results.json",
        abstracts_file="sciencedirect_abstracts.json",
        max_results=50,
        fetch_details=True,  # Activar búsqueda de detalles adicionales
        year_range=(2008, 2025)  # Filtrar artículos desde 2018 hasta 2023
    )