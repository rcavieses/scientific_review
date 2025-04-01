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
                    self.df = self.df[self.df['year'].notna()]
                    self.df['year'] = self.df['year'].astype(int)
        except Exception as e:
            print(f"Error al cargar los artículos clasificados: {str(e)}")
            self.articles = []
            self.df = pd.DataFrame()
        
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
                self.domain_stats = pd.read_csv(self.domain_stats_file)
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
        
        # 1. Análisis temporal
        self.plot_publications_by_year()
        self.plot_publications_trend_by_domain()
        
        # 2. Análisis de dominios
        self.plot_domain_distribution()
        self.plot_domain_overlap()
        
        # 2.5. Análisis por fuente de datos (Nueva función)
        self.plot_source_distribution()
        
        # 3. Análisis de contenido
        self.plot_top_journals()
        self.plot_top_authors()
        self.plot_ai_models_distribution()
        
        # 4. Análisis de temas
        if len(self.abstracts) > 0:
            self.plot_wordcloud_by_domain()
            self.plot_topic_co_occurrence()
        
        # 5. Análisis de citaciones
        self.plot_citations_by_year()
        self.plot_top_cited_papers()
        
        # 6. Análisis de redes (si es posible)
        self.plot_collaboration_network()
        
        print(f"\nTodas las figuras han sido guardadas en la carpeta '{self.figures_dir}'.")

    def plot_publications_by_year(self):
        """Grafica la distribución de publicaciones por año."""
        if 'year' not in self.df.columns:
            print("No hay información de año para visualizar.")
            return
        
        plt.figure(figsize=(12, 6))
        
        # Crear un contador de publicaciones por año
        years_count = self.df['year'].value_counts().sort_index()
        
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

    def plot_source_distribution(self):
        """Grafica la distribución de artículos por fuente de datos."""
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
            'Scopus': 'salmon'  # Considerar Science Direct y Scopus como el mismo color
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

    def plot_publications_trend_by_domain(self):
        """Grafica la tendencia de publicaciones por dominio a lo largo del tiempo."""
        # Verificar columnas de dominio
        domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
        
        if not domain_columns or 'year' not in self.df.columns:
            print("No hay información de dominios o años para visualizar.")
            return
        
        # Preparar datos
        df_domains = self.df[['year'] + domain_columns].copy()
        
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

    def plot_domain_distribution(self):
        """Grafica la distribución de publicaciones por dominio."""
        # Verificar columnas de dominio
        domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
        
        if not domain_columns:
            print("No hay información de dominios para visualizar.")
            return
        
        # Sumar ocurrencias de cada dominio
        domain_counts = {}
        for col in domain_columns:
            domain_name = col.replace('in_', '').replace('_domain', '').capitalize()
            domain_counts[domain_name] = self.df[col].sum()
        
        # Ordenar por frecuencia
        domain_counts = {k: v for k, v in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True)}
        
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

    def plot_domain_overlap(self):
        """Crea un diagrama de Venn/superposición para los tres dominios principales."""
        # Verificar columnas de dominio
        domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
        
        if len(domain_columns) < 2:
            print("Se necesitan al menos 2 dominios para analizar superposiciones.")
            return
        
        # Limitar a los 3 primeros dominios si hay más
        if len(domain_columns) > 3:
            domain_columns = domain_columns[:3]
        
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
            
            from matplotlib_venn import venn2
            
            # Nombres legibles
            d1_name = domain1.replace('in_', '').replace('_domain', '').capitalize()
            d2_name = domain2.replace('in_', '').replace('_domain', '').capitalize()
            
            v = venn2(subsets=(domain1_only, domain2_only, both_domains), 
                     set_labels=(d1_name, d2_name))
            
            # Personalizar colores
            v.get_patch_by_id('10').set_color('skyblue')
            v.get_patch_by_id('01').set_color('lightgreen')
            v.get_patch_by_id('11').set_color('sandybrown')
            
            plt.title('Superposición entre Dominios', fontsize=16)
            
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
            
            from matplotlib_venn import venn3
            
            # Nombres legibles
            d1_name = domain1.replace('in_', '').replace('_domain', '').capitalize()
            d2_name = domain2.replace('in_', '').replace('_domain', '').capitalize()
            d3_name = domain3.replace('in_', '').replace('_domain', '').capitalize()
            
            v = venn3(subsets=(d1_only, d2_only, d1_d2, d3_only, d1_d3, d2_d3, all_three),
                     set_labels=(d1_name, d2_name, d3_name))
            
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
        
        plt.tight_layout()
        
        # Guardar figura
        plt.savefig(os.path.join(self.figures_dir, 'domain_overlap.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ Generada figura: Superposición de dominios")

    def plot_top_journals(self, top_n: int = 15):
        """Grafica las principales revistas por número de publicaciones."""
        if 'journal' not in self.df.columns:
            print("No hay información de revistas para visualizar.")
            return
        
        # Contar publicaciones por revista
        journal_counts = self.df['journal'].value_counts().head(top_n)
        
        # Filtrar revistas con nombre vacío
        journal_counts = journal_counts[journal_counts.index.str.strip() != '']
        
        if journal_counts.empty:
            print("No hay información de revistas válida para visualizar.")
            return
        
        # Crear gráfico
        plt.figure(figsize=(12, 8))
        
        # Definir colores
        colors = plt.cm.cool(np.linspace(0, 0.8, len(journal_counts)))
        
        # Gráfico de barras horizontales
        bars = plt.barh(journal_counts.index, journal_counts.values, color=colors)
        
        # Añadir etiquetas con valores
        for bar in bars:
            width = bar.get_width()
            plt.text(width + 0.1, bar.get_y() + bar.get_height()/2, f'{int(width)}', 
                    ha='left', va='center', fontsize=10)
        
        plt.title(f'Top {len(journal_counts)} Revistas por Número de Publicaciones', fontsize=16)
        plt.xlabel('Número de Publicaciones', fontsize=14)
        plt.ylabel('Revista', fontsize=14)
        plt.tight_layout()
        
        # Guardar figura
        plt.savefig(os.path.join(self.figures_dir, 'top_journals.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ Generada figura: Principales revistas")

    def plot_top_authors(self, top_n: int = 20):
        """Grafica los principales autores por número de publicaciones."""
        if 'authors' not in self.df.columns:
            print("No hay información de autores para visualizar.")
            return
        
        # Extraer todos los autores
        all_authors = []
        for authors_list in self.df['authors']:
            if isinstance(authors_list, list):
                all_authors.extend(authors_list)
        
        # Contar ocurrencias de cada autor
        author_counts = Counter(all_authors)
        
        # Filtrar autores con nombre vacío
        if '' in author_counts:
            del author_counts['']
        
        # Obtener los top autores
        top_authors = author_counts.most_common(top_n)
        
        if not top_authors:
            print("No hay información de autores válida para visualizar.")
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

    def plot_ai_models_distribution(self):
        """Grafica la distribución de modelos de IA mencionados en los artículos."""
        # Buscar columnas relacionadas con modelos de IA
        model_columns = [col for col in self.df.columns if 'model' in col.lower() and 'type' in col.lower()]
        
        if not model_columns:
            print("No hay información de modelos de IA para visualizar.")
            return
        
        # Seleccionar la primera columna de modelos encontrada
        model_col = model_columns[0]
        
        # Contar ocurrencias de cada modelo
        model_counts = self.df[model_col].value_counts()
        
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

    def plot_wordcloud_by_domain(self):
        """Crea nubes de palabras para cada dominio basado en los resúmenes."""
        if not self.abstracts:
            print("No hay resúmenes disponibles para generar nubes de palabras.")
            return
        
        # Verificar columnas de dominio
        domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
        
        if not domain_columns:
            print("No hay información de dominios para visualizar nubes de palabras.")
            return
        
        # Para cada dominio, crear una nube de palabras
        for domain_col in domain_columns:
            # Nombre legible del dominio
            domain_name = domain_col.replace('in_', '').replace('_domain', '').capitalize()
            
            # Filtrar artículos de este dominio
            domain_articles = self.df[self.df[domain_col] == 1]
            
            # Recopilar todos los resúmenes de este dominio
            domain_abstracts = []
            for _, article in domain_articles.iterrows():
                if 'doi' in article and article['doi'] in self.abstracts:
                    domain_abstracts.append(self.abstracts[article['doi']])
            
            if not domain_abstracts:
                print(f"No hay resúmenes suficientes para el dominio {domain_name}.")
                continue
            
            # Unir todos los resúmenes
            text = " ".join(domain_abstracts)
            
            # Eliminar palabras comunes en inglés
            stopwords = set(['a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 
                             'by', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between',
                             'out', 'of', 'during', 'without', 'before', 'under', 'around', 'among',
                             'is', 'are', 'was', 'were', 'be', 'been', 'being',
                             'have', 'has', 'had', 'having',
                             'do', 'does', 'did', 'doing',
                             'this', 'that', 'these', 'those',
                             'i', 'you', 'he', 'she', 'it', 'we', 'they',
                             'me', 'him', 'her', 'us', 'them',
                             'who', 'which', 'what', 'whose', 'whom',
                             'my', 'your', 'his', 'her', 'its', 'our', 'their'])
            
            # Crear la nube de palabras
            wordcloud = WordCloud(width=1000, height=600, background_color='white',
                                 stopwords=stopwords, max_words=100, colormap='viridis')
            
            wordcloud.generate(text)
            
            # Crear figura
            plt.figure(figsize=(12, 8))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.title(f'Términos Frecuentes en Resúmenes - Dominio {domain_name}', fontsize=16)
            plt.tight_layout()
            
            # Guardar figura
            plt.savefig(os.path.join(self.figures_dir, f'wordcloud_{domain_name.lower()}.png'), dpi=300, bbox_inches='tight')
            plt.close()
            print(f"✓ Generada figura: Nube de palabras para dominio {domain_name}")

    def plot_topic_co_occurrence(self):
        """Crea un mapa de calor para co-ocurrencia de temas basado en los resúmenes."""
        # Identificar columnas de características específicas
        binary_columns = [col for col in self.df.columns if self.df[col].dtype == 'int64' and 
                         (self.df[col].max() == 1 and self.df[col].min() == 0)]
        
        # Filtrar columnas de dominio y otras características binarias relevantes
        feature_cols = [col for col in binary_columns if 
                        col.startswith('in_') or 
                        col.startswith('is_') or 
                        'uses_' in col or 
                        'has_' in col]
        
        if len(feature_cols) < 2:
            print("No hay suficientes características binarias para analizar co-ocurrencia.")
            return
        
        # Calcular matriz de correlación
        corr_matrix = self.df[feature_cols].corr()
        
        # Mejorar nombres de las características
        nice_names = {}
        for col in feature_cols:
            name = col
            if col.startswith('in_'):
                name = col.replace('in_', '').replace('_domain', '')
            elif col.startswith('is_'):
                name = col.replace('is_', '')
            elif 'uses_' in col:
                name = col.replace('uses_', '').replace('_', ' ')
            
            # Capitalizar primera letra de cada palabra
            words = name.split('_')
            name = ' '.join(word.capitalize() for word in words)
            nice_names[col] = name
        
        # Usar nombres mejorados en la matriz
        corr_matrix.index = [nice_names.get(col, col) for col in corr_matrix.index]
        corr_matrix.columns = [nice_names.get(col, col) for col in corr_matrix.columns]
        
        # Crear figura
        plt.figure(figsize=(14, 12))
        
        # Crear mapa de calor
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))  # Máscara para mostrar solo la mitad inferior
        cmap = sns.diverging_palette(230, 20, as_cmap=True)
        
        sns.heatmap(corr_matrix, mask=mask, cmap=cmap, vmax=1, vmin=-1, center=0,
                   annot=True, fmt=".2f", square=True, linewidths=.5)
        
        plt.title('Matriz de Co-ocurrencia de Temas', fontsize=16)
        plt.tight_layout()
        
        # Guardar figura
        plt.savefig(os.path.join(self.figures_dir, 'topic_co_occurrence.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ Generada figura: Co-ocurrencia de temas")

    def plot_citations_by_year(self):
        """Grafica la distribución de citaciones por año."""
        if 'citations' not in self.df.columns or 'year' not in self.df.columns:
            print("No hay información de citaciones o años para visualizar.")
            return
        
        # Convertir citaciones a numérico si es necesario
        if self.df['citations'].dtype == 'object':
            self.df['citations'] = pd.to_numeric(self.df['citations'], errors='coerce')
        
        # Agrupar por año y sumar citaciones
        citations_by_year = self.df.groupby('year')['citations'].sum().reset_index()
        
        # Calcular media de citaciones por artículo
        mean_citations = self.df.groupby('year').agg(
            total_citations=('citations', 'sum'),
            article_count=('citations', 'count')
        )
        mean_citations['avg_per_article'] = mean_citations['total_citations'] / mean_citations['article_count']
        mean_citations = mean_citations.reset_index()
        
        # Crear gráfico
        fig, ax1 = plt.subplots(figsize=(14, 8))
        
        # Barras para total de citaciones
        ax1.bar(citations_by_year['year'], citations_by_year['citations'], 
               color='skyblue', alpha=0.7, label='Total de citaciones')
        ax1.set_xlabel('Año', fontsize=14)
        ax1.set_ylabel('Total de Citaciones', fontsize=14, color='navy')
        ax1.tick_params(axis='y', labelcolor='navy')
        
        # Línea para media de citaciones por artículo
        ax2 = ax1.twinx()
        ax2.plot(mean_citations['year'], mean_citations['avg_per_article'], 
                color='red', marker='o', linewidth=2, label='Media por artículo')
        ax2.set_ylabel('Media de Citaciones por Artículo', fontsize=14, color='darkred')
        ax2.tick_params(axis='y', labelcolor='darkred')
        
        # Título y leyenda
        plt.title('Impacto por Año: Citaciones Totales y Media por Artículo', fontsize=16)
        
        # Combinar leyendas
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        plt.tight_layout()
        
        # Guardar figura
        plt.savefig(os.path.join(self.figures_dir, 'citations_by_year.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ Generada figura: Citaciones por año")

    def plot_top_cited_papers(self, top_n: int = 10):
        """Grafica los artículos más citados."""
        if 'citations' not in self.df.columns or 'title' not in self.df.columns:
            print("No hay información de citaciones o títulos para visualizar.")
            return
        
        # Convertir citaciones a numérico si es necesario
        if self.df['citations'].dtype == 'object':
            self.df['citations'] = pd.to_numeric(self.df['citations'], errors='coerce')
        
        # Filtrar artículos con citaciones válidas y ordenar
        papers_with_citations = self.df[['title', 'citations', 'year', 'journal']].dropna(subset=['citations'])
        top_papers = papers_with_citations.sort_values('citations', ascending=False).head(top_n)
        
        if top_papers.empty:
            print("No hay suficientes datos de citaciones para visualizar.")
            return
        
        # Acortar títulos largos
        top_papers['short_title'] = top_papers['title'].apply(
            lambda x: x[:50] + '...' if len(x) > 50 else x
        )
        
        # Crear etiquetas combinadas con título, año y revista
        top_papers['label'] = top_papers.apply(
            lambda x: f"{x['short_title']} ({x['year']}, {x['journal'][:20]}{'...' if len(x['journal']) > 20 else ''})", 
            axis=1
        )
        
        # Crear gráfico
        plt.figure(figsize=(14, 10))
        
        # Definir colores basados en el año
        min_year = top_papers['year'].min()
        max_year = top_papers['year'].max()
        norm = mcolors.Normalize(vmin=min_year, vmax=max_year)
        colors = plt.cm.viridis(norm(top_papers['year']))
        
        # Gráfico de barras horizontales
        bars = plt.barh(top_papers['label'], top_papers['citations'], color=colors)
        
        # Añadir etiquetas con valores
        for bar in bars:
            width = bar.get_width()
            plt.text(width + 5, bar.get_y() + bar.get_height()/2, f'{int(width)}', 
                    ha='left', va='center', fontsize=10)
        
        plt.title(f'Top {top_n} Artículos Más Citados', fontsize=16)
        plt.xlabel('Número de Citaciones', fontsize=14)
        plt.ylabel('Artículo (Año, Revista)', fontsize=14)
        
        # Añadir una barra de color para el año
        sm = plt.cm.ScalarMappable(cmap=plt.cm.viridis, norm=norm)
        sm.set_array([])
        # Especificar el eje actual para la barra de colores
        ax = plt.gca()  # Obtener el eje actual
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label('Año de Publicación', fontsize=12)
        plt.tight_layout()
        
        # Guardar figura
        plt.savefig(os.path.join(self.figures_dir, 'top_cited_papers.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ Generada figura: Artículos más citados")

    def plot_collaboration_network(self, min_collaborations: int = 2):
        """Crea un gráfico de red de colaboración entre autores."""
        if 'authors' not in self.df.columns:
            print("No hay información de autores para visualizar la red de colaboración.")
            return
        
        # Crear grafo de colaboración
        G = nx.Graph()
        
        # Para cada artículo, añadir aristas entre todos los autores
        for _, article in self.df.iterrows():
            authors = article.get('authors', [])
            if isinstance(authors, list) and len(authors) > 1:
                # Añadir aristas entre cada par de autores
                for i in range(len(authors)):
                    for j in range(i+1, len(authors)):
                        if authors[i] and authors[j]:  # Evitar nombres vacíos
                            # Si la arista ya existe, incrementar su peso
                            if G.has_edge(authors[i], authors[j]):
                                G[authors[i]][authors[j]]['weight'] += 1
                            else:
                                G.add_edge(authors[i], authors[j], weight=1)
        
        # Filtrar aristas con peso mínimo
        edges_to_remove = [(u, v) for u, v, d in G.edges(data=True) if d['weight'] < min_collaborations]
        G.remove_edges_from(edges_to_remove)
        
        # Eliminar nodos aislados
        G.remove_nodes_from(list(nx.isolates(G)))
        
        if G.number_of_nodes() == 0:
            print("No hay suficientes relaciones de colaboración para visualizar la red.")
            return
        
        # Limitar a componentes más grandes si hay demasiados nodos
        if G.number_of_nodes() > 100:
            # Obtener el componente más grande
            largest_cc = max(nx.connected_components(G), key=len)
            G = G.subgraph(largest_cc).copy()
            
            # Si aún hay demasiados nodos, limitar por grado
            if G.number_of_nodes() > 50:
                # Calcular grado de cada nodo
                degrees = dict(G.degree())
                # Ordenar nodos por grado
                sorted_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
                # Tomar los 50 nodos con mayor grado
                top_nodes = [node for node, _ in sorted_nodes[:50]]
                # Crear subgrafo
                G = G.subgraph(top_nodes).copy()
        
        # Calcular el tamaño de los nodos basado en su grado
        node_size = [v * 50 for _, v in G.degree()]
        
        # Calcular el ancho de las aristas basado en su peso
        edge_width = [d['weight'] * 1.5 for _, _, d in G.edges(data=True)]
        
        # Crear diseño para la visualización
        plt.figure(figsize=(16, 12))
        
        # Calcular posición de los nodos usando un algoritmo de disposición
        pos = nx.spring_layout(G, seed=42, k=0.2)
        
        # Dibujar nodos
        nodes = nx.draw_networkx_nodes(G, pos, node_size=node_size, node_color='skyblue', alpha=0.8)
        
        # Dibujar aristas
        edges = nx.draw_networkx_edges(G, pos, width=edge_width, alpha=0.5, edge_color='gray')
        
        # Añadir etiquetas para nodos con grado alto
        high_degree_nodes = [node for node, degree in G.degree() if degree > min(min_collaborations+2, 5)]
        labels = {node: node for node in high_degree_nodes}
        
        # Mover etiquetas para evitar superposición
        if labels:
            texts = nx.draw_networkx_labels(G, pos, labels=labels, font_size=10, font_weight='bold')
            if isinstance(texts, dict):  # Si la función devuelve un diccionario de objetos Text
                adjust_text([text for text in texts.values()])
        
        plt.title('Red de Colaboración entre Autores', fontsize=16)
        plt.axis('off')  # Ocultar ejes
        
        # Añadir leyenda para el tamaño de los nodos
        plt.text(0.02, 0.02, 'Tamaño del nodo: Número de colaboradores\nGrosor de arista: Número de colaboraciones',
                transform=plt.gca().transAxes, fontsize=12, verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        plt.tight_layout()
        
        # Guardar figura
        plt.savefig(os.path.join(self.figures_dir, 'collaboration_network.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print("✓ Generada figura: Red de colaboración entre autores")

    def generate_statistics_for_report(self):
        """Genera estadísticas básicas para incluir en el informe."""
        stats = {}
        
        # Total de artículos
        stats['total_articles'] = int(len(self.df))
        
        # Rango de años
        if 'year' in self.df.columns:
            stats['year_range'] = [int(self.df['year'].min()), int(self.df['year'].max())]
        
        # Artículos por dominio
        domain_columns = [col for col in self.df.columns if col.startswith('in_') and col.endswith('_domain')]
        stats['domain_counts'] = {}
        for col in domain_columns:
            domain_name = col.replace('in_', '').replace('_domain', '').capitalize()
            stats['domain_counts'][domain_name] = int(self.df[col].sum())
        
        # Distribución de artículos por fuente
        if 'source' in self.df.columns:
            source_counts = self.df['source'].value_counts().to_dict()
            # Convertir valores a int estándar de Python
            stats['source_counts'] = {k: int(v) for k, v in source_counts.items()}
        
        # Top 5 revistas
        if 'journal' in self.df.columns:
            top_journals = self.df['journal'].value_counts().head(5).to_dict()
            # Convertir valores a int estándar de Python
            stats['top_journals'] = {k: int(v) for k, v in top_journals.items()}
        
        # Top 5 autores
        if 'authors' in self.df.columns:
            all_authors = []
            for authors_list in self.df['authors']:
                if isinstance(authors_list, list):
                    all_authors.extend(authors_list)
            # Convertir Counter a lista de tuplas con valores int
            stats['top_authors'] = [(author, int(count)) 
                                for author, count in Counter(all_authors).most_common(5)]
        
        # Top 5 modelos de IA/ML
        model_columns = [col for col in self.df.columns if 'model' in col.lower() and 'type' in col.lower()]
        if model_columns:
            model_col = model_columns[0]
            # Filtrar "No mencionado" y nombres vacíos
            model_counts = self.df[model_col].value_counts()
            model_counts = model_counts[(model_counts.index != "No mencionado") & 
                                    (model_counts.index != "Not mentioned") & 
                                    (model_counts.index.str.strip() != '')]
            # Convertir valores a int estándar de Python
            stats['top_models'] = {k: int(v) for k, v in model_counts.head(5).to_dict().items()}
        
        # Clase personalizada para serialización JSON que maneja tipos de NumPy
        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                import numpy as np
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                return json.JSONEncoder.default(self, obj)
        
        # Guardar estadísticas en un archivo JSON con el encoder personalizado
        try:
            with open(os.path.join(self.figures_dir, 'statistics.json'), 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=4, cls=NumpyEncoder)
            print("✓ Generadas estadísticas básicas para el informe")
        except Exception as e:
            print(f"Error al guardar estadísticas: {str(e)}")
        
        return stats
    

# Función principal
def main():
    parser = argparse.ArgumentParser(description='Genera análisis y visualizaciones a partir de resultados clasificados.')
    
    parser.add_argument('--classified-file', type=str, default='outputs/classified_results.json',
                       help='Ruta al archivo JSON con artículos clasificados')
    
    parser.add_argument('--abstracts-file', type=str, default='outputs/integrated_abstracts.json',
                       help='Ruta al archivo JSON con resúmenes')
    
    parser.add_argument('--domain-stats-file', type=str, default='outputs/domain_statistics.csv',
                       help='Ruta al archivo CSV con estadísticas de dominio')
    
    parser.add_argument('--figures-dir', type=str, default='figures',
                       help='Carpeta donde guardar las figuras generadas')
    
    args = parser.parse_args()
    
    print("\n====== INICIANDO GENERACIÓN DE ANÁLISIS Y VISUALIZACIONES ======\n")
    
    # Verificar si existen los archivos
    if not os.path.exists(args.classified_file):
        print(f"ERROR: No se encontró el archivo de resultados clasificados: {args.classified_file}")
        return
    
    # Crear analizador de resultados
    analyzer = ResultsAnalyzer(
        classified_file=args.classified_file,
        abstracts_file=args.abstracts_file if os.path.exists(args.abstracts_file) else None,
        domain_stats_file=args.domain_stats_file if os.path.exists(args.domain_stats_file) else None
    )
    
    # Generar todas las visualizaciones
    analyzer.generate_all_figures()
    
    # Generar estadísticas para el informe
    stats = analyzer.generate_statistics_for_report()
    
    print("\n====== GENERACIÓN DE ANÁLISIS Y VISUALIZACIONES COMPLETADA ======")
    print(f"\nSe han generado {len(os.listdir(analyzer.figures_dir))} archivos en la carpeta '{analyzer.figures_dir}'.")
    
    # Mostrar algunas estadísticas básicas
    print("\nEstadísticas básicas:")
    print(f"- Total de artículos analizados: {stats.get('total_articles', 'N/A')}")
    if 'year_range' in stats:
        print(f"- Rango de años: {stats['year_range'][0]}-{stats['year_range'][1]}")
    
    # Mostrar conteo por dominio
    if 'domain_counts' in stats:
        print("\nArtículos por dominio:")
        for domain, count in stats['domain_counts'].items():
            print(f"- {domain}: {count}")


if __name__ == "__main__":
    main()