#!/usr/bin/env python3
"""
Script de prueba para verificar la extracción de parámetros con RAG.

Prueba:
1. Cargando el índice RAG
2. Consultando una especie de prueba
3. Parseando la respuesta JSON
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

RAG_INDEX_DIR = Path(__file__).parent.parent / "outputs" / "rag_index_goc_full"

SYSTEM_PROMPT_PARAMETERS = """\
Eres un asistente especializado en extraer parámetros poblacionales de literatura científica marina.

Tu tarea es extraer información SOLO del contexto proporcionado y devolver un JSON estructurado.

IMPORTANTE:
1. Solo reporta valores encontrados EXPLÍCITAMENTE en los documentos
2. No inventes ni hagas estimaciones
3. Si no encuentras un parámetro, establécelo como null
4. Todos los valores numéricos deben ser números (sin unidades)

Parámetros a extraer (todos opcionales):
- biomass_mt: biomasa en toneladas métricas (número)
- abundance_numbers: abundancia en número de individuos (número)
- mean_body_size: tamaño corporal promedio en cm (número)
- max_age: edad máxima en años (número)
- natural_mortality: tasa de mortalidad natural (número, 0-1)
- Lmax: longitud máxima en cm (número)
- Von_bertalanffy_a: coeficiente a (número)
- Von_bertalanffy_b: coeficiente b (número)
- growth_rate: tasa de crecimiento (número)
- age_first_maturity: edad de primera madurez en años (número)
- larval_duration: duración larval en días (número)
- StartSpawnDayOfYear: día de inicio de desove (número, 1-365)
- EndSpawnDayOfYear: día de fin de desove (número, 1-365)
- IsMigratory: ¿es migratoria? ("Yes" o "No")

Retorna ÚNICAMENTE un JSON válido sin explicaciones adicionales.
"""


def test_rag_connection():
    """Prueba que el índice RAG está disponible."""
    print("="*70)
    print("PRUEBA 1: Verificando índice RAG")
    print("="*70)

    if not RAG_INDEX_DIR.exists():
        print(f"❌ ERROR: Índice RAG no encontrado en {RAG_INDEX_DIR}")
        print("Ejecuta primero: python scripts/run_exhaustive_rebuild.py")
        return False

    print(f"✓ Índice RAG encontrado: {RAG_INDEX_DIR}")

    try:
        vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
        vector_db.load()
        stats = vector_db.get_stats()
        print(f"✓ Índice cargado exitosamente")
        print(f"  - Total chunks: {stats.total_chunks}")
        print(f"  - Total papers: {stats.total_papers}")
        print(f"  - Embedding dimension: {stats.embedding_dimension}")
        return True
    except Exception as e:
        print(f"❌ Error cargando índice: {e}")
        return False


def test_parameter_extraction():
    """Prueba la extracción de parámetros para una especie."""
    print("\n" + "="*70)
    print("PRUEBA 2: Extracción de parámetros")
    print("="*70)

    # Cargar índice
    vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
    vector_db.load()

    # Crear query engine con prompt personalizado
    query_engine = RAGQueryEngine(
        vector_db=vector_db,
        model="claude-haiku-4-5-20251001",
        top_k=10,  # Aumentado de 5 a 10
        min_score=0.15,  # Bajado de 0.2 a 0.15
        verbose=True,
        system_prompt=SYSTEM_PROMPT_PARAMETERS
    )

    # Consultar una especie de prueba
    species_name = "Seriola lalandi"  # Amberjack
    print(f"\nConsultando parámetros para: {species_name}")
    print("-" * 70)

    query = (
        f"¿Qué información hay disponible sobre {species_name} en el Golfo de California? "
        f"Incluye todos los parámetros biológicos y poblacionales disponibles: "
        f"características de tamaño, edad, crecimiento, reproducción, alimentación, distribución, "
        f"abundancia, biomasa, comportamiento migratorio, o cualquier otra información cuantitativa disponible. "
        f"\n\nExtrae TODA la información cuantitativa (números, valores) que encuentres. "
        f"Retorna SOLO un JSON válido sin explicaciones. "
        f"Formato:\n"
        f'{{"biomass_mt": null, "abundance_numbers": null, "mean_body_size": null, '
        f'"max_age": null, "natural_mortality": null, "Lmax": null, '
        f'"Von_bertalanffy_a": null, "Von_bertalanffy_b": null, "growth_rate": null, '
        f'"age_first_maturity": null, "larval_duration": null, "StartSpawnDayOfYear": null, '
        f'"EndSpawnDayOfYear": null, "IsMigratory": null}}'
    )

    try:
        result = query_engine.query(query)

        print(f"\n✓ Consulta ejecutada exitosamente")
        print(f"  - Chunks utilizados: {result.chunks_used}")
        print(f"\n📄 Respuesta RAG (primeros 200 chars):")
        print(f"  {result.answer[:200]}...")

        # Intentar parsear JSON
        print(f"\n🔍 Parseando respuesta JSON...")
        response_text = result.answer.strip()

        # Limpiar si viene con markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        params = json.loads(response_text)

        print(f"✓ JSON parseado exitosamente")
        print(f"\n📊 Parámetros extraídos:")

        extracted_count = 0
        for param, value in params.items():
            if value is not None and value != "null":
                print(f"  ✓ {param}: {value}")
                extracted_count += 1

        if extracted_count == 0:
            print("  (No se encontraron parámetros con valores)")

        print(f"\nResumen: {extracted_count} parámetros extraídos de {len(params)} totales")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON: {e}")
        print(f"   Respuesta recibida:\n{result.answer}")
        return False
    except Exception as e:
        print(f"❌ Error ejecutando consulta: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todas las pruebas."""
    print("\n🧪 TEST SUITE: Extracción de Parámetros Poblacionales\n")

    # Test 1
    if not test_rag_connection():
        print("\n❌ Prueba 1 falló. Deteniendo.")
        return 1

    # Test 2
    if not test_parameter_extraction():
        print("\n⚠️  Prueba 2 mostró problemas. Revisa los logs.")
        return 1

    print("\n" + "="*70)
    print("✅ TODAS LAS PRUEBAS PASARON")
    print("="*70)
    print("\nPuedes ejecutar el script principal:")
    print("  python scripts/complete_population_parameters.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
