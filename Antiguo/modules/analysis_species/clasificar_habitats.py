"""
Clasifica las especies de species_unicas.csv en acuaticas / terrestres / pendientes.

Estrategia:
  1. WoRMS batch API (50 nombres por peticion) -> si existe en WoRMS = MARINE
  2. GBIF species/match + species/{key} -> habitat "MARINE", "FRESHWATER", "TERRESTRIAL"
  3. Cache JSON local para reanudar si se interrumpe

Salidas:
  species_acuaticas.csv   -> MARINE o FRESHWATER (o ambos)
  species_terrestres.csv  -> solo TERRESTRIAL (sin rastro acuatico)
  species_pendientes.csv  -> sin datos de habitat

Uso:
  python clasificar_habitats.py [--input species_unicas.csv] [--cache cache_habitats.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
WORMS_URL = "https://www.marinespecies.org/rest/AphiaRecordsByNames"
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_SPECIES_URL = "https://api.gbif.org/v1/species/{key}"

WORMS_BATCH = 50       # max nombres por peticion WoRMS
GBIF_BATCH_SLEEP = 0.15  # segundos entre peticiones GBIF
WORMS_SLEEP = 1.0       # segundos entre lotes WoRMS
TIMEOUT = 15            # segundos timeout HTTP
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, params: dict | None = None) -> Any | None:
    """GET con reintentos. Devuelve JSON o None."""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 10))
                print(f"  [rate-limit] esperando {wait}s ...", flush=True)
                time.sleep(wait)
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                print(f"  [error] {url}: {exc}", flush=True)
            else:
                time.sleep(2 ** attempt)
    return None


def _post(url: str, json_body: Any) -> Any | None:
    """POST con reintentos. Devuelve JSON o None."""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(url, json=json_body, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 10))
                time.sleep(wait)
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                print(f"  [error] POST {url}: {exc}", flush=True)
            else:
                time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# WoRMS
# ---------------------------------------------------------------------------

def query_worms_batch(names: list[str]) -> dict[str, str]:
    """
    Consulta WoRMS por lote via GET con query string.
    Devuelve {nombre: 'MARINE'} para los que existan en WoRMS.
    """
    import urllib.parse

    result: dict[str, str] = {}
    qs = "&".join(f"scientificnames[]={urllib.parse.quote(n)}" for n in names)
    url = f"{WORMS_URL}?{qs}"
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return result
        data = r.json()
    except Exception as exc:
        print(f"  [worms error] {exc}", flush=True)
        return result

    # data es lista de listas (una por nombre buscado)
    if not isinstance(data, list):
        return result

    for idx, records in enumerate(data):
        name = names[idx] if idx < len(names) else ""
        if records and isinstance(records, list) and len(records) > 0:
            result[name] = "MARINE"

    return result


# ---------------------------------------------------------------------------
# GBIF
# ---------------------------------------------------------------------------

def query_gbif_habitat(species_name: str) -> str:
    """
    Consulta GBIF species/match y luego species/{key}.
    Devuelve: 'MARINE', 'FRESHWATER', 'TERRESTRIAL', 'MARINE_FRESHWATER', o ''
    """
    match_data = _get(GBIF_MATCH_URL, params={"name": species_name, "verbose": False})
    if not match_data:
        return ""

    usage_key = match_data.get("usageKey") or match_data.get("speciesKey")
    if not usage_key:
        return ""

    species_data = _get(GBIF_SPECIES_URL.format(key=usage_key))
    if not species_data:
        return ""

    marine = species_data.get("marine", False)
    freshwater = species_data.get("freshwater", False)
    terrestrial = species_data.get("terrestrial", False)

    if (marine or freshwater) and not terrestrial:
        return "MARINE" if marine else "FRESHWATER"
    if (marine or freshwater) and terrestrial:
        return "MARINE_FRESHWATER"  # eurihalino / anfidromo -> conservar
    if terrestrial:
        return "TERRESTRIAL"
    return ""


# ---------------------------------------------------------------------------
# Clasificador principal
# ---------------------------------------------------------------------------

def clasificar(
    species_list: list[str],
    cache: dict[str, str],
) -> dict[str, str]:
    """
    Clasifica todas las especies usando cache primero, luego WoRMS, luego GBIF.
    Actualiza cache in-place y devuelve {nombre: clasificacion}.
    """
    pendientes = [s for s in species_list if s not in cache]

    # --- Paso 1: WoRMS en lotes ---
    sin_worms: list[str] = []
    total = len(pendientes)
    print(f"\n[WoRMS] Consultando {total} especies en lotes de {WORMS_BATCH}...", flush=True)

    for i in range(0, total, WORMS_BATCH):
        lote = pendientes[i : i + WORMS_BATCH]
        hits = query_worms_batch(lote)
        for name in lote:
            if name in hits:
                cache[name] = "MARINE"
            else:
                sin_worms.append(name)
        progreso = min(i + WORMS_BATCH, total)
        print(f"  WoRMS {progreso}/{total} | marine hasta ahora: {sum(1 for v in cache.values() if v=='MARINE')}", flush=True)
        time.sleep(WORMS_SLEEP)

    # --- Paso 2: GBIF para los no encontrados en WoRMS ---
    print(f"\n[GBIF] Consultando {len(sin_worms)} especies no encontradas en WoRMS...", flush=True)
    for idx, name in enumerate(sin_worms, 1):
        habitat = query_gbif_habitat(name)
        cache[name] = habitat or ""
        if idx % 100 == 0 or idx == len(sin_worms):
            print(f"  GBIF {idx}/{len(sin_worms)}", flush=True)
        time.sleep(GBIF_BATCH_SLEEP)

    return cache


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_cache(path: Path) -> dict[str, str]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(path: Path, cache: dict[str, str]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def read_species(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            (row.get("species") or "").strip()
            for row in reader
            if (row.get("species") or "").strip()
        ]


def write_csv(path: Path, species: list[str], habitat_col: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["species", "habitat"])
        for s in species:
            writer.writerow([s, habitat_col])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    here = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=here / "species_unicas.csv")
    parser.add_argument("--cache", type=Path, default=here / "cache_habitats.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra estadisticas de la cache, sin consultar APIs",
    )
    args = parser.parse_args()

    species_list = read_species(args.input)
    print(f"Especies cargadas: {len(species_list)}")

    cache = load_cache(args.cache)
    print(f"Cache previa: {len(cache)} entradas")

    if not args.dry_run:
        clasificar(species_list, cache)
        save_cache(args.cache, cache)
        print(f"\nCache guardada en {args.cache}")

    # --- Clasificar con la cache resultante ---
    acuaticas, terrestres, pendientes = [], [], []
    for s in species_list:
        hab = (cache.get(s) or "").upper()
        if hab in ("MARINE", "FRESHWATER", "MARINE_FRESHWATER"):
            acuaticas.append((s, hab))
        elif hab == "TERRESTRIAL":
            terrestres.append((s, hab))
        else:
            pendientes.append((s, hab))

    # Escribir resultados
    out_acuaticas = here / "species_acuaticas.csv"
    out_terrestres = here / "species_terrestres.csv"
    out_pendientes = here / "species_pendientes.csv"

    for path, data in [
        (out_acuaticas, acuaticas),
        (out_terrestres, terrestres),
        (out_pendientes, pendientes),
    ]:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["species", "habitat"])
            for s, h in data:
                writer.writerow([s, h])

    print(f"\n=== RESUMEN ===")
    print(f"  Acuaticas (MARINE/FRESHWATER): {len(acuaticas):>6}")
    print(f"  Terrestres:                    {len(terrestres):>6}")
    print(f"  Pendientes (sin dato):         {len(pendientes):>6}")
    print(f"\nArchivos exportados:")
    print(f"  {out_acuaticas}")
    print(f"  {out_terrestres}")
    print(f"  {out_pendientes}")


if __name__ == "__main__":
    main()
