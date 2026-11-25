#!/usr/bin/env python3
"""Quinto canal de sugerencias: dos notebooks de NotebookLM.

EL PROBLEMA
===========
Hay literatura que el índice FAISS no tiene —informes técnicos, literatura gris,
capítulos que nunca se digitalizaron como PDF del corpus— y que sí está cargada
en dos notebooks de NotebookLM. Hasta ahora esa información sólo se consultaba a
mano, especie por especie, y no dejaba rastro en el dataset.

QUÉ HACE ESTE SCRIPT
====================
Pregunta a los dos notebooks por las celdas (especie × parámetro) que siguen
vacías, y emite el resultado como sugerencias para el tablero. No escribe en
ningún CSV: una sugerencia sólo se convierte en dato cuando un humano la acepta,
igual que en FishBase, IA, reclasificación y peso-talla.

POR QUÉ DOS NOTEBOOKS, Y QUÉ SE GANA
====================================
No se concatenan: se pregunta a cada uno por separado y se reconcilian. La
concordancia entre dos corpus independientes es la señal de confianza más barata
que existe, y la discrepancia es información que un promedio habría escondido:

    ambos coinciden (≤ tolerancia) → confianza alta   → severidad warning
    sólo uno responde             → confianza media  → severidad serious
    responden y discrepan         → confianza baja   → severidad critical
    ninguno responde              → descarte, con su motivo

Como el tablero ya ordena por severidad, las discrepancias suben solas al
principio de la cola en vez de diluirse.

DOS PASOS POR ESPECIE
=====================
  1. Pregunta en prosa a NotebookLM, una por (especie, notebook), pidiendo de
     golpe todos los parámetros que ese notebook declara cubrir. NotebookLM
     aterriza mejor en prosa que forzado a JSON, y agrupar por especie en vez de
     por celda reduce el gasto de cuota unas cinco veces.
  2. Parseo de esa prosa a JSON con Claude, exigiendo cita textual. Un valor sin
     frase que lo sostenga se descarta: es la defensa contra que el parseador
     rellene huecos por su cuenta.

LO QUE HAY QUE SABER ANTES DE USARLO
====================================
`notebooklm-py` NO es oficial de Google (ver nblm_client.py). Y una respuesta de
NotebookLM **no es reproducible**: su corpus no está versionado en este repo. Por
eso el crudo de cada consulta —respuesta íntegra, citas y títulos de fuente— se
guarda en `outputs/review/nblm_extractions.jsonl`. Ése, y no la conexión, es el
activo que perdura.

Uso:
    python3 scripts/phase_7_review/nblm_client.py --listar     # ids -> config
    python3 scripts/phase_7_review/nblm_extract.py --dry-run --limit 1
    python3 scripts/phase_7_review/nblm_extract.py --limit 10 --group "Peces demersales"
    python3 scripts/phase_7_review/nblm_extract.py
    python3 scripts/phase_7_review/nblm_extract.py --informe
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from build_review_queue import (  # noqa: E402
    PARAMS, load_searches, norm_cat, norm_num, spread_pct,
)
# De lw_extract se reusan sólo utilidades puras. Su `llm()` NO sirve aquí:
# lleva clavado el system prompt de peso-talla, y aquí se parsea cualquier
# parámetro. Ver `llm()` más abajo.
from lw_extract import as_number, make_client, strip_fences  # noqa: E402
from nblm_client import NblmSession, NotebookCfg, load_config  # noqa: E402

OUT_DIR = ROOT / "outputs" / "review"
SUGGESTIONS = OUT_DIR / "nblm_suggestions.json"
RAW_JSONL = OUT_DIR / "nblm_extractions.jsonl"
DECISIONS = OUT_DIR / "decisions.json"
BASE_CSV = ROOT / "data" / "output" / "Atlantis_GOC_parametros_biologicos_BUSQUEDA1.csv"

LLM_MODEL = "claude-sonnet-5"
MAX_TOKENS = 3072

AUTHOR = "Consulta a notebooks de NotebookLM, reconciliada entre dos fuentes"

# Rangos de imposibilidad, no de gusto. Un valor fuera de aquí no puede ser lo
# que dice ser, y aceptarlo callado es exactamente como `Von_bertalanffy_a` se
# llenó de L∞ y de t₀. Longitudes en cm (3000 cm cubre a la ballena azul).
RANGOS: dict[str, tuple[float, float]] = {
    "biomass_mt":          (0, 5e7),
    "abundance_numbers":   (0, 1e15),
    "mean_body_size":      (0, 3000),
    "max_age":             (0, 250),
    "natural_mortality":   (0, 5),
    "Lmax":                (0, 3000),
    "li_a":                (1e-9, 1.0),
    "li_b":                (1.5, 4.5),
    "vb_Linf":             (0, 3000),
    "vb_t0":               (-10, 10),
    "growth_rate":         (0, 5),
    "age_first_maturity":  (0, 100),
    "larval_duration":     (0, 400),
    "StartSpawnDayOfYear": (1, 366),
    "EndSpawnDayOfYear":   (1, 366),
}

SEVERIDAD = {"alta": "warning", "media": "serious", "baja": "critical"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nblm-extract")


PARSE_SYSTEM = """\
Extraes valores numéricos y categóricos de la respuesta de un asistente que ha
leído literatura pesquera y marina. Tu única fuente es el texto que te dan.

