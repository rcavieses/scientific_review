#!/usr/bin/env python3
"""Recupera los coeficientes a y b de peso-talla (W = a·L^b) que la extracción perdió.

EL PROBLEMA
===========
`li_a` y `li_b` salen vacíos en el CSV consolidado —0 valores de 1 122 especies—
y no es porque el corpus no los tenga. Es porque a las seis búsquedas se les
pidió «Von Bertalanffy coefficient a/b», que no significa nada: la ecuación de
von Bertalanffy tiene L∞, K y t₀, no una «a» ni una «b». El paso 2 de B6, al no
tener dónde poner un exponente alométrico, lo tiraba.

El crudo del paso 1 que B6 guardó (`outputs/busqueda6_extractions.jsonl`) lo
demuestra especie por especie:

    Triphoturus mexicanus   corpus: b = 2.79    guardado: nada
    Benthosema panamense    corpus: b = 2.09    guardado: nada
    Caulolatilus affinis    corpus: b = 2.66    guardado: L∞ y K, sin la b
    Holacanthus passer      corpus: b = 2.618   guardado: 0.127, que es K

QUÉ HACE ESTE SCRIPT
====================
Dos fases, ambas dirigidas sólo a peso-talla:

  --remap   Reprocesa los 37 crudos del paso 1 que B6 alcanzó a guardar, con la
            definición correcta. No recupera nada del índice: el texto ya está
            extraído, sólo se vuelve a mapear. Barato y verificable.

  --corpus  Consulta el índice, una pregunta por especie, únicamente sobre la
            relación peso-talla. Sólo peces: W = a·L^b no aplica a aves ni
            mamíferos, y es justo ahí donde el emparejamiento difuso metió
            valores de peces en un pato (Aythya affinis heredó la b = 2.66 de
            Caulolatilus affinis por compartir epíteto).

No escribe en ningún CSV. Emite sugerencias a `outputs/review/lw_suggestions.json`
—mismo formato que FishBase, IA y reclasificación— para que el tablero las ponga
frente a un revisor. Un valor extraído sigue siendo una lectura hasta que alguien
la confirma contra su cita.

Uso:
    python3 scripts/phase_7_review/lw_extract.py --remap
    python3 scripts/phase_7_review/lw_extract.py --corpus --limit 20     # prueba
    python3 scripts/phase_7_review/lw_extract.py --corpus                # 827 peces
    python3 scripts/phase_7_review/lw_extract.py --informe
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DATA = ROOT / "data" / "output"
OUT_DIR = ROOT / "outputs" / "review"
SUGGESTIONS = OUT_DIR / "lw_suggestions.json"
RAW_JSONL = OUT_DIR / "lw_extractions.jsonl"
B6_RAW = ROOT / "outputs" / "busqueda6_extractions.jsonl"
BASE_CSV = DATA / "Atlantis_GOC_parametros_biologicos_BUSQUEDA1.csv"
RAG_INDEX_DIR = ROOT / "outputs" / "rag_index_goc_full"
LOG_DIR = ROOT / "outputs" / "logs"

LLM_MODEL = "claude-sonnet-5"
MAX_TOKENS = 2048
THINKING = {"type": "disabled"}

AUTHOR = "Extracción dirigida a peso-talla (W = a·L^b) sobre el corpus, con cita textual"

# W = a·L^b sólo tiene sentido en peces dentro de este corpus. Fuera de aquí, un
# valor de peso-talla es la firma de un emparejamiento equivocado, no un dato.
CLASES_PEZ = {"Teleostei", "Actinopterygii", "Chondrichthyes"}

# Rangos de plausibilidad. No son un gusto estético: fuera de ellos el número no
# puede ser lo que dice ser, y aceptarlo callado es como se llenó
# `Von_bertalanffy_a` de L∞ y de t₀.
#   a depende de la unidad (g/cm frente a kg/cm) pero vive en potencias negativas
#   b es adimensional y ronda 3 — Froese (2006) sitúa el 95 % entre 2.5 y 3.5
A_RANGE = (1e-9, 1.0)
B_RANGE = (1.5, 4.5)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("lw")


SYSTEM_PROMPT = """\
You are extracting ONE specific thing from marine scientific literature: the
allometric WEIGHT-LENGTH relationship W = a * L^b.

    a = the multiplicative coefficient (units depend on whether W is in g or kg
        and L in cm or mm; it is a small number, typically 1e-6 to 1e-2)
    b = the dimensionless exponent, close to 3 (isometric growth). Papers also
        call it the "allometric coefficient", "slope of the log-log regression",
        or report it as "b = 3.05".

