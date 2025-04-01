#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script corregido para realizar búsquedas en Semantic Scholar API sin necesidad de API key.
Permite buscar artículos usando hasta tres dominios de términos y filtrar por rango de años.
"""

import os
import json
import time
import requests
from typing import List, Dict, Any, Tuple, Optional


def construct_simple_query(domain_terms_list: List[List[str]]) -> str:
    """
    Construye una query simple para Semantic Scholar.
    Semantic Scholar puede tener problemas con consultas complejas, así que
    usamos un enfoque más directo.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        
    Returns:
        Query simple para Semantic Scholar.
    """
    # Para mejorar los resultados, usamos una consulta simple con los términos principales
    # de cada dominio, luego filtraremos los resultados manualmente
    all_terms = []
    
    # Tomamos algunos términos de cada dominio para la consulta principal
    for domain_terms in domain_terms_list:
        if domain_terms:
            # Tomamos hasta 2 términos de cada dominio para no sobrecargar la consulta
            all_terms.extend(domain_terms[:2])
    
    # Unir todos los términos seleccionados con AND
    return " ".join(all_terms)


def search_semantic_scholar(domain_terms_list: List[List[str]], max_results: int = 100, 
                           year_start: Optional[int] = None, year_end: Optional[int] = None) -> Tuple[List[Dict[Any, Any]], Dict[str, str]]:
    """
    Realiza una búsqueda en Semantic Scholar utilizando la API pública.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        max_results: Número máximo de resultados a devolver.
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
        
    Returns:
        Tupla con (lista de resultados, diccionario de resúmenes)
    """
    # Construir una query simple
    query = construct_simple_query(domain_terms_list)
    
    print(f"Ejecutando búsqueda con query: {query}")
    if year_start or year_end:
        year_filter = f" (Años: {year_start or 'cualquiera'}-{year_end or 'actual'})"
        print(f"Filtro de años activo: {year_filter}")
    
    # URL base para la API de Semantic Scholar
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    # Parámetros para la solicitud - solicitamos más resultados para poder filtrar después
    params = {
        "query": query,
        "limit": 100,  # Máximo permitido
        "fields": "title,authors,year,venue,publicationVenue,url,abstract,externalIds,citationCount"
    }
    
    # Configurar headers generales
    headers = {
        "Accept": "application/json"
    }
    
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
    
    # Verificar si la respuesta tiene la estructura esperada
    if "data" not in data:
        print(f"Advertencia: La respuesta de la API no tiene el formato esperado. Respuesta: {data}")
        return [], {}
    
    print(f"Total de resultados en bruto: {len(data['data'])}")
    
    # Procesar los papers encontrados
    for paper in data.get("data", []):
        # Extraer año para filtrar
        paper_year = paper.get("year")
        
        # Aplicar filtro de años si está especificado
        if (year_start and paper_year and paper_year < year_start) or (year_end and paper_year and paper_year > year_end):
            continue
            
        # Extraer título y abstract
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        
        # Texto completo para verificar términos (si hay abstract)
        full_text = (title + " " + (abstract or "")).lower()
        
        # Verificar relevancia con criterios más flexibles
        relevant = True
        matched_domains = 0
        
        for domain_terms in domain_terms_list:
            # Verificar si al menos un término del dominio está en el texto completo
            domain_match = any(term.lower() in full_text for term in domain_terms)
            if domain_match:
                matched_domains += 1
        
        # Consideramos relevante si coincide con al menos 2 dominios
        # o si solo tenemos un dominio y coincide con él
        if len(domain_terms_list) > 1 and matched_domains < 2:
            relevant = False
        
        # Si no es relevante, pasar al siguiente artículo
        if not relevant:
            continue
        
        # Extraer autores si están disponibles
        authors = []
        if "authors" in paper:
            for author in paper["authors"]:
                if author and "name" in author:
                    authors.append(author.get("name", ""))
        
        # Extraer DOI si está disponible
        doi = ""
        if "externalIds" in paper and "DOI" in paper["externalIds"]:
            doi = paper["externalIds"]["DOI"]
        
        # Extraer nombre de la revista/venue
        venue = ""
        if "venue" in paper and paper["venue"]:
            venue = paper.get("venue", "")
        elif "publicationVenue" in paper and paper["publicationVenue"]:
            venue = paper.get("publicationVenue", {}).get("name", "")
        
        # Construir el objeto de artículo con información enriquecida
        article = {
            "title": title,
            "authors": authors,
            "year": paper_year,
            "journal": venue,
            "doi": doi,
            "url": paper.get("url", ""),
            "citations": paper.get("citationCount", 0),
            "matched_domains": matched_domains  # Información adicional
        }
        
        # Añadir a la lista de resultados
        results.append(article)
        
        # Guardar el resumen
        if abstract:
            if doi:
                abstracts[doi] = abstract
            else:
                # Usar título como clave si no hay DOI
                abstracts[title] = abstract
        
        # Si ya tenemos suficientes resultados, terminamos
        if len(results) >= max_results:
            break
    
    print(f"Encontrados {len(results)} artículos relevantes después del filtrado")
    
    # Ordenar por año de publicación (más recientes primero)
    results = sorted(results, key=lambda x: x.get("year", 0) if x.get("year") else 0, reverse=True)
    
    return results, abstracts


def save_results(results: List[Dict[Any, Any]], filename: str = "semanticscholar_results.json") -> None:
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


def save_abstracts(abstracts: Dict[str, str], filename: str = "semanticscholar_abstracts.json") -> None:
    """
    Guarda los resúmenes en un archivo JSON en la carpeta outputs.
    
    Args:
        abstracts: Diccionario de resúmenes (DOI o título: resumen).
        filename: Nombre del archivo donde guardar los resúmenes.
    """
    # Crear la carpeta outputs si no existe
    os.makedirs("outputs", exist_ok=True)
    
    # Ruta completa del archivo
    filepath = os.path.join("outputs", filename)
    
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(abstracts, file, ensure_ascii=False, indent=4)
        
    print(f"Resúmenes guardados en {filepath}")


def run_semantic_scholar_search(domain1_terms: List[str], 
                              domain2_terms: List[str],
                              domain3_terms: Optional[List[str]] = None,
                              results_file: str = "semanticscholar_results.json",
                              abstracts_file: str = "semanticscholar_abstracts.json",
                              max_results: int = 100,
                              year_start: Optional[int] = None,
                              year_end: Optional[int] = None) -> None:
    """
    Función principal que ejecuta todo el proceso de búsqueda en Semantic Scholar.
    
    Args:
        domain1_terms: Lista de términos del primer dominio.
        domain2_terms: Lista de términos del segundo dominio.
        domain3_terms: Lista de términos del tercer dominio (opcional).
        results_file: Nombre del archivo para guardar los resultados.
        abstracts_file: Nombre del archivo para guardar los resúmenes.
        max_results: Número máximo de resultados a devolver.
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
    """
    try:
        # Preparar la lista de dominios
        domain_terms_list = []
        if domain1_terms:
            domain_terms_list.append(domain1_terms)
        if domain2_terms:
            domain_terms_list.append(domain2_terms)
        if domain3_terms:
            domain_terms_list.append(domain3_terms)
        
        if not domain_terms_list:
            raise ValueError("Debe proporcionar al menos un dominio con términos.")
            
        # Realizar la búsqueda
        start_time = time.time()
        results, abstracts = search_semantic_scholar(
            domain_terms_list, 
            max_results,
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
        if year_start or year_end:
            years = [paper.get("year") for paper in results if paper.get("year")]
            if years:
                oldest = min(years)
                newest = max(years)
                print(f"Rango de años en los resultados: {oldest}-{newest}")
                
                # Distribución por década
                from collections import Counter
                decades = [str(year - year % 10) + "s" for year in years]
                decade_counts = Counter(decades)
                print("\nDistribución por década:")
                for decade, count in sorted(decade_counts.items()):
                    print(f"  {decade}: {count} artículos")
        
    except Exception as e:
        print(f"Error durante la búsqueda en Semantic Scholar: {str(e)}")


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
    run_semantic_scholar_search(
        domain1_terms=dominio1_modelos,
        domain2_terms=dominio2_pronostico,
        domain3_terms=dominio3_pesca,
        results_file="semanticscholar_results.json",
        abstracts_file="semanticscholar_abstract.json",
        max_results=100,
        year_start=2008,  # Filtrar artículos desde 2020
        year_end=None     # Hasta el presente
    )