"""FishBase para el buscador, desde el snapshot local en parquet.

El adaptador web de FishBase ya no existe (la API histórica está caída), así que
el buscador consulta el mismo snapshot que usa el tablero de revisión
(`data/external/fishbase`). Reutiliza `fishbase_suggestions` y `fb_region`:
mismos parámetros, misma mediana regional y misma cita primaria de cada registro.
"""
import re
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "phase_7_review"))

import fishbase_suggestions as fbs  # noqa: E402
import fb_region  # noqa: E402

BINOMIO = re.compile(r"\b([A-Z][a-z]{2,})\s+([a-z]{3,})\b")
_lock = threading.Lock()
_fb = _acepta = _sinon = None
_comunes = _proyecto = _por_codigo = None


def disponible() -> bool:
    return all((fbs.FB_DIR / f"{t}.parquet").exists() for t in fbs.TABLES)


def _cargar():
    global _fb, _acepta, _sinon
    with _lock:
        if _fb is None:
            _fb = fbs.load_tables()
            _acepta, _sinon = fbs.build_index(_fb)
    return _fb


def _indices():
    """Índices auxiliares: nombres comunes de FishBase y especies del proyecto."""
    global _comunes, _proyecto, _por_codigo
    if _comunes is None:
        fb = _cargar()
        sp = fb["species"]
        _por_codigo = {int(c): f"{g.strip()} {e.strip()}" for g, e, c in
                       zip(sp["Genus"], sp["Species"], sp["SpecCode"])
                       if isinstance(g, str) and isinstance(e, str)}
        _comunes = {}
        for nom, c in zip(sp["FBname"], sp["SpecCode"]):
            if isinstance(nom, str) and len(nom) > 4:
                _comunes.setdefault(nom.lower(), int(c))
        try:
            import pandas as pd
            _proyecto = set(pd.read_csv(fbs.BASE_CSV)["Species"].astype(str).str.strip())
        except Exception:
            _proyecto = set()
    return _comunes, _proyecto


def especies_en(texto: str, contexto: str = "", maximo: int = 2) -> list[tuple[str, int, str]]:
    """Especies de la pregunta (y, si no hay, del contexto recuperado) → (nombre, SpecCode, aviso).

    Orden de prioridad: binomio escrito en la pregunta (sin exigir mayúsculas),
    nombre común inglés de FishBase en la pregunta y, por último, las especies
    del proyecto que más aparecen en los fragmentos y la respuesta del RAG:
    «cabrilla sardinera» no está en FishBase, pero los papers que la tratan
    nombran *Mycteroperca rosacea*.
    """
    comunes, proyecto = _indices()
    out, vistos = [], set()

    def agrega(nombre, spec, aviso=""):
        if spec and nombre not in vistos and len(out) < maximo:
            vistos.add(nombre); out.append((nombre, spec, aviso))

    def resolver(n):
        if n in _acepta: return n, _acepta[n], ""
        if n in _sinon: return n, _sinon[n], "sinónimo en FishBase"
        return None

    low = texto.lower()
    for g, e in re.findall(r"\b([A-Za-z]{3,})\s+([a-z]{3,})\b", texto):
        r = resolver(f"{g.capitalize()} {e.lower()}")
        if r: agrega(*r)
    for nom, spec in comunes.items():
        if re.search(rf"\b{re.escape(nom)}s?\b", low):
            agrega(_por_codigo.get(spec, nom), spec, f"nombre común «{nom}»")
    if not out and contexto:
        cuenta = {}
        for g, e in BINOMIO.findall(contexto):
            n = f"{g} {e}"
            if n in proyecto and resolver(n):
                cuenta[n] = cuenta.get(n, 0) + 1
        # Una sola: la segunda suele ser una especie mencionada de pasada.
        for n, _ in sorted(cuenta.items(), key=lambda x: -x[1])[:1]:
            r = resolver(n)
            agrega(r[0], r[1], "especie inferida de los papers recuperados")
    return out


def consultar(texto: str, contexto: str = "") -> list[dict]:
    """Parámetros de FishBase, con procedencia y cita, de las especies detectadas."""
    fb = _cargar()
    resultado = []
    for nombre, spec, aviso in especies_en(texto, contexto):
        params = []
        for param, meta in fbs.PARAM_MAP.items():
            dato = fbs.valor_agregado(fb, spec, meta) if meta["agg"] else fbs.valor_simple(fb, spec, meta)
            if not dato:
                continue
            reg = dato.get("region")
            params.append({
                "param": param, "descripcion": meta["what"], "valor": dato["value"],
                "unidad": meta["unit"], "n_registros": dato["n"], "rango": dato["rango"],
                "procedencia": fb_region.ETIQUETA[reg["nivel"]] if reg else "sin localidad registrada",
                "valor_mundial": dato["value_global"],
                "citas": [c["ref"] for c in dato["refs"]],
            })
        resultado.append({"especie": nombre, "speccode": spec, "aviso": aviso,
                          "url": f"https://www.fishbase.org/summary/{spec}",
                          "parametros": params})
    return resultado


def a_texto(datos: list[dict]) -> str:
    """Resumen legible para el modelo y para la interfaz."""
    bloques = []
    for d in datos:
        if not d["parametros"]:
            bloques.append(f"**{d['especie']}** (FishBase SpecCode {d['speccode']}): sin parámetros poblacionales registrados en FishBase.")
            continue
        lin = [f"**{d['especie']}** (FishBase SpecCode {d['speccode']}{', ' + d['aviso'] if d['aviso'] else ''})"]
        for p in d["parametros"]:
            rng = f", rango {p['rango'][0]}–{p['rango'][1]}" if p["rango"] and p["n_registros"] > 1 else ""
            lin.append(f"- {p['descripcion']}: {p['valor']} {p['unidad']} "
                       f"(n={p['n_registros']}{rng}; procedencia: {p['procedencia']}; "
                       f"mediana mundial {p['valor_mundial']})")
        bloques.append("\n".join(lin))
    return "\n\n".join(bloques)
