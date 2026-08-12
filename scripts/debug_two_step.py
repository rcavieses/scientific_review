#!/usr/bin/env python3
"""Debug: ver cada paso del proceso de dos LLMs"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

RAG_INDEX_DIR = Path(__file__).parent.parent / "outputs" / "rag_index_goc_full"

SYSTEM_PROMPT_EXTRACT = """\
You are an assistant that extracts quantitative data from marine scientific literature.

Your task:
1. Read all provided paper fragments
2. Extract ALL numeric values and quantitative data found
3. Report EXACTLY what you found, don't invent
4. If information is not found, be honest about it

Return JSON with all extracted data. Be flexible with structure.
Include everything: size ranges, weight ranges, age data, abundance, biomass, growth parameters,
spawning information, migratory status, aquaculture data, or any other quantitative values found.
"""

SYSTEM_PROMPT_FORMAT = """\
You are a specialist in marine species biological parameters.

You are given extracted information about a species from scientific literature.

Your task is to intelligently map that information to these 14 specific table fields:
- biomass_mt: biomass in metric tons
- abundance_numbers: abundance (number of individuals)
- mean_body_size: mean body size (cm)
- max_age: maximum age (years)
- natural_mortality: natural mortality rate (0-1)
- Lmax: maximum length (cm)
- Von_bertalanffy_a: Von Bertalanffy coefficient a
- Von_bertalanffy_b: Von Bertalanffy coefficient b
- growth_rate: growth rate
- age_first_maturity: age at first maturity (years)
- larval_duration: larval duration (days)
- StartSpawnDayOfYear: spawning start day (1-365)
- EndSpawnDayOfYear: spawning end day (1-365)
- IsMigratory: is migratory? (Yes/No)

IMPORTANT:
- If data can be reasonably mapped to a field, do it (e.g., subadult weight ranges → mean_body_size)
- Include both wild population data AND aquaculture data if available
- If a field cannot be mapped or data doesn't exist, use null
- Return ONLY a JSON with exactly these 14 fields, nothing else
- All numeric values should be numbers (no units), strings for Yes/No only
"""

# Cargar
vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
vector_db.load()

query_extract = RAGQueryEngine(
    vector_db=vector_db,
    model="claude-haiku-4-5-20251001",
    top_k=10,
    min_score=0.15,
    verbose=False,
    system_prompt=SYSTEM_PROMPT_EXTRACT
)

query_format = RAGQueryEngine(
    vector_db=vector_db,
    model="claude-haiku-4-5-20251001",
    top_k=1,
    min_score=0.0,
    verbose=False,
    system_prompt=SYSTEM_PROMPT_FORMAT
)

species = "Red snapper (Huachinango)"  # Well-documented commercial species

print(f"{'='*80}")
print(f"ESPECIE: {species}")
print(f"{'='*80}")

# PASO 1
print(f"\n{'='*60}")
print(f"PASO 1: Extracción del RAG")
print(f"{'='*60}")

query1 = (
    f"What quantitative information (numbers, measurements, biological parameters) "
    f"do you have about {species} in the Gulf of California? "
    f"\n\nReport ALL numeric values found (sizes, ages, weights, abundances, growth rates, "
    f"spawning info, migration status, aquaculture data, or any other numbers). "
    f"If information is not found, be honest. Return JSON format."
)

result1 = query_extract.query(query1)
print(f"\n📄 Step 1 Response:")
print("-" * 60)
print(result1.answer)

# STEP 2
print(f"\n{'='*60}")
print(f"STEP 2: Map to table schema")
print(f"{'='*60}")

query2 = (
    f"Extracted information about {species}:\n\n"
    f"{result1.answer}\n\n"
    f"Map this information intelligently to these 14 table fields: "
    f"biomass_mt, abundance_numbers, mean_body_size, max_age, natural_mortality, "
    f"Lmax, Von_bertalanffy_a, Von_bertalanffy_b, growth_rate, "
    f"age_first_maturity, larval_duration, StartSpawnDayOfYear, EndSpawnDayOfYear, IsMigratory. "
    f"\n\nReturn ONLY JSON with exactly these 14 fields."
)

result2 = query_format.query(query2)
print(f"\n📄 Respuesta paso 2:")
print("-" * 60)
print(result2.answer)

# Intentar parsear
print(f"\n{'='*60}")
print(f"ANÁLISIS FINAL")
print(f"{'='*60}")

response_text = result2.answer.strip()

if response_text.startswith("```"):
    parts = response_text.split("```")
    response_text = parts[1]
    if response_text.startswith("json"):
        response_text = response_text[4:]
    response_text = response_text.strip()

try:
    data = json.loads(response_text)
    print(f"\n✓ JSON válido")
    print(json.dumps(data, indent=2))

    found = sum(1 for v in data.values() if v is not None and v != "null")
    print(f"\n✓ Parámetros con valores: {found}/14")
except json.JSONDecodeError as e:
    print(f"\n❌ Error parseando JSON: {e}")
    print(f"\nTexto intento: {response_text}")
