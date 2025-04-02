#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script mejorado para realizar búsquedas en Crossref API.
Permite buscar artículos usando tres dominios de términos con la estructura:
(term1_dominio1 OR term2_dominio1 OR...) AND (term1_dominio2 OR term2_dominio2 OR...) AND (term1_dominio3 OR term2_dominio3 OR...)
Incluye filtro por rango de años de publicación y manejo mejorado de errores.
"""

import os
import json
import time
import requests
import re
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


def clean_text(text: str) -> str:
    """
    Limpia y normaliza texto para remover caracteres problemáticos y formato extraño.
    
    Args:
        text: Texto a limpiar.
        
    Returns:
        Texto limpio y normalizado.
    """
    if not text:
        return ""
    
    # Eliminar múltiples espacios
    cleaned = re.sub(r'\s+', ' ', text)
    # Eliminar caracteres de control
    cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
    # Normalizar comillas y otros caracteres especiales
    cleaned = cleaned.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    # Eliminar espacios al inicio y final
    cleaned = cleaned.strip()
    
    return cleaned


def extract_year_from_text(text: str) -> Optional[int]:
    """
    Extrae un año (formato 19XX o 20XX) de un texto.
    
    Args:
        text: Texto del cual extraer el año.
        
    Returns:
        Año como entero o None si no se encuentra.
    """
    if not text:
        return None
        
    # Buscar patrón de año (19XX o 20XX)
    year_match = re.search(r'(19|20)\d{2}', text)
    if year_match:
        try:
            return int(year_match.group(0))
        except ValueError:
            pass
    
    return None


def search_crossref(domain_terms_list: List[List[str]], 
                   max_results: int = 100, 
                   email: str = None,
                   year_start: Optional[int] = None,
                   year_end: Optional[int] = None) -> Tuple[List[Dict[Any, Any]], Dict[str, str]]:
    """
    Realiza una búsqueda en Crossref utilizando la API con mejor manejo de errores.
    
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
    
    # Parámetros para la solicitud con mejor filtrado
    params = {
        "query": query,
        "rows": max_results * 3,  # Solicitamos más resultados para compensar el filtrado posterior
        "sort": "relevance",
        "order": "desc",
        "filter": "type:journal-article,has-abstract:true"  # Filtramos solo artículos con abstract
    }
    
    # Añadir filtro de rango de años directamente en la API si es posible
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
    headers = {
        "Accept": "application/json"  # Especificar explícitamente que queremos JSON
    }
    
    if email:
        headers["User-Agent"] = f"PythonSearchScript/{email}"
    
    # Implementamos un mecanismo de reintentos con espera exponencial
    max_attempts = 3
    attempt = 0
    backoff_time = 2  # segundos
    
    while attempt < max_attempts:
        try:
            # Realizar la solicitud a la API
            response = requests.get(base_url, params=params, headers=headers, timeout=45)
            
            # Información de diagnóstico
            print(f"DEBUG: Status Code: {response.status_code}")
            print(f"DEBUG: Content-Type: {response.headers.get('Content-Type', 'No content type')}")
            
            # Verificar el estado de la respuesta
            if response.status_code == 200:
                # Verificar que la respuesta es realmente JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    print(f"ADVERTENCIA: La respuesta no es JSON, Content-Type: {content_type}")
                    print(f"Primeros 500 caracteres de la respuesta: {response.text[:500]}...")
                    
                # Intentar parsear la respuesta como JSON
                try:
                    response_data = response.json()
                    # Verificar la estructura básica de la respuesta
                    if "message" not in response_data:
                        print("ADVERTENCIA: Respuesta JSON sin campo 'message'")
                        print(f"Claves en la respuesta: {list(response_data.keys())}")
                        
                    if "items" not in response_data.get("message", {}):
                        print("ADVERTENCIA: La respuesta no contiene una lista de artículos (items)")
                        print(f"Claves en 'message': {list(response_data.get('message', {}).keys())}")
                        
                    # Si todo está bien, salir del bucle de reintentos
                    break
                except json.JSONDecodeError:
                    print("ERROR: La respuesta no es un JSON válido")
                    print(f"Primeros 500 caracteres de la respuesta: {response.text[:500]}...")
                    attempt += 1
                    time.sleep(backoff_time)
                    backoff_time *= 2
                    continue
                    
            elif response.status_code == 429:  # Rate limit
                print(f"Rate limit alcanzado. Esperando {backoff_time} segundos...")
                time.sleep(backoff_time)
                backoff_time *= 2  # Espera exponencial
                attempt += 1
            else:
                print(f"Error en la solicitud HTTP: {response.status_code}")
                print(f"Detalles: {response.text[:500]}...")
                time.sleep(backoff_time)
                attempt += 1
        
        except requests.RequestException as e:
            print(f"Error de conexión: {e}. Reintento {attempt+1}/{max_attempts}...")
            attempt += 1
            time.sleep(backoff_time)
            backoff_time *= 2
    
    if attempt == max_attempts:
        print("No se pudo completar la solicitud después de varios intentos")
        return [], {}
    
    # Procesar la respuesta
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("ERROR: No se pudo decodificar la respuesta como JSON")
        return [], {}
    
    # Extraer y formatear los resultados
    results = []
    abstracts = {}
    
    # Procesar los items encontrados
    items = data.get("message", {}).get("items", [])
    print(f"Encontrados {len(items)} artículos en la respuesta inicial")
    
    for item in items:
        try:
            # Verificar que el item sea un diccionario
            if not isinstance(item, dict):
                print(f"Omitiendo item no válido (tipo: {type(item)})")
                continue
            
            # Manejar casos donde el título es una cadena de texto larga que contiene varios campos
            if "title" in item and isinstance(item["title"], list) and item["title"]:
                title_text = item["title"][0]
                
                # Verificar si el título parece ser una combinación de varios campos
                if len(title_text) > 200 and ("abstract" in title_text.lower() or "keywords" in title_text.lower()):
                    # El título puede contener múltiples campos, intentar extraerlos
                    print(f"Detectado un título largo que puede contener múltiples campos: {title_text[:100]}...")
                    
                    # Extraer título real (primera parte antes de "abstract" o algún otro marcador)
                    title_match = re.match(r'^(.*?)(?:abstract:|authors:|keywords:|doi:)', title_text.lower())
                    if title_match:
                        clean_title = title_match.group(1).strip()
                    else:
                        # Si no hay marcadores claros, tomar las primeras 150 caracteres como título
                        clean_title = title_text[:150].strip()
                    
                    # Buscar el abstract
                    abstract_match = re.search(r'abstract:?\s*(.*?)(?:keywords:|doi:|$)', title_text.lower())
                    if abstract_match:
                        abstract = abstract_match.group(1).strip()
                    else:
                        abstract = ""
                    
                    # Intentar extraer autores si están presentes
                    authors_match = re.search(r'authors:?\s*(.*?)(?:abstract:|keywords:|doi:|$)', title_text.lower())
                    extra_authors = []
                    if authors_match:
                        author_text = authors_match.group(1)
                        # Dividir por comas o punto y coma
                        extra_authors = [a.strip() for a in re.split(r'[,;]', author_text) if a.strip()]
                    
                    # Intentar extraer DOI si está presente en el texto
                    doi_match = re.search(r'doi:?\s*(\S+)', title_text.lower())
                    extracted_doi = doi_match.group(1) if doi_match else ""
                    
                    # Actualizar el item para usar estos valores extraídos
                    item["title"] = [clean_title]
                    if abstract:
                        item["abstract"] = abstract
                    if extra_authors and not item.get("author"):
                        # Crear estructura de autores similar a la de Crossref
                        item["author"] = [{"name": author} for author in extra_authors]
                    if extracted_doi and not item.get("DOI"):
                        item["DOI"] = extracted_doi
                    
                    # Intentar extraer año de publicación del texto
                    year = extract_year_from_text(title_text)
                    if year and not (item.get("published") and item["published"].get("date-parts")):
                        # Crear estructura similar a la que usa Crossref
                        item["published"] = {"date-parts": [[year]]}
                        
            # Continuar con el procesamiento normal
            # Extraer año de publicación para verificar rango de años
            year = None
            if "published" in item and "date-parts" in item["published"]:
                if item["published"]["date-parts"] and item["published"]["date-parts"][0]:
                    year = item["published"]["date-parts"][0][0]  # Año como número entero
            
            # Si no hay año en la estructura estándar, buscarlo en otros lugares
            if not year:
                # Buscar en el título
                if "title" in item and item["title"]:
                    title_text = item["title"][0] if isinstance(item["title"], list) else item["title"]
                    year = extract_year_from_text(title_text)
                
                # Si aun no se encuentra, buscar en otras partes del item
                if not year and isinstance(item, dict):
                    # Convertir todo el item a texto y buscar un patrón de año
                    item_text = json.dumps(item)
                    year = extract_year_from_text(item_text)
            
            # Filtro adicional por año (por si acaso el filtro de la API no funcionó correctamente)
            if year:
                if (year_start and year < year_start) or (year_end and year > year_end):
                    continue
                    
            # Extraer título
            if "title" in item and item["title"]:
                if isinstance(item["title"], list):
                    title = clean_text(item["title"][0])
                else:
                    title = clean_text(item["title"])
            else:
                # Si no hay título, omitir este artículo
                continue
            
            # Extraer resumen/abstract si está disponible
            abstract = ""
            if "abstract" in item:
                abstract = clean_text(item["abstract"])
            
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
                    if isinstance(author, dict):
                        author_name = ""
                        if "given" in author:
                            author_name += author["given"] + " "
                        if "family" in author:
                            author_name += author["family"]
                        # Si hay un campo "name" directo, usarlo
                        if "name" in author:
                            author_name = author["name"]
                        
                        if author_name.strip():
                            authors.append(author_name.strip())
                    elif isinstance(author, str):
                        # Si el autor ya es un string, usarlo directamente
                        authors.append(author)
            
            # Extraer DOI
            doi = item.get("DOI", "")
            
            # Extraer nombre de la revista/journal
            journal = ""
            if "container-title" in item:
                if isinstance(item["container-title"], list) and item["container-title"]:
                    journal = item["container-title"][0]
                elif isinstance(item["container-title"], str):
                    journal = item["container-title"]
            
            # Construir el objeto de artículo con los campos limpios
            article = {
                "title": clean_text(title),
                "authors": [clean_text(a) for a in authors if a],
                "year": year,
                "journal": clean_text(journal),
                "doi": clean_text(doi),
                "url": clean_text(item.get("URL", "")),
                "citations": item.get("is-referenced-by-count", 0)
            }
            
            # Añadir a la lista de resultados
            results.append(article)
            
            # Guardar el resumen si está disponible
            if abstract:
                abstracts[doi] = clean_text(abstract)
                
            # Si ya tenemos suficientes resultados, terminamos
            if len(results) >= max_results:
                break
                
        except Exception as e:
            print(f"Error al procesar un artículo: {str(e)}")
            # Continuar con el siguiente artículo
            continue
    
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
    
    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(results, file, ensure_ascii=False, indent=4)
            
        print(f"Resultados guardados en {filepath}")
    except Exception as e:
        print(f"Error al guardar los resultados: {str(e)}")
        # Intentar guardar con una codificación alternativa
        try:
            with open(filepath, 'w', encoding='utf-8-sig') as file:
                json.dump(results, file, ensure_ascii=True, indent=4)
            print(f"Resultados guardados con codificación alternativa en {filepath}")
        except Exception as e2:
            print(f"Error al guardar con codificación alternativa: {str(e2)}")


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
    
    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(abstracts, file, ensure_ascii=False, indent=4)
            
        print(f"Resúmenes guardados en {filepath}")
    except Exception as e:
        print(f"Error al guardar los resúmenes: {str(e)}")
        # Intentar guardar con una codificación alternativa
        try:
            with open(filepath, 'w', encoding='utf-8-sig') as file:
                json.dump(abstracts, file, ensure_ascii=True, indent=4)
            print(f"Resúmenes guardados con codificación alternativa en {filepath}")
        except Exception as e2:
            print(f"Error al guardar con codificación alternativa: {str(e2)}")


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
        
        # Verificar si se encontraron resultados
        if not results:
            print("ADVERTENCIA: No se encontraron resultados que cumplan con los criterios.")
            
            # Guardar archivo vacío para mantener consistencia
            save_results([], results_file)
            save_abstracts({}, abstracts_file)
            print("Se han guardado archivos vacíos para mantener consistencia en el flujo de trabajo.")
            return
        
        # Guardar resultados y resúmenes
        save_results(results, results_file)
        save_abstracts(abstracts, abstracts_file)
        
        print(f"Búsqueda completada en {end_time - start_time:.2f} segundos.")
        print(f"Se encontraron {len(results)} resultados.")
        
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
        print(f"Error durante la búsqueda en Crossref: {str(e)}")
        import traceback
        traceback.print_exc()


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
    
    # Ejecutar la búsqueda con los tres dominios y filtro de años (desde 2008 hasta la actualidad)
    run_crossref_search(
        domain1_terms=dominio1_modelos,
        domain2_terms=dominio2_pronostico,
        domain3_terms=dominio3_pesca,
        results_file="crossref_results.json",
        abstracts_file="crossref_abstracts.json",
        max_results=50,
        email="your@mail.com",  # Reemplazar con tu email
        year_start=2008,  
        year_end=None     # Hasta el presente
    )