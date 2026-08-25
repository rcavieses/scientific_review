#!/usr/bin/env python3
"""BÚSQUEDA 6 — extracción de parámetros poblacionales CON RANGOS.

Qué cambia respecto a B5 (scripts/complete_population_parameters_BUSQUEDA5.py):

1. El paso 2 ya no devuelve un escalar por parámetro, sino un objeto
   {value, min, max, unit, basis, source, quote}. Los rangos que la literatura
   reporta dejan de tirarse.
2. La tabla gana columnas `<param>_min` y `<param>_max` junto a cada `<param>`.
3. Se persiste el JSON crudo del paso 1 en un JSONL, uno por especie. En B1–B5
   ese intermedio se perdía y no era recuperable.
4. Parte de un CSV **vacío** alineado fila a fila con B1 (aviso metodológico 2 de
   COMPARACION_BUSQUEDAS.md: B5 heredó el archivo de B4 y contaminó la
   comparación).

Uso:
    # Prueba en pocos grupos/especies antes de la corrida larga
    python3 scripts/complete_population_parameters_BUSQUEDA6.py \
        --groups "Drums and croakers" --limit-species 3

    # Corrida completa (~3-4 h)
    python3 scripts/complete_population_parameters_BUSQUEDA6.py

    # Reanudar tras una interrupción (usa el progreso guardado)
    python3 scripts/complete_population_parameters_BUSQUEDA6.py
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.vector_db import VectorDBManager          # noqa: E402
from scripts.section_aware_engine import (                  # noqa: E402
    SectionAwareRAGQueryEngine, load_sections,
)

# ── Configuración ────────────────────────────────────────────────────────────

LOG_DIR = PROJECT_ROOT / "outputs" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "rag_parameter_completion_BUSQUEDA6.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

LLM_MODEL = "claude-sonnet-5"          # el mismo que B5, para poder comparar
MAX_TOKENS = 4096
THINKING = {"type": "disabled"}

RAG_INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
SKELETON_CSV = PROJECT_ROOT / "data" / "output" / "Atlantis_GOC_parametros_biologicos_BUSQUEDA1.csv"
OUTPUT_CSV = PROJECT_ROOT / "data" / "output" / "Atlantis_GOC_parametros_biologicos_BUSQUEDA_6.csv"
LONG_CSV = PROJECT_ROOT / "data" / "output" / "Atlantis_GOC_parametros_BUSQUEDA_6_detalle.csv"
RAW_JSONL = PROJECT_ROOT / "outputs" / "busqueda6_extractions.jsonl"
PROGRESS_JSON = PROJECT_ROOT / "outputs" / "rag_completion_progress_BUSQUEDA_6.json"

TAXONOMY = ["Group", "Code", "Species", "Genus", "Family", "Order", "Class", "Phylum"]

NUMERIC_PARAMS = [
    "biomass_mt", "abundance_numbers", "mean_body_size", "max_age",
    "natural_mortality", "Lmax", "li_a", "li_b", "vb_Linf", "vb_t0",
    "growth_rate", "age_first_maturity", "larval_duration",
    "StartSpawnDayOfYear", "EndSpawnDayOfYear",
]
CAT_PARAMS = ["IsMigratory"]
ALL_PARAMS = NUMERIC_PARAMS + CAT_PARAMS

# Unidad canónica de cada parámetro; se le pide al modelo que convierta a ella.
UNITS = {
    "biomass_mt": "metric tons (t)",
    "abundance_numbers": "number of individuals",
    "mean_body_size": "cm",
    "max_age": "years",
    "natural_mortality": "1/year (instantaneous rate M)",
    "Lmax": "cm",
    "li_a": "dimensionless (coefficient a of W = a*L^b)",
    "li_b": "dimensionless (exponent b of W = a*L^b, near 3)",
    "vb_Linf": "cm (von Bertalanffy asymptotic length)",
    "vb_t0": "years (von Bertalanffy t0, usually negative)",
    "growth_rate": "1/year",
    "age_first_maturity": "years",
    "larval_duration": "days",
    "StartSpawnDayOfYear": "day of year (1-365)",
    "EndSpawnDayOfYear": "day of year (1-365)",
}

# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_EXTRACT = """\
You are an assistant that extracts quantitative data from marine scientific literature.

