#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para realizar búsquedas en Springer API usando la sintaxis de query recomendada por Springer.
Permite buscar artículos usando tres dominios de términos con la estructura de búsqueda de Springer.
"""

import os
import json
import time
import pandas as pd
import requests
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter

# Importar la librería oficial de Springer
import springernature_api_client.metadata as metadata
from springernature_api_client.utils import results_to_dataframe


def load_api_key(filepath: str = "springer_apikey.txt") -> str:
    """
    Carga la API key de Springer desde un archivo.
    
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


def construct_springer_query(domain_terms_list: List[List[str]]) -> str:
    """
    Construye la query para Springer API siguiendo su sintaxis específica.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        
    Returns:
        Query estructurada para Springer.
    """
    domain_queries = []
    
    for i, domain_terms in enumerate(domain_terms_list):
        if not domain_terms:
            continue
            
        # Para cada dominio, creamos una consulta OR de los términos
        domain_terms_query = []
        for term in domain_terms:
            # Usar keyword: para términos específicos
            domain_terms_query.append(f'keyword:"{term}"')
        
        # Unir los términos con OR
        domain_query = " OR ".join(domain_terms_query)
        
        # Envolver en paréntesis si hay más de un término
        if len(domain_terms_query) > 1:
            domain_query = f"({domain_query})"
            
        domain_queries.append(domain_query)
    
    # Unir los dominios con AND
    full_query = " AND ".join(domain_queries)
    
    return full_query


