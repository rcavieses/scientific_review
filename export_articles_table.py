#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para exportar artículos a formato CSV/Excel.
Este script genera una tabla de los artículos clasificados para una visualización rápida,
incluyendo información como título, año, autores, DOI y fuente.
"""

import os
import json
import csv
import argparse
import pandas as pd
from typing import List, Dict, Any, Optional


def load_articles(filepath: str) -> List[Dict[Any, Any]]:
    """
    Carga los artículos desde un archivo JSON.
    
    Args:
        filepath: Ruta al archivo JSON con los artículos.
        
    Returns:
        Lista de artículos cargados.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            articles = json.load(file)
            print(f"Cargados {len(articles)} artículos desde {filepath}")
            return articles
    except Exception as e:
        print(f"Error al cargar los artículos: {str(e)}")
        return []


def process_authors(authors_data) -> str:
    """
    Procesa los datos de autores para obtener una cadena formateada.
    
    Args:
        authors_data: Datos de autores (lista o cadena).
        
    Returns:
        Cadena con los autores formateados.
    """
    if not authors_data:
        return ""
    
    if isinstance(authors_data, list):
        # Si es una lista, unir con comas
        return ", ".join([author for author in authors_data if author])
    elif isinstance(authors_data, str):
        # Si ya es una cadena, devolverla tal cual
        return authors_data
    else:
        # Para otro tipo de datos, convertir a cadena
        return str(authors_data)


def create_articles_table(articles: List[Dict[Any, Any]], output_file: str, format: str = "csv") -> bool:
    """
    Crea una tabla de artículos en el formato especificado.
    
    Args:
        articles: Lista de artículos.
        output_file: Ruta del archivo de salida.
        format: Formato de salida ("csv" o "excel").
        
    Returns:
        True si se creó correctamente, False en caso de error.
    """
    if not articles:
        print("No hay artículos para exportar.")
        return False
    
    try:
        # Crear directorio de salida si no existe
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        
        # Determinar campos disponibles
        common_fields = ["title", "authors", "year", "doi", "journal", "source", "citations"]
        domain_fields = [field for field in articles[0].keys() if field.startswith("in_") and field.endswith("_domain")]
        ai_fields = [field for field in articles[0].keys() if "model" in field.lower() or field.startswith("uses_") or field.startswith("is_")]
        
        # Seleccionar campos para la tabla
        selected_fields = common_fields + domain_fields + ai_fields[:3]  # Limitar campos de AI para no sobrecargar
        
        # Preparar datos para la tabla
        table_data = []
        for article in articles:
            row = {}
            for field in selected_fields:
                if field in article:
                    if field == "authors":
                        row[field] = process_authors(article[field])
                    else:
                        row[field] = article[field]
                else:
                    row[field] = ""
            table_data.append(row)
        
        # Crear DataFrame
        df = pd.DataFrame(table_data)
        
        # Renombrar columnas para mejor legibilidad
        column_mapping = {
            "title": "Título",
            "authors": "Autores",
            "year": "Año",
            "doi": "DOI",
            "journal": "Revista/Fuente",
            "source": "Base de Datos",
            "citations": "Citaciones"
        }
        
        # Mapear columnas de dominio
        for field in domain_fields:
            domain_name = field.replace("in_", "").replace("_domain", "").title()
            column_mapping[field] = f"Dominio: {domain_name}"
        
        # Mapear columnas de IA
        for field in ai_fields[:3]:
            if "model" in field.lower():
                column_mapping[field] = "Modelo de IA"
            elif field.startswith("uses_"):
                column_mapping[field] = field.replace("uses_", "Usa: ").replace("_", " ").title()
            elif field.startswith("is_"):
                column_mapping[field] = field.replace("is_", "Es: ").replace("_", " ").title()
        
        # Renombrar columnas
        df = df.rename(columns=column_mapping)
        
        # Ordenar por año (descendente) y citaciones (descendente)
        try:
            df["Año"] = pd.to_numeric(df["Año"], errors="coerce")
            df = df.sort_values(by=["Año", "Citaciones"], ascending=[False, False])
        except:
            # Si hay error al ordenar, seguir sin ordenamiento
            pass
        
        # Exportar según el formato especificado
        if format.lower() == "csv":
            df.to_csv(output_file, index=False, encoding="utf-8-sig")  # utf-8-sig para compatibilidad con Excel
            print(f"Tabla exportada en formato CSV: {output_file}")
        elif format.lower() == "excel":
            df.to_excel(output_file, index=False, engine="openpyxl")
            print(f"Tabla exportada en formato Excel: {output_file}")
        else:
            print(f"Formato no soportado: {format}")
            return False
        
        return True
    
    except Exception as e:
        print(f"Error al crear la tabla de artículos: {str(e)}")
        return False


def export_articles_table(input_file: str, output_file: str, format: str = "csv") -> bool:
    """
    Función principal para exportar la tabla de artículos.
    
    Args:
        input_file: Ruta al archivo JSON con los artículos clasificados.
        output_file: Ruta de salida para la tabla.
        format: Formato de salida ("csv" o "excel").
        
    Returns:
        True si se completó con éxito, False en caso de error.
    """
    # Cargar artículos
    articles = load_articles(input_file)
    if not articles:
        return False
    
    # Crear tabla
    return create_articles_table(articles, output_file, format)


# Función principal
def main():
    # Configurar parser de argumentos
    parser = argparse.ArgumentParser(description="Exporta una tabla de artículos a CSV o Excel")
    
    parser.add_argument("--input", type=str, default="outputs/classified_results.json",
                       help="Ruta al archivo JSON con los artículos clasificados (default: outputs/classified_results.json)")
    
    parser.add_argument("--output", type=str, default="outputs/articles_table.csv",
                       help="Ruta de salida para la tabla (default: outputs/articles_table.csv)")
    
    parser.add_argument("--format", type=str, choices=["csv", "excel"], default="csv",
                       help="Formato de salida: csv o excel (default: csv)")
    
    # Parsear argumentos
    args = parser.parse_args()
    
    # Verificar la extensión del archivo de salida según el formato
    if args.format == "csv" and not args.output.lower().endswith(".csv"):
        args.output += ".csv"
    elif args.format == "excel" and not args.output.lower().endswith((".xlsx", ".xls")):
        args.output += ".xlsx"
    
    # Ejecutar la exportación
    success = export_articles_table(args.input, args.output, args.format)
    
    # Retornar código de salida
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    import sys
    sys.exit(exit_code)