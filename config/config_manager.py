__all__ = ['ConfigManager', 'PipelineConfig']

import argparse
from dataclasses import dataclass
from typing import Optional

@dataclass
class PipelineConfig:
    # Search settings
    domain1: str
    domain2: str
    domain3: str
    max_results: int
    year_start: int
    year_end: Optional[int]
    email: Optional[str]
    
    # Output settings
    figures_dir: str
    report_file: str
    generate_pdf: bool
    pandoc_path: Optional[str]
    table_file: str
    table_format: str
    
    # Flow control
    skip_searches: bool
    skip_integration: bool
    skip_domain_analysis: bool
    skip_classification: bool
    skip_table: bool
    only_search: bool
    only_analysis: bool
    only_report: bool

class ConfigManager:
    @staticmethod
    def get_config() -> PipelineConfig:
        parser = argparse.ArgumentParser(
            description='Ejecuta el flujo de trabajo completo para análisis bibliométrico.',
            formatter_class=argparse.RawTextHelpFormatter
        )
        
        # Add argument groups
        search_group = parser.add_argument_group('Opciones de búsqueda')
        ConfigManager._add_search_arguments(search_group)
        
        output_group = parser.add_argument_group('Opciones de salida')
        ConfigManager._add_output_arguments(output_group)
        
        flow_group = parser.add_argument_group('Control de flujo de trabajo')
        ConfigManager._add_flow_arguments(flow_group)
        
        args = parser.parse_args()
        return PipelineConfig(**vars(args))
    
    @staticmethod
    def _add_search_arguments(group):
        group.add_argument('--domain1', type=str, default='Domain1.csv',
                          help='Archivo CSV con términos del primer dominio')
        group.add_argument('--domain2', type=str, default='Domain2.csv',
                          help='Archivo CSV con términos del segundo dominio')
        group.add_argument('--domain3', type=str, default='Domain3.csv',
                          help='Archivo CSV con términos del tercer dominio')
        group.add_argument('--max-results', type=int, default=50,
                          help='Número máximo de resultados por búsqueda')
        group.add_argument('--year-start', type=int, default=2008,
                          help='Año inicial para filtrar resultados')
        group.add_argument('--year-end', type=int, default=None,
                          help='Año final para filtrar resultados')
        group.add_argument('--email', type=str, default=None,
                          help='Email para APIs académicas')

    @staticmethod
    def _add_output_arguments(group):
        group.add_argument('--figures-dir', type=str, default='figures',
                          help='Directorio para guardar figuras')
        group.add_argument('--report-file', type=str, default='report.md',
                          help='Archivo de salida para el reporte')
        group.add_argument('--generate-pdf', action='store_true',
                          help='Generar versión PDF del reporte')
        group.add_argument('--pandoc-path', type=str, default=None,
                          help='Ruta al ejecutable de Pandoc')
        group.add_argument('--table-file', type=str, default='articles_table.csv',
                          help='Archivo para la tabla de artículos')
        group.add_argument('--table-format', type=str, choices=['csv', 'excel'],
                          default='csv', help='Formato de la tabla de artículos')

    @staticmethod
    def _add_flow_arguments(group):
        group.add_argument('--skip-searches', action='store_true',
                          help='Omitir búsquedas')
        group.add_argument('--skip-integration', action='store_true',
                          help='Omitir integración')
        group.add_argument('--skip-domain-analysis', action='store_true',
                          help='Omitir análisis de dominio')
        group.add_argument('--skip-classification', action='store_true',
                          help='Omitir clasificación')
        group.add_argument('--skip-table', action='store_true',
                          help='Omitir generación de tabla')
        group.add_argument('--only-search', action='store_true',
                          help='Ejecutar solo búsquedas')
        group.add_argument('--only-analysis', action='store_true',
                          help='Ejecutar solo análisis')
        group.add_argument('--only-report', action='store_true',
                          help='Ejecutar solo reporte')
