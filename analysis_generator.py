#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para generar análisis y visualizaciones de los resultados de la búsqueda y clasificación.
Produce figuras para su uso en un informe markdown posterior.

Este script:
1. Carga los resultados clasificados
2. Analiza la distribución temporal de publicaciones
3. Crea visualizaciones por dominio y características
4. Genera mapas de calor para análisis de co-ocurrencia
5. Visualiza modelos específicos de IA/ML mencionados
6. Guarda todas las figuras en una carpeta 'figures'
"""

import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple, Optional
import re
from wordcloud import WordCloud
import matplotlib.colors as mcolors
from matplotlib.ticker import MaxNLocator
import networkx as nx
from adjustText import adjust_text
import argparse
import warnings
import traceback

# Ignorar advertencias para una salida más limpia
warnings.filterwarnings("ignore")

# Configurar estilo de seaborn para gráficos más atractivos
sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 12})
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12

# Función auxiliar para extraer año como entero
def extract_year(year_value):
    """Extrae el año como entero, manejando diferentes formatos posibles."""
    if pd.isna(year_value):
        return None
    
    if isinstance(year_value, int):
        return year_value
    elif isinstance(year_value, str):
        try:
            # Intentar extraer los primeros 4 dígitos que parezcan un año
            match = re.search(r'(19|20)\d{2}', year_value)
            if match:
                return int(match.group(0))
        except:
            pass
    return None

class ResultsAnalyzer:
    """Clase para analizar y visualizar los resultados de la búsqueda y clasificación."""
    
    def __init__(self, classified_file: str, abstracts_file: Optional[str] = None, domain_stats_file: Optional[str] = None):
        """
        Inicializa el analizador de resultados.
        
        Args:
            classified_file: Ruta al archivo JSON con los artículos clasificados.
            abstracts_file: Ruta al archivo JSON con los resúmenes de los artículos (opcional).
            domain_stats_file: Ruta al archivo CSV con estadísticas de dominio (opcional).
        """
        self.classified_file = classified_file
        self.abstracts_file = abstracts_file
        self.domain_stats_file = domain_stats_file
        self.articles = []
        self.abstracts = {}
        self.domain_stats = {}
        self.df = None
        self.figures_dir = 'figures'
        
        # Crear carpeta para figuras si no existe
        os.makedirs(self.figures_dir, exist_ok=True)
        
        # Cargar datos
        self._load_data()
        
    def _load_data(self):
        """Carga los datos desde los archivos especificados."""
        # Cargar artículos clasificados
        try:
            with open(self.classified_file, 'r', encoding='utf-8') as f:
                self.articles = json.load(f)
                print(f"Cargados {len(self.articles)} artículos clasificados.")
                
                # Convertir a DataFrame para análisis más sencillo
                self.df = pd.DataFrame(self.articles)
                
                # Limpiar y convertir la columna de año
                if 'year' in self.df.columns:
                    self.df['year'] = self.df['year'].apply(extract_year)
                    # Filtrar artículos sin año
                    valid_years = self.df['year'].notna()
                    if valid_years.any():
                        self.df_with_years = self.df[valid_years].copy()
                        self.df_with_years['year'] = self.df_with_years['year'].astype(int)
                        print(f"De ellos, {len(self.df_with_years)} tienen información de año válida.")
                    else:
                        self.df_with_years = pd.DataFrame()
                        print("Ningún artículo tiene información de año válida.")
                else:
                    self.df_with_years = pd.DataFrame()
                    print("No se encontró la columna 'year' en los datos.")
                    
        except Exception as e:
            print(f"Error al cargar los artículos clasificados: {str(e)}")
            traceback.print_exc()
            self.articles = []
            self.df = pd.DataFrame()
            self.df_with_years = pd.DataFrame()
        
        # Cargar resúmenes si están disponibles
        if self.abstracts_file and os.path.exists(self.abstracts_file):
            try:
                with open(self.abstracts_file, 'r', encoding='utf-8') as f:
                    self.abstracts = json.load(f)
                    print(f"Cargados {len(self.abstracts)} resúmenes de artículos.")
            except Exception as e:
                print(f"Error al cargar los resúmenes: {str(e)}")
                self.abstracts = {}
        
        # Cargar estadísticas de dominio si están disponibles
        if self.domain_stats_file and os.path.exists(self.domain_stats_file):
            try:
                # Intentar diferentes separadores y manejar errores de formato
                try:
                    self.domain_stats = pd.read_csv(self.domain_stats_file)
                except:
                    try:
                        self.domain_stats = pd.read_csv(self.domain_stats_file, sep=';')
                    except:
                        try:
                            # Intento con un parser más flexible
                            self.domain_stats = pd.read_csv(self.domain_stats_file, sep=None, engine='python')
                        except Exception as e:
                            print(f"No se pudo cargar el archivo CSV con formatos estándar: {str(e)}")
                            self.domain_stats = {}
                            
                if not isinstance(self.domain_stats, dict):  # Verificar que se cargó como DataFrame
                    print(f"Cargadas estadísticas de dominio desde {self.domain_stats_file}.")
            except Exception as e:
                print(f"Error al cargar las estadísticas de dominio: {str(e)}")
                self.domain_stats = {}

    def check_data_validity(self) -> bool:
        """Verifica si hay datos suficientes para el análisis."""
        if len(self.articles) == 0 or self.df.empty:
            print("No hay datos suficientes para realizar análisis.")
            return False
        return True

    def generate_all_figures(self):
        """Genera todas las figuras de análisis."""
        if not self.check_data_validity():
            return
        
        print("\nGenerando figuras de análisis...")
        
        try:
            # 1. Análisis temporal (solo si hay datos de años)
            if not self.df_with_years.empty:
                self.plot_publications_by_year()
                self.plot_publications_trend_by_domain()
                self.plot_citations_by_year()
            else:
                print("No se generarán visualizaciones temporales por falta de datos de año válidos.")
            
            # 2. Análisis de dominios
            self.plot_domain_distribution()
            self.plot_domain_overlap()
            
            # 2.5. Análisis por fuente de datos
            self.plot_source_distribution()
            
            # 3. Análisis de contenido
            self.plot_top_journals()
            self.plot_top_authors()
            self.plot_ai_models_distribution()
            
            # 4. Análisis de temas (solo si hay resúmenes)
            if len(self.abstracts) > 0:
                self.plot_wordcloud_by_domain()
                self.plot_topic_co_occurrence()
            else:
                print("No se generarán nubes de palabras por falta de resúmenes.")
            
            # 5. Análisis de artículos más citados
            self.plot_top_cited_papers()
            
            # 6. Análisis de redes (si es posible)
            self.plot_collaboration_network()
            
            print(f"\nTodas las figuras han sido guardadas en la carpeta '{self.figures_dir}'.")
        except Exception as e:
            print(f"Error durante la generación de figuras: {str(e)}")
            traceback.print_exc()

    def plot_publications_by_year(self):
        """Grafica la distribución de publicaciones por año."""
        try:
            if self.df_with_years.empty:
                print("No hay información de año válida para visualizar la distribución de publicaciones.")
                return
            
            plt.figure(figsize=(12, 6))
            
            # Crear un contador de publicaciones por año
            years_count = self.df_with_years['year'].value_counts().sort_index()
            
            # Gráfico de barras
            ax = years_count.plot(kind='bar', color='skyblue')
            
            # Añadir línea de tendencia
            ax2 = ax.twinx()
            years_count.plot(ax=ax2, kind='line', marker='o', color='darkblue', linewidth=2)
            ax2.set_ylim(0, years_count.max() * 1.2)
            ax2.grid(False)
            
            plt.title('Número de Publicaciones por Año', fontsize=16)
            ax.set_xlabel('Año', fontsize=14)
            ax.set_ylabel('Cantidad de Publicaciones', fontsize=14)
            
            # Ajustar etiquetas del eje x para mejor legibilidad
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'publications_by_year.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Publicaciones por año")
        except Exception as e:
            print(f"Error al generar la gráfica de publicaciones por año: {str(e)}")

    def plot_source_distribution(self):
        """Grafica la distribución de artículos por fuente de datos."""
        try:
            if 'source' not in self.df.columns:
                print("No hay información de fuente de datos para visualizar.")
                return
            
            # Contar artículos por fuente
            source_counts = self.df['source'].value_counts()
            
            if source_counts.empty:
                print("No hay datos de fuente de artículos para visualizar.")
                return
            
            # Crear gráfico
            plt.figure(figsize=(10, 6))
            
            # Colores para las diferentes fuentes
            colors = {
                'Crossref': 'skyblue',
                'Semantic Scholar': 'lightgreen',
                'Science Direct': 'salmon',
                'Scopus': 'lightcoral',
                'Google Scholar': 'gold'
            }
            
            # Colores predeterminados para fuentes no especificadas
            default_colors = plt.cm.Set3(np.linspace(0, 1, len(source_counts)))
            
            # Asignar colores a las barras
            bar_colors = [colors.get(source, default_colors[i % len(default_colors)]) 
                        for i, source in enumerate(source_counts.index)]
            
            # Crear gráfico de barras
            bars = plt.bar(source_counts.index, source_counts.values, color=bar_colors)
            
            # Añadir etiquetas con valores
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2, height + 0.5, f'{int(height)}', 
                        ha='center', va='bottom', fontsize=12)
            
            plt.title('Distribución de Artículos por Fuente de Datos', fontsize=16)
            plt.xlabel('Fuente', fontsize=14)
            plt.ylabel('Número de Artículos', fontsize=14)
            plt.xticks(rotation=0)  # Horizontal
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'source_distribution.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Distribución por fuente de datos")
        except Exception as e:
            print(f"Error al generar la gráfica de distribución por fuente: {str(e)}")

    def plot_publications_trend_by_domain(self):
        """Grafica la tendencia de publicaciones por dominio a lo largo del tiempo."""
        try:
            if self.df_with_years.empty:
                print("No hay información de año válida para visualizar tendencias por dominio.")
                return
                
            # Verificar columnas de dominio
            domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
            
            if not domain_columns:
                print("No hay información de dominios para visualizar tendencias.")
                return
            
            # Preparar datos
            df_domains = self.df_with_years[['year'] + domain_columns].copy()
            
            # Para cada año y dominio, contar el número de publicaciones
            grouped_data = {}
            
            for domain_col in domain_columns:
                # Nombre legible del dominio
                domain_name = domain_col.replace('in_', '').replace('_domain', '').capitalize()
                
                # Agrupar por año y contar
                time_series = df_domains[df_domains[domain_col] == 1].groupby('year').size()
                grouped_data[domain_name] = time_series
            
            # Crear gráfico
            plt.figure(figsize=(14, 7))
            
            # Colormap
            colors = plt.cm.tab10(np.linspace(0, 1, len(domain_columns)))
            
            # Plotear cada dominio
            for i, (domain_name, time_series) in enumerate(grouped_data.items()):
                plt.plot(time_series.index, time_series.values, marker='o', linewidth=2, 
                         color=colors[i], label=domain_name)
            
            plt.title('Evolución de Publicaciones por Dominio', fontsize=16)
            plt.xlabel('Año', fontsize=14)
            plt.ylabel('Cantidad de Publicaciones', fontsize=14)
            plt.legend(fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            
            # Ajustar escala del eje y para mostrar números enteros
            plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
            
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'publications_trend_by_domain.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Tendencia de publicaciones por dominio")
        except Exception as e:
            print(f"Error al generar la gráfica de tendencias por dominio: {str(e)}")

    def plot_domain_distribution(self):
        """Grafica la distribución de publicaciones por dominio."""
        try:
            # Verificar columnas de dominio
            domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
            
            if not domain_columns:
                print("No hay información de dominios para visualizar distribución.")
                return
            
            # Sumar ocurrencias de cada dominio
            domain_counts = {}
            for col in domain_columns:
                domain_name = col.replace('in_', '').replace('_domain', '').capitalize()
                domain_counts[domain_name] = self.df[col].sum()
            
            # Ordenar por frecuencia
            domain_counts = {k: v for k, v in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True)}
            
            # Verificar que hay datos para mostrar
            if not domain_counts or all(count == 0 for count in domain_counts.values()):
                print("No hay datos de dominio válidos para visualizar distribución.")
                return
                
            # Crear gráfico
            plt.figure(figsize=(12, 8))
            
            # Definir colores
            colors = plt.cm.viridis(np.linspace(0, 0.8, len(domain_counts)))
            
            # Crear gráfico de barras horizontales
            bars = plt.barh(list(domain_counts.keys()), list(domain_counts.values()), color=colors)
            
            # Añadir etiquetas con valores
            for bar in bars:
                width = bar.get_width()
                plt.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'{int(width)}', 
                        ha='left', va='center', fontsize=12)
            
            plt.title('Distribución de Publicaciones por Dominio', fontsize=16)
            plt.xlabel('Número de Publicaciones', fontsize=14)
            plt.ylabel('Dominio', fontsize=14)
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'domain_distribution.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Distribución por dominio")
        except Exception as e:
            print(f"Error al generar la gráfica de distribución por dominio: {str(e)}")

    def plot_domain_overlap(self):
        """Crea un diagrama de Venn/superposición para los tres dominios principales."""
        try:
            # Verificar columnas de dominio
            domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
            
            if len(domain_columns) < 2:
                print("Se necesitan al menos 2 dominios para analizar superposiciones.")
                return
            
            # Limitar a los 3 primeros dominios si hay más
            if len(domain_columns) > 3:
                domain_columns = domain_columns[:3]
            
            # Intentar importar matplotlib_venn
            try:
                import matplotlib_venn
            except ImportError:
                print("No se pudo importar matplotlib_venn. No se generará el diagrama de superposición.")
                print("Para instalarlo, ejecute: pip install matplotlib-venn")
                return
                
            from matplotlib_venn import venn2, venn3
                
            # Contar superposiciones
            if len(domain_columns) == 2:
                # Caso de 2 dominios
                domain1 = domain_columns[0]
                domain2 = domain_columns[1]
                
                domain1_only = self.df[(self.df[domain1] == 1) & (self.df[domain2] == 0)].shape[0]
                domain2_only = self.df[(self.df[domain1] == 0) & (self.df[domain2] == 1)].shape[0]
                both_domains = self.df[(self.df[domain1] == 1) & (self.df[domain2] == 1)].shape[0]
                
                # Crear gráfico simple de Venn
                plt.figure(figsize=(10, 6))
                
                # Nombres legibles
                d1_name = domain1.replace('in_', '').replace('_domain', '').capitalize()
                d2_name = domain2.replace('in_', '').replace('_domain', '').capitalize()
                
                v = venn2(subsets=(domain1_only, domain2_only, both_domains), 
                         set_labels=(d1_name, d2_name))
                
                # Verificar que se generó el diagrama correctamente
                if v:
                    # Personalizar colores
                    if v.get_patch_by_id('10'):
                        v.get_patch_by_id('10').set_color('skyblue')
                    if v.get_patch_by_id('01'):
                        v.get_patch_by_id('01').set_color('lightgreen')
                    if v.get_patch_by_id('11'):
                        v.get_patch_by_id('11').set_color('sandybrown')
                    
                    plt.title('Superposición entre Dominios', fontsize=16)
                else:
                    print("No se pudo generar el diagrama de Venn de 2 dominios.")
                    return
                
            elif len(domain_columns) == 3:
                # Caso de 3 dominios
                domain1 = domain_columns[0]
                domain2 = domain_columns[1]
                domain3 = domain_columns[2]
                
                # Contar ocurrencias para cada combinación
                d1_only = self.df[(self.df[domain1] == 1) & (self.df[domain2] == 0) & (self.df[domain3] == 0)].shape[0]
                d2_only = self.df[(self.df[domain1] == 0) & (self.df[domain2] == 1) & (self.df[domain3] == 0)].shape[0]
                d3_only = self.df[(self.df[domain1] == 0) & (self.df[domain2] == 0) & (self.df[domain3] == 1)].shape[0]
                
                d1_d2 = self.df[(self.df[domain1] == 1) & (self.df[domain2] == 1) & (self.df[domain3] == 0)].shape[0]
                d1_d3 = self.df[(self.df[domain1] == 1) & (self.df[domain2] == 0) & (self.df[domain3] == 1)].shape[0]
                d2_d3 = self.df[(self.df[domain1] == 0) & (self.df[domain2] == 1) & (self.df[domain3] == 1)].shape[0]
                
                all_three = self.df[(self.df[domain1] == 1) & (self.df[domain2] == 1) & (self.df[domain3] == 1)].shape[0]
                
                # Crear gráfico de Venn
                plt.figure(figsize=(10, 6))
                
                # Nombres legibles
                d1_name = domain1.replace('in_', '').replace('_domain', '').capitalize()
                d2_name = domain2.replace('in_', '').replace('_domain', '').capitalize()
                d3_name = domain3.replace('in_', '').replace('_domain', '').capitalize()
                
                v = venn3(subsets=(d1_only, d2_only, d1_d2, d3_only, d1_d3, d2_d3, all_three),
                         set_labels=(d1_name, d2_name, d3_name))
                
                # Verificar que se generó el diagrama correctamente
                if v:
                    # Personalizar colores si los patches existen
                    patch_100 = v.get_patch_by_id('100')
                    if patch_100 is not None:
                        patch_100.set_color('skyblue')
    
                    patch_010 = v.get_patch_by_id('010')
                    if patch_010 is not None:
                        patch_010.set_color('lightgreen')
    
                    patch_001 = v.get_patch_by_id('001')
                    if patch_001 is not None:
                        patch_001.set_color('salmon')
                    
                    plt.title('Superposición entre los Tres Dominios', fontsize=16)
                else:
                    print("No se pudo generar el diagrama de Venn de 3 dominios.")
                    return
            
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'domain_overlap.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Superposición de dominios")
        except Exception as e:
            print(f"Error al generar el diagrama de superposición de dominios: {str(e)}")
            traceback.print_exc()

    def plot_top_journals(self, top_n: int = 15):
        """Grafica las principales revistas por número de publicaciones."""
        try:
            if 'journal' not in self.df.columns:
                print("No hay información de revistas para visualizar.")
                return
            
            # Excluir valores nulos o vacíos
            valid_journals = self.df['journal'].dropna()
            valid_journals = valid_journals[valid_journals.str.strip() != '']
            
            if valid_journals.empty:
                print("No hay información válida de revistas para visualizar.")
                return
                
            # Contar publicaciones por revista
            journal_counts = valid_journals.value_counts().head(top_n)
            
            if journal_counts.empty:
                print("No hay suficientes datos de revistas para visualizar.")
                return
            
            # Crear gráfico
            plt.figure(figsize=(12, 8))
            
            # Definir colores
            colors = plt.cm.cool(np.linspace(0, 0.8, len(journal_counts)))
            
            # Acortar nombres muy largos
            journal_names = [j[:50] + '...' if len(j) > 50 else j for j in journal_counts.index]
            
            # Gráfico de barras horizontales
            bars = plt.barh(journal_names, journal_counts.values, color=colors)
            
            # Añadir etiquetas con valores
            for bar in bars:
                width = bar.get_width()
                plt.text(width + 0.1, bar.get_y() + bar.get_height()/2, f'{int(width)}', 
                        ha='left', va='center', fontsize=10)
            
            plt.title(f'Top {len(top_authors)} Autores por Número de Publicaciones', fontsize=16)
            plt.xlabel('Número de Publicaciones', fontsize=14)
            plt.ylabel('Autor', fontsize=14)
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'top_authors.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Principales autores")
        except Exception as e:
            print(f"Error al generar la gráfica de autores principales: {str(e)}")

    def plot_ai_models_distribution(self):
        """Grafica la distribución de modelos de IA mencionados en los artículos."""
        try:
            # Buscar columnas relacionadas con modelos de IA
            model_columns = [col for col in self.df.columns if 'model' in col.lower() and 'type' in col.lower()]
            
            if not model_columns:
                print("No hay información de modelos de IA para visualizar.")
                return
            
            # Seleccionar la primera columna de modelos encontrada
            model_col = model_columns[0]
            
            # Excluir valores nulos o vacíos
            valid_models = self.df[model_col].dropna()
            valid_models = valid_models[valid_models.str.strip() != '']
            
            # Contar ocurrencias de cada modelo
            model_counts = valid_models.value_counts()
            
            # Filtrar "No mencionado" y nombres vacíos
            model_counts = model_counts[(model_counts.index != "No mencionado") & 
                                      (model_counts.index != "Not mentioned") & 
                                      (model_counts.index.str.strip() != '')]
            
            if model_counts.empty or model_counts.sum() == 0:
                print("No hay suficientes datos de modelos de IA para visualizar.")
                return
            
            # Tomar los top 15 modelos
            top_models = model_counts.head(15)
            
            # Crear gráfico
            plt.figure(figsize=(12, 8))
            
            # Definir colores
            colors = plt.cm.viridis(np.linspace(0, 0.8, len(top_models)))
            
            # Gráfico de barras
            bars = plt.bar(top_models.index, top_models.values, color=colors)
            
            # Añadir etiquetas con valores
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2, height + 0.1, f'{int(height)}', 
                        ha='center', va='bottom', fontsize=10)
            
            plt.title('Modelos de IA/ML Mencionados en los Artículos', fontsize=16)
            plt.xlabel('Modelo', fontsize=14)
            plt.ylabel('Número de Menciones', fontsize=14)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'ai_models_distribution.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Distribución de modelos de IA")
        except Exception as e:
            print(f"Error al generar la gráfica de distribución de modelos de IA: {str(e)}")
            
            plt.title(f'Top {len(journal_counts)} Revistas por Número de Publicaciones', fontsize=16)
            plt.xlabel('Número de Publicaciones', fontsize=14)
            plt.ylabel('Revista', fontsize=14)
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'top_journals.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Principales revistas")
        except Exception as e:
            print(f"Error al generar la gráfica de revistas principales: {str(e)}")

    def plot_top_authors(self, top_n: int = 20):
        """Grafica los principales autores por número de publicaciones."""
        try:
            if 'authors' not in self.df.columns:
                print("No hay información de autores para visualizar.")
                return
            
            # Extraer todos los autores
            all_authors = []
            for authors_list in self.df['authors']:
                if isinstance(authors_list, list):
                    all_authors.extend([a for a in authors_list if a])  # Excluir autores vacíos
                elif isinstance(authors_list, str):
                    # Manejar caso de autores como cadena de texto
                    author_names = [name.strip() for name in authors_list.split(',') if name.strip()]
                    all_authors.extend(author_names)
            
            if not all_authors:
                print("No hay información de autores válida para visualizar.")
                return
                
            # Contar ocurrencias de cada autor
            author_counts = Counter(all_authors)
            
            # Filtrar autores con nombre vacío
            if '' in author_counts:
                del author_counts['']
            
            # Obtener los top autores
            top_authors = author_counts.most_common(top_n)
            
            if not top_authors:
                print("No hay suficientes datos de autores para visualizar.")
                return
            
            # Crear gráfico
            plt.figure(figsize=(12, 10))
            
            # Definir colores
            colors = plt.cm.autumn(np.linspace(0, 0.8, len(top_authors)))
            
            # Nombres e valores
            names = [x[0] if len(x[0]) < 25 else x[0][:22] + '...' for x in top_authors]
            values = [x[1] for x in top_authors]
            
            # Gráfico de barras horizontales
            bars = plt.barh(names, values, color=colors)
            
            # Añadir etiquetas con valores
            for bar in bars:
                width = bar.get_width()
                plt.text(width + 0.1, bar.get_y() + bar.get_height()/2, f'{int(width)}', 
                        ha='left', va='center', fontsize=10)
            
            plt.title(f'Top {len(top_authors)} Autores por Número de Publicaciones', fontsize=16)
            plt.xlabel('Número de Publicaciones', fontsize=14)
            plt.ylabel('Autor', fontsize=14)
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, 'top_authors.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Generada figura: Principales autores")
        except Exception as e:
            print(f"Error al generar la gráfica de autores principales: {str(e)}")

    