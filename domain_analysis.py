#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para analizar la aparición de términos de dominio en los títulos de artículos científicos
y generar estadísticas frecuentistas. Añade valores binarios a cada artículo para indicar
su pertenencia a cada dominio y exporta un resumen de estadísticas a CSV.
"""

import os
import json
import csv
import re
from typing import List, Dict, Any, Tuple, Counter
from collections import defaultdict


def load_integrated_results(filepath: str) -> List[Dict[Any, Any]]:
    """
    Carga los resultados integrados de un archivo JSON.
    
    Args:
        filepath: Ruta al archivo JSON con los resultados integrados.
        
    Returns:
        Lista de resultados cargados.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            results = json.load(file)
            print(f"Se cargaron {len(results)} artículos del archivo {filepath}")
            return results
    except Exception as e:
        print(f"Error al cargar los resultados: {str(e)}")
        return []


def normalize_text(text: str) -> str:
    """
    Normaliza un texto para el análisis de términos.
    
    Args:
        text: Texto a normalizar.
        
    Returns:
        Texto normalizado.
    """
    if not text:
        return ""
    
    # Convertir a minúsculas
    text = text.lower()
    
    # Eliminar caracteres especiales y reemplazar por espacios
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Eliminar números
    text = re.sub(r'\d+', ' ', text)
    
    # Eliminar espacios múltiples
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def check_domain_presence(title: str, domain_terms: List[str]) -> bool:
    """
    Verifica si algún término del dominio está presente en el título.
    
    Args:
        title: Título normalizado del artículo.
        domain_terms: Lista de términos del dominio a verificar.
        
    Returns:
        True si al menos un término del dominio está presente, False en caso contrario.
    """
    normalized_title = normalize_text(title)
    
    # Verificar cada término del dominio
    for term in domain_terms:
        normalized_term = normalize_text(term)
        
        # Para términos compuestos (más de una palabra), verificamos la coincidencia exacta
        if len(normalized_term.split()) > 1:
            if normalized_term in normalized_title:
                return True
        else:
            # Para términos de una sola palabra, verificamos que sea una palabra completa
            pattern = r'\b' + re.escape(normalized_term) + r'\b'
            if re.search(pattern, normalized_title):
                return True
    
    return False


def analyze_domains(results: List[Dict[Any, Any]], domain_terms_list: List[List[str]], domain_names: List[str]) -> Tuple[List[Dict[Any, Any]], Dict[str, Any]]:
    """
    Analiza la presencia de términos de dominio en los títulos de los artículos.
    
    Args:
        results: Lista de resultados cargados.
        domain_terms_list: Lista de listas, donde cada lista contiene los términos de un dominio.
        domain_names: Lista con los nombres de los dominios.
        
    Returns:
        Tupla con (resultados actualizados, estadísticas).
    """
    # Inicializar contadores
    total_articles = len(results)
    domain_counters = [0] * len(domain_terms_list)
    domain_term_counters = [defaultdict(int) for _ in range(len(domain_terms_list))]
    
    # Verificar que tengamos los mismos dominios y nombres
    if len(domain_terms_list) != len(domain_names):
        raise ValueError("La cantidad de dominios no coincide con la cantidad de nombres de dominio")
    
    # Analizar cada artículo
    for article in results:
        title = article.get("title", "")
        
        # Verificar y actualizar cada dominio
        for i, (domain_terms, domain_name) in enumerate(zip(domain_terms_list, domain_names)):
            # Verificar si el artículo pertenece al dominio actual
            in_domain = check_domain_presence(title, domain_terms)
            
            # Añadir el valor binario al artículo
            domain_key = f"in_{domain_name.lower().replace(' ', '_')}_domain"
            article[domain_key] = 1 if in_domain else 0
            
            # Actualizar contadores
            if in_domain:
                domain_counters[i] += 1
                
                # Contar qué términos específicos aparecen
                for term in domain_terms:
                    normalized_term = normalize_text(term)
                    normalized_title = normalize_text(title)
                    
                    # Verificar presencia del término
                    if len(normalized_term.split()) > 1:
                        if normalized_term in normalized_title:
                            domain_term_counters[i][term] += 1
                    else:
                        pattern = r'\b' + re.escape(normalized_term) + r'\b'
                        if re.search(pattern, normalized_title):
                            domain_term_counters[i][term] += 1
    
    # Calcular estadísticas
    stats = {
        "total_articles": total_articles,
        "domains": []
    }
    
    for i, (domain_name, counter, term_counter) in enumerate(zip(domain_names, domain_counters, domain_term_counters)):
        # Ordenar términos por frecuencia
        sorted_terms = sorted(term_counter.items(), key=lambda x: x[1], reverse=True)
        
        domain_stats = {
            "name": domain_name,
            "count": counter,
            "percentage": round(counter / total_articles * 100, 2) if total_articles > 0 else 0,
            "terms": sorted_terms
        }
        
        stats["domains"].append(domain_stats)
    
    # Calcular métricas de intersección
    stats["intersections"] = {}
    
    # Intersección entre dominios (pares)
    for i in range(len(domain_names)):
        for j in range(i+1, len(domain_names)):
            # Contar artículos que pertenecen a ambos dominios
            intersection_count = sum(
                1 for article in results 
                if article.get(f"in_{domain_names[i].lower().replace(' ', '_')}_domain") == 1 
                and article.get(f"in_{domain_names[j].lower().replace(' ', '_')}_domain") == 1
            )
            
            intersection_key = f"{domain_names[i]}_{domain_names[j]}"
            stats["intersections"][intersection_key] = {
                "count": intersection_count,
                "percentage": round(intersection_count / total_articles * 100, 2) if total_articles > 0 else 0
            }
    
    # Artículos que pertenecen a todos los dominios
    if len(domain_names) > 2:
        all_domains_count = sum(
            1 for article in results 
            if all(article.get(f"in_{domain.lower().replace(' ', '_')}_domain") == 1 for domain in domain_names)
        )
        
        stats["intersections"]["all_domains"] = {
            "count": all_domains_count,
            "percentage": round(all_domains_count / total_articles * 100, 2) if total_articles > 0 else 0
        }
    
    return results, stats


