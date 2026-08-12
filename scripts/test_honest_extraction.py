#!/usr/bin/env python3
"""
Script para probar extracción honesta - sin forzar JSON.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

RAG_INDEX_DIR = Path(__file__).parent.parent / "outputs" / "rag_index_goc_full"

HONEST_PROMPT = """\
Eres un asistente que extrae información de literatura científica.

Tu tarea es:
1. Leer los fragmentos proporcionados
2. Si encuentras un valor numérico (edad, tamaño, biomasa, etc),
   reportarlo honestamente con su contexto
3. Si NO encuentras el valor, di explícitamente "no encontrado"
4. No inventes datos

Retorna SOLO un JSON con los valores encontrados.
Para valores no encontrados, usa "not found" (string, no null).
"""

def main():
    print("Cargando índice...")
    vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
    vector_db.load()

    query_engine = RAGQueryEngine(
        vector_db=vector_db,
        model="claude-haiku-4-5-20251001",
        top_k=15,
        min_score=0.1,
        verbose=True,
        system_prompt=HONEST_PROMPT
    )

    species = "Seriola lalandi"

    # Consulta muy simple
    query = (
        f"¿Qué información cuantitativa (números, medidas, parámetros) "
        f"tienes sobre {species} en el Golfo de California? "
        f"Reporta TODO lo que encuentres en formato JSON. "
        f"Usa 'not found' para valores no disponibles."
    )

    print(f"\n{'='*80}")
    print(f"Consultando: {species}")
    print(f"{'='*80}\n")

    try:
        result = query_engine.query(query)

        print(f"\n{'='*80}")
        print("RESPUESTA COMPLETA DEL RAG:")
        print(f"{'='*80}")
        print(result.answer)

        print(f"\n{'='*80}")
        print("ANÁLISIS:")
        print(f"{'='*80}")

        # Ver si contiene JSON
        if "{" in result.answer and "}" in result.answer:
            try:
                # Extraer JSON
                json_start = result.answer.find("{")
                json_end = result.answer.rfind("}") + 1
                json_str = result.answer[json_start:json_end]

                data = json.loads(json_str)
                print("\n✓ JSON encontrado y parseado:")
                print(json.dumps(data, indent=2))

                # Contar valores encontrados
                found = sum(1 for v in data.values() if v and v != "not found")
                print(f"\nValores encontrados: {found}/{len(data)}")

            except json.JSONDecodeError:
                print("⚠ Tiene estructura JSON pero no parsea correctamente")
                print(json_str)
        else:
            print("⚠ Respuesta no contiene JSON")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
