#!/usr/bin/env python3
"""Construye la cola de revisión manual a partir de las búsquedas B1/B3/B4/B5.

Una celda (especie × parámetro) entra a la cola cuando **dos o más búsquedas
le asignan valor y esos valores discrepan**:

  - numéricos    → dispersión relativa (max-min)/max > 10 %
  - categóricos  → cadenas normalizadas distintas

Salida: outputs/review/review_queue.json

Uso:
    python3 scripts/phase_7_review/build_review_queue.py
    python3 scripts/phase_7_review/build_review_queue.py --tolerance 0.05
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "output"
OUT = ROOT / "outputs" / "review"

SEARCHES = {
    "B1": "BUSQUEDA1",
    "B3": "BUSQUEDA_3",
    "B4": "BUSQUEDA_4",
    "B5": "BUSQUEDA_5",
    "B6": "BUSQUEDA_6",
}

# B6 es la única corrida con evidencia por celda (unidad, base, fuente y cita
# textual) y con rangos. El diagnóstico sobre 12 especies perdidas mostró que en
# 10 el corpus no contiene ningún dato de la especie: donde B6 calla, el valor de
# las otras búsquedas es sospechoso por defecto, no simplemente "no corroborado".
EVIDENCE_SEARCH = "B6"
EVIDENCE_CSV = DATA / "Atlantis_GOC_parametros_BUSQUEDA_6_detalle.csv"
AI_SUGGESTIONS = OUT / "ai_suggestions.json"
RECLASS_SUGGESTIONS = OUT / "reclass_suggestions.json"
LW_SUGGESTIONS = OUT / "lw_suggestions.json"
NBLM_SUGGESTIONS = OUT / "nblm_suggestions.json"

# B5 partió de una copia del CSV de B4: sus coincidencias no son evidencia
# independiente. Se marca para poder ponderar el consenso honestamente.
DERIVED_FROM = {"B5": "B4"}

TAXONOMY = ["Group", "Code", "Species", "Genus", "Family", "Order", "Class", "Phylum"]

PARAMS = {
    "biomass_mt":          {"label": "Biomasa",                 "unit": "t",        "type": "num"},
    "abundance_numbers":   {"label": "Abundancia",              "unit": "ind",      "type": "num"},
    "mean_body_size":      {"label": "Talla media",             "unit": "cm",       "type": "num"},
    "max_age":             {"label": "Edad máxima",             "unit": "años",     "type": "num"},
    "natural_mortality":   {"label": "Mortalidad natural (M)",  "unit": "1/año",    "type": "num"},
    "Lmax":                {"label": "Longitud máxima",         "unit": "cm",       "type": "num"},
    # Sustituyen a Von_bertalanffy_a/b, que mezclaban cuatro cantidades bajo dos
    # nombres. La causa fue la definición que recibió el extractor —«Von
    # Bertalanffy coefficient a», que no existe: la ecuación tiene L∞, K y t0—,
    # así que cada corrida la resolvió a su manera. K vive sólo en growth_rate:
    # darle dos casas fue parte del enredo original.
    # Se llaman «a» y «b» a secas: el nombre largo hacía que las dos columnas
    # empezaran igual («Peso-talla …») y a golpe de vista fueran indistinguibles,
    # que es justo el error que este esquema vino a deshacer. Lo que son se
    # explica en `hint`, que la interfaz pone como título al pasar el cursor.
    "li_a":                {"label": "a",                       "unit": "",         "type": "num",
                            "hint": "Coeficiente a de la relación peso-talla W = a·L^b. "
                                    "Depende de las unidades de W y L (típicamente 1e-6 a 1e-2). "
                                    "No es un parámetro de von Bertalanffy."},
    "li_b":                {"label": "b",                       "unit": "",         "type": "num",
                            "hint": "Exponente b de la relación peso-talla W = a·L^b. "
                                    "Adimensional, ronda 3. No es un parámetro de von Bertalanffy."},
    "vb_Linf":             {"label": "Talla asintótica (L∞)",   "unit": "cm",       "type": "num"},
    "vb_t0":               {"label": "Edad a talla cero (t₀)",  "unit": "años",     "type": "num"},
    "growth_rate":         {"label": "Tasa de crecimiento",     "unit": "1/año",    "type": "num"},
    "age_first_maturity":  {"label": "Edad 1ª madurez",         "unit": "años",     "type": "num"},
    "larval_duration":     {"label": "Duración larval",         "unit": "días",     "type": "num"},
    "StartSpawnDayOfYear": {"label": "Inicio de desove",        "unit": "día juliano", "type": "num"},
    "EndSpawnDayOfYear":   {"label": "Fin de desove",           "unit": "día juliano", "type": "num"},
    "IsMigratory":         {"label": "¿Migratoria?",            "unit": "",         "type": "cat"},
}

# Parámetros que Atlantis necesita con más urgencia (§7 de COMPARACION_BUSQUEDAS.md)
CRITICAL = {"natural_mortality", "age_first_maturity", "biomass_mt", "growth_rate", "max_age"}

CITE_RE = re.compile(r'"source":\s*"([^"]+)"')


# ── carga y normalización ───────────────────────────────────────────────

def load_evidence() -> dict[tuple[str, str], dict]:
    """Evidencia por celda de B6: unidad, base del valor, fuente y cita textual."""
    if not EVIDENCE_CSV.exists():
        return {}
    df = pd.read_csv(EVIDENCE_CSV)
    out = {}
    for row in df.itertuples():
        out[(str(row.Species), str(row.param))] = {
            "unit": None if pd.isna(row.unit) else str(row.unit),
            "basis": None if pd.isna(row.basis) else str(row.basis),
            "source": None if pd.isna(row.source) else str(row.source),
            "quote": None if pd.isna(row.quote) else str(row.quote)[:400],
        }
    return out


def load_ai_suggestions() -> dict[str, dict]:
    """Sugerencias de IA: inferencia taxonómica, NO extracción del corpus."""
    if not AI_SUGGESTIONS.exists():
        return {}
    return json.loads(AI_SUGGESTIONS.read_text(encoding="utf-8")).get("suggestions", {})


def load_reclass() -> dict[str, dict]:
    """Valores repartidos desde Von_bertalanffy_a/b hacia el esquema nuevo.
    No son medición nueva: son los mismos números, leídos en la columna que les
    corresponde. Aun así pasan por revisión, porque el reparto es una lectura."""
    if not RECLASS_SUGGESTIONS.exists():
        return {}
    return json.loads(RECLASS_SUGGESTIONS.read_text(encoding="utf-8")).get("suggestions", {})


def load_lw() -> dict[str, dict]:
    """Coeficientes de peso-talla recuperados del corpus con cita textual.

    Canal aparte de los demás: no es inferencia del modelo (como las sugerencias
    taxonómicas) ni un reparto de columnas (como la reclasificación), sino
    extracción dirigida sobre el mismo corpus, hecha después de corregir la
    definición que las seis búsquedas recibieron mal. Ver lw_extract.py."""
    if not LW_SUGGESTIONS.exists():
        return {}
    return json.loads(LW_SUGGESTIONS.read_text(encoding="utf-8")).get("suggestions", {})


def load_nblm() -> dict[str, dict]:
    """Valores que dos notebooks de NotebookLM afirman, ya reconciliados.

    El canal más externo de todos: su corpus no vive en este repo y la respuesta
    no es reproducible desde aquí. A cambio cubre literatura que el índice FAISS
    no tiene. Cada sugerencia trae lo que dijo *cada* notebook por separado, y
    marca si discrepan — que es justo lo que el revisor necesita ver.
    Ver nblm_extract.py."""
    if not NBLM_SUGGESTIONS.exists():
        return {}
    return json.loads(NBLM_SUGGESTIONS.read_text(encoding="utf-8")).get("suggestions", {})


def load_searches() -> dict[str, pd.DataFrame]:
    frames = {}
    for key, suffix in SEARCHES.items():
        path = DATA / f"Atlantis_GOC_parametros_biologicos_{suffix}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Falta el CSV de {key}: {path}")
        frames[key] = pd.read_csv(path)
    base = frames["B1"]
    for key, df in frames.items():
        if len(df) != len(base) or not (df["Species"] == base["Species"]).all():
            raise ValueError(f"El CSV de {key} no está alineado por fila con B1")
    return frames


def norm_cat(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip().lower()
    if not text or text in {"nan", "none", "null", "n/a", "unknown"}:
        return None
    if text in {"yes", "y", "sí", "si", "true", "1"}:
        return "Yes"
    if text in {"no", "n", "false", "0"}:
        return "No"
    return str(value).strip()


def norm_num(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
        if not match:
            return None
        num = float(match.group(0).replace(",", "."))
    return None if math.isnan(num) else num


def parse_citations(raw) -> list[str]:
    """Extrae las claves bibliográficas únicas del campo `citations` de la fila."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    keys = list(dict.fromkeys(CITE_RE.findall(str(raw))))
    return keys[:12]


