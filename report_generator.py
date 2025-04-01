#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script genérico para generar un informe en formato Markdown basado en visualizaciones bibliométricas.
Esta versión:
1. Es adaptable a cualquier tema de revisión bibliométrica
2. Se enfoca en presentar las figuras con explicaciones breves
3. Permite personalizar el título y la introducción
4. Detecta y organiza automáticamente las visualizaciones disponibles
"""

import os
import json
import argparse
import datetime
import subprocess
from typing import Dict, List, Any, Optional
import re

class GenericReportGenerator:
    """Clase para generar un informe en formato Markdown genérico basado en visualizaciones."""
    
    def __init__(self, 
                 stats_file: str, 
                 figures_dir: str, 
                 output_file: str = "report.md",
                 report_title: str = "Análisis Bibliométrico",
                 report_intro: str = None):
        """
        Inicializa el generador de informes.
        
        Args:
            stats_file: Ruta al archivo JSON con estadísticas generadas.
            figures_dir: Carpeta donde se encuentran las figuras.
            output_file: Nombre del archivo markdown a generar.
            report_title: Título personalizado para el informe.
            report_intro: Introducción personalizada para el informe.
        """
        self.stats_file = stats_file
        self.figures_dir = figures_dir
        self.output_file = output_file
        self.report_title = report_title
        self.report_intro = report_intro
        self.stats = {}
        self.figures = []
        
        # Cargar datos
        self._load_data()
        
    def _load_data(self):
        """Carga las estadísticas y lista las figuras disponibles."""
        # Cargar estadísticas
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    # Leer el contenido primero para diagnóstico
                    content = f.read()
                    try:
                        self.stats = json.loads(content)
                        print(f"Estadísticas cargadas desde {self.stats_file}")
                    except json.JSONDecodeError as json_err:
                        # Mostrar más detalles sobre el error de formato JSON
                        line_no = json_err.lineno
                        col_no = json_err.colno
                        print(f"Error en el formato JSON: {json_err}")
                        
                        # Mostrar la línea problemática y señalar el error
                        lines = content.split('\n')
                        if 0 <= line_no-1 < len(lines):
                            print(f"Línea problemática ({line_no}): {lines[line_no-1]}")
                            print(f"{' ' * (col_no-1)}^ Error aquí")
                        
                        # Sugerencias para solucionar el problema
                        print("Sugerencias para solucionar el error:")
                        print("1. Comprueba que el archivo JSON tiene el formato correcto")
                        print("2. Verifica que no haya comas extra o faltantes")
                        print("3. Asegúrate de que los strings estén correctamente entrecomillados")
                        
                        self.stats = {}
            else:
                print(f"No se encontró el archivo de estadísticas: {self.stats_file}")
                self.stats = {}
        except Exception as e:
            print(f"Error al cargar estadísticas: {str(e)}")
            self.stats = {}
                
        # Listar figuras disponibles
        if os.path.exists(self.figures_dir):
            self.figures = [f for f in os.listdir(self.figures_dir) if f.endswith(('.png', '.jpg', '.svg'))]
            print(f"Se encontraron {len(self.figures)} figuras en {self.figures_dir}")
        else:
            print(f"No se encontró la carpeta de figuras: {self.figures_dir}")
            self.figures = []
    
    def _get_figure_path(self, figure_name: str) -> str:
        """Obtiene la ruta relativa de una figura específica."""
        return os.path.join(self.figures_dir, figure_name)
    
    def generate_report(self):
        """Genera el informe simplificado en formato Markdown."""
        print(f"\nGenerando informe en formato Markdown: {self.output_file}...")
        
        # Crear texto del informe
        report_text = []
        
        # Agregar encabezado
        report_text.append(self._generate_header())
        
        # Agregar secciones de figuras con breves explicaciones
        report_text.append(self._generate_figures_section())
        
        # Unir todo el texto
        full_report = "\n\n".join(report_text)
        
        # Guardar informe
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(full_report)
            print(f"Informe generado con éxito en: {self.output_file}")
        except Exception as e:
            print(f"Error al guardar el informe: {str(e)}")
            
        return full_report
        
    def _generate_header(self) -> str:
        """Genera el encabezado del informe."""
        date = datetime.datetime.now().strftime("%d de %B de %Y")
        
        # Usar el título personalizado o el predeterminado
        title = self.report_title
        
        header = f"""# {title}