def search_springer_with_direct_query(api_key: str, query: str, max_results: int = 50) -> Dict:
    """
    Realiza una búsqueda directa a la API de Springer usando requests.
    
    Args:
        api_key: API key para Springer.
        query: Query de búsqueda.
        max_results: Número máximo de resultados.
        
    Returns:
        Respuesta de la API en formato JSON.
    """
    url = "https://api.springernature.com/meta/v2/json"
    
    params = {
        "q": query,
        "api_key": api_key,
        "p": max_results
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
        return {}


def search_springer(
    domain_terms_list: List[List[str]], 
    api_key: str, 
    max_results: int = 100,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None
) -> Tuple[List[Dict[Any, Any]], Dict[str, str]]:
    """
    Realiza una búsqueda en Springer API usando la librería oficial.
    
    Args:
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        api_key: API key para Springer.
        max_results: Número máximo de resultados a devolver.
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
        
    Returns:
        Tupla con (lista de resultados, diccionario de resúmenes)
    """
    # Construir la query en formato Springer
    query = construct_springer_query(domain_terms_list)
    
    # Añadir filtros de año si corresponde
    if year_start:
        query += f" AND year>={year_start}"
    if year_end:
        query += f" AND year<={year_end}"
    
    print(f"Ejecutando búsqueda con query: {query}")
    
    # Intentar primero con la librería oficial
    try:
        print("Usando cliente oficial de Springer...")
        metadata_client = metadata.MetadataAPI(api_key=api_key)
        
        # Usar el método search para obtener resultados
        response = metadata_client.search(
            q=query,
            p=max_results,
            s=1,
            fetch_all=False,
            is_premium=False
        )
        
        # Guardar respuesta en bruto para depuración
        with open("outputs/springer_raw_response.json", "w") as f:
            try:
                json.dump(response, f, indent=4)
                print("Respuesta en bruto guardada en outputs/springer_raw_response.json")
            except:
                print("No se pudo guardar la respuesta en bruto")
        
        # Verificar si hay datos en la respuesta
        if not response or not response.get('records'):
            print("No se encontraron datos con la librería oficial, intentando con solicitud directa...")
            raise Exception("No data found")
            
        # Convertir a DataFrame
        df = results_to_dataframe(response, export_to_excel=False)
        if df.empty:
            print("DataFrame vacío, intentando con solicitud directa...")
            raise Exception("Empty DataFrame")
            
    except Exception as e:
        print(f"Error o sin resultados con librería oficial: {e}")
        print("Intentando con solicitud HTTP directa...")
        
        # Intentar con solicitud directa como alternativa
        response_data = search_springer_with_direct_query(api_key, query, max_results)
        
        # Verificar si tenemos resultados
        if not response_data or 'records' not in response_data:
            print("No se encontraron resultados con ningún método")
            return [], {}
            
        # Crear DataFrame manualmente
        records = response_data.get('records', [])
        df_data = []
        
        for record in records:
            item = {
                'title': record.get('title', ''),
                'doi': record.get('doi', ''),
                'publicationName': record.get('publicationName', ''),
                'publicationDate': record.get('publicationDate', ''),
                'abstract': record.get('abstract', ''),
                'url': record.get('url', '')
            }
            
            # Extraer autores
            creators = []
            if 'creators' in record:
                for creator in record['creators']:
                    if 'creator' in creator:
                        creators.append(creator.get('creator', ''))
            
            item['creators'] = creators
            df_data.append(item)
            
        df = pd.DataFrame(df_data)
    
    # Guardar el DataFrame para inspección
    try:
        df.to_csv("outputs/springer_raw_results.csv", index=False)
        print("Resultados brutos guardados en outputs/springer_raw_results.csv")
    except Exception as e:
        print(f"Error al guardar resultados brutos: {e}")
    
    # Procesar los resultados
    results = []
    abstracts = {}
    
    # Verificar si el DataFrame tiene datos
    if df.empty:
        print("No hay resultados para procesar")
        return [], {}
        
    print(f"Procesando {len(df)} resultados encontrados")
    print(f"Columnas disponibles: {df.columns.tolist()}")
    
    for _, row in df.iterrows():
        # Extraer título
        title = row.get('title', '')
        if not isinstance(title, str) or not title.strip():
            continue
        
        # Extraer resumen
        abstract = row.get('abstract', '')
        if not isinstance(abstract, str):
            abstract = ''
        
        # Extraer DOI
        doi = row.get('doi', '')
        
        # Extraer y procesar año de publicación
        year = None
        pub_date = row.get('publicationDate', '')
        if isinstance(pub_date, str) and len(pub_date) >= 4:
            try:
                year = int(pub_date[:4])
            except (ValueError, TypeError):
                year = None
        
        # Formatear autores
        authors = []
        creators = row.get('creators', [])
        if isinstance(creators, list):
            authors = [creator for creator in creators if creator]
        elif isinstance(creators, str):
            authors = [creators]
        
        # Crear objeto de artículo
        article = {
            "title": title,
            "authors": authors,
            "year": year,
            "journal": row.get('publicationName', ''),
            "doi": doi,
            "url": row.get('url', ''),
            "source": "Springer"
        }
        
        # Añadir a los resultados
        results.append(article)
        
        # Guardar abstract si está disponible
        if abstract and doi:
            abstracts[doi] = abstract
    
    print(f"Procesados {len(results)} artículos")
    
    # Ordenar por año (más recientes primero)
    results = sorted(results, key=lambda x: x.get("year", 0) if x.get("year") else 0, reverse=True)
    
    return results, abstracts


def save_results(results: List[Dict[Any, Any]], filename: str = "springer_results.json") -> None:
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


def save_abstracts(abstracts: Dict[str, str], filename: str = "springer_abstracts.json") -> None:
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


def test_simple_query(api_key: str):
    """
    Realiza una prueba simple con un solo término para verificar que la API funciona.
    
    Args:
        api_key: API key para Springer.
    """
    print("\n===== PRUEBA SIMPLE =====")
    test_query = 'keyword:"machine learning"'
    
    # Inicializar el cliente
    metadata_client = metadata.MetadataAPI(api_key=api_key)
    
    # Realizar búsqueda simple
    try:
        response = metadata_client.search(q=test_query, p=5, s=1, fetch_all=False, is_premium=False)
        
        # Verificar respuesta
        if response and 'records' in response:
            print(f"¡Prueba exitosa! Se encontraron {len(response['records'])} resultados")
            
            # Mostrar algunos resultados
            for i, record in enumerate(response['records'][:2]):
                print(f"\nResultado {i+1}:")
                print(f"Título: {record.get('title', '[No title]')}")
                print(f"DOI: {record.get('doi', '[No DOI]')}")
        else:
            print("No se encontraron resultados en la prueba simple")
    except Exception as e:
        print(f"Error en la prueba simple: {e}")


def run_springer_search(
    domain1_terms: List[str],
    domain2_terms: List[str],
    domain3_terms: Optional[List[str]] = None,
    apikey_file: str = "springer_apikey.txt",
    results_file: str = "springer_results.json",
    abstracts_file: str = "springer_abstracts.json",
    max_results: int = 100,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    test_mode: bool = False
) -> None:
    """
    Función principal que ejecuta todo el proceso de búsqueda en Springer.
    
    Args:
        domain1_terms: Lista de términos del primer dominio.
        domain2_terms: Lista de términos del segundo dominio.
        domain3_terms: Lista de términos del tercer dominio (opcional).
        apikey_file: Ruta al archivo con la API key.
        results_file: Nombre del archivo para guardar los resultados.
        abstracts_file: Nombre del archivo para guardar los resúmenes.
        max_results: Número máximo de resultados a devolver.
        year_start: Año inicial para filtrar resultados (inclusive).
        year_end: Año final para filtrar resultados (inclusive).
        test_mode: Si es True, ejecuta una prueba simple antes de la búsqueda principal.
    """
    try:
        # Cargar la API key
        api_key = load_api_key(apikey_file)
        
        # Crear carpeta de outputs si no existe
        os.makedirs("outputs", exist_ok=True)
        
        # Ejecutar prueba simple si está en modo test
        if test_mode:
            test_simple_query(api_key)
        
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
        results, abstracts = search_springer(
            domain_terms_list, 
            api_key, 
            max_results,
            year_start=year_start,
            year_end=year_end
        )
        end_time = time.time()
        
        # Guardar resultados y resúmenes
        save_results(results, results_file)
        save_abstracts(abstracts, abstracts_file)
        
        print(f"Proceso completo finalizado en {end_time - start_time:.2f} segundos.")
        print(f"Se encontraron y procesaron {len(results)} resultados relevantes.")
        
        # Mostrar estadísticas de años si se aplicó filtro
        if (year_start or year_end) and results:
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
        print(f"Error durante la búsqueda en Springer: {str(e)}")


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
    
    # Ejecutar la búsqueda con los tres dominios y filtro de años
    run_springer_search(
        domain1_terms=dominio1_modelos,
        domain2_terms=dominio2_pronostico,
        domain3_terms=dominio3_pesca,
        results_file="springer_results.json",
        abstracts_file="springer_abstracts.json",
        max_results=50,
        year_start=2008,  # Filtrar artículos desde 2008
        year_end=None,    # Hasta el presente
        test_mode=True    # Ejecutar prueba simple primero
    )