Your task:
1. Read all provided paper fragments.
2. Extract ALL numeric values and quantitative data found.
3. Report EXACTLY what you found, don't invent.
4. For EACH data point include: the value, ITS UNITS, whether it is a single
   estimate or a RANGE (give both endpoints when it is a range), the sample size
   if stated, the study area, the life stage / sex if stated, and the source paper.
5. Quote the sentence or table cell the number comes from.
6. If information is not found, be honest about it.

Ranges matter as much as point estimates: never collapse "L∞ ranged from 28 to
34 cm" into a single number — report both endpoints.

Return JSON with all extracted data including sources and quotes. Be flexible
with structure. Include everything: size ranges, weight ranges, age data,
abundance, biomass, growth parameters, spawning information, migratory status,
aquaculture data, or any other quantitative values found.
"""

SYSTEM_PROMPT_FORMAT = """\
You are a specialist in marine species biological parameters for the Atlantis
ecosystem model of the Gulf of California.

You are given information extracted from scientific literature about one species.
Map it to these 14 fields:

- biomass_mt: biomass, in metric tons (t)
- abundance_numbers: abundance, number of individuals
- mean_body_size: mean body size, cm
- max_age: maximum age, years
- natural_mortality: instantaneous natural mortality M, 1/year
- Lmax: maximum length, cm
- li_a: coefficient a of the WEIGHT-LENGTH relationship W = a * L^b (typically 1e-6 to 1e-2). NOT a von Bertalanffy parameter.
- li_b: exponent b of the WEIGHT-LENGTH relationship W = a * L^b (typically 2.5 to 3.5, near 3). NOT a von Bertalanffy parameter.
- vb_Linf: von Bertalanffy asymptotic length L-infinity, in cm.
- vb_t0: von Bertalanffy theoretical age at zero length t0, in years (usually negative).
- growth_rate: von Bertalanffy growth coefficient K, in 1/year. This is the ONLY column for K; do not repeat it anywhere else.
- growth_rate: growth rate, 1/year
- age_first_maturity: age at first maturity, years
- larval_duration: larval duration, days
- StartSpawnDayOfYear: spawning start, day of year (1-365)
- EndSpawnDayOfYear: spawning end, day of year (1-365)
- IsMigratory: "Yes" or "No"

Return ONLY a JSON object with exactly those 14 keys. Each value is either null
(no evidence) or an object:

{
  "value": <number>,          // point estimate in the unit above; for IsMigratory "Yes"/"No"
  "min": <number|null>,       // lower bound IF the literature reports a range
  "max": <number|null>,       // upper bound IF the literature reports a range
  "unit": "<unit as reported>",
  "basis": "point_estimate" | "range_midpoint" | "single_observation" | "computed",
  "source": "<paper id / authors year>",
  "quote": "<short verbatim fragment supporting the number>"
}

RULES — these are what the field is judged on:
1. If the literature gives a RANGE, fill min and max, and set value to the
   midpoint with basis "range_midpoint". NEVER discard the endpoints.
2. If it gives a single figure, set value, leave min and max null, basis
   "point_estimate" (or "single_observation" for one measured individual).
3. NEVER invent bounds. min/max come from the text, never from your own guess
   about plausible variation.
