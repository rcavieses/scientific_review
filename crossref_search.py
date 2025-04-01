#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script optimizado para realizar búsquedas en Crossref API.
Permite buscar artículos usando tres dominios de términos con la estructura:
(term1_dominio1 OR term2_dominio1 OR...) AND (term1_dominio2 OR term2_dominio2 OR...) AND (term1_dominio3 OR term2_dominio3 OR...)
Incluye filtro por rango de años de publicación.
"""

import os
import json
import time
import requests
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter


def construct_query(domain_terms_list: List[List[str]]) -> str:
    """
    Construye la query para Crossref según la estructura solicitada.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        
    Returns:
        Query estructurada para Crossref.
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


def search_crossref(domain_terms_list: List[List[str]], 
                  max_results: int = 100, 
                  email: str = None,
                  year_start: Optional[int] = None,
                  year_end: Optional[int] = None) -> Tuple[List[Dict[Any, Any]], Dict[str, str]]:
    """
    Realiza una búsqueda en Crossref utilizando la API.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        max_results: Número máximo de resultados a devolver.
        email: Email opcional para identificarse con la API de Crossref (buena práctica).
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
        
    Returns:
        Tupla con (lista de resultados, diccionario de resúmenes)
    """
    # Construir la query
    query = construct_query(domain_terms_list)
    
    print(f"Ejecutando búsqueda con query: {query}")
    if year_start or year_end:
        year_filter = f" (Años: {year_start or 'cualquiera'}-{year_end or 'actual'})"
        print(f"Filtro de años activo: {year_filter}")
    
    # URL base para la API de Crossref
    base_url = "https://api.crossref.org/works"
    
    # Parámetros para la solicitud - aumentamos el número de resultados para poder filtrar después
    params = {
        "query": query,
        "rows": max_results * 3,  # Solicitamos más resultados para compensar el filtrado posterior
        "sort": "relevance",
        "order": "desc",
        "filter": "type:journal-article"
    }
    
    # Añadir filtro de rango de años directamente en la API si es posible
    # Crossref permite filtrar por un rango de fechas usando el parámetro 'filter'
    if year_start or year_end:
        date_filters = []
        if year_start:
            date_filters.append(f"from-pub-date:{year_start}")
        if year_end:
            date_filters.append(f"until-pub-date:{year_end}")
        
        # Agregar los filtros de fecha a los filtros existentes
        if "filter" in params:
            params["filter"] += "," + ",".join(date_filters)
        else:
            params["filter"] = ",".join(date_filters)
    
    # Agregar email si se proporciona (buena práctica según Crossref)
    headers = {}
    if email:
        headers["User-Agent"] = f"PythonSearchScript/{email}"
    
    # Implementamos un mecanismo de reintentos con espera exponencial
    max_attempts = 3
    attempt = 0
    backoff_time = 2  # segundos
    
    while attempt < max_attempts:
        try:
            # Realizar la solicitud a la API
            response = requests.get(base_url, params=params, headers=headers, timeout=30)
            
            # Verificar el estado de la respuesta
            if response.status_code == 200:
                break
            elif response.status_code == 429:  # Rate limit
                print(f"Rate limit alcanzado. Esperando {backoff_time} segundos...")
                time.sleep(backoff_time)
                backoff_time *= 2  # Espera exponencial
                attempt += 1
            else:
                print(f"Error en la solicitud HTTP: {response.status_code}, {response.text}")
                time.sleep(backoff_time)
                attempt += 1
        
        except requests.RequestException as e:
            print(f"Error de conexión: {e}. Reintento {attempt+1}/{max_attempts}...")
            attempt += 1
            time.sleep(backoff_time)
            backoff_time *= 2
    
    if attempt == max_attempts:
        raise Exception("No se pudo completar la solicitud después de varios intentos")
    
    # Convertir la respuesta a JSON
    data = response.json()
    
    # Extraer y formatear los resultados
    results = []
    abstracts = {}
    
    # Procesar los items encontrados
    for item in data.get("message", {}).get("items", []):
        # Extraer año de publicación para verificar rango de años
        year = None
        if "published" in item and "date-parts" in item["published"]:
            if item["published"]["date-parts"] and item["published"]["date-parts"][0]:
                year = item["published"]["date-parts"][0][0]  # Año como número entero
        
        # Filtro adicional por año (por si acaso el filtro de la API no funcionó correctamente)
        if year:
            if (year_start and year < year_start) or (year_end and year > year_end):
                continue
                
        # Extraer título y verificar si cumple con todas las condiciones de búsqueda
        title = item.get("title", [""])[0] if item.get("title") else ""
        
        # Extraer resumen/abstract si está disponible
        abstract = item.get("abstract", "")
        
        # Texto completo para verificar términos (título + abstract)
        full_text = (title + " " + abstract).lower()
        
        # Verificar que el artículo contiene al menos un término de cada dominio
        # Este es un filtro más estricto que el que aplica Crossref por defecto
        matches_all_domains = True
        
        for domain_terms in domain_terms_list:
            # Verificar si al menos un término del dominio está en el texto completo
            domain_match = False
            for term in domain_terms:
                if term.lower() in full_text:
                    domain_match = True
                    break
            
            # Si no hay coincidencia con ningún término del dominio, rechazar el artículo
            if not domain_match:
                matches_all_domains = False
                break
        
        # Si no cumple con todas las condiciones, pasar al siguiente artículo
        if not matches_all_domains:
            continue
        
        # A partir de aquí procesamos solo los artículos que cumplen con todos los dominios
        # Extraer autores si están disponibles
        authors = []
        if "author" in item:
            for author in item["author"]:
                author_name = ""
                if "given" in author:
                    author_name += author["given"] + " "
                if "family" in author:
                    author_name += author["family"]
                authors.append(author_name.strip())
        
        # Extraer DOI
        doi = item.get("DOI", "")
        
        # Construir el objeto de artículo
        article = {
            "title": title,
            "authors": authors,
            "year": year,
            "journal": item.get("container-title", [""])[0] if item.get("container-title") else "",
            "doi": doi,
            "url": item.get("URL", ""),
            "citations": item.get("is-referenced-by-count", 0)
        }
        
        # Añadir a la lista de resultados
        results.append(article)
        
        # Guardar el resumen si está disponible
        if abstract:
            abstracts[doi] = abstract
            
        # Si ya tenemos suficientes resultados, terminamos
        if len(results) >= max_results:
            break
    
    print(f"Encontrados {len(results)} artículos que cumplen con todos los criterios de búsqueda")
    
    # Ordenar por año de publicación (más recientes primero)
    results = sorted(results, key=lambda x: x.get("year", 0) if x.get("year") else 0, reverse=True)
    
    return results, abstracts