Reglas, sin excepción:
1. No aportes conocimiento propio sobre la especie ni sobre taxones parecidos.
   Si el texto no da un valor, ese parámetro es null.
2. Una afirmación cualitativa («crece rápido», «es longeva») NO es un valor.
   Devuelve null y anótalo en `notes`.
3. Copia la frase de la que sale cada número, literal, en `quote`. Un valor sin
   frase que lo sostenga no sirve: se va a descartar.
4. Si el texto marca la afirmación con un número de cita entre corchetes, ponlo
   en `cita` como entero. Si no lo marca, pon null; no lo inventes.
5. Respeta las unidades que declare el texto y conviértelas a la unidad pedida
   sólo si la conversión es evidente (kg→t, mm→cm). Si conviertes, dilo en
   `quote` añadiendo « [convertido de X]».
6. Si el texto habla de otra especie —un congénere, o una que sólo comparte
   epíteto específico— es null, y lo dices en `notes`.
"""


# ── selección de celdas ─────────────────────────────────────────────────

def celdas_pendientes(frames: dict[str, pd.DataFrame], params: list[str],
                      decisions: dict) -> dict[int, set[str]]:
    """Celdas vacías en las seis búsquedas y sin decisión humana.

    Dos filtros, y los dos importan. El primero evita gastar cuota en celdas que
    ya tienen valor. El segundo es la invariante que respetan todos los canales
    automáticos (ver fb_autovalidate.seleccionar): una celda que un humano ya
    aceptó o rechazó no se vuelve a proponer.
    """
    base = frames["B1"]
    pendientes: dict[int, set[str]] = {}
    for idx in range(len(base)):
        libres = set()
        for param in params:
            meta = PARAMS[param]
            tiene_valor = False
            for df in frames.values():
                if param not in df.columns:
                    continue
                valor = (norm_num(df.at[idx, param]) if meta["type"] == "num"
                         else norm_cat(df.at[idx, param]))
                if valor is not None:
                    tiene_valor = True
                    break
            if tiene_valor:
                continue
            decidida = decisions.get(f"{idx}:{param}", {}).get("status")
            if decidida in ("accepted", "rejected"):
                continue
            libres.add(param)
        if libres:
            pendientes[idx] = libres
    return pendientes


def load_decisions() -> dict:
    if not DECISIONS.exists():
        return {}
    try:
        return json.loads(DECISIONS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("decisions.json ilegible: se sigue sin él")
        return {}


# ── paso 1 · pregunta en prosa al notebook ──────────────────────────────

def descripcion_param(param: str) -> str:
    meta = PARAMS[param]
    unidad = f" en {meta['unit']}" if meta["unit"] else ""
    hint = f" ({meta['hint']})" if meta.get("hint") else ""
    return f"- {meta['label']}{unidad} [clave: {param}]{hint}"


def pregunta_notebook(species: str, group: str, params: list[str]) -> str:
    return (
        f"¿Qué valores reportan estas fuentes para *{species}* "
        f"(grupo funcional: {group}) en el Golfo de California o el Pacífico "
        f"mexicano?\n\n"
        f"Busco específicamente:\n"
        + "\n".join(descripcion_param(p) for p in params)
        + "\n\nPara cada uno, si el material lo dice: el valor, las unidades tal "
          "como aparecen, el tamaño de muestra, la zona y el año del estudio, y "
          "la frase textual de donde sale.\n\n"
          "Si estas fuentes no lo dicen, dilo explícitamente en lugar de "
          "estimarlo: un hueco declarado me sirve, un número inventado no. No "
          "uses conocimiento general sobre el taxón ni valores de especies "
          "parecidas — sólo lo que estas fuentes afirman sobre esta especie."
    )


def instrucciones_parseo(params: list[str]) -> str:
    lineas = []
    for p in params:
        tipo = '"Yes" | "No"' if PARAMS[p]["type"] == "cat" else "<número>"
        unidad = PARAMS[p]["unit"] or "sin unidad"
        lineas.append(
            f'  "{p}": null | {{"value": {tipo}, "unit": "<unidad declarada; '
            f'la pedida es {unidad}>", "n": <muestra o null>, '
            f'"cita": <entero o null>, "quote": "<frase literal>", '
            f'"scope": "<zona y año, o null>"}}'
        )
    return ("Devuelve SÓLO un objeto JSON, sin prosa alrededor:\n\n"
            "{\n" + ",\n".join(lineas)
            + ',\n  "notes": "<una línea: qué se encontró, o por qué nada>"\n}')


# ── paso 2 · parseo a JSON ──────────────────────────────────────────────

def llm(client, pregunta: str) -> str:
    response = client.messages.create(
        model=LLM_MODEL, max_tokens=MAX_TOKENS, thinking={"type": "disabled"},
        system=PARSE_SYSTEM,
        messages=[{"role": "user", "content": pregunta}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def parsear(client, species: str, params: list[str], respuesta: dict) -> Optional[dict]:
    citas = "\n".join(f"[{c['n']}] {c['source_title']}" for c in respuesta["citations"]) or "(ninguna)"
    pregunta = (
        f"Respuesta de un asistente que ha leído literatura sobre {species}:\n\n"
        f"---\n{respuesta['answer']}\n---\n\n"
        f"Citas que acompañan a esa respuesta:\n{citas}\n\n"
        f"Extrae de ese texto, y sólo de él, los siguientes parámetros para "
        f"{species}.\n\n{instrucciones_parseo(params)}"
    )
    try:
        crudo = llm(client, pregunta)
    except Exception as exc:                              # noqa: BLE001
        logger.error("    parseo falló: %s", exc)
        return None
    try:
        return json.loads(strip_fences(crudo))
    except json.JSONDecodeError:
        logger.warning("    ⚠ el parseo no devolvió JSON válido")
        return None


def normalizar(param: str, raw, citations: list[dict]) -> tuple[Optional[dict], Optional[str]]:
    """Devuelve (campo normalizado, motivo del descarte)."""
    if raw is None or raw == "null":
        return None, None
    if not isinstance(raw, dict):
        raw = {"value": raw}

    meta = PARAMS[param]
    if meta["type"] == "cat":
        value = norm_cat(raw.get("value"))
        if value is None:
            return None, "sin valor categórico reconocible"
    else:
        value = as_number(raw.get("value"))
        if value is None:
            return None, "sin valor numérico"
        lo, hi = RANGOS.get(param, (float("-inf"), float("inf")))
        if not (lo <= value <= hi):
            return None, (f"{value:g} está fuera del rango admisible para "
                          f"{meta['label']} ({lo:g}–{hi:g}): no puede ser ese parámetro")

    quote = (raw.get("quote") or "").strip()
    if not quote:
        return None, "sin cita textual: no se puede comprobar"

    # La cita resoluble es lo que distingue «lo dice esta fuente» de «lo dice el
    # asistente». Sin ella el valor sigue emitiéndose —descartarlo perdería
    # recall real— pero baja de confianza y el tablero lo dice.
    cita_n = raw.get("cita")
    fuente = next((c for c in citations if c.get("n") == cita_n), None) if cita_n is not None else None

    return {
        "value": value,
        "unit": (raw.get("unit") or "").strip() or None,
        "n": as_number(raw.get("n")),
        "scope": (raw.get("scope") or "").strip() or None,
        "quote": quote[:500],
        "cita_n": cita_n,
        "fuente": fuente["source_title"] if fuente else None,
        "fuente_texto": fuente["text"] if fuente else None,
    }, None


# ── reconciliación entre notebooks ──────────────────────────────────────

def reconciliar(param: str, lecturas: list[tuple[NotebookCfg, dict]],
                tolerancia: float) -> dict:
    """Funde lo que dijo cada notebook en una sola sugerencia.

    `lecturas` viene ordenada por prioridad, así que la primera manda cuando hay
    que desempatar. Devuelve siempre el detalle por notebook: el revisor tiene
    que poder ver los dos números, no sólo el que ganó.
    """
    meta = PARAMS[param]
    cfg0, f0 = lecturas[0]

    if len(lecturas) == 1:
        return {
            "value": f0["value"],
            "confidence": "baja" if f0["fuente"] is None else "media",
            "discrepancia": False,
            "acuerdo": None,
            "scope": f"sólo {cfg0.alias}",
        }

    cfg1, f1 = lecturas[1]
    if meta["type"] == "cat":
        coinciden = f0["value"] == f1["value"]
        spread = 0.0 if coinciden else 100.0
        valor = f0["value"]
    else:
        spread = spread_pct([f0["value"], f1["value"]])
        coinciden = spread <= tolerancia * 100
        valor = round((f0["value"] + f1["value"]) / 2, 6) if coinciden else f0["value"]

    if coinciden:
        return {
            "value": valor,
            # Dos corpus independientes que coinciden es la mejor señal que este
            # canal puede dar — pero si ninguno de los dos trae cita resoluble,
            # lo que coincide son dos afirmaciones sin respaldo localizable.
            "confidence": "alta" if (f0["fuente"] or f1["fuente"]) else "media",
            "discrepancia": False,
            "acuerdo": round(spread, 1),
            "scope": f"{cfg0.alias} + {cfg1.alias} (concuerdan, {spread:.1f} %)",
        }
    return {
        "value": valor,
        "confidence": "baja",
        "discrepancia": True,
        "acuerdo": round(spread, 1),
        "scope": f"{cfg0.alias} vs {cfg1.alias} (discrepan {spread:.0f} %)",
    }


def build_suggestion(param: str, species: str, group: str,
                     lecturas: list[tuple[NotebookCfg, dict]],
                     rec: dict) -> dict:
    meta = PARAMS[param]
    razones = []
    for cfg, f in lecturas:
        trozo = f"{cfg.alias} reporta {meta['label']} = "
        trozo += f"{f['value']:g}" if meta["type"] == "num" else str(f["value"])
        if f.get("unit"):
            trozo += f" {f['unit']}"
        if f.get("n"):
            trozo += f" (n = {f['n']:g})"
        if f.get("scope"):
            trozo += f", {f['scope']}"
        razones.append(trozo + ".")

    if rec["discrepancia"]:
        razones.append(
            f"Los dos notebooks NO coinciden ({rec['acuerdo']:.0f} % de diferencia). "
            f"Se propone el del notebook prioritario, pero lo que hay que decidir "
            f"es cuál de las dos fuentes aplica al Golfo de California."
        )
    elif rec["acuerdo"] is not None:
        razones.append(f"Ambos notebooks concuerdan dentro del {rec['acuerdo']:.1f} %.")

    sin_cita = [cfg.alias for cfg, f in lecturas if not f["fuente"]]
    if sin_cita:
        razones.append(
            f"Sin cita resoluble en: {', '.join(sin_cita)} — el asistente lo afirmó "
            f"sin marcar de qué documento sale. Comprueba la frase antes de aceptar."
        )
    razones.append("Respuesta de NotebookLM sobre un corpus externo a este repo: "
                   "no es reproducible desde aquí. Lee la cita.")

    citations = [{
        "key": f"[{f['cita_n']}]" if f.get("cita_n") is not None else cfg.alias,
        "ref": f["fuente"] or f"{cfg.alias} (fuente no identificada)",
        "supports": f["quote"],
    } for cfg, f in lecturas]

    return {
        "param": param,
        "species": species,
        "group": group,
        "value": rec["value"],
        "unit": next((f["unit"] for _, f in lecturas if f.get("unit")), None) or meta["unit"] or None,
        "confidence": rec["confidence"],
        "basis": "consulta_notebooklm",
        "scope": rec["scope"],
        "discrepancia": rec["discrepancia"],
        "acuerdo_pct": rec["acuerdo"],
        "n_records": int(next((f["n"] for _, f in lecturas if f.get("n")), 0)) or None,
        "notebooks": [{
            "alias": cfg.alias,
            "value": f["value"],
            "unit": f.get("unit"),
            "n": f.get("n"),
            "scope": f.get("scope"),
            "quote": f["quote"],
            "source_title": f["fuente"],
        } for cfg, f in lecturas],
        "quote": lecturas[0][1]["quote"],
        "citations": citations,
        "author": AUTHOR,
    }


# ── persistencia ────────────────────────────────────────────────────────

def crudos() -> dict[tuple[str, str], dict]:
    """Lo ya consultado, por (especie, notebook), con su parseo.

    Reanudar no es sólo saltarse lo hecho: para reconciliar hace falta lo que
    dijo el otro notebook, aunque se preguntara en una corrida anterior.
    """
    if not RAW_JSONL.exists():
        return {}
    out: dict[tuple[str, str], dict] = {}
    for line in RAW_JSONL.open(encoding="utf-8"):
        try:
            rec = json.loads(line)
            out[(rec["species"], rec["alias"])] = rec
        except (json.JSONDecodeError, KeyError):
            continue
    return out


def anotar_crudo(rec: dict) -> None:
    RAW_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with RAW_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cargar() -> tuple[dict, list]:
    if not SUGGESTIONS.exists():
        return {}, []
    doc = json.loads(SUGGESTIONS.read_text(encoding="utf-8"))
    return doc.get("suggestions", {}), doc.get("discarded", [])


def guardar(suggestions: dict, descartes: list, cfgs: list[NotebookCfg]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUGGESTIONS.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": f"NotebookLM ({len(cfgs)} notebooks: "
                  + ", ".join(c.alias for c in cfgs) + ")",
        "author": AUTHOR,
        "model": f"{LLM_MODEL} (sólo para el parseo; el valor lo da NotebookLM)",
        "warning": (
            "Respuestas de NotebookLM sobre un corpus externo a este repositorio. "
            "NO son reproducibles: no hay índice versionado detrás, y la librería "
            "que las obtiene no es oficial de Google. Lee la cita antes de aceptar; "
            "un valor sin fuente identificada no es un dato."
        ),
        "params_covered": sorted({s["param"] for s in suggestions.values()}),
        "notebooks": [{"alias": c.alias, "prioridad": c.prioridad,
                       "params_covered": c.params_covered} for c in cfgs],
        "suggestions": suggestions,
        "discarded": descartes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def informe(suggestions: dict, descartes: list) -> None:
    if not suggestions:
        print("Sin sugerencias todavía. Ejecuta el script sin --informe.")
        return
    print(f"{'especie':<30} {'param':<20} {'valor':>14}  {'conf':<6} origen")
    print("-" * 110)
    for key in sorted(suggestions, key=lambda k: (suggestions[k]["species"], k)):
        s = suggestions[key]
        valor = f"{s['value']:g}" if isinstance(s["value"], (int, float)) else str(s["value"])
        marca = "⚠ " if s.get("discrepancia") else "  "
        print(f"{s['species']:<30} {s['param']:<20} {valor:>14}  "
              f"{marca}{s['confidence']:<5} {s['scope']}")
    n_disc = sum(1 for s in suggestions.values() if s.get("discrepancia"))
    por_conf = {c: sum(1 for s in suggestions.values() if s["confidence"] == c)
                for c in ("alta", "media", "baja")}
    print(f"\n{len(suggestions)} sugerencias · {n_disc} con discrepancia entre notebooks "
          f"· {len(descartes)} descartes")
    print("  por confianza: " + " · ".join(f"{c}={n}" for c, n in por_conf.items()))
    if descartes:
        print("\nDescartes (primeros 30):")
        for d in descartes[:30]:
            print(f"  {d['species']:<30} {d['param']:<20} {d['reason']}")


# ── corrida ─────────────────────────────────────────────────────────────

async def correr(args, cfgs: list[NotebookCfg], suggestions: dict, descartes: list) -> int:
    frames = load_searches()
    base = frames["B1"]
    params = sorted({p for c in cfgs for p in c.params_covered})
    desconocidos = [p for p in params if p not in PARAMS]
    if desconocidos:
        raise SystemExit(f"params_covered nombra parámetros que no existen en "
                         f"PARAMS: {', '.join(desconocidos)}")

    pendientes = celdas_pendientes(frames, params, load_decisions())
    filas = [i for i in pendientes if not args.group or str(base.at[i, "Group"]) == args.group]
    if args.param:
        filas = [i for i in filas if args.param in pendientes[i]]
    filas.sort()
    if args.limit:
        filas = filas[:args.limit]

    ya = crudos()
    client = make_client()
    logger.info("%d especies con celdas pendientes · %d parámetros cubiertos",
                len(filas), len(params))

    nuevos = 0
    async with NblmSession() as ses:
        for n, idx in enumerate(filas, 1):
            species = str(base.at[idx, "Species"])
            group = str(base.at[idx, "Group"])
            libres = pendientes[idx] & set(params)
            if args.param:
                libres &= {args.param}
            logger.info("[%d/%d] %s · %d celdas", n, len(filas), species, len(libres))

            # lecturas[param] = [(cfg, campo), …] en orden de prioridad
            lecturas: dict[str, list[tuple[NotebookCfg, dict]]] = {}
            for cfg in cfgs:
                pide = [p for p in cfg.params_covered if p in libres]
                if not pide:
                    continue

                cacheado = ya.get((species, cfg.alias))
                if cacheado and not args.rehacer:
                    parsed = cacheado.get("parsed") or {}
                    citations = cacheado.get("citations") or []
                    logger.info("    · %s (del caché)", cfg.alias)
                else:
                    pregunta = pregunta_notebook(species, group, pide)
                    if args.dry_run:
                        print(f"\n--- pregunta a {cfg.alias} ---\n{pregunta}\n")
                    respuesta = await ses.ask(cfg.id, pregunta)
                    if respuesta is None:
                        continue
                    if args.dry_run:
                        print(f"--- respuesta de {cfg.alias} ---\n{respuesta['answer']}\n")
                        for c in respuesta["citations"]:
                            print(f"  [{c['n']}] {c['source_title']}")
                    parsed = parsear(client, species, pide, respuesta) or {}
                    citations = respuesta["citations"]
                    if args.dry_run:
                        print(f"--- parseo ---\n{json.dumps(parsed, ensure_ascii=False, indent=2)}\n")
                    else:
                        anotar_crudo({
                            "species": species, "alias": cfg.alias, "row": idx,
                            "notebook_id": cfg.id, "group": group,
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                            "params_pedidos": pide, "model": LLM_MODEL,
                            "answer": respuesta["answer"], "citations": citations,
                            "parsed": parsed,
                        })
                    await asyncio.sleep(args.pausa)

                for param in pide:
                    campo, motivo = normalizar(param, parsed.get(param), citations)
                    if motivo:
                        descartes.append({"species": species, "param": param,
                                          "notebook": cfg.alias, "reason": motivo,
                                          "raw": parsed.get(param)})
                        logger.info("    ✗ %s (%s): %s", param, cfg.alias, motivo)
                        continue
                    if campo:
                        lecturas.setdefault(param, []).append((cfg, campo))

            for param, lect in lecturas.items():
                rec = reconciliar(param, lect, args.tolerancia)
                sug = build_suggestion(param, species, group, lect, rec)
                if args.dry_run:
                    print(json.dumps({f"{idx}:{param}": sug}, ensure_ascii=False, indent=2))
                else:
                    suggestions[f"{idx}:{param}"] = sug
                nuevos += 1
                marca = " ⚠discrepan" if rec["discrepancia"] else ""
                logger.info("    ✓ %s = %s [%s]%s", param, rec["value"],
                            rec["confidence"], marca)

            faltaron = libres - set(lecturas)
            for param in sorted(faltaron):
                descartes.append({"species": species, "param": param, "notebook": "—",
                                  "reason": "sin evidencia en los notebooks"})

            if not args.dry_run and n % 10 == 0:
                guardar(suggestions, descartes, cfgs)
    return nuevos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="tope de especies (para probar)")
    parser.add_argument("--group", help="restringir a un grupo funcional")
    parser.add_argument("--param", help="restringir a un solo parámetro")
    parser.add_argument("--tolerancia", type=float, default=0.15,
                        help="diferencia relativa bajo la cual dos notebooks concuerdan (0.15 = 15%%)")
    parser.add_argument("--pausa", type=float, default=3.0,
                        help="segundos entre consultas: es una API interna, no la machaques")
    parser.add_argument("--rehacer", action="store_true",
                        help="vuelve a preguntar aunque haya crudo en caché")
    parser.add_argument("--dry-run", action="store_true",
                        help="imprime pregunta, respuesta y parseo sin escribir nada")
    parser.add_argument("--informe", action="store_true", help="muestra lo ya extraído")
    parser.add_argument("--reset", action="store_true", help="empieza de cero")
    args = parser.parse_args()

    if args.reset:
        for path in (SUGGESTIONS, RAW_JSONL):
            path.unlink(missing_ok=True)

    suggestions, descartes = cargar()
    if args.informe:
        informe(suggestions, descartes)
        return

    cfgs = load_config()
    nuevos = asyncio.run(correr(args, cfgs, suggestions, descartes))

    if args.dry_run:
        print(f"\n(dry-run) {nuevos} sugerencias se habrían emitido · no se escribió nada")
        return

    guardar(suggestions, descartes, cfgs)
    print(f"\n✅ {nuevos} sugerencias nuevas · {len(suggestions)} en total")
    print(f"   {SUGGESTIONS.relative_to(ROOT)}")
    print(f"   Crudo: {RAW_JSONL.relative_to(ROOT)}")
    print("\n   Siguiente paso — llevarlas al tablero:")
    print("   python3 scripts/phase_7_review/build_review_queue.py")


if __name__ == "__main__":
    main()
