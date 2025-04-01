#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Función integradora de resultados de búsquedas académicas.
Este script proporciona una función para combinar los resultados de búsquedas previamente realizadas
en Science Direct, Crossref y Semantic Scholar, eliminando duplicados y manteniendo
etiquetas de la fuente de cada resultado.
"""

import os
import json
import time
from typing import List, Dict, Any, Tuple, Optional, Set


def normalize_doi(doi: str) -> str:
    """
    Normaliza un DOI para comparación y detección de duplicados.
    
    Args:
        doi: El DOI a normalizar.
        
    Returns:
        DOI normalizado.
    """
    if not doi:
        return ""
    
    # Eliminar espacios y convertir a minúsculas
    doi = doi.lower().strip()
    
    # Eliminar prefijos comunes
    prefixes = ["doi:", "https://doi.org/", "http://doi.org/", "doi.org/"]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break
    
    return doi


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


def load_results(results_files: Dict[str, str]) -> List[Dict[Any, Any]]:
    """
    Carga los resultados de las búsquedas previas y los etiqueta según su fuente.
    
    Args:
        results_files: Diccionario con pares {nombre_fuente: ruta_archivo}
        
    Returns:
        Lista combinada de resultados con etiquetas de fuente.
    """
    combined_results = []
    
    for source_name, file_path in results_files.items():
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    source_results = json.load(file)
                    
                    # Añadir etiqueta de fuente a cada resultado
                    for result in source_results:
                        result["source"] = source_name
                        combined_results.append(result)
                        
                    print(f"Se cargaron {len(source_results)} resultados de {source_name}")
            else:
                print(f"Archivo no encontrado: {file_path}")
        except Exception as e:
            print(f"Error al cargar resultados de {source_name}: {str(e)}")
    
    print(f"Total de resultados brutos combinados: {len(combined_results)}")
    return combined_results


def remove_duplicates(results: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
    """
    Elimina duplicados de los resultados combinados.
    
    Args:
        results: Lista de resultados combinados.
        
    Returns:
        Lista de resultados sin duplicados.
    """
    unique_results = []
    seen_dois = set()
    seen_titles = set()
    duplicates_count = 0
    
    for result in results:
        # Normalizar DOI y título para comparación
        doi = normalize_doi(result.get("doi", ""))
        title = normalize_title(result.get("title", ""))
        
        # Verificar si es un duplicado
        is_duplicate = False
        
        if doi and doi in seen_dois:
            is_duplicate = True
        elif title and title in seen_titles:
            is_duplicate = True
        
        if not is_duplicate:
            # No es duplicado, lo añadimos a los resultados únicos
            unique_results.append(result)
            
            # Registrar este DOI y título como vistos
            if doi:
                seen_dois.add(doi)
            if title:
                seen_titles.add(title)
        else:
            duplicates_count += 1
    
    print(f"Se eliminaron {duplicates_count} duplicados")
    return unique_results


def merge_abstracts(abstracts_files: Dict[str, str]) -> Dict[str, str]:
    """
    Combina los resúmenes de todas las fuentes, priorizando los más completos.
    
    Args:
        abstracts_files: Diccionario con pares {nombre_fuente: ruta_archivo}
        
    Returns:
        Diccionario combinado de resúmenes.
    """
    combined_abstracts = {}
    
    # Cargar todos los archivos de resúmenes
    abstracts_by_source = {}
    for source_name, file_path in abstracts_files.items():
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    abstracts_by_source[source_name] = json.load(file)
                    print(f"Se cargaron {len(abstracts_by_source[source_name])} resúmenes de {source_name}")
            else:
                print(f"Archivo de resúmenes no encontrado: {file_path}")
        except Exception as e:
            print(f"Error al cargar resúmenes de {source_name}: {str(e)}")
    
    # Combinar todos los resúmenes, priorizando los más largos para cada clave
    all_keys = set()
    for abstracts in abstracts_by_source.values():
        all_keys.update(abstracts.keys())
    
    for key in all_keys:
        best_abstract = ""
        for source_name, abstracts in abstracts_by_source.items():
            if key in abstracts and len(abstracts[key]) > len(best_abstract):
                best_abstract = abstracts[key]
        
        if best_abstract:
            combined_abstracts[key] = best_abstract
    
    return combined_abstracts


def integrate_search_results(
    sciencedirect_results: str,
    crossref_results: str,
    semanticscholar_results: str,
    sciencedirect_abstracts: str,
    crossref_abstracts: str,
    semanticscholar_abstracts: str,
    output_results: str = "integrated_results.json",
    output_abstracts: str = "integrated_abstracts.json"
) -> None:
    """
    Integra los resultados de búsquedas previamente realizadas.
    
    Args:
        sciencedirect_results: Ruta al archivo de resultados de Science Direct.
        crossref_results: Ruta al archivo de resultados de Crossref.
        semanticscholar_results: Ruta al archivo de resultados de Semantic Scholar.
        sciencedirect_abstracts: Ruta al archivo de resúmenes de Science Direct.
        crossref_abstracts: Ruta al archivo de resúmenes de Crossref.
        semanticscholar_abstracts: Ruta al archivo de resúmenes de Semantic Scholar.
        output_results: Nombre del archivo para guardar los resultados integrados.
        output_abstracts: Nombre del archivo para guardar los resúmenes integrados.
    """
    try:
        start_time = time.time()
        
        print("Iniciando integración de resultados de búsqueda...")
        
        # 1. Cargar resultados
        results_files = {
            "Science Direct": sciencedirect_results,
            "Crossref": crossref_results,
            "Semantic Scholar": semanticscholar_results
        }
        
        all_results = load_results(results_files)
        
        # 2. Eliminar duplicados
        unique_results = remove_duplicates(all_results)
        
        # 3. Ordenar resultados por año (más recientes primero) y luego por citas
        sorted_results = sorted(
            unique_results, 
            key=lambda x: (
                int(x.get("year", "0")) if x.get("year") and (isinstance(x.get("year"), int) or (isinstance(x.get("year"), str) and x.get("year").isdigit())) else 0,
                int(x.get("citations", 0)) if x.get("citations") else 0
            ), 
            reverse=True
        )
        
        # 4. Combinar resúmenes de todas las fuentes
        abstracts_files = {
            "Science Direct": sciencedirect_abstracts,
            "Crossref": crossref_abstracts,
            "Semantic Scholar": semanticscholar_abstracts
        }
        
        combined_abstracts = merge_abstracts(abstracts_files)
        
        # 5. Guardar resultados y resúmenes integrados
        os.makedirs(os.path.dirname(output_results) if os.path.dirname(output_results) else ".", exist_ok=True)
        os.makedirs(os.path.dirname(output_abstracts) if os.path.dirname(output_abstracts) else ".", exist_ok=True)
        
        with open(output_results, 'w', encoding='utf-8') as file:
            json.dump(sorted_results, file, ensure_ascii=False, indent=4)
        
        with open(output_abstracts, 'w', encoding='utf-8') as file:
            json.dump(combined_abstracts, file, ensure_ascii=False, indent=4)
        
        end_time = time.time()
        
        # Obtener estadísticas por fuente
        sources_stats = {}
        for result in sorted_results:
            source = result.get("source", "Desconocido")
            if source not in sources_stats:
                sources_stats[source] = 0
            sources_stats[source] += 1
        
        print("\nEstadísticas de resultados por fuente:")
        for source, count in sources_stats.items():
            print(f"  {source}: {count} resultados")
        
        print(f"\nIntegración completada en {end_time - start_time:.2f} segundos.")
        print(f"Resultados únicos: {len(sorted_results)}")
        print(f"Resúmenes únicos: {len(combined_abstracts)}")
        print(f"Resultados guardados en: {output_results}")
        print(f"Resúmenes guardados en: {output_abstracts}")
        
    except Exception as e:
        print(f"Error durante la integración de resultados: {str(e)}")


if __name__ == "__main__":
    # Ejemplo de uso
    integrate_search_results(
        sciencedirect_results="outputs/sciencedirect_results.json",
        crossref_results="outputs/crossref_results.json",
        semanticscholar_results="outputs/semanticscholar_results.json",
        sciencedirect_abstracts="outputs/sciencedirect_abstracts.json",
        crossref_abstracts="outputs/crossref_abstracts.json",
        semanticscholar_abstracts="outputs/semanticscholar_abstracts.json",
        output_results="outputs/integrated_results.json",
        output_abstracts="outputs/integrated_abstracts.json"
    )