These are NOT von Bertalanffy parameters. If the fragments give L-infinity, K or
t0, those are a DIFFERENT relationship and you must ignore them here.

Rules:
1. Answer ONLY from the provided fragments. Never supply a from general
   knowledge of the taxon or of a related species.
2. The value must belong to the species asked. Congeners are not acceptable, and
   neither is a species that merely shares a specific epithet: "affinis" appears
   in a silverside, a machete, a tilefish and a DUCK. If the fragment is about a
   different species, return null and say which species it was about.
3. Report the units as the paper states them (e.g. "W in g, TL in cm"). A
   weight-length a is meaningless without knowing them.
4. Quote verbatim the sentence or table cell the number comes from.
5. A qualitative statement ("growth was positively allometric") is NOT a value.
   Return null for it, but record it in `notes`.
"""

SCHEMA_INSTRUCTIONS = """\
Return ONLY a JSON object, no prose around it:

{
  "li_a": null | {"value": <number>, "unit": "<W and L units as reported>",
                  "n": <sample size or null>, "r2": <number or null>,
                  "sex_stage": "<sex/life stage or null>",
                  "source": "<paper id / authors year>",
                  "quote": "<verbatim fragment>"},
  "li_b": null | { ... same shape ... },
  "notes": "<one line: what was found, or why nothing was>"
}
"""


# ── utilidades ───────────────────────────────────────────────────────────

def strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    return text.strip()


def as_number(value) -> Optional[float]:
    if value is None or value in ("null", ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("×", "x").replace("−", "-")
    m = re.search(r"-?\d+(?:\.\d+)?(?:\s*[eEx]\s*10?\s*\^?\s*-?\d+)?", text)
    if not m:
        return None
    token = m.group(0).replace(" ", "")
    token = re.sub(r"x10\^?", "e", token)
    try:
        return float(token)
    except ValueError:
        return None


def plausible(param: str, value: float) -> tuple[bool, str]:
    lo, hi = A_RANGE if param == "li_a" else B_RANGE
    if not (lo <= value <= hi):
        que = ("un coeficiente de peso-talla" if param == "li_a"
               else "un exponente alométrico")
        return False, f"{value:g} no puede ser {que} (rango admisible {lo:g}–{hi:g})"
    return True, ""


def epiteto(species: str) -> str:
    parts = species.split()
    return parts[1] if len(parts) > 1 else ""


def cita_es_de_la_especie(species: str, field: dict) -> tuple[bool, str]:
    """¿La cita habla de esta especie, o de otra que comparte epíteto?

    Es la comprobación que faltó cuando la b = 2.66 de Caulolatilus affinis
    terminó en Aythya affinis, un pato. Se busca el género (o su abreviatura
    «C.») en la cita; si sólo aparece el epíteto, no basta.
    """
    quote = f"{field.get('quote') or ''} {field.get('source') or ''}"
    genero = species.split()[0]
    if not genero:
        return True, ""
    if genero.lower() in quote.lower():
        return True, ""
    if re.search(rf"\b{re.escape(genero[0])}\.\s*{re.escape(epiteto(species))}", quote, re.I):
        return True, ""
    if epiteto(species) and epiteto(species).lower() in quote.lower():
        return False, (f"la cita nombra «{epiteto(species)}» pero no el género "
                       f"«{genero}»: puede ser otra especie con el mismo epíteto")
    return True, ""


def normalize(param: str, raw, species: str) -> tuple[Optional[dict], Optional[str]]:
    """Devuelve (campo normalizado, motivo del descarte)."""
    if raw is None or raw == "null":
        return None, None
    if not isinstance(raw, dict):
        raw = {"value": raw}
    value = as_number(raw.get("value"))
    if value is None:
        return None, "sin valor numérico"

    ok, motivo = plausible(param, value)
    if not ok:
        return None, motivo

    quote = (raw.get("quote") or "").strip()
    if not quote:
        return None, "sin cita textual: no se puede comprobar"

    coincide, aviso = cita_es_de_la_especie(species, raw)
    return {
        "value": value,
        "unit": (raw.get("unit") or "").strip() or None,
        "n": as_number(raw.get("n")),
        "r2": as_number(raw.get("r2")),
        "sex_stage": (raw.get("sex_stage") or "").strip() or None,
        "source": (raw.get("source") or "").strip() or None,
        "quote": quote[:500],
        "epithet_warning": None if coincide else aviso,
    }, None


# ── construcción de la sugerencia ────────────────────────────────────────

def build_suggestion(idx: int, param: str, species: str, group: str,
                     field: dict, origen: str) -> dict:
    aviso = field.get("epithet_warning")
    confianza = "baja" if aviso else ("alta" if field.get("n") else "media")

    razones = [f"El corpus reporta {param.replace('li_', '')} = {field['value']:g} "
               f"para {species}."]
    if field.get("unit"):
        razones.append(f"Unidades declaradas: {field['unit']}.")
    else:
        razones.append("El paper no declara las unidades de W y L: sin ellas, "
                       "la «a» no es interpretable — confírmalas antes de aceptar.")
    if field.get("n"):
        razones.append(f"n = {field['n']:g}.")
    if field.get("r2"):
        razones.append(f"r² = {field['r2']:g}.")
    if field.get("sex_stage"):
        razones.append(f"Sexo / etapa: {field['sex_stage']}.")
    if aviso:
        razones.append(aviso.capitalize() + ".")
    razones.append("Extraído del corpus con cita textual; confírmalo contra ella.")

    citations = []
    if field.get("source"):
        citations.append({
            "key": field["source"],
            "ref": field["source"],
            "supports": field["quote"],
        })

    return {
        "param": param,
        "species": species,
        "group": group,
        "value": field["value"],
        "unit": field.get("unit"),
        "confidence": confianza,
        "basis": "extraccion_dirigida_peso_talla",
        "scope": origen,
        "n_records": int(field["n"]) if field.get("n") else None,
        "observed_range": None,
        "rationale": " ".join(razones),
        "quote": field["quote"],
        "citations": citations,
        "author": AUTHOR,
    }


# ── fase A · re-mapeo del crudo ya guardado ──────────────────────────────

def fase_remap(client, base: pd.DataFrame, suggestions: dict, descartes: list) -> int:
    if not B6_RAW.exists():
        logger.error("No existe %s", B6_RAW)
        return 0

    fila = {str(base.at[i, "Species"]): i for i in range(len(base))}
    registros = [json.loads(line) for line in B6_RAW.open(encoding="utf-8")]
    logger.info("Re-mapeo de %d crudos del paso 1 de B6", len(registros))

    nuevos = 0
    for i, rec in enumerate(registros, 1):
        species, group = rec["species"], rec["group"]
        idx = fila.get(species)
        if idx is None:
            logger.warning("  [%s] no está en el CSV base", species)
            continue

        pregunta = (
            f"Fragments already extracted from the corpus about {species} ({group}):\n\n"
            f"{rec['step1_raw']}\n\n"
            f"From this text ONLY, extract the weight-length relationship "
            f"W = a * L^b for {species}.\n\n{SCHEMA_INSTRUCTIONS}"
        )
        logger.info("[%d/%d] %s", i, len(registros), species)
        try:
            answer = llm(client, pregunta)
        except Exception as exc:                              # noqa: BLE001
            logger.error("    error: %s", exc)
            continue
        nuevos += cosechar(answer, idx, species, group, "re-mapeo del crudo de B6",
                           suggestions, descartes, rec["step1_raw"])
    return nuevos


# ── fase B · consulta dirigida al índice ─────────────────────────────────

def fase_corpus(engine, base: pd.DataFrame, suggestions: dict, descartes: list,
                limit: Optional[int], solo_grupo: Optional[str]) -> int:
    peces = base[base["Class"].isin(CLASES_PEZ)]
    if solo_grupo:
        peces = peces[peces["Group"] == solo_grupo]
    # Reanudable: una especie ya consultada no se vuelve a preguntar, aunque no
    # haya dado nada. Sin esto, una corrida interrumpida repite —y cobra— todo
    # lo que ya se sabe que el corpus no tiene.
    hechos = consultadas() | {s["species"] for s in suggestions.values()}
    pendientes = [(i, str(peces.at[i, "Species"]), str(peces.at[i, "Group"]))
                  for i in peces.index if str(peces.at[i, "Species"]) not in hechos]
    if limit:
        pendientes = pendientes[:limit]

    logger.info("Consulta dirigida a peso-talla · %d especies de peces", len(pendientes))
    nuevos = 0
    for i, (idx, species, group) in enumerate(pendientes, 1):
        pregunta = (
            f"What is the weight-length relationship W = a * L^b reported for "
            f"{species} in the Gulf of California?\n\n"
            f"Look for: the coefficient a, the exponent b (the allometric or "
            f"condition-factor exponent, close to 3), the units of W and L, the "
            f"sample size, r squared, and the sex or life stage. Ignore von "
            f"Bertalanffy growth parameters — they are a different relationship.\n\n"
            f"{SCHEMA_INSTRUCTIONS}"
        )
        logger.info("[%d/%d] %s", i, len(pendientes), species)
        try:
            answer = engine.query(pregunta).answer or ""
        except Exception as exc:                              # noqa: BLE001
            logger.error("    error: %s", exc)
            continue
        nuevos += cosechar(answer, idx, species, group, "consulta dirigida al corpus",
                           suggestions, descartes, None)
        if i % 25 == 0:
            guardar(suggestions, descartes)
    return nuevos


# ── cosecha común a las dos fases ────────────────────────────────────────

def cosechar(answer: str, idx: int, species: str, group: str, origen: str,
             suggestions: dict, descartes: list, crudo: Optional[str]) -> int:
    try:
        parsed = json.loads(strip_fences(answer))
    except json.JSONDecodeError:
        logger.warning("    ⚠ JSON inválido")
        return 0

    encontrados = 0
    for param in ("li_a", "li_b"):
        field, motivo = normalize(param, parsed.get(param), species)
        if motivo:
            descartes.append({"species": species, "param": param, "reason": motivo,
                              "raw": parsed.get(param)})
            logger.info("    ✗ %s descartado: %s", param, motivo)
            continue
        if not field:
            continue
        suggestions[f"{idx}:{param}"] = build_suggestion(idx, param, species, group,
                                                         field, origen)
        encontrados += 1
        marca = " ⚠epíteto" if field.get("epithet_warning") else ""
        logger.info("    ✓ %s = %g%s", param, field["value"], marca)

    RAW_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with RAW_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "species": species, "group": group, "row": idx, "origen": origen,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "model": LLM_MODEL, "answer": answer,
            "notes": parsed.get("notes"),
            "step1_raw": crudo,
        }, ensure_ascii=False) + "\n")

    if not encontrados:
        logger.info("    — sin peso-talla (%s)", (parsed.get("notes") or "")[:90])
    return encontrados


# ── LLM sin recuperación (fase A) ────────────────────────────────────────

def llm(client, question: str) -> str:
    response = client.messages.create(
        model=LLM_MODEL, max_tokens=MAX_TOKENS, thinking=THINKING,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def make_client():
    import anthropic
    from dotenv import load_dotenv
    import os
    load_dotenv(ROOT / ".env")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Falta ANTHROPIC_API_KEY (ponla en .env)")
    return anthropic.Anthropic(api_key=key)


def make_engine():
    from pipeline.rag.vector_db import VectorDBManager
    from section_aware_engine import SectionAwareRAGQueryEngine, load_sections
    logger.info("Cargando índice RAG…")
    vector_db = VectorDBManager(index_dir=str(RAG_INDEX_DIR), embedding_dim=384)
    vector_db.load()
    sections = load_sections(RAG_INDEX_DIR)
    engine = SectionAwareRAGQueryEngine(
        vector_db=vector_db, model=LLM_MODEL, top_k=10, min_score=0.15,
        max_tokens=MAX_TOKENS, verbose=False,
        system_prompt=SYSTEM_PROMPT, thinking=THINKING, sections=sections,
    )
    logger.info("RAG cargado · %d chunks", vector_db.get_stats().total_chunks)
    return engine


# ── persistencia e informe ───────────────────────────────────────────────

def consultadas() -> set[str]:
    """Especies que ya pasaron por una consulta, con o sin resultado."""
    if not RAW_JSONL.exists():
        return set()
    hechas = set()
    for line in RAW_JSONL.open(encoding="utf-8"):
        try:
            hechas.add(json.loads(line)["species"])
        except (json.JSONDecodeError, KeyError):
            continue
    return hechas


def cargar() -> tuple[dict, list]:
    if not SUGGESTIONS.exists():
        return {}, []
    doc = json.loads(SUGGESTIONS.read_text(encoding="utf-8"))
    return doc.get("suggestions", {}), doc.get("discarded", [])


def guardar(suggestions: dict, descartes: list) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUGGESTIONS.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "author": AUTHOR,
        "model": LLM_MODEL,
        "warning": (
            "Valores del corpus con cita textual, NO datos confirmados. La «a» de "
            "peso-talla depende de las unidades de W y L: sin ellas no es "
            "comparable entre especies. Revisa la cita antes de aceptar."
        ),
        "params_covered": ["li_a", "li_b"],
        "plausibility": {"li_a": list(A_RANGE), "li_b": list(B_RANGE)},
        "suggestions": suggestions,
        "discarded": descartes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def informe(suggestions: dict, descartes: list) -> None:
    if not suggestions:
        print("Sin sugerencias todavía. Ejecuta --remap o --corpus.")
        return
    print(f"{'especie':<30} {'param':<7} {'valor':>12}  {'n':>5}  unidad / aviso")
    print("-" * 100)
    for key in sorted(suggestions, key=lambda k: (suggestions[k]["species"], k)):
        s = suggestions[key]
        aviso = "⚠ epíteto" if s["confidence"] == "baja" else (s.get("unit") or "sin unidad")
        n = s.get("n_records") or ""
        print(f"{s['species']:<30} {s['param']:<7} {s['value']:>12g}  {n:>5}  {aviso}")
    print(f"\n{len(suggestions)} sugerencias · {len(descartes)} descartes")
    if descartes:
        print("\nDescartes:")
        for d in descartes[:30]:
            print(f"  {d['species']:<30} {d['param']:<7} {d['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remap", action="store_true",
                        help="reprocesa los crudos del paso 1 de B6 (sin recuperación)")
    parser.add_argument("--corpus", action="store_true",
                        help="consulta dirigida al índice, sólo peces")
    parser.add_argument("--limit", type=int, help="tope de especies (para probar)")
    parser.add_argument("--group", help="restringir a un grupo funcional")
    parser.add_argument("--informe", action="store_true", help="muestra lo ya extraído")
    parser.add_argument("--reset", action="store_true", help="empieza de cero")
    args = parser.parse_args()

    if args.reset:
        for path in (SUGGESTIONS, RAW_JSONL):
            path.unlink(missing_ok=True)

    suggestions, descartes = cargar()
    if args.informe or not (args.remap or args.corpus):
        informe(suggestions, descartes)
        return

    base = pd.read_csv(BASE_CSV)
    nuevos = 0
    if args.remap:
        nuevos += fase_remap(make_client(), base, suggestions, descartes)
        guardar(suggestions, descartes)
    if args.corpus:
        nuevos += fase_corpus(make_engine(), base, suggestions, descartes,
                              args.limit, args.group)
        guardar(suggestions, descartes)

    print(f"\n✅ {nuevos} valores nuevos · {len(suggestions)} sugerencias en total")
    print(f"   {SUGGESTIONS.relative_to(ROOT)}")
    print(f"   Crudo: {RAW_JSONL.relative_to(ROOT)}")
    print("\n   Siguiente paso — llevarlas al tablero:")
    print("   python3 scripts/phase_7_review/build_review_queue.py")


if __name__ == "__main__":
    main()