# ── evaluación de una celda ─────────────────────────────────────────────

def spread_pct(values: list[float]) -> float:
    """Dispersión relativa: (max-min)/|max| en porcentaje."""
    lo, hi = min(values), max(values)
    denom = max(abs(hi), abs(lo))
    if denom == 0:
        return 0.0 if lo == hi else 100.0
    return (hi - lo) / denom * 100.0


def consensus(values: dict[str, object], kind: str, frames_derived: bool = True):
    """Valor sugerido por votación entre búsquedas independientes.

    Devuelve (valor_sugerido, método, hay_empate). Reglas:
      - Si B6 tiene valor, gana: es la única corrida que adjunta unidad, base y
        cita textual, así que su número es verificable y los demás no.
      - B5 se descuenta cuando su valor es idéntico al heredado de B4: no aporta
        un voto independiente.
    """
    if EVIDENCE_SEARCH in values:
        return values[EVIDENCE_SEARCH], f"{EVIDENCE_SEARCH} (única con cita textual)", False

    votes = dict(values)
    if frames_derived:
        for derived, parent in DERIVED_FROM.items():
            if derived in votes and parent in votes and votes[derived] == votes[parent]:
                votes.pop(derived)

    counts = Counter(votes.values())
    top = counts.most_common()
    if top and (len(top) == 1 or top[0][1] > top[1][1]):
        return top[0][0], "mayoría", False

    # Empate real
    if kind == "num":
        nums = sorted(votes.values())
        mid = len(nums) // 2
        median = nums[mid] if len(nums) % 2 else (nums[mid - 1] + nums[mid]) / 2
        return round(median, 6), "mediana (empate)", True
    return None, "sin consenso (empate)", True


