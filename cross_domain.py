#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para generar una tabla de artículos que pertenecen a los tres dominios.
Este script analiza los resultados clasificados y crea una tabla formateada
con los artículos que están presentes en los tres dominios simultáneamente.
"""

import os
import json
import pandas as pd
import argparse
from typing import List, Dict, Any


def load_classified_articles(filepath: str) -> List[Dict[Any, Any]]:
    """
    Carga los artículos clasificados desde un archivo JSON.
    
    Args:
        filepath: Ruta al archivo JSON con los artículos clasificados.
        
    Returns:
        Lista de artículos clasificados.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            articles = json.load(file)
            print(f"Cargados {len(articles)} artículos del archivo {filepath}")
            return articles
    except Exception as e:
        print(f"Error al cargar los artículos: {str(e)}")
        return []


def filter_triple_domain_articles(articles: List[Dict[Any, Any]], domain_prefix: str = "in_") -> List[Dict[Any, Any]]:
    """
    Filtra los artículos que pertenecen a los tres dominios.
    
    Args:
        articles: Lista de artículos clasificados.
        domain_prefix: Prefijo utilizado para los campos de dominio.
        
    Returns:
        Lista de artículos que pertenecen a los tres dominios.
    """
    # Identificar las columnas de dominio
    if not articles:
        return []
    
    # Examinar el primer artículo para identificar campos de dominio
    sample_article = articles[0]
    domain_fields = [field for field in sample_article.keys() 
                    if field.startswith(domain_prefix) and field.endswith("_domain")]
    
    if len(domain_fields) < 3:
        print(f"Advertencia: Se encontraron menos de 3 dominios: {domain_fields}")
        return []
    
    # Si hay más de 3 dominios, tomamos los 3 primeros
    if len(domain_fields) > 3:
        domain_fields = domain_fields[:3]
        print(f"Utilizando los 3 primeros dominios: {domain_fields}")
    
    # Filtrar artículos que están en los tres dominios
    triple_domain_articles = []
    for article in articles:
        if all(article.get(field, 0) == 1 for field in domain_fields):
            triple_domain_articles.append(article)
    
    print(f"Se encontraron {len(triple_domain_articles)} artículos presentes en los tres dominios")
    return triple_domain_articles


def create_articles_dataframe(articles: List[Dict[Any, Any]], selected_fields: List[str] = None) -> pd.DataFrame:
    """
    Crea un DataFrame con los campos seleccionados de los artículos.
    
    Args:
        articles: Lista de artículos.
        selected_fields: Lista de campos a incluir (si es None, se incluyen todos).
        
    Returns:
        DataFrame con los campos seleccionados.
    """
    if not articles:
        return pd.DataFrame()
    
    # Si no se especifican campos, usar un conjunto predeterminado de campos importantes
    if selected_fields is None:
        selected_fields = [
            "title", "authors", "year", "journal", "doi", "source", 
            "citations", "ai_model_type", "uses_ai_ml"
        ]
    
    # Crear un DataFrame con todos los campos
    df = pd.DataFrame(articles)
    
    # Seleccionar solo los campos especificados que están presentes en el DataFrame
    available_fields = [field for field in selected_fields if field in df.columns]
    if set(available_fields) != set(selected_fields):
        missing_fields = set(selected_fields) - set(available_fields)
        print(f"Advertencia: Algunos campos seleccionados no están disponibles: {missing_fields}")
    
    # Formatear campos especiales
    df_selected = df[available_fields].copy()
    
    # Formatear autores si es una lista
    if "authors" in available_fields:
        df_selected["authors"] = df_selected["authors"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )
    
    return df_selected


