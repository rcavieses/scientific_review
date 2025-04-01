#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script simplificado para generar archivos mínimos para pruebas.
Crea archivos CSV de dominio con pocos términos y un archivo de preguntas básico.
"""

import json
import os

def create_simple_files():
    """
    Crea archivos CSV de dominio y de preguntas sencillos para pruebas.
    """
    # Crear directorio outputs si no existe
    os.makedirs("outputs", exist_ok=True)
    
    # Dominios con menos términos
    domain1_terms = [
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "neural network"
    ]
    
    domain2_terms = [
        "forecast",
        "prediction",
        "time series"
    ]
    
    domain3_terms = [
        "fishery",
        "fish stock",
        "marine resources"
    ]
    
    # Preguntas básicas (solo 2)
    simple_questions = [
        {
            "text": "¿El título menciona explícitamente IA o ML?",
            "response_format": "1 o 0",
            "field_name": "uses_ai_ml",
            "answer_type": "int",
            "default_value": 0
        },
        {
            "text": "¿Qué tipo de modelo de IA/ML se menciona?",
            "response_format": "el nombre del modelo o \"No mencionado\"",
            "field_name": "ai_model_type",
            "answer_type": "string",
            "default_value": "No mencionado"
        }
    ]
    
    # Crear archivos de dominio
    with open("Domain1.csv", 'w', encoding='utf-8') as file:
        for term in domain1_terms:
            file.write(f"{term}\n")
    
    with open("Domain2.csv", 'w', encoding='utf-8') as file:
        for term in domain2_terms:
            file.write(f"{term}\n")
    
    with open("Domain3.csv", 'w', encoding='utf-8') as file:
        for term in domain3_terms:
            file.write(f"{term}\n")
    
    # Crear archivo de preguntas simplificado
    with open("questions.json", 'w', encoding='utf-8') as file:
        json.dump(simple_questions, file, ensure_ascii=False, indent=2)
    
    # Crear archivo de ejemplo para API key de Anthropic
    # (Solo creamos un placeholder, deberá ser reemplazado con la clave real)
    with open("anthropic-apikey.example", 'w', encoding='utf-8') as file:
        file.write("sk-ant-api01-REEMPLAZAR-CON-TU-CLAVE-REAL")
    
    print("Archivos básicos creados con éxito:")
    print("- Domain1.csv, Domain2.csv, Domain3.csv: Archivos de dominio con pocos términos")
    print("- questions.json: Archivo de preguntas simplificado")
    print("- anthropic-apikey.example: Archivo de ejemplo para la API key de Anthropic")
    print("\nPara utilizar el script principal:")
    print("1. Renombra anthropic-apikey.example a anthropic-apikey y actualiza con tu API key real")
    print("2. Ejecuta: python main_script.py --max-results 10 --year-start 2020")
    print("   (El parámetro --max-results 10 reduce el número de resultados para pruebas rápidas)")

if __name__ == "__main__":
    create_simple_files()