def severity(kind: str, spread: float, tie: bool, param: str) -> str:
    if kind == "cat":
        return "critical" if tie else "serious"
    if spread > 100:
        return "critical"
    if spread > 50 or tie:
        return "serious"
    if param in CRITICAL:
        return "serious"
    return "warning"


# ── construcción ────────────────────────────────────────────────────────

def build(tolerance: float) -> dict:
    frames = load_searches()
    base = frames["B1"]
    citations = {k: [parse_citations(v) for v in df["citations"]] for k, df in frames.items()}
    evidence = load_evidence()
    ai = load_ai_suggestions()
    rec = load_reclass()
    lw = load_lw()
    nblm = load_nblm()

    items: list[dict] = []
    group_cells: defaultdict[str, Counter] = defaultdict(Counter)
    group_species_conflict: defaultdict[str, set] = defaultdict(set)

    def base_item(idx: int, param: str, meta: dict, raw: dict, rng, evi) -> dict:
        return {
            "id": f"{idx}:{param}",
            "row": idx,
            **{col.lower(): (None if pd.isna(base.at[idx, col]) else str(base.at[idx, col]))
               for col in TAXONOMY},
            "param": param,
            "param_label": meta["label"],
            "param_hint": meta.get("hint"),
            "unit": meta["unit"],
            "kind": meta["type"],
            "critical_param": param in CRITICAL,
            "values": raw,
            "n_sources": len(raw),
            "range_b6": rng,
            "evidence_b6": evi,
            "ai_suggestion": ai.get(f"{idx}:{param}"),
            "reclass_suggestion": rec.get(f"{idx}:{param}"),
            "lw_suggestion": lw.get(f"{idx}:{param}"),
            "nblm_suggestion": nblm.get(f"{idx}:{param}"),
            # ¿Cada valor cae dentro del intervalo que la literatura reporta?
            # Es el discriminador más limpio cuando B6 trae rango.
            "inside_range": ({k: (rng[0] <= v <= rng[1]) for k, v in raw.items()}
                             if rng else None),
            "citations": {k: citations[k][idx] for k in raw if citations[k][idx]},
        }

    for idx in range(len(base)):
        species = str(base.at[idx, "Species"])
        for param, meta in PARAMS.items():
            kind = meta["type"]
            raw = {}
            for key, df in frames.items():
                # Las columnas nuevas del esquema todavía no existen en los CSV
                # de las búsquedas: ausente no es lo mismo que vacío.
                if param not in df.columns:
                    continue
                value = norm_num(df.at[idx, param]) if kind == "num" else norm_cat(df.at[idx, param])
                if value is not None:
                    raw[key] = value

            group = str(base.at[idx, "Group"])
            if raw:
                group_cells[group]["con_valor"] += 1

            # Rango y evidencia de B6 (unidad, base, fuente, cita textual)
            rng = None
            if kind == "num" and EVIDENCE_SEARCH in raw:
                lo = norm_num(frames[EVIDENCE_SEARCH].at[idx, f"{param}_min"])
                hi = norm_num(frames[EVIDENCE_SEARCH].at[idx, f"{param}_max"])
                if lo is not None and hi is not None:
                    rng = [lo, hi]
            evi = evidence.get((species, param))

            # Celda que otras búsquedas afirman y la corrida con evidencia NO
            # respalda. B6 procesó las 1 122 especies, así que su silencio es un
            # resultado, no una omisión: entra a revisión con su propia etiqueta.
            if EVIDENCE_SEARCH not in raw and raw:
                group_cells[group]["sin_respaldo"] += 1
                sev = "critical" if param in CRITICAL else ("serious" if len(raw) >= 2 else "warning")
                group_cells[group][sev] += 1
                group_species_conflict[group].add(species)
                item = base_item(idx, param, meta, raw, rng, evi)
                item.update({
                    "tipo": "sin_respaldo",
                    "spread_pct": round(spread_pct(list(raw.values())), 1) if kind == "num" and len(raw) > 1 else 0.0,
                    "severity": sev,
                    "tie": False,
                    "suggested": None,
                    "suggested_method": f"{EVIDENCE_SEARCH} no halló evidencia en el corpus",
                })
                items.append(item)
                continue

            if not raw and f"{idx}:{param}" in ai:
                # Celda vacía en las seis búsquedas, con sugerencia de IA. Entra a
                # la cola con etiqueta propia: es una hipótesis a validar, no un dato.
                sug = ai[f"{idx}:{param}"]
                sev = {"alta": "warning", "media": "serious", "baja": "critical"}[sug["confidence"]]
                group_cells[group]["sugerencia_ia"] += 1
                group_cells[group][sev] += 1
                item = base_item(idx, param, meta, raw, rng, evi)
                item.update({
                    "tipo": "sugerencia_ia",
                    "spread_pct": 0.0,
                    "severity": sev,
                    "tie": False,
                    "suggested": sug["value"],
                    "suggested_method": f"inferencia taxonómica ({sug['scope']})",
                })
                items.append(item)
                continue

            if not raw and f"{idx}:{param}" in lw:
                # Peso-talla extraído del corpus con cita. Entra a la cola porque
                # una cita hay que leerla: el mismo emparejamiento difuso que
                # puso una b de pez en un pato sigue siendo posible.
                lws = lw[f"{idx}:{param}"]
                sev = {"alta": "warning", "media": "serious", "baja": "critical"}[lws["confidence"]]
                group_cells[group]["peso_talla"] += 1
                group_cells[group][sev] += 1
                item = base_item(idx, param, meta, raw, rng, evi)
                item.update({
                    "tipo": "peso_talla",
                    "spread_pct": 0.0,
                    "severity": sev,
                    "tie": False,
                    "suggested": lws["value"],
                    "suggested_method": f"extracción dirigida ({lws['scope']})",
                })
                items.append(item)
                continue

            if not raw and f"{idx}:{param}" in nblm:
                # Literatura que el índice FAISS no tiene, leída por NotebookLM.
                # Entra a la cola siempre: la respuesta no se puede reproducir
                # desde este repo, así que la única verificación posible es que
                # un humano lea la cita. Cuando los dos notebooks discrepan, la
                # confianza baja y el item sube al principio de la cola.
                nbs = nblm[f"{idx}:{param}"]
                sev = {"alta": "warning", "media": "serious", "baja": "critical"}[nbs["confidence"]]
                group_cells[group]["notebooklm"] += 1
                group_cells[group][sev] += 1
                item = base_item(idx, param, meta, raw, rng, evi)
                item.update({
                    "tipo": "notebooklm",
                    "spread_pct": 0.0,
                    "severity": sev,
                    "tie": bool(nbs.get("discrepancia")),
                    "suggested": nbs["value"],
                    "suggested_method": f"consulta a NotebookLM ({nbs['scope']})",
                })
                items.append(item)
                continue

            if not raw and f"{idx}:{param}" in rec:
                # Valor que ya existía en el CSV, sólo que en la columna
                # equivocada. Se propone en su columna real y se revisa: es un
                # reparto por magnitud, no una medición.
                rcg = rec[f"{idx}:{param}"]
                sev = {"alta": "warning", "media": "serious", "baja": "critical"}[rcg["confidence"]]
                group_cells[group]["reclasificado"] += 1
                group_cells[group][sev] += 1
                item = base_item(idx, param, meta, raw, rng, evi)
                item.update({
                    "tipo": "reclasificado",
                    "spread_pct": 0.0,
                    "severity": sev,
                    "tie": False,
                    "suggested": rcg["value"],
                    "suggested_method": f"reparto de esquema ({rcg['scope']})",
                })
                items.append(item)
                continue

            if len(raw) < 2:
                if len(raw) == 1:
                    group_cells[group]["sin_corroborar"] += 1
                continue

            if kind == "num":
                spread = spread_pct(list(raw.values()))
                conflict = spread > tolerance * 100
            else:
                spread = 0.0 if len(set(raw.values())) == 1 else 100.0
                conflict = len(set(raw.values())) > 1

            if not conflict:
                group_cells[group]["acuerdo"] += 1
                continue

            suggested, method, tie = consensus(raw, kind)
            sev = severity(kind, spread, tie, param)
            group_cells[group]["conflicto"] += 1
            group_cells[group][sev] += 1
            group_species_conflict[group].add(str(base.at[idx, "Species"]))

            item = base_item(idx, param, meta, raw, rng, evi)
            item.update({
                "tipo": "conflicto",
                "spread_pct": round(spread, 1),
                "severity": sev,
                "tie": tie,
                "suggested": suggested,
                "suggested_method": method,
            })
            items.append(item)

    # Se listan TODOS los grupos funcionales, incluidos los que no tienen ningún
    # dato: esa ausencia es un resultado del análisis, no un vacío que ocultar.
    groups = []
    for group in sorted(base["Group"].dropna().astype(str).unique()):
        counter = group_cells[group]
        rows = base[base["Group"] == group]
        groups.append({
            "group": group,
            "code": str(rows["Code"].iloc[0]) if len(rows) else "",
            "n_species": int(len(rows)),
            "cells_with_value": counter["con_valor"],
            "cells_agree": counter["acuerdo"],
            "cells_single_source": counter["sin_corroborar"],
            "conflicts": counter["conflicto"],
            "unsupported": counter["sin_respaldo"],
            "ai_suggested": counter["sugerencia_ia"],
            "reclasificado": counter["reclasificado"],
            "peso_talla": counter["peso_talla"],
            "notebooklm": counter["notebooklm"],
            "critical": counter["critical"],
            "serious": counter["serious"],
            "warning": counter["warning"],
            "species_affected": len(group_species_conflict[group]),
        })

    by_param = Counter(item["param"] for item in items)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tolerance_pct": tolerance * 100,
        "searches": list(SEARCHES),
        "derived_from": DERIVED_FROM,
        "params": PARAMS,
        "critical_params": sorted(CRITICAL),
        "totals": {
            "species": int(len(base)),
            "groups": len(groups),
            "conflicts": len(items),
            "cells_with_value": sum(g["cells_with_value"] for g in groups),
            "cells_agree": sum(g["cells_agree"] for g in groups),
            "cells_single_source": sum(g["cells_single_source"] for g in groups),
            "by_severity": dict(Counter(item["severity"] for item in items)),
            "by_tipo": dict(Counter(item["tipo"] for item in items)),
            "by_param": dict(by_param),
            "cells_with_range": sum(1 for item in items if item.get("range_b6")),
            "cells_with_quote": sum(1 for item in items
                                    if (item.get("evidence_b6") or {}).get("quote")),
            "ai_suggestions": len(ai),
            "reclass_suggestions": len(rec),
            "lw_suggestions": len(lw),
            "nblm_suggestions": len(nblm),
            "nblm_discrepancias": sum(1 for s in nblm.values() if s.get("discrepancia")),
            "ai_contradicts": sum(1 for item in items
                                  if item.get("ai_suggestion") and item["values"]
                                  and any(v != item["ai_suggestion"]["value"]
                                          for v in item["values"].values())),
        },
        "groups": groups,
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tolerance", type=float, default=0.10,
                        help="Tolerancia relativa para considerar iguales dos números (0.10 = 10%%)")
    parser.add_argument("--output", type=Path, default=OUT / "review_queue.json")
    args = parser.parse_args()

    queue = build(args.tolerance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")

    t = queue["totals"]
    print(f"✓ {args.output.relative_to(ROOT)}")
    print(f"  Celdas con valor en ≥1 búsqueda : {t['cells_with_value']}")
    print(f"  Sin corroborar (1 sola búsqueda): {t['cells_single_source']}")
    print(f"  En acuerdo (≤{queue['tolerance_pct']:.0f}%)          : {t['cells_agree']}")
    print(f"  → EN COLA DE REVISIÓN           : {t['conflicts']}")
    for tipo, n in sorted(t.get("by_tipo", {}).items()):
        print(f"      {tipo:20s}: {n}")
    print(f"  Celdas con rango de B6          : {t.get('cells_with_range', 0)}")
    print(f"  Celdas con cita textual de B6   : {t.get('cells_with_quote', 0)}")
    for sev in ("critical", "serious", "warning"):
        print(f"      {sev:9s}: {t['by_severity'].get(sev, 0)}")
    print(f"  Grupos con conflicto            : {sum(1 for g in queue['groups'] if g['conflicts'])}")
    top = sorted(t["by_param"].items(), key=lambda kv: -kv[1])[:6]
    print("  Parámetros más conflictivos     : " + ", ".join(f"{k} ({v})" for k, v in top))


if __name__ == "__main__":
    main()