def save_updated_results(results: List[Dict[Any, Any]], filepath: str) -> None:
    """
    Guarda los resultados actualizados en un archivo JSON.
    
    Args:
        results: Lista de resultados actualizados.
        filepath: Ruta donde guardar el archivo JSON.
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(results, file, ensure_ascii=False, indent=4)
        print(f"Resultados actualizados guardados en {filepath}")
    except Exception as e:
        print(f"Error al guardar los resultados actualizados: {str(e)}")


def save_stats_csv(stats: Dict[str, Any], filepath: str) -> None:
    """
    Guarda las estadísticas en un archivo CSV.
    
    Args:
        stats: Diccionario con estadísticas.
        filepath: Ruta donde guardar el archivo CSV.
    """
    try:
        with open(filepath, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            
            # Escribir encabezado
            writer.writerow(["Estadísticas de Dominio"])
            writer.writerow(["Total de artículos analizados", stats["total_articles"]])
            writer.writerow([])
            
            # Escribir estadísticas por dominio
            writer.writerow(["Estadísticas por Dominio"])
            writer.writerow(["Dominio", "Artículos", "Porcentaje"])
            
            for domain in stats["domains"]:
                writer.writerow([domain["name"], domain["count"], f"{domain['percentage']}%"])
            
            writer.writerow([])
            
            # Escribir intersecciones
            writer.writerow(["Intersecciones entre Dominios"])
            writer.writerow(["Dominios", "Artículos", "Porcentaje"])
            
            for key, value in stats["intersections"].items():
                writer.writerow([key.replace("_", " & "), value["count"], f"{value['percentage']}%"])
            
            writer.writerow([])
            
            # Escribir términos más frecuentes por dominio
            for domain in stats["domains"]:
                writer.writerow([f"Términos más frecuentes en {domain['name']}"])
                writer.writerow(["Término", "Frecuencia"])
                
                for term, count in domain["terms"]:
                    writer.writerow([term, count])
                
                writer.writerow([])
        
        print(f"Estadísticas guardadas en {filepath}")
    except Exception as e:
        print(f"Error al guardar las estadísticas en CSV: {str(e)}")


def run_domain_analysis(
    input_file: str,
    output_results_file: str,
    output_stats_file: str,
    domain1_terms: List[str],
    domain2_terms: List[str],
    domain3_terms: List[str] = None,
    domain_names: List[str] = None
) -> None:
    """
    Ejecuta el análisis de dominio completo.
    
    Args:
        input_file: Ruta al archivo JSON con los resultados integrados.
        output_results_file: Ruta donde guardar los resultados actualizados.
        output_stats_file: Ruta donde guardar las estadísticas en CSV.
        domain1_terms: Lista de términos del primer dominio.
        domain2_terms: Lista de términos del segundo dominio.
        domain3_terms: Lista de términos del tercer dominio (opcional).
        domain_names: Lista con los nombres de los dominios (opcional).
    """
    try:
        print(f"Iniciando análisis de dominio...")
        
        # Cargar resultados
        results = load_integrated_results(input_file)
        
        if not results:
            print("No se encontraron resultados para analizar.")
            return
        
        # Preparar lista de dominios
        domain_terms_list = [domain1_terms, domain2_terms]
        if domain3_terms:
            domain_terms_list.append(domain3_terms)
        
        # Nombres de dominios por defecto si no se proporcionan
        if not domain_names:
            domain_names = [f"Dominio{i+1}" for i in range(len(domain_terms_list))]
        elif len(domain_names) < len(domain_terms_list):
            # Completar nombres faltantes
            domain_names.extend([f"Dominio{i+1}" for i in range(len(domain_names), len(domain_terms_list))])
        
        # Analizar dominios
        updated_results, stats = analyze_domains(results, domain_terms_list, domain_names)
        
        # Guardar resultados actualizados
        save_updated_results(updated_results, output_results_file)
        
        # Guardar estadísticas en CSV
        save_stats_csv(stats, output_stats_file)
        
        print(f"Análisis de dominio completado correctamente.")
        
    except Exception as e:
        print(f"Error durante el análisis de dominio: {str(e)}")


if __name__ == "__main__":
    # Crear carpeta outputs si no existe
    os.makedirs("outputs", exist_ok=True)
    
    # Ejemplo de uso con tres dominios para análisis de modelos de IA para pronóstico en pesquerías
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
    
    nombres_dominios = ["IA", "Pronóstico", "Pesquerías"]
    
    # Ejecutar el análisis
    run_domain_analysis(
        input_file="outputs/integrated_results.json",
        output_results_file="outputs/domain_analyzed_results.json",
        output_stats_file="outputs/domain_statistics.csv",
        domain1_terms=dominio1_modelos,
        domain2_terms=dominio2_pronostico,
        domain3_terms=dominio3_pesca,
        domain_names=nombres_dominios
    )
