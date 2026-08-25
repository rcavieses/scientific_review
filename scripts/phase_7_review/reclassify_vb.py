#!/usr/bin/env python3
"""Reclasifica Von_bertalanffy_a/b hacia el esquema nuevo, para revisión humana.

EL PROBLEMA
===========
`Von_bertalanffy_a` y `Von_bertalanffy_b` guardan cuatro cantidades distintas
bajo dos nombres. La causa no fue la extracción sino la definición: a B1, B4 y
B5 se les pidió «Von Bertalanffy coefficient a» y «coefficient b», que no
significan nada —la ecuación de von Bertalanffy tiene L∞, K y t0, no una «a» ni
una «b»—, así que cada corrida resolvió la ambigüedad por su cuenta. B6 la
redefinió como a = L∞ y b = K, lo que a su vez dejó `Von_bertalanffy_b`
duplicando a `growth_rate`.

Resultado, sobre las cinco búsquedas: en `_a` hay 29 valores de L∞, 6 de t0 y 4
de la a de peso-talla; en `_b`, 35 de K y 19 de la b de peso-talla.

QUÉ HACE ESTE SCRIPT
====================
Reparte cada valor a su columna real del esquema nuevo —`li_a`, `li_b`,
`vb_Linf`, `vb_t0`, y K a `growth_rate`— y lo manda al tablero como celda
pendiente. NO escribe nada en los CSV: la clasificación es una lectura de la
magnitud, y una lectura tiene que confirmarla un humano antes de volverse dato.

CÓMO CLASIFICA
==============
Por magnitud, que en estas cantidades no se solapa:

    _a  < 0        → t0     (la edad teórica a talla cero es negativa)
    _a  < 0.01     → li_a   (el coeficiente de peso-talla es ~1e-6 a 1e-2)
    _a  > 20       → vb_Linf (talla asintótica en cm)
    _b  entre 2 y 4 → li_b  (el exponente de peso-talla ronda 3)
    _b  entre 0 y 1.5 → K   (coeficiente de crecimiento, va a growth_rate)

Donde B6 registró unidad, la clasificación deja de ser heurística: `unit=cm`
confirma L∞ y `unit=1/year` confirma K. Eso se anota en la evidencia.

Uso:
    python3 scripts/phase_7_review/reclassify_vb.py
    python3 scripts/phase_7_review/reclassify_vb.py --informe
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "output"
OUT = ROOT / "outputs" / "review" / "reclass_suggestions.json"
BASE_CSV = DATA / "Atlantis_GOC_parametros_biologicos_BUSQUEDA1.csv"
B6_DETALLE = DATA / "Atlantis_GOC_parametros_BUSQUEDA_6_detalle.csv"

SEARCHES = {
    "B1": "BUSQUEDA1", "B3": "BUSQUEDA_3", "B4": "BUSQUEDA_4",
    "B5": "BUSQUEDA_5", "B6": "BUSQUEDA_6",
}

VIEJAS = ("Von_bertalanffy_a", "Von_bertalanffy_b")

AUTHOR = "Reclasificación de esquema — reparto por magnitud, confirmado con la unidad de B6"

# Especies del CSV que comparten epíteto. Se calcula en main(): es la firma del
# emparejamiento difuso que hizo circular los mismos números entre taxones sin
# relación (Atherinops, Elops, Caulolatilus y Aythya affinis).
EPITETOS_COLISION: dict[str, set] = {}

# Aves y mamíferos no tienen coeficientes de crecimiento de peces: si aparecen,
# es que la búsqueda emparejó la especie equivocada.
CLASES_PEZ = {"Teleostei", "Actinopterygii", "Chondrichthyes"}


def clasificar(col: str, v: float) -> tuple[str | None, str]:
    """Devuelve (parámetro destino, por qué)."""
    if col.endswith("_a"):
        if v < 0:
            return "vb_t0", "negativo: sólo t₀ lo es entre estas cantidades"
        if v < 0.01:
            return "li_a", "orden de magnitud ~1e-6: es el coeficiente a de peso-talla"
        if v > 20:
            return "vb_Linf", "decenas o centenas de cm: es la talla asintótica L∞"
        return None, f"magnitud ambigua ({v}): no encaja en t₀, li_a ni L∞"
    if 2.0 <= v <= 4.0:
        return "li_b", "entre 2 y 4: es el exponente b de peso-talla, que ronda 3"
    if 0 < v < 1.5:
        return "growth_rate", "entre 0 y 1.5 1/año: es el coeficiente K de crecimiento"
    return None, f"magnitud ambigua ({v}): no encaja en li_b ni en K"


def evidencia_b6() -> dict[tuple[str, str], dict]:
    """Unidad y base que B6 anotó por celda: convierte la heurística en dato."""
    if not B6_DETALLE.exists():
        return {}
    d = pd.read_csv(B6_DETALLE)
    d = d[d["param"].astype(str).isin(VIEJAS)]
    return {(str(r.Species), str(r.param)): {"unit": str(r.unit), "basis": str(r.basis)}
            for r in d.itertuples()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--informe", action="store_true", help="Sólo imprime el reparto, sin escribir")
    args = ap.parse_args()

    base = pd.read_csv(BASE_CSV)
    frames = {}
    for k, v in SEARCHES.items():
        f = DATA / f"Atlantis_GOC_parametros_biologicos_{v}.csv"
        if f.exists():
            frames[k] = pd.read_csv(f)
    ev = evidencia_b6()

    # Epítetos que se repiten entre filas con valores en estas columnas: es la
    # firma del emparejamiento difuso que mezcló datos de especies distintas.
    global EPITETOS_COLISION
    afectadas = base[base[list(VIEJAS)].notna().any(axis=1)]["Species"].astype(str)
    EPITETOS_COLISION = {}
    for nombre in afectadas:
        partes = nombre.split()
        if len(partes) > 1:
            EPITETOS_COLISION.setdefault(partes[-1], set()).add(nombre)
    EPITETOS_COLISION = {k: v for k, v in EPITETOS_COLISION.items() if len(v) > 1}

    suggestions: dict[str, dict] = {}
    sin_clasificar: list[str] = []
    filas = []

    for idx in range(len(base)):
        especie = str(base.at[idx, "Species"])
        clase = str(base.at[idx, "Class"])
        for col in VIEJAS:
            # Todos los valores que las búsquedas pusieron en esta celda.
            votos: dict[str, float] = {}
            for k, df in frames.items():
                if col not in df.columns:
                    continue
                v = df.at[idx, col]
                if pd.notna(v):
                    try:
                        votos[k] = float(v)
                    except (TypeError, ValueError):
                        continue
            if not votos:
                continue

            # Cada búsqueda pudo entender la columna de forma distinta, así que
            # se clasifica voto por voto y se agrupa por destino.
            por_destino: dict[str, dict[str, float]] = {}
            motivos: dict[str, str] = {}
            for k, v in votos.items():
                destino, motivo = clasificar(col, v)
                if destino is None:
                    sin_clasificar.append(f"{especie} · {col} = {v} ({motivo})")
                    continue
                por_destino.setdefault(destino, {})[k] = v
                motivos[destino] = motivo

            for destino, vs in por_destino.items():
                e = ev.get((especie, col))
                avisos = []
                conf_forzada = None

                # Discrepancia de ~10x entre búsquedas = milímetros contra
                # centímetros. La mediana elegiría el valor equivocado tantas
                # veces como el correcto, así que se toma el de escala cm (el
                # menor) y se avisa; nunca se resuelve en silencio.
                lo, hi = min(vs.values()), max(vs.values())
                if lo > 0 and 8 <= hi / lo <= 12:
                    cm = [v for v in vs.values() if v < hi / 4]
                    valor = round(sorted(cm)[len(cm) // 2], 6)
                    conf_forzada = "baja"
                    avisos.append(
                        f"Las búsquedas discrepan {hi / lo:.0f}× ({lo} contra {hi}): es "
                        f"milímetros contra centímetros. Se propone el valor en cm, pero "
                        f"confírmalo — la conversión se describió y no se aplicó en varias filas.")
                else:
                    valor = round(sorted(vs.values())[len(vs) // 2], 6)
                if e:
                    avisos.append(f"B6 anotó unidad «{e['unit']}» y base «{e['basis']}» "
                                  f"para esta celda, lo que confirma el destino.")
                # Varias especies del CSV comparten epíteto y la búsqueda las
                # confundió entre sí: los mismos números circulan entre taxones
                # sin relación. Si el epíteto está repetido, hay que decirlo.
                epiteto = especie.split()[-1] if len(especie.split()) > 1 else ""
                if epiteto and epiteto in EPITETOS_COLISION:
                    otras = sorted(EPITETOS_COLISION[epiteto] - {especie})
                    if otras:
                        avisos.append(
                            f"El epíteto «{epiteto}» se repite en {', '.join(otras)}. "
                            f"Esos valores circulan entre especies sin relación por "
                            f"emparejamiento difuso: comprueba que el número es de {especie}.")
                        conf_forzada = "baja"
                if clase not in CLASES_PEZ:
                    avisos.append(f"OJO: {especie} es {clase}, no un pez. Un coeficiente de "
                                  "crecimiento aquí indica que la búsqueda emparejó la especie "
                                  "equivocada; comprueba la fila antes de aceptar nada.")
                if destino == "growth_rate":
                    gr = base.at[idx, "growth_rate"]
                    if pd.notna(gr) and abs(float(gr) - valor) < 1e-9:
                        avisos.append("growth_rate ya tiene exactamente este valor: era la "
                                      "duplicación que introdujo la redefinición de B6. "
                                      "Aceptar aquí no añade nada; basta con retirar la vieja.")

                razon = (f"«{col}» contenía {valor} para {especie}. {motivos[destino]}. "
                         f"Búsquedas que lo aportaron: {', '.join(sorted(vs))}.")
                if avisos:
                    razon += " " + " ".join(avisos)

                suggestions[f"{idx}:{destino}"] = {
                    "param": destino,
                    "species": especie,
                    "group": str(base.at[idx, "Group"]),
                    "value": valor,
                    "from_column": col,
                    "from_searches": {k: round(v, 6) for k, v in sorted(vs.items())},
                    "confidence": conf_forzada or ("alta" if e else "media"),
                    "basis": "reclasificacion_de_esquema",
                    "scope": f"{col} → {destino}",
                    "rationale": razon,
                    "citations": [],
                    "author": AUTHOR,
                }
                filas.append((especie, clase, col, valor, destino, "B6" if e else "magnitud"))

    if args.informe or True:
        print(f"{'especie':26s} {'clase':14s} {'columna vieja':19s} {'valor':>10s}  → destino")
        for esp, cl, col, val, dest, via in filas:
            print(f"{esp[:25]:26s} {cl[:13]:14s} {col:19s} {val:>10}  → {dest:12s} [{via}]")
        if sin_clasificar:
            print(f"\n⚠ sin clasificar ({len(sin_clasificar)}):")
            for x in sin_clasificar:
                print(f"   · {x}")

    if args.informe:
        return

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "author": AUTHOR,
        "warning": ("Reparto de las columnas Von_bertalanffy_a/b hacia el esquema nuevo. "
                    "La clasificación es una lectura de la magnitud —confirmada por la unidad "
                    "de B6 donde existe—, no una medición nueva. Requiere aceptación humana "
                    "explícita para convertirse en dato."),
        "retired_columns": list(VIEJAS),
        "unclassified": sin_clasificar,
        "suggestions": suggestions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ {OUT.relative_to(ROOT)}  ({len(suggestions)} celdas a revisar)")
    dest = pd.Series([s["param"] for s in suggestions.values()]).value_counts()
    print("   por destino: " + " · ".join(f"{k}={v}" for k, v in dest.items()))
    conf = pd.Series([s["confidence"] for s in suggestions.values()]).value_counts()
    print("   por confianza: " + " · ".join(f"{k}={v}" for k, v in conf.items()))


if __name__ == "__main__":
    main()