**Fecha del informe:** {date}

---
"""
        # Agregar información sobre fuentes si está disponible
        if self.stats and 'source_counts' in self.stats:
            header += "## Resumen de Fuentes\n\n"
            header += "Los artículos analizados en este informe provienen de las siguientes fuentes:\n\n"
            
            source_counts = self.stats['source_counts']
            for source, count in source_counts.items():
                header += f"- **{source}**: {count} artículos\n"
            
            # Verificar si hay artículos de Google Scholar
            if 'Google Scholar' in source_counts and source_counts['Google Scholar'] > 0:
                header += f"\n**Nota**: Los {source_counts['Google Scholar']} artículos de Google Scholar fueron integrados con el resto de resultados.\n"
            
            header += f"\n**Total de artículos**: {self.stats.get('total_articles', 'N/A')}\n\n"
            header += "---\n\n"
        
        # Agregar introducción personalizada si se proporcionó
        if self.report_intro:
            header += f"{self.report_intro}\n\n"
        else:
            header += """## Introducción

    Este informe presenta las visualizaciones generadas a partir del análisis bibliométrico.
    Cada figura está acompañada de una breve descripción.

    """
        return header
    
    def _generate_figures_section(self) -> str:
        """Genera una sección que muestra todas las figuras disponibles con breves descripciones."""
        section = "## Visualizaciones del Análisis\n\n"
        
        # Comprobar si hay figuras
        if not self.figures:
            return section + "No se encontraron visualizaciones para mostrar.\n"
        
        # Organizar figuras por categorías
        figure_categories = self._categorize_figures()
        
        # Crear sección para cada categoría
        for category, figs in figure_categories.items():
            if figs:  # Solo agregar categorías con figuras
                section += f"### {category}\n\n"
                for fig in figs:
                    title = self._generate_figure_title(fig)
                    description = self._generate_figure_description(fig)
                    
                    section += f"#### {title}\n\n"
                    section += f"![{title}]({self._get_figure_path(fig)})\n\n"
                    section += f"{description}\n\n"
        
        return section
    
    def _categorize_figures(self) -> Dict[str, List[str]]:
        """Organiza las figuras en categorías por nombre."""
        categories = {
            "Análisis Temporal": [],
            "Distribución por Dominios": [],
            "Fuentes de Datos": [],  # Nueva categoría
            "Análisis de Contenido": [],
            "Análisis de Impacto": [],
            "Análisis de Colaboración": [],
            "Términos y Temas": [],
            "Otros Análisis": []
        }
        
        for fig in self.figures:
            fig_lower = fig.lower()
            
            # Clasificar por patrones en el nombre
            if any(term in fig_lower for term in ['year', 'annual', 'trend', 'temporal', 'evolution']):
                categories["Análisis Temporal"].append(fig)
            elif any(term in fig_lower for term in ['domain', 'area', 'field', 'category', 'distribution', 'overlap']):
                # Excepción para la distribución por fuente
                if 'source' in fig_lower:
                    categories["Fuentes de Datos"].append(fig)
                else:
                    categories["Distribución por Dominios"].append(fig)
            elif any(term in fig_lower for term in ['source', 'database', 'scopus', 'crossref', 'semantic']):
                categories["Fuentes de Datos"].append(fig)
            elif any(term in fig_lower for term in ['journal', 'author', 'country', 'institution', 'model', 'method']):
                categories["Análisis de Contenido"].append(fig)
            elif any(term in fig_lower for term in ['citation', 'impact', 'cited']):
                categories["Análisis de Impacto"].append(fig)
            elif any(term in fig_lower for term in ['collab', 'network', 'co_author', 'coauthor']):
                categories["Análisis de Colaboración"].append(fig)
            elif any(term in fig_lower for term in ['wordcloud', 'keyword', 'term', 'topic', 'co_occurrence']):
                categories["Términos y Temas"].append(fig)
            else:
                categories["Otros Análisis"].append(fig)
                
        # Eliminar categorías vacías
        return {k: v for k, v in categories.items() if v}
    
    def _generate_figure_title(self, figure_name: str) -> str:
        """Genera un título descriptivo para la figura basado en su nombre de archivo."""
        # Eliminar extensión y reemplazar caracteres especiales
        title = os.path.splitext(figure_name)[0]
        title = title.replace('_', ' ').replace('-', ' ')
        
        # Capitalizar cada palabra
        words = title.split()
        title = ' '.join(word.capitalize() for word in words)
        
        return title
    
    def _generate_figure_description(self, figure_name: str) -> str:
        """Genera una descripción genérica para la figura basada en su nombre."""
        fig_lower = figure_name.lower()
        
        # Biblioteca de descripciones generales basadas en patrones en el nombre del archivo
        if 'year' in fig_lower or 'annual' in fig_lower:
            return "Muestra la evolución temporal de publicaciones a lo largo del período analizado."
        elif 'trend' in fig_lower:
            return "Visualiza las tendencias de publicación a lo largo del tiempo."
        elif 'domain_distribution' in fig_lower:
            return "Representa la distribución de publicaciones entre los diferentes dominios o áreas temáticas."
        elif 'source_distribution' in fig_lower:
            return "Muestra la distribución de artículos por fuente de datos (Crossref, Semantic Scholar, Science Direct/Scopus y Google Scholar)."
        elif 'sources_by_year' in fig_lower:
            return "Ilustra la contribución de cada fuente de datos (incluyendo Google Scholar) a lo largo del tiempo."
        elif 'domain_overlap' in fig_lower or 'venn' in fig_lower:
            return "Ilustra el solapamiento entre diferentes dominios o áreas temáticas."
        elif 'journal' in fig_lower:
            return "Presenta las principales revistas científicas con publicaciones en el área estudiada."
        elif 'author' in fig_lower:
            return "Muestra los autores más prolíficos en el campo analizado."
        elif 'ai_models_by_source' in fig_lower:
            return "Compara la distribución de modelos de IA mencionados según las diferentes fuentes de datos."
        elif 'country' in fig_lower:
            return "Ilustra la distribución geográfica de las publicaciones por país."
        elif 'institution' in fig_lower:
            return "Presenta las instituciones líderes en investigación en el área analizada."
        elif 'model' in fig_lower or 'method' in fig_lower:
            return "Muestra la distribución de métodos o modelos utilizados en las publicaciones."
        elif 'citation' in fig_lower or 'cited' in fig_lower:
            return "Visualiza el impacto de las publicaciones según sus citaciones."
        elif 'collab' in fig_lower or 'network' in fig_lower:
            return "Representa la red de colaboración entre autores o instituciones."
        elif 'wordcloud' in fig_lower:
            return "Muestra los términos más frecuentes en las publicaciones analizadas."
        elif 'keyword' in fig_lower:
            return "Presenta las palabras clave más utilizadas en las publicaciones."
        elif 'co_occurrence' in fig_lower or 'cooccurrence' in fig_lower:
            return "Visualiza qué temas o términos tienden a aparecer juntos en las publicaciones."
        else:
            return "Visualización generada a partir del análisis bibliométrico."
        
    def convert_to_pdf(self, pandoc_path: Optional[str] = None):
        """
        Convierte el informe de Markdown a PDF usando Pandoc (si está disponible).
        
        Args:
            pandoc_path: Ruta al ejecutable de Pandoc (opcional).
        """
        # Verificar si existe el archivo markdown
        if not os.path.exists(self.output_file):
            print(f"No se encontró el archivo markdown: {self.output_file}")
            return False
        
        # Determinar ruta de Pandoc
        if not pandoc_path:
            pandoc_path = "pandoc"  # Asumir que está en PATH
        
        # Generar nombre de archivo de salida
        pdf_file = self.output_file.replace(".md", ".pdf")
        
        try:
            # Construir comando para Pandoc
            cmd = [
                pandoc_path,
                self.output_file,
                "-o", pdf_file,
                "--pdf-engine=xelatex",
                "-V", "geometry:margin=1in",
                "--toc"  # Incluir tabla de contenidos
            ]
            
            # Ejecutar Pandoc
            print(f"Convirtiendo a PDF con Pandoc: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            print(f"Informe PDF generado con éxito en: {pdf_file}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error al ejecutar Pandoc: {e}")
            print(f"Output: {e.stdout}")
            print(f"Error: {e.stderr}")
            return False
            
        except FileNotFoundError:
            print(f"No se encontró Pandoc. Asegúrese de que Pandoc está instalado y disponible en PATH.")
            return False


def main():
    parser = argparse.ArgumentParser(description='Genera un informe genérico en formato Markdown basado en visualizaciones bibliométricas.')
    
    parser.add_argument('--stats-file', type=str, default='figures/statistics.json',
                       help='Ruta al archivo JSON con estadísticas generadas')
    
    parser.add_argument('--figures-dir', type=str, default='figures',
                       help='Carpeta donde se encuentran las figuras generadas')
    
    parser.add_argument('--output-file', type=str, default='report.md',
                       help='Nombre del archivo markdown a generar')
    
    parser.add_argument('--title', type=str, default='Análisis Bibliométrico',
                       help='Título personalizado para el informe')
    
    parser.add_argument('--intro-file', type=str, default=None,
                       help='Archivo con texto de introducción personalizado')
    
    parser.add_argument('--convert-to-pdf', action='store_true',
                       help='Convertir el informe a PDF usando Pandoc (si está disponible)')
    
    parser.add_argument('--pandoc-path', type=str, default=None,
                       help='Ruta al ejecutable de Pandoc (opcional)')
    
    args = parser.parse_args()
    
    print("\n====== INICIANDO GENERACIÓN DE INFORME BIBLIOMÉTRICO ======\n")
    
    # Cargar introducción personalizada si se proporcionó un archivo
    intro_text = None
    if args.intro_file and os.path.exists(args.intro_file):
        try:
            with open(args.intro_file, 'r', encoding='utf-8') as f:
                intro_text = f.read()
            print(f"Introducción personalizada cargada desde: {args.intro_file}")
        except Exception as e:
            print(f"Error al cargar la introducción: {str(e)}")
    
    # Verificar si existe el archivo de estadísticas
    if not os.path.exists(args.stats_file):
        print(f"ADVERTENCIA: No se encontró el archivo de estadísticas: {args.stats_file}")
        print("El informe se generará con información limitada.")
    
    # Verificar si existe la carpeta de figuras
    if not os.path.exists(args.figures_dir):
        print(f"ADVERTENCIA: No se encontró la carpeta de figuras: {args.figures_dir}")
        print("El informe se generará sin figuras.")
    
    # Crear generador de informes
    report_generator = GenericReportGenerator(
        stats_file=args.stats_file,
        figures_dir=args.figures_dir,
        output_file=args.output_file,
        report_title=args.title,
        report_intro=intro_text
    )
    
    # Generar informe
    report_generator.generate_report()
    
    # Convertir a PDF si se solicita
    if args.convert_to_pdf:
        report_generator.convert_to_pdf(pandoc_path=args.pandoc_path)
    
    print("\n====== GENERACIÓN DE INFORME COMPLETADA ======")


if __name__ == "__main__":
    main()