def save_results(results: List[Dict[Any, Any]], filename: str = "crossref_results.json") -> None:
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


def save_abstracts(abstracts: Dict[str, str], filename: str = "crossref_abstracts.json") -> None:
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


def run_crossref_search(domain1_terms: List[str],
                      domain2_terms: List[str],
                      domain3_terms: Optional[List[str]] = None,
                      results_file: str = "crossref_results.json",
                      abstracts_file: str = "crossref_abstracts.json",
                      max_results: int = 100,
                      email: str = None,
                      year_start: Optional[int] = None,
                      year_end: Optional[int] = None) -> None:
    """
    Función principal que ejecuta todo el proceso de búsqueda en Crossref.
    
    Args:
        domain1_terms: Lista de términos del primer dominio.
        domain2_terms: Lista de términos del segundo dominio.
        domain3_terms: Lista de términos del tercer dominio (opcional).
        results_file: Nombre del archivo para guardar los resultados.
        abstracts_file: Nombre del archivo para guardar los resúmenes.
        max_results: Número máximo de resultados a devolver.
        email: Email opcional para identificarse con la API de Crossref.
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
    """
    try:
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
        results, abstracts = search_crossref(
            domain_terms_list, 
            max_results, 
            email,
            year_start=year_start,
            year_end=year_end
        )
        end_time = time.time()
        
        # Guardar resultados y resúmenes
        save_results(results, results_file)
        save_abstracts(abstracts, abstracts_file)
        
        print(f"Búsqueda completada en {end_time - start_time:.2f} segundos.")
        print(f"Se encontraron {len(results)} resultados.")
        
        # Mostrar estadísticas de años si se aplicó filtro
        if year_start or year_end and results:
            years = [paper.get("year") for paper in results if paper.get("year")]
            if years:
                oldest = min(years)
                newest = max(years)
                print(f"Rango de años en los resultados: {oldest}-{newest}")
                
                # Distribución por década
                decades = [str(year - year % 10) + "s" for year in years]
                decade_counts = Counter(decades)
                print("\nDistribución por década:")
                for decade, count in sorted(decade_counts.items()):
                    print(f"  {decade}: {count} artículos")
        
    except Exception as e:
        print(f"Error durante la búsqueda en Crossref: {str(e)}")


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
    
    # Ejecutar la búsqueda con los tres dominios y filtro de años (desde 2020 hasta la actualidad)
    run_crossref_search(
        domain1_terms=dominio1_modelos,
        domain2_terms=dominio2_pronostico,
        domain3_terms=dominio3_pesca,
        results_file="crossref_results.json",
        abstracts_file="crossref_abstracts.json",
        max_results=50,
        email="your@mail.com",  # Reemplazar con tu email
        year_start=2008,  # Filtrar artículos desde 2020
        year_end=None     # Hasta el presente
    )