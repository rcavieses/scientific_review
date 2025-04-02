#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script principal que integra todo el flujo de trabajo usando el nuevo sistema de pipeline.
"""

import os
import sys

# Add the project directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from config.config_manager import ConfigManager, PipelineConfig
from pipeline.pipeline_executor import PipelineExecutor

def main():
    """Función principal que coordina la ejecución del pipeline."""
    start_time = datetime.now()
    
    # Obtener configuración desde argumentos de línea de comandos
    config = ConfigManager.get_config()
    
    # Crear y ejecutar el pipeline
    executor = PipelineExecutor(config)
    
    print("\n====== INICIANDO EJECUCIÓN DEL PIPELINE ======")
    print(f"Hora de inicio: {start_time}")
    print("\nConfiguración:")
    print(f"- Dominios: {config.domain1}, {config.domain2}, {config.domain3}")
    print(f"- Resultados máximos: {config.max_results}")
    print(f"- Rango de años: {config.year_start}-{config.year_end or 'presente'}")
    
    # Mostrar qué fases se ejecutarán
    phases = []
    if not (config.only_analysis or config.only_report):
        phases.append("Búsqueda")
    if not (config.only_search or config.only_report):
        phases.append("Análisis")
    if not (config.only_search or config.only_analysis):
        phases.append("Reporte")
    
    print(f"\nFases a ejecutar: {', '.join(phases)}")
    
    # Ejecutar pipeline
    success = executor.execute()
    
    # Mostrar resultado
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n====== FINALIZACIÓN DEL PIPELINE ======")
    print(f"Estado: {'EXITOSO' if success else 'FALLIDO'}")
    print(f"Hora de finalización: {end_time}")
    print(f"Duración total: {duration}")
    
    # Retornar código de estado
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())