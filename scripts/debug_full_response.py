#!/usr/bin/env python3
"""Debug: ver respuesta completa de Claude para una especie"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

RAG_INDEX_DIR = Path(__file__).parent.parent / "outputs" / "rag_index_goc_full"

SYSTEM_PROMPT = """\
Eres un asistente que extrae datos cuantitativos de literatura científica marina.

Tu tarea:
1. Lee los fragmentos de papers proporcionados
2. Extrae TODOS los valores numéricos (edad, tamaño, biomasa, etc.) que encuentres
3. Reporta EXACTAMENTE lo que encontraste, sin inventar
4. Si NO encuentras información sobre un parámetro, REPORTALO HONESTAMENTE

IMPORTANTE:
- No inventes datos
- Si la información no está en los fragmentos, se honesto
- Mapea los valores encontrados a estos campos (si aplica):
  * biomass_mt, abundance_numbers, mean_body_size, max_age, natural_mortality
  * Lmax, Von_bertalanffy_a, Von_bertalanffy_b, growth_rate
  * age_first_maturity, larval_duration, StartSpawnDayOfYear, EndSpawnDayOfYear
  * IsMigratory

Retorna un JSON limpio. Para valores no encontrados, usa "not found" o null.
"""

# Cargar
vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
vector_db.load()

query_engine = RAGQueryEngine(
    vector_db=vector_db,
    model="claude-haiku-4-5-20251001",
    top_k=10,
    min_score=0.15,
    verbose=False,
    system_prompt=SYSTEM_PROMPT
)

# Probar con varias especies
species_list = [
    "Seriola lalandi",
    "Balaenoptera edeni",
    "Pacific Sardine",
]

for species in species_list:
    query = (
        f"¿Qué información cuantitativa (números, medidas, parámetros biológicos) "
        f"tienes sobre {species} en el Golfo de California? "
        f"\n\nReporta TODOS los valores numéricos que encuentres "
        f"(edad, tamaño, biomasa, abundancia, parámetros de crecimiento, desove, etc.). "
        f"Si NO encuentras un dato específico, reportalo como 'not found'. "
        f"Retorna un JSON limpio."
    )

    print(f"\n{'='*80}")
    print(f"ESPECIE: {species}")
    print(f"{'='*80}")

    try:
        result = query_engine.query(query)

        print(f"\n📄 RESPUESTA RAG COMPLETA:")
        print("-" * 80)
        print(result.answer)
        print("-" * 80)

        # Intentar parsear
        response_text = result.answer.strip()
        if response_text.startswith("```"):
            parts = response_text.split("```")
            response_text = parts[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        try:
            data = json.loads(response_text)
            print(f"\n✓ JSON válido")
            print(f"\nEstructura JSON:")
            print(json.dumps(data, indent=2)[:500])
        except Exception as e:
            print(f"\n❌ Error parseando JSON: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")
