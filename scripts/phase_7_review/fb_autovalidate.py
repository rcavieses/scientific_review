#!/usr/bin/env python3
"""Aprueba como validadas las celdas de FishBase con procedencia regional.

LA REGLA
========
Si el parámetro se midió en el Golfo de California, en el Pacífico mexicano o
en el Pacífico oriental, se aprueba. No porque FishBase sea fiable —eso no
cambia—, sino porque el valor describe el sistema que se está modelando, y esa
era la pregunta que la revisión celda a celda tenía que contestar. Cuando la
procedencia ya la contesta, revisarla a mano es repetir trabajo.

QUÉ CUENTA COMO PROCEDENCIA
---------------------------
Dos cosas, y no valen lo mismo:

  · `localidad`  — FishBase registra dónde se midió («Guaymas, Gulf of
                   California»). Es prueba directa y entra por defecto.
  · `referencia` — la localidad está vacía y lo que casa es el título del
                   estudio. Un catálogo del Pacífico oriental puede citar una
                   talla medida en cualquier parte, así que esto es indicio y
                   NO entra si no se pide con `--incluir-referencia`.

Los parámetros de la tabla `species` de FishBase (Lmax, talla común, longevidad)
sólo pueden clasificarse por referencia: esa tabla no guarda localidad. Por eso
en la práctica quedan fuera del aprobado por defecto.

LO QUE NO TOCA
--------------
  · Celdas ya resueltas en la cola de revisión con otra fuente. Una decisión
    humana sobre la evidencia no la pisa un lote automático.
  · Celdas sin señal regional. Que FishBase no diga de dónde salió un dato no
    significa que venga de fuera: se quedan pendientes, como estaban.

Uso:
    python3 scripts/phase_7_review/fb_autovalidate.py --dry-run
    python3 scripts/phase_7_review/fb_autovalidate.py --reviewer "R. Cavieses"
    python3 scripts/phase_7_review/fb_autovalidate.py --nivel pacifico_mexicano
    python3 scripts/phase_7_review/fb_autovalidate.py --deshacer
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fb_region

ROOT = HERE.parent.parent
FB_FILE = ROOT / "outputs" / "review" / "fishbase_suggestions.json"
DECISIONS_FILE = ROOT / "outputs" / "review" / "decisions.json"

MARCA = "validacion_regional"      # sello que deja este proceso en la decisión
REVISOR_POR_DEFECTO = "validación regional (automática)"


def niveles_hasta(nivel: str) -> set[str]:
    """El nivel pedido y todos los más específicos que él.

    Pedir «Pacífico oriental» incluye lo del Golfo: es la cuenca que lo
    contiene. Pedir «Golfo de California» no incluye lo de Perú.
    """
    if nivel not in fb_region.NIVELES:
        raise ValueError(f"nivel desconocido: {nivel}")
    return set(fb_region.NIVELES[:fb_region.NIVELES.index(nivel) + 1])


def seleccionar(sugerencias: dict, decisions: dict, *, nivel: str = "pacifico_oriental",
                origenes: tuple[str, ...] = ("localidad",),
                group: str | None = None,
                rehacer: bool = False) -> tuple[dict, list[dict]]:
    """Celdas que cumplen la regla. Devuelve `(elegibles, bloqueadas)`."""
    admitidos = niveles_hasta(nivel)
    elegibles, bloqueadas = {}, []
    for item_id, sug in sugerencias.items():
        if group and sug["group"] != group:
            continue
        if sug.get("region") not in admitidos:
            continue
        if sug.get("region_origin") not in origenes:
            continue
        previa = decisions.get(item_id) or {}
        estado = previa.get("status")
        if estado in ("accepted", "rejected") and previa.get("source") != "FishBase":
            # Resuelta en la cola con otra fuente: es una decisión humana.
            bloqueadas.append({"item_id": item_id, "species": sug["species"],
                               "param": sug["param"], "source": previa.get("source"),
                               "reviewer": previa.get("reviewer", "")})
            continue
        if estado and not rehacer:
            continue          # ya decidida en la propia página de FishBase
        elegibles[item_id] = sug
    return elegibles, bloqueadas


def aplicar(elegibles: dict, decisions: dict, revisor: str, nivel_pedido: str) -> None:
    """Escribe las aceptaciones sobre el diccionario de decisiones, en sitio."""
    ahora = datetime.now().isoformat(timespec="seconds")
    for item_id, sug in elegibles.items():
        previo = decisions.get(item_id)
        history = (previo or {}).get("history", [])
        if previo:
            history = history + [{k: previo[k] for k in
                                  ("status", "value", "source", "reviewer", "updated_at")
                                  if k in previo}]
        etq = sug.get("region_label") or fb_region.ETIQUETA.get(sug.get("region"), "—")
        donde = "; ".join(dict.fromkeys(
            e.get("locality") or e.get("fragmento", "")
            for e in sug.get("region_evidence", []))) or "—"
        comentario = (
            f"Validado por procedencia: {sug.get('region_n', 0)} de "
            f"{sug.get('region_of', 0)} registro(s) del {etq} ({donde}). "
            f"Valor calculado sólo con los registros regionales"
            + (f"; la mediana mundial era {sug['value_global']}."
               if sug.get("value_global") not in (None, sug["value"]) else "."))
        decisions[item_id] = {
            "item_id": item_id,
            "species": sug["species"],
            "group": sug["group"],
            "param": sug["param"],
            "status": "accepted",
            "value": sug["value"],
            "source": "FishBase",
            "reference": " | ".join(c["ref"] for c in sug.get("citations", [])),
            "reviewer": revisor,
            "comment": comentario,
            # Sello propio: permite deshacer exactamente este lote sin tocar
            # las aceptaciones que hizo alguien a mano en el tablero.
            MARCA: {"region": sug.get("region"), "origin": sug.get("region_origin"),
                    "n": sug.get("region_n"), "de": sug.get("region_of"),
                    "nivel_pedido": nivel_pedido},
            "updated_at": ahora,
            "history": history[-10:],
        }


def deshacer(decisions: dict, group: str | None = None) -> int:
    """Reabre sólo las celdas que aprobó este proceso."""
    fuera = [i for i, d in decisions.items()
             if d.get(MARCA) and (group is None or d.get("group") == group)]
    for i in fuera:
        decisions.pop(i)
    return len(fuera)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nivel", default="pacifico_oriental", choices=list(fb_region.NIVELES),
                    help="Hasta qué nivel se acepta (incluye los más específicos)")
    ap.add_argument("--incluir-referencia", action="store_true",
                    help="Acepta también las clasificadas sólo por el título del estudio")
    ap.add_argument("--group", help="Sólo este grupo funcional")
    ap.add_argument("--reviewer", default=REVISOR_POR_DEFECTO)
    ap.add_argument("--rehacer", action="store_true",
                    help="Reescribe también las que ya tienen decisión de FishBase")
    ap.add_argument("--deshacer", action="store_true",
                    help="Reabre las celdas aprobadas por este proceso y sale")
    ap.add_argument("--dry-run", action="store_true", help="Enseña qué haría y no escribe")
    args = ap.parse_args()

    decisions = json.loads(DECISIONS_FILE.read_text(encoding="utf-8")) \
        if DECISIONS_FILE.exists() else {}

    if args.deshacer:
        n = deshacer(decisions, args.group)
        if not args.dry_run:
            DECISIONS_FILE.write_text(json.dumps(decisions, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
        print(f"↩ {n} celda(s) reabiertas" + (" (simulado)" if args.dry_run else ""))
        return

    if not FB_FILE.exists():
        raise SystemExit("Falta fishbase_suggestions.json. Ejecuta antes "
                         "scripts/phase_7_review/fishbase_suggestions.py")
    sug = json.loads(FB_FILE.read_text(encoding="utf-8"))["suggestions"]

    if args.group and args.group not in {s["group"] for s in sug.values()}:
        # Un grupo mal escrito daba «0 celdas», que se lee como «no hay nada
        # regional aquí» y es una respuesta falsa a otra pregunta.
        raise SystemExit(f"No hay sugerencias de FishBase para el grupo «{args.group}».\n"
                         "Grupos disponibles: "
                         + ", ".join(sorted({s["group"] for s in sug.values()})))

    origenes = ("localidad", "referencia") if args.incluir_referencia else ("localidad",)
    elegibles, bloqueadas = seleccionar(sug, decisions, nivel=args.nivel,
                                        origenes=origenes, group=args.group,
                                        rehacer=args.rehacer)

    print(f"Regla: hasta «{fb_region.ETIQUETA[args.nivel]}» · procedencia por "
          f"{' y '.join(origenes)}" + (f" · grupo «{args.group}»" if args.group else ""))
    print(f"  celdas que se aprobarían : {len(elegibles)}")
    print(f"  intactas (ya resueltas en la cola con otra fuente): {len(bloqueadas)}")
    por_nivel: dict[str, int] = {}
    cambia_valor = 0
    for s in elegibles.values():
        por_nivel[s["region"]] = por_nivel.get(s["region"], 0) + 1
        if s.get("value_global") is not None and s["value_global"] != s["value"]:
            cambia_valor += 1
    for niv in fb_region.NIVELES:
        if por_nivel.get(niv):
            print(f"    {fb_region.ETIQUETA[niv]:22s} {por_nivel[niv]:5d}")
    print(f"  con valor distinto de la mediana mundial: {cambia_valor} "
          f"(se escribe el regional)")

    if args.dry_run:
        print("\n(simulado: no se ha escrito nada)")
        for item_id, s in list(elegibles.items())[:10]:
            print(f"  {item_id:12s} {s['species'][:28]:28s} {s['param']:18s} "
                  f"{s['value']} ← {s['region_label']} ({s['region_n']}/{s['region_of']})")
        return

    aplicar(elegibles, decisions, args.reviewer.strip() or REVISOR_POR_DEFECTO, args.nivel)
    DECISIONS_FILE.write_text(json.dumps(decisions, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"\n✓ {len(elegibles)} celda(s) aprobadas como validadas en "
          f"{DECISIONS_FILE.relative_to(ROOT)}")
    print("  para revertir sólo este lote:  --deshacer")


if __name__ == "__main__":
    main()