4. Convert to the unit listed above and say so in "unit" (e.g. "reported in g,
   converted to t"). A unit error is worse than a missing value.
5. Do not transfer values from a different species, even a congener. If the
   fragments discuss another species, return null.
6. Do not infer IsMigratory from general knowledge of the taxon: it needs
   explicit textual support, otherwise null.
7. If a field cannot be supported by the extracted information, return null.
"""

# ── Motores RAG ──────────────────────────────────────────────────────────────


def load_rag_engines() -> Tuple[SectionAwareRAGQueryEngine, SectionAwareRAGQueryEngine]:
    logger.info("Cargando índice RAG...")
    vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
    vector_db.load()

    # Etiquetas de sección: relegan las listas de referencias del top_k. Sin
    # ellas, el 68 % de las consultas por especie arrastra bibliografía.
    sections = load_sections(RAG_INDEX_DIR)
    logger.info(f"Etiquetas de sección: {len(sections)} chunks")

    engine_extract = SectionAwareRAGQueryEngine(
        vector_db=vector_db, model=LLM_MODEL, top_k=10, min_score=0.15,
        max_tokens=MAX_TOKENS, verbose=False,
        system_prompt=SYSTEM_PROMPT_EXTRACT, thinking=THINKING,
        sections=sections,
    )
    # El motor de formateo no recupera nada: sólo reescribe lo ya extraído.
    engine_format = SectionAwareRAGQueryEngine(
        vector_db=vector_db, model=LLM_MODEL, top_k=1, min_score=0.0,
        max_tokens=MAX_TOKENS, verbose=False,
        system_prompt=SYSTEM_PROMPT_FORMAT, thinking=THINKING,
        sections=sections,
    )
    logger.info(f"RAG cargado. Chunks: {vector_db.get_stats().total_chunks}")
    return engine_extract, engine_format


# ── Parseo y normalización ───────────────────────────────────────────────────

def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    return text.strip()


def as_number(value) -> Optional[float]:
    if value is None or value == "null" or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def normalize_field(param: str, raw) -> Optional[dict]:
    """Acepta tanto el objeto nuevo como un escalar suelto (si el modelo falla)."""
    if raw is None or raw == "null":
        return None

    if not isinstance(raw, dict):                      # el modelo devolvió un escalar
        raw = {"value": raw, "basis": "point_estimate"}

    if param in CAT_PARAMS:
        value = str(raw.get("value", "")).strip().capitalize()
        if value not in {"Yes", "No"}:
            return None
        low, high = None, None
    else:
        value = as_number(raw.get("value"))
        low = as_number(raw.get("min"))
        high = as_number(raw.get("max"))
        if value is None and low is not None and high is not None:
            value = (low + high) / 2                   # el modelo dio sólo el rango
        if value is None:
            return None
        if low is not None and high is not None and low > high:
            low, high = high, low

    return {
        "value": value,
        "min": low,
        "max": high,
        "unit": (raw.get("unit") or "").strip() or None,
        "basis": (raw.get("basis") or "").strip() or None,
        "source": (raw.get("source") or "").strip() or None,
        "quote": (raw.get("quote") or "").strip()[:500] or None,
    }


def collect_citations(fields: Dict[str, dict]) -> str:
    seen = []
    for field in fields.values():
        src = field.get("source")
        if src and src not in seen:
            seen.append(src)
    return "; ".join(seen)


# ── Consulta por especie ─────────────────────────────────────────────────────

def query_species(engine_extract, engine_format, species: str, group: str) -> Tuple[Dict[str, dict], str, str]:
    """Devuelve (campos normalizados, texto crudo del paso 1, citas)."""
    logger.info(f"  [{species}] extrayendo…")
    extract_query = (
        f"What quantitative information (numbers, measurements, biological parameters) "
        f"do you have about {species} in the Gulf of California?\n\n"
        f"Report ALL numeric values found (sizes, ages, weights, abundances, growth "
        f"rates, spawning dates, migration status, aquaculture data, or any other "
        f"numbers). For EACH value give its units, say whether it is a point estimate "
        f"or a range (with both endpoints), the sample size, study area, life stage, "
        f"the source paper, and a verbatim quote. Be honest if nothing is found. "
        f"Return JSON."
    )
    extracted = engine_extract.query(extract_query).answer or ""
    if len(extracted.strip()) < 20:
        logger.info("    ✗ sin información")
        return {}, extracted, ""

    logger.info(f"  [{species}] mapeando al esquema…")
    unit_lines = "\n".join(f"- {p}: {u}" for p, u in UNITS.items())
    format_query = (
        f"Extracted information about {species} ({group}):\n\n{extracted}\n\n"
        f"Map it to the 14 Atlantis fields. Target units:\n{unit_lines}\n\n"
        f"Return ONLY the JSON object described in your instructions, with one entry "
        f"per field (null when unsupported). Preserve ranges in min/max."
    )
    formatted = engine_format.query(format_query).answer or ""

    try:
        parsed = json.loads(strip_fences(formatted))
    except json.JSONDecodeError as exc:
        logger.warning(f"    ⚠ JSON inválido: {str(exc)[:60]}")
        return {}, extracted, ""

    fields = {}
    for param in ALL_PARAMS:
        norm = normalize_field(param, parsed.get(param))
        if norm:
            fields[param] = norm

    ranges = sum(1 for f in fields.values() if f["min"] is not None)
    logger.info(f"    ✓ {len(fields)} parámetros ({ranges} con rango)")
    return fields, extracted, collect_citations(fields)


# ── Persistencia ─────────────────────────────────────────────────────────────

def build_skeleton() -> pd.DataFrame:
    """CSV vacío, alineado fila a fila con B1 para poder comparar por índice."""
    base = pd.read_csv(SKELETON_CSV)
    out = base[TAXONOMY].copy()
    for param in NUMERIC_PARAMS:
        out[param] = pd.NA
        out[f"{param}_min"] = pd.NA
        out[f"{param}_max"] = pd.NA
    for param in CAT_PARAMS:
        out[param] = pd.NA
    out["citations"] = pd.NA
    out["notes"] = pd.NA
    return out


def load_table() -> pd.DataFrame:
    if OUTPUT_CSV.exists():
        return pd.read_csv(OUTPUT_CSV)
    table = build_skeleton()
    table.to_csv(OUTPUT_CSV, index=False)
    logger.info(f"CSV inicial creado (vacío, {len(table)} filas): {OUTPUT_CSV.name}")
    return table


def write_row(table: pd.DataFrame, species: str, group: str, fields: Dict[str, dict], citations: str) -> int:
    mask = (table["Species"] == species) & (table["Group"] == group)
    indices = table[mask].index
    if len(indices) == 0:
        logger.warning(f"    especie ausente del CSV: {species} ({group})")
        return 0
    for idx in indices:
        for param, field in fields.items():
            table.at[idx, param] = field["value"]
            if param in NUMERIC_PARAMS:
                table.at[idx, f"{param}_min"] = field["min"]
                table.at[idx, f"{param}_max"] = field["max"]
        if citations:
            table.at[idx, "citations"] = citations
    return len(indices)


def append_raw(species: str, group: str, fields: Dict[str, dict], raw_extraction: str) -> None:
    """Guarda el intermedio del paso 1 — lo que B1–B5 perdían."""
    RAW_JSONL.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "species": species,
        "group": group,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": LLM_MODEL,
        "step1_raw": raw_extraction,
        "step2_fields": fields,
    }
    with RAW_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_long_csv() -> None:
    """Formato largo: una fila por (especie, parámetro) con unidad, base y cita."""
    if not RAW_JSONL.exists():
        return
    rows = []
    with RAW_JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for param, field in (rec.get("step2_fields") or {}).items():
                rows.append({
                    "Species": rec["species"], "Group": rec["group"], "param": param,
                    "value": field.get("value"), "min": field.get("min"), "max": field.get("max"),
                    "unit": field.get("unit"), "basis": field.get("basis"),
                    "source": field.get("source"), "quote": field.get("quote"),
                    "timestamp": rec.get("timestamp"),
                })
    if rows:
        pd.DataFrame(rows).to_csv(LONG_CSV, index=False)
        logger.info(f"Detalle largo: {len(rows)} filas → {LONG_CSV.name}")


def load_progress() -> dict:
    if PROGRESS_JSON.exists():
        return json.loads(PROGRESS_JSON.read_text())
    return {"done_species": [], "groups": {}, "errors": [], "started": datetime.now().isoformat(timespec="seconds")}


def save_progress(progress: dict) -> None:
    PROGRESS_JSON.write_text(json.dumps(progress, ensure_ascii=False, indent=2))


# ── Bucle principal ──────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", help="Lista de grupos separados por coma (por defecto: todos)")
    parser.add_argument("--limit-species", type=int, help="Máximo de especies por grupo (para pruebas)")
    parser.add_argument("--restart", action="store_true", help="Ignora el progreso previo y empieza de cero")
    args = parser.parse_args()

    if not RAG_INDEX_DIR.exists():
        logger.error(f"Índice RAG no encontrado: {RAG_INDEX_DIR}")
        return 1

    if args.restart:
        for path in (OUTPUT_CSV, RAW_JSONL, PROGRESS_JSON):
            path.unlink(missing_ok=True)
        logger.info("Reinicio limpio: CSV, JSONL y progreso borrados")

    engine_extract, engine_format = load_rag_engines()
    table = load_table()
    progress = load_progress()
    done = set(progress["done_species"])

    groups = sorted(table["Group"].dropna().unique().tolist())
    if args.groups:
        wanted = {g.strip() for g in args.groups.split(",")}
        groups = [g for g in groups if g in wanted]
        if not groups:
            logger.error(f"Ningún grupo coincide con {sorted(wanted)}")
            return 1

    logger.info("=" * 70)
    logger.info(f"BÚSQUEDA 6 · {LLM_MODEL} · {len(groups)} grupos · rangos activados")
    logger.info(f"Ya procesadas: {len(done)} especies")
    logger.info("=" * 70)

    total_found = total_ranges = 0

    for gi, group in enumerate(groups, 1):
        species_list = table.loc[table["Group"] == group, "Species"].dropna().unique().tolist()
        if args.limit_species:
            species_list = species_list[: args.limit_species]

        pending = [s for s in species_list if f"{group}|{s}" not in done]
        logger.info(f"\n[{gi}/{len(groups)}] {group} — {len(pending)} pendientes de {len(species_list)}")

        found = ranges = 0
        for si, species in enumerate(pending, 1):
            logger.info(f"[{si}/{len(pending)}] {species}")
            try:
                fields, raw, citations = query_species(engine_extract, engine_format, species, group)
            except Exception as exc:                       # noqa: BLE001
                logger.error(f"    error: {exc}")
                progress["errors"].append(f"{group}|{species}: {exc}")
                save_progress(progress)
                continue

            if fields:
                found += 1
                ranges += sum(1 for f in fields.values() if f["min"] is not None)
                write_row(table, species, group, fields, citations)
                table.to_csv(OUTPUT_CSV, index=False)

            # El crudo del paso 1 se guarda SIEMPRE, tenga o no el paso 2 algo que
            # mapear: si no, no hay forma de distinguir "el corpus no lo tiene" de
            # "el paso 2 lo descartó" — justo el diagnóstico que B1-B5 hacía imposible.
            append_raw(species, group, fields, raw)

            done.add(f"{group}|{species}")
            progress["done_species"] = sorted(done)
            save_progress(progress)

        progress["groups"][group] = {"species": len(species_list), "found": found, "cells_with_range": ranges}
        save_progress(progress)
        total_found += found
        total_ranges += ranges
        logger.info(f"  → {group}: {found} especies con datos, {ranges} celdas con rango")

    write_long_csv()
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ BÚSQUEDA 6 completada · {total_found} especies con datos · {total_ranges} celdas con rango")
    logger.info(f"   Tabla:   {OUTPUT_CSV}")
    logger.info(f"   Detalle: {LONG_CSV}")
    logger.info(f"   Crudo:   {RAW_JSONL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