def export_to_formats(df: pd.DataFrame, base_filename: str, formats: List[str] = ["csv", "xlsx", "html", "latex"]):
    """
    Exporta el DataFrame a múltiples formatos.
    
    Args:
        df: DataFrame a exportar.
        base_filename: Nombre base para los archivos de salida.
        formats: Lista de formatos a generar.
    """
    if df.empty:
        print("El DataFrame está vacío. No se generarán archivos de salida.")
        return
    
    # Crear carpeta de salida si no existe
    output_dir = os.path.dirname(base_filename) or "."
    os.makedirs(output_dir, exist_ok=True)
    
    # Exportar a cada formato solicitado
    for fmt in formats:
        try:
            if fmt.lower() == "csv":
                output_file = f"{base_filename}.csv"
                df.to_csv(output_file, index=False, encoding="utf-8")
                print(f"Tabla exportada a CSV: {output_file}")
                
            elif fmt.lower() == "xlsx":
                output_file = f"{base_filename}.xlsx"
                df.to_excel(output_file, index=False, engine="openpyxl")
                print(f"Tabla exportada a Excel: {output_file}")
                
            elif fmt.lower() == "html":
                output_file = f"{base_filename}.html"
                # Crear un HTML estilizado para mejor visualización
                html_content = """
                <html>
                <head>
                    <style>
                        table { border-collapse: collapse; width: 100%; }
                        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                        th { background-color: #f2f2f2; }
                        tr:nth-child(even) { background-color: #f9f9f9; }
                        tr:hover { background-color: #f1f1f1; }
                    </style>
                </head>
                <body>
                    <h2>Artículos presentes en los tres dominios</h2>
                """ + df.to_html(index=False) + """
                </body>
                </html>
                """
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"Tabla exportada a HTML: {output_file}")
                
            elif fmt.lower() == "latex":
                output_file = f"{base_filename}.tex"
                # Generar tabla LaTeX con estilo científico
                latex_content = df.to_latex(index=False, longtable=True, escape=False)
                # Mejorar el formato de la tabla LaTeX
                latex_content = latex_content.replace("\\begin{longtable}", "\\begin{longtable}{" + "l" * len(df.columns) + "}")
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(latex_content)
                print(f"Tabla exportada a LaTeX: {output_file}")
                
            elif fmt.lower() == "markdown":
                output_file = f"{base_filename}.md"
                # Generar tabla en formato Markdown
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("# Artículos presentes en los tres dominios\n\n")
                    f.write(df.to_markdown(index=False))
                print(f"Tabla exportada a Markdown: {output_file}")
                
            else:
                print(f"Formato no soportado: {fmt}")
                
        except Exception as e:
            print(f"Error al exportar a formato {fmt}: {str(e)}")


def main():
    """Función principal del script."""
    # Configurar parser de argumentos
    parser = argparse.ArgumentParser(description="Genera una tabla de artículos presentes en los tres dominios")
    
    parser.add_argument("--input", type=str, default="outputs/classified_results.json",
                       help="Ruta al archivo JSON con los artículos clasificados (default: outputs/classified_results.json)")
    
    parser.add_argument("--output", type=str, default="outputs/triple_domain_articles",
                       help="Ruta base para los archivos de salida (default: outputs/triple_domain_articles)")
    
    parser.add_argument("--formats", type=str, default="csv,xlsx,html,latex,markdown",
                       help="Formatos de salida separados por comas (default: csv,xlsx,html,latex,markdown)")
    
    parser.add_argument("--fields", type=str, default=None,
                       help="Campos a incluir en la tabla, separados por comas (default: campos predeterminados)")
    
    args = parser.parse_args()
    
    # Cargar artículos clasificados
    articles = load_classified_articles(args.input)
    if not articles:
        print("No se encontraron artículos para procesar.")
        return
    
    # Filtrar artículos en los tres dominios
    triple_domain_articles = filter_triple_domain_articles(articles)
    if not triple_domain_articles:
        print("No se encontraron artículos presentes en los tres dominios.")
        return
    
    # Determinar campos a incluir
    selected_fields = None
    if args.fields:
        selected_fields = [field.strip() for field in args.fields.split(",")]
    
    # Crear DataFrame
    df = create_articles_dataframe(triple_domain_articles, selected_fields)
    
    # Exportar a los formatos solicitados
    formats = [fmt.strip() for fmt in args.formats.split(",")]
    export_to_formats(df, args.output, formats)
    
    print("\nProceso completado con éxito.")
    print(f"Se encontraron {len(triple_domain_articles)} artículos presentes en los tres dominios.")


if __name__ == "__main__":
    main()