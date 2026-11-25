#!/usr/bin/env python3
"""Sugerencias numéricas por celda, tomadas de FishBase, para revisión humana.

QUÉ ES ESTO, Y EN QUÉ SE DIFERENCIA DE `ai_suggestions.py`
==========================================================
`ai_suggestions.py` infiere IsMigratory desde el taxón: es una hipótesis del
modelo, respaldada por literatura pero no extraída de ningún registro. Esto es
otra cosa. Aquí no hay inferencia: se busca la especie en FishBase y se copia
lo que la base afirma, con el estudio primario que lo sostiene.

Por eso viaja en un canal propio (`fb_suggestion`) y con su propia etiqueta en
el tablero. Confundir «lo que dedujo el modelo» con «lo que dice una base
curada» borraría justo la distinción que este tablero existe para conservar.

Lo que NO cambia: sigue siendo una sugerencia. No entra en las columnas de
valor, requiere aceptación humana explícita y al exportar queda marcada.

FUENTE
------
Snapshot público de FishBase en formato parquet, el mismo que consume hoy
`rfishbase`, servido desde Source Cooperative:

    s3://us-west-2.opendata.source.coop/cboettig/fishbase/fb/{VERSION}/parquet

Se descarga a `data/external/fishbase/` y se consulta en local: las consultas
son reproducibles y no dependen de que un servicio esté en pie. La API
histórica de FishBase ya no existe y el espejo de rOpenSci está caído, así que
esta es la vía viva.

CITAS
-----
Cada valor cita dos cosas: el registro de FishBase (la especie, con su
SpecCode) y —cuando la tabla lo registra— el estudio primario del que FishBase
lo tomó, resuelto contra `refrens`. La cita primaria es la que hay que ir a
comprobar; FishBase es el intermediario, no la evidencia.

REGIÓN
------
De cada registro se lee además de dónde salió (`fb_region.py`): su localidad y,
si calla, el título de su referencia. Cuando hay registros del Golfo de
California, del Pacífico mexicano o del Pacífico oriental, el valor propuesto
se calcula SÓLO con ellos —no con la mediana mundial— y la sugerencia queda
marcada como regional. Es la diferencia entre «así crece esta especie en algún
sitio» y «así crece en el sistema que se está modelando»; proponer lo primero
y aprobarlo como lo segundo sería el error que este canal debe evitar.

Uso:
    python3 scripts/phase_7_review/fishbase_suggestions.py --download
    python3 scripts/phase_7_review/fishbase_suggestions.py
    python3 scripts/phase_7_review/fishbase_suggestions.py --species "Totoaba macdonaldi"
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

import fb_region

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "output"
FB_DIR = ROOT / "data" / "external" / "fishbase"
OUT = ROOT / "outputs" / "review" / "fishbase_suggestions.json"
BASE_CSV = DATA / "Atlantis_GOC_parametros_biologicos_BUSQUEDA1.csv"

VERSION = "v24.07"
BUCKET = "https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop"
PREFIX = f"cboettig/fishbase/fb/{VERSION}/parquet"
TABLES = ("species", "popgrowth", "poplw", "maturity", "estimate", "refrens", "synonyms")

AUTHOR = f"FishBase {VERSION} — registro de base curada, con su referencia primaria"

FISHBASE_CITATION = {
    "key": "fishbase",
    "ref": f"Froese, R. & Pauly, D. (eds.) (2024). FishBase, versión {VERSION}. "
           "Publicación electrónica, www.fishbase.org.",
    "url": "https://www.fishbase.org",
    "supports": "Base de datos curada de parámetros poblacionales por especie.",
}


# ── mapeo de parámetros ─────────────────────────────────────────────────
# Cada parámetro del modelo dice de qué tabla y columna de FishBase sale.
# `agg` marca los que se calculan sobre varios registros (varios stocks,
# sexos y localidades): ahí se reporta la mediana, el número de registros y
# el rango observado, porque un solo número escondería esa dispersión.

PARAM_MAP = {
    # Los tres de `species` no traen localidad: la tabla guarda un único valor
    # curado por especie y su referencia. Para saber si son regionales sólo se
    # puede mirar el título de esa referencia, que es señal más floja que una
    # localidad — y así queda anotado en la evidencia.
    "Lmax": {
        "table": "species", "col": "Length", "agg": False, "unit": "cm",
        "ref_col": "MaxLengthRef", "what": "longitud máxima registrada",
    },
    "mean_body_size": {
        "table": "species", "col": "CommonLength", "agg": False, "unit": "cm",
        "ref_col": "CommonLengthRef", "what": "longitud común (talla típica del adulto)",
    },
    "max_age": {
        "table": "species", "col": "LongevityWild", "agg": False, "unit": "años",
        "ref_col": "LongevityWildRef", "what": "longevidad observada en el medio silvestre",
    },
    "natural_mortality": {
        "table": "popgrowth", "col": "M", "agg": True, "unit": "1/año",
        "ref_col": "PopGrowthRef", "what": "tasa de mortalidad natural M",
    },
    "growth_rate": {
        "table": "popgrowth", "col": "K", "agg": True, "unit": "1/año",
        "ref_col": "PopGrowthRef", "what": "coeficiente K de crecimiento de von Bertalanffy",
    },
    "age_first_maturity": {
        "table": "maturity", "col": "tm", "agg": True, "unit": "años",
        "ref_col": "MaturityRefNo", "spec_col": "Speccode",
        "what": "edad de primera madurez tm",
    },
    # Con el esquema separado, cada cantidad tiene su columna y FishBase la
    # llena sin ambigüedad: se acabó el aviso de convención que hacía falta
    # mientras Von_bertalanffy_a/b mezclaba cuatro cosas bajo dos nombres.
    "li_a": {
        "table": "poplw", "col": "a", "agg": True, "unit": "",
        "ref_col": "PopLWRef",
        "what": "coeficiente a de la relación peso–talla W = a·L^b",
    },
    "li_b": {
        "table": "poplw", "col": "b", "agg": True, "unit": "",
        "ref_col": "PopLWRef",
        "what": "exponente b de la relación peso–talla W = a·L^b",
    },
    "vb_Linf": {
        "table": "popgrowth", "col": "Loo", "agg": True, "unit": "cm",
        "ref_col": "PopGrowthRef",
        "what": "talla asintótica L∞ de von Bertalanffy",
    },
    "vb_t0": {
        "table": "popgrowth", "col": "to", "agg": True, "unit": "años",
        "ref_col": "PopGrowthRef", "negativo": True,
        "what": "edad teórica a talla cero t₀ de von Bertalanffy",
    },
}




# ── descarga del snapshot ───────────────────────────────────────────────

def download(force: bool = False) -> None:
    """Baja las tablas de FishBase que hacen falta, si no están ya."""
    FB_DIR.mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        dest = FB_DIR / f"{t}.parquet"
        if dest.exists() and not force:
            print(f"   · {t:10s} ya está ({dest.stat().st_size / 1e6:.1f} MB)")
            continue
        url = f"{BUCKET}/{PREFIX}/{t}.parquet"
        print(f"   ↓ {t:10s} {url}")
        tmp = dest.with_suffix(".parquet.tmp")
        with urllib.request.urlopen(url, timeout=300) as r, tmp.open("wb") as fh:
            fh.write(r.read())
        tmp.replace(dest)
        print(f"     {dest.stat().st_size / 1e6:.1f} MB")


def load_tables() -> dict[str, pd.DataFrame]:
    faltan = [t for t in TABLES if not (FB_DIR / f"{t}.parquet").exists()]
    if faltan:
        raise SystemExit(
            f"Faltan tablas de FishBase: {', '.join(faltan)}.\n"
            f"Ejecuta primero:  python3 {Path(__file__).relative_to(ROOT)} --download")
    return {t: pd.read_parquet(FB_DIR / f"{t}.parquet") for t in TABLES}


# ── resolución de especies ──────────────────────────────────────────────

def build_index(fb: dict[str, pd.DataFrame]) -> tuple[dict[str, int], dict[str, int]]:
    """Devuelve (nombre aceptado → SpecCode, sinónimo → SpecCode)."""
    sp = fb["species"]
    acepta = {
        f"{g.strip()} {e.strip()}": int(c)
        for g, e, c in zip(sp["Genus"], sp["Species"], sp["SpecCode"])
        if isinstance(g, str) and isinstance(e, str)
    }
    syn = fb["synonyms"]
    sinon = {}
    for g, e, c in zip(syn["SynGenus"], syn["SynSpecies"], syn["SpecCode"]):
        if not (isinstance(g, str) and isinstance(e, str)) or not c:
            continue
        nombre = f"{g.strip()} {e.strip()}"
        if nombre not in acepta and int(c) > 0:
            sinon.setdefault(nombre, int(c))
    return acepta, sinon


def limpiar_ref(txt) -> str:
    """Quita el marcado HTML que FishBase deja en autores y títulos."""
    if not isinstance(txt, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", txt)).strip()


_REF_IDX: dict[int, dict] = {}


def ref_row(refrens: pd.DataFrame, refno) -> dict | None:
    """Una referencia por RefNo, con índice en memoria.

    Se consulta una vez por registro y `refrens` trae 62 000 filas: recorrerla
    entera cada vez multiplicaba por diez el tiempo de generación.
    """
    if refno is None or pd.isna(refno):
        return None
    if not _REF_IDX:
        cols = ["RefNo", "Author", "Year", "Title", "Source"]
        for r in refrens[cols].itertuples(index=False):
            _REF_IDX.setdefault(int(r.RefNo), dict(zip(cols[1:], r[1:])))
    return _REF_IDX.get(int(refno))


def cita_primaria(refrens: pd.DataFrame, refno, what: str) -> dict | None:
    """Convierte un RefNo de FishBase en una entrada de cita completa."""
    r = ref_row(refrens, refno)
    if r is None:
        return None
    autor, anio = limpiar_ref(r.get("Author")), r.get("Year")
    titulo, fuente = limpiar_ref(r.get("Title")), limpiar_ref(r.get("Source"))
    if not autor and not titulo:
        return None
    ref = f"{autor} ({int(anio) if pd.notna(anio) else 's.f.'}). {titulo}"
    if fuente:
        ref += f" {fuente}"
    return {
        "key": f"fb_ref_{int(refno)}",
        "ref": ref,
        "url": f"https://www.fishbase.org/references/FBRefSummary.php?ID={int(refno)}",
        "supports": f"Estudio del que FishBase toma {what}.",
    }


# ── extracción de valores ───────────────────────────────────────────────

def texto_ref(fb, refno) -> str:
    """Título y fuente de una referencia, para clasificarla por región."""
    r = ref_row(fb["refrens"], refno)
    if r is None:
        return ""
    return " ".join(limpiar_ref(r.get(c)) for c in ("Title", "Source"))


def valor_simple(fb, spec: int, meta: dict):
    """Un único valor curado de la tabla `species`."""
    fila = fb["species"][fb["species"]["SpecCode"] == spec]
    if fila.empty:
        return None
    r = fila.iloc[0]
    v = r.get(meta["col"])
    if v is None or pd.isna(v) or float(v) <= 0:
        return None
    refno = r.get(meta.get("ref_col", ""))
    refs = [c for c in [cita_primaria(fb["refrens"], refno, meta["what"])] if c]
    nivel, frag = fb_region.clasificar(texto_ref(fb, refno))
    region = None
    if nivel:
        region = {
            "nivel": nivel, "n": 1, "de": 1,
            "evidencia": [{"nivel": nivel, "fragmento": frag, "origen": "referencia",
                           "locality": "", "ref": refs[0]["ref"] if refs else ""}],
        }
    return {"value": round(float(v), 4), "n": 1, "rango": None, "refs": refs,
            "region": region, "value_global": round(float(v), 4), "rango_global": None}


def valor_agregado(fb, spec: int, meta: dict):
    """Mediana sobre los registros de la especie, con su dispersión.

    Si algún registro es de la región modelada, la mediana se calcula sólo con
    esos: la mundial se conserva aparte para poder comparar. Un valor que se va
    a aprobar como validado para el Golfo tiene que salir del Golfo.
    """
    tabla = fb[meta["table"]]
    col_spec = meta.get("spec_col", "SpecCode")
    filas = tabla[tabla[col_spec] == spec]
    serie = pd.to_numeric(filas[meta["col"]], errors="coerce").dropna()
    # t₀ es negativo por definición; el resto de cantidades no puede ser ≤ 0.
    serie = serie[serie != 0] if meta.get("negativo") else serie[serie > 0]
    if serie.empty:
        return None

    ref_col = meta.get("ref_col") if meta.get("ref_col") in filas.columns else None

    # Procedencia registro a registro: localidad, país y —si la localidad
    # calla— el título del estudio del que FishBase lo tomó.
    niveles: dict = {}
    evidencia: list[dict] = []
    for i in serie.index:
        fila = filas.loc[i]
        refno = fila.get(ref_col) if ref_col else None
        nivel, frag, origen = fb_region.clasificar_registro(
            fila.get("Locality"), fila.get("C_Code"), texto_ref(fb, refno))
        if not nivel:
            continue
        niveles[i] = nivel
        evidencia.append({
            "nivel": nivel, "fragmento": frag, "origen": origen,
            "locality": limpiar_ref(fila.get("Locality")),
            "ref": (cita_primaria(fb["refrens"], refno, meta["what"]) or {}).get("ref", ""),
        })

    def resumen(s: pd.Series) -> dict:
        return {"value": round(float(s.median()), 6), "n": int(s.size),
                "rango": [round(float(s.min()), 6), round(float(s.max()), 6)]}

    global_ = resumen(serie)
    usada = serie
    region = None
    if niveles:
        nivel = fb_region.mejor(niveles.values())
        # Se usan los registros del nivel detectado y de los más específicos:
        # si hay datos del Golfo, mandan ellos; los del Pacífico oriental no
        # los diluyen. Ordena de específico a laxo, así que basta con el índice.
        admitidos = set(fb_region.NIVELES[:fb_region.NIVELES.index(nivel) + 1])
        idx = [i for i, n in niveles.items() if n in admitidos]
        usada = serie.loc[idx]
        region = {"nivel": nivel, "n": int(usada.size), "de": int(serie.size),
                  "evidencia": [e for e in evidencia if e["nivel"] in admitidos][:5]}

    # Las citas: primero las de los registros que sostienen el valor propuesto.
    refs, vistos = [], set()
    if ref_col:
        orden = list(usada.index) + [i for i in serie.index if i not in set(usada.index)]
        for i in orden:
            rn = filas.at[i, ref_col]
            if pd.isna(rn) or int(rn) in vistos:
                continue
            vistos.add(int(rn))
            c = cita_primaria(fb["refrens"], rn, meta["what"])
            if c:
                refs.append(c)
            if len(refs) >= 3:
                break

    dato = resumen(usada)
    dato.update({"refs": refs, "region": region,
                 "value_global": global_["value"], "rango_global": global_["rango"]})
    return dato


def confianza(meta: dict, dato: dict) -> str:
    """Alta sólo si hay varios registros concordantes; baja si el campo es ambiguo."""
    if not meta["agg"]:
        return "alta"
    if dato["n"] == 1 and dato.get("region"):
        # Un único registro, pero medido en la región modelada. Un dato local
        # solitario dice más sobre este sistema que tres de otros océanos.
        return "media"
    lo, hi = dato["rango"]
    a, b = abs(lo), abs(hi)
    lo_abs, hi_abs = min(a, b), max(a, b)
    disperso = hi_abs > 2 * lo_abs if lo_abs > 0 else True
    if dato["n"] >= 3 and not disperso:
        return "alta"
    if dato["n"] >= 3 or not disperso:
        return "media"
    return "baja"


def razonamiento(meta: dict, dato: dict, nombre: str, via: str) -> str:
    partes = []
    if meta["agg"]:
        lo, hi = dato["rango"]
        partes.append(
            f"FishBase reúne {dato['n']} registro(s) de {meta['what']} para {nombre}; "
            f"se propone la mediana. Rango observado: {lo} – {hi} {meta['unit']}."
            if dato["n"] > 1 else
            f"FishBase tiene un único registro de {meta['what']} para {nombre}.")
    else:
        partes.append(f"FishBase registra {meta['what']} de {nombre}.")
    reg = dato.get("region")
    if reg:
        etq = fb_region.ETIQUETA[reg["nivel"]]
        donde = "; ".join(dict.fromkeys(
            e["locality"] or f"referencia: «{e['fragmento']}»" for e in reg["evidencia"]))
        if meta["agg"]:
            partes.append(
                f"Región: {reg['n']} de {reg['de']} registro(s) son del {etq} ({donde}), "
                f"y el valor propuesto se calcula sólo con ellos"
                + (f" — la mediana mundial sería {dato['value_global']}."
                   if reg["n"] < reg["de"] else "."))
        else:
            partes.append(
                f"Región: la referencia de este valor es del {etq} ({donde}). "
                "Es el título del estudio, no una localidad de medición: "
                "confirma que el valor que cita sea el de esa región.")
    if via:
        partes.append(via)
    if not dato["refs"] and meta["agg"]:
        partes.append("El registro no trae referencia primaria: sólo respalda FishBase.")
    return " ".join(partes)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download", action="store_true", help="Descarga o refresca el snapshot")
    ap.add_argument("--force", action="store_true", help="Vuelve a bajar aunque ya exista")
    ap.add_argument("--species", help="Sólo esta especie (para inspeccionar un caso)")
    ap.add_argument("--params", help="Lista de parámetros separada por coma")
    args = ap.parse_args()

    if args.download:
        print(f"→ Snapshot de FishBase {VERSION} en {FB_DIR.relative_to(ROOT)}")
        download(force=args.force)
        if not args.species:
            return

    fb = load_tables()
    base = pd.read_csv(BASE_CSV)
    acepta, sinon = build_index(fb)

    params = list(PARAM_MAP)
    if args.params:
        params = [p.strip() for p in args.params.split(",") if p.strip() in PARAM_MAP]

    suggestions: dict[str, dict] = {}
    por_param: dict[str, int] = {}
    especies_ok, sin_match, sin_dato = set(), [], set()

    for row in base.itertuples():
        nombre = str(row.Species).strip()
        if args.species and nombre != args.species:
            continue
        spec, via = acepta.get(nombre), ""
        if spec is None:
            spec = sinon.get(nombre)
            if spec is not None:
                valida = fb["species"][fb["species"]["SpecCode"] == spec]
                acepta_nom = (f"{valida.iloc[0]['Genus']} {valida.iloc[0]['Species']}"
                              if not valida.empty else "?")
                via = (f"«{nombre}» es sinónimo; FishBase lo trata como {acepta_nom} "
                       f"(SpecCode {spec}). Confirma que es la misma especie del modelo.")
        if spec is None:
            sin_match.append(nombre)
            continue
        especies_ok.add(nombre)

        tuvo = False
        for param in params:
            meta = PARAM_MAP[param]
            dato = (valor_agregado(fb, spec, meta) if meta["agg"]
                    else valor_simple(fb, spec, meta))
            if not dato:
                continue
            tuvo = True
            citas = [FISHBASE_CITATION | {
                "url": f"https://www.fishbase.org/summary/{spec}",
                "supports": f"Registro de {nombre} en FishBase (SpecCode {spec}): {meta['what']}.",
            }] + dato["refs"]
            reg = dato.get("region")
            suggestions[f"{row.Index}:{param}"] = {
                "param": param,
                "species": nombre,
                "group": str(row.Group),
                "value": dato["value"],
                "unit": meta["unit"],
                "confidence": confianza(meta, dato),
                "basis": "consulta_base_curada",
                "scope": (f"FishBase SpecCode {spec} · {fb_region.ETIQUETA[reg['nivel']]}"
                          if reg else f"FishBase SpecCode {spec}"),
                "speccode": spec,
                "n_records": dato["n"],
                "observed_range": dato["rango"],
                # Procedencia geográfica: lo que decide si esta celda se puede
                # aprobar como validada sin ir al paper. `region` es None
                # cuando FishBase no dice de dónde salió el dato — que no es lo
                # mismo que decir que viene de fuera de la región.
                "region": reg["nivel"] if reg else None,
                "region_label": fb_region.ETIQUETA[reg["nivel"]] if reg else None,
                # De dónde salió la señal regional. «localidad» es donde se
                # midió, y es prueba; «referencia» es el título del estudio, y
                # sólo es indicio: un catálogo del Pacífico oriental puede
                # citar una talla medida en cualquier parte. El aprobado
                # automático distingue las dos.
                "region_origin": ("localidad"
                                  if reg and any(e["origen"] == "localidad"
                                                 for e in reg["evidencia"])
                                  else "referencia" if reg else None),
                "region_n": reg["n"] if reg else 0,
                "region_of": reg["de"] if reg else dato["n"],
                "region_evidence": reg["evidencia"] if reg else [],
                "value_global": dato["value_global"],
                "observed_range_global": dato["rango_global"],
                "rationale": razonamiento(meta, dato, nombre, via),
                "citations": citas,
                "author": AUTHOR,
            }
            por_param[param] = por_param.get(param, 0) + 1
        if not tuvo:
            sin_dato.add(nombre)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": f"FishBase {VERSION} (snapshot parquet, Source Cooperative)",
        "author": AUTHOR,
        "warning": ("Valores copiados de una base curada, NO extraídos del corpus del proyecto "
                    "y NO inferidos por el modelo. La cita primaria es lo que hay que "
                    "comprobar; FishBase es el intermediario. Requiere aceptación humana "
                    "explícita para convertirse en dato."),
        "params_covered": params,
        "region_levels": {n: fb_region.ETIQUETA[n] for n in fb_region.NIVELES},
        "region_counts": {
            n: sum(1 for s in suggestions.values() if s["region"] == n)
            for n in fb_region.NIVELES},
        "matched_species": len(especies_ok),
        "unmatched_species": sorted(set(sin_match)),
        "suggestions": suggestions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"✓ {OUT.relative_to(ROOT)}  ({len(suggestions)} sugerencias)")
    print(f"   especies del modelo encontradas en FishBase : {len(especies_ok)} de {len(base)}")
    print(f"   encontradas pero sin ningún parámetro       : {len(sin_dato)}")
    print(f"   no encontradas (aves, mamíferos, sinónimos) : {len(set(sin_match))}")
    print("\n   por parámetro:")
    for p, n in sorted(por_param.items(), key=lambda kv: -kv[1]):
        print(f"     {p:22s} {n:5d}   ({PARAM_MAP[p]['unit']})")
    conf = pd.Series([s["confidence"] for s in suggestions.values()]).value_counts()
    print("\n   por confianza: " + " · ".join(f"{k}={v}" for k, v in conf.items()))
    regionales = [s for s in suggestions.values() if s["region"]]
    porloc = [s for s in regionales if s["region_origin"] == "localidad"]
    print(f"\n   con procedencia regional: {len(regionales)} de {len(suggestions)}"
          f"  ({len(porloc)} por localidad medida, {len(regionales) - len(porloc)} "
          f"sólo por el título de la referencia)")
    for niv in fb_region.NIVELES:
        n = sum(1 for s in regionales if s["region"] == niv)
        nl = sum(1 for s in porloc if s["region"] == niv)
        if n:
            print(f"     {fb_region.ETIQUETA[niv]:22s} {n:5d}   (por localidad: {nl})")
    con_prim = sum(1 for s in suggestions.values() if len(s["citations"]) > 1)
    print(f"   con referencia primaria además de FishBase: {con_prim} de {len(suggestions)}")


if __name__ == "__main__":
    main()
