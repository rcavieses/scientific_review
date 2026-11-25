#!/usr/bin/env python3
"""Aprueba como validadas las sugerencias de IA respaldadas por literatura regional.

EL MISMO CRITERIO, UNA COSA DISTINTA
====================================
`fb_autovalidate.py` aprueba un número de FishBase cuando el registro se MIDIÓ
en la región. Aquí no hay medición: `ai_suggestions.py` infiere IsMigratory del
taxón y lo respalda con literatura. Lo que se clasifica, entonces, es la cita.

La diferencia importa y no se puede borrar:

    FishBase validado  →  «este valor se midió en el Golfo».
    IA validada        →  «esta afirmación biológica la sostiene literatura
                           del Golfo; el valor sigue siendo una inferencia
                           taxonómica, no un dato medido».

Por eso salen al export con estado propio, `validado_region_cita`, y no se
mezclan con los de FishBase. Un modelador que quiera sólo mediciones puede
filtrar por estado y quedarse sin ninguna de éstas.

LA REGLA
--------
Se aprueba la sugerencia si al menos una de sus citas es del Golfo de
California o del Pacífico mexicano (`fb_region.py`). Que la regla se apoye
además en literatura de Barbados o Nueva Zelanda no la invalida: lo que se
exige es que exista respaldo regional, no que todo lo sea.

LO QUE NO ENTRA
---------------
  · Confianza **baja**. Esas reglas dicen en su propio texto que el campo es
    ambiguo para ese taxón —los mictófidos migran verticalmente, no entre
    zonas; las mobulas se agregan DENTRO del Golfo— y piden decidir qué mide
    IsMigratory antes de aceptar nada. Aprobarlas en lote sería contestar
    automáticamente justo la pregunta que la regla deja abierta.
  · Celdas ya resueltas con otra fuente: son decisiones humanas sobre la
    evidencia.
  · Reglas cuya literatura no es regional. La afirmación puede ser cierta
    igualmente —un gobio es sedentario en cualquier océano—; lo que falta es
    el respaldo local, así que se quedan para revisión humana.

Uso:
    python3 scripts/phase_7_review/ai_autovalidate.py --dry-run
    python3 scripts/phase_7_review/ai_autovalidate.py --reviewer "R. Cavieses"
    python3 scripts/phase_7_review/ai_autovalidate.py --citas      # qué cita es regional
    python3 scripts/phase_7_review/ai_autovalidate.py --deshacer
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
from fb_autovalidate import niveles_hasta

ROOT = HERE.parent.parent
AI_FILE = ROOT / "outputs" / "review" / "ai_suggestions.json"
DECISIONS_FILE = ROOT / "outputs" / "review" / "decisions.json"

MARCA = "validacion_regional_cita"     # sello propio: no es el de FishBase
REVISOR_POR_DEFECTO = "validación regional por cita (automática)"


def clasificar_citas(citations: list[dict]) -> list[dict]:
    """Clasifica cada cita de una sugerencia por región.

    Se mira el texto de la referencia y el campo `supports`, que es donde
    `ai_suggestions.py` dice qué afirmación sostiene la cita — muchas veces con
    más precisión geográfica que el propio título.
    """
    out = []
    for c in citations:
        nivel, frag = fb_region.clasificar(c.get("ref", ""), c.get("supports", ""))
        if nivel:
            out.append({"key": c.get("key", ""), "nivel": nivel, "fragmento": frag,
                        "ref": c.get("ref", "")})
    return out


def seleccionar(sugerencias: dict, decisions: dict, *, nivel: str = "pacifico_mexicano",
                incluir_baja: bool = False, group: str | None = None,
                rehacer: bool = False) -> tuple[dict, list[dict], list[dict]]:
    """Sugerencias que cumplen la regla.

    Devuelve `(elegibles, bloqueadas, sin_respaldo_regional)`. La tercera lista
    es la que hay que mirar después: son afirmaciones sin literatura local, no
    afirmaciones falsas.
    """
    admitidos = niveles_hasta(nivel)
    elegibles, bloqueadas, sin_region = {}, [], []
    for item_id, sug in sugerencias.items():
        if group and sug["group"] != group:
            continue
        regionales = [c for c in clasificar_citas(sug.get("citations", []))
                      if c["nivel"] in admitidos]
        if not regionales:
            sin_region.append({"item_id": item_id, "species": sug["species"],
                               "group": sug["group"], "scope": sug.get("scope", "")})
            continue
        if sug.get("confidence") == "baja" and not incluir_baja:
            continue
        previa = decisions.get(item_id) or {}
        estado = previa.get("status")
        if estado in ("accepted", "rejected") and previa.get("source") != "IA":
            bloqueadas.append({"item_id": item_id, "species": sug["species"],
                               "param": sug["param"], "source": previa.get("source"),
                               "reviewer": previa.get("reviewer", "")})
            continue
        if estado and not rehacer:
            continue
        elegibles[item_id] = (sug, regionales)
    return elegibles, bloqueadas, sin_region


def aplicar(elegibles: dict, decisions: dict, revisor: str, nivel_pedido: str) -> None:
    ahora = datetime.now().isoformat(timespec="seconds")
    for item_id, (sug, regionales) in elegibles.items():
        previo = decisions.get(item_id)
        history = (previo or {}).get("history", [])
        if previo:
            history = history + [{k: previo[k] for k in
                                  ("status", "value", "source", "reviewer", "updated_at")
                                  if k in previo}]
        mejor = fb_region.mejor(c["nivel"] for c in regionales)
        cuales = "; ".join(f"{c['key']} («{c['fragmento']}»)" for c in regionales)
        comentario = (
            f"Validado por respaldo regional: {fb_region.ETIQUETA[mejor]} — {cuales}. "
            f"Regla: {sug.get('scope', '')}. El valor sigue siendo una inferencia "
            f"taxonómica, no una medición: lo que la literatura regional sostiene es "
            f"la afirmación biológica.")
        decisions[item_id] = {
            "item_id": item_id,
            "species": sug["species"],
            "group": sug["group"],
            "param": sug["param"],
            "status": "accepted",
            "value": sug["value"],
            "source": "IA",
            "reference": " | ".join(c["ref"] for c in sug.get("citations", [])),
            "reviewer": revisor,
            "comment": comentario,
            MARCA: {"region": mejor, "citas": [c["key"] for c in regionales],
                    "confidence": sug.get("confidence"), "nivel_pedido": nivel_pedido},
            "updated_at": ahora,
            "history": history[-10:],
        }


def deshacer(decisions: dict, group: str | None = None) -> int:
    fuera = [i for i, d in decisions.items()
             if d.get(MARCA) and (group is None or d.get("group") == group)]
    for i in fuera:
        decisions.pop(i)
    return len(fuera)


def imprimir_citas() -> None:
    """Qué cita del catálogo cuenta como regional y cuál no."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ai", HERE / "ai_suggestions.py")
    ai = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai)
    reg, no_reg = [], []
    for k, c in sorted(ai.CITATIONS.items()):
        nivel, frag = fb_region.clasificar(c["ref"], c["supports"])
        (reg if nivel else no_reg).append((k, nivel, frag, c["ref"]))
    print(f"REGIONALES ({len(reg)} de {len(reg) + len(no_reg)})")
    for k, nivel, frag, ref in sorted(reg, key=lambda x: fb_region.NIVELES.index(x[1])):
        print(f"  {fb_region.SIGLA[nivel]}  {k:18s} «{frag}»\n      {ref[:100]}")
    print(f"\nSIN SEÑAL REGIONAL ({len(no_reg)}) — la afirmación puede ser correcta; "
          "lo que falta es respaldo local")
    for k, _, _, ref in no_reg:
        print(f"      {k:18s} {ref[:100]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nivel", default="pacifico_mexicano", choices=list(fb_region.NIVELES),
                    help="Hasta qué nivel se acepta (incluye los más específicos)")
    ap.add_argument("--incluir-baja", action="store_true",
                    help="Acepta también las reglas de confianza baja, que avisan de que "
                         "el campo es ambiguo para ese taxón")
    ap.add_argument("--group", help="Sólo este grupo funcional")
    ap.add_argument("--reviewer", default=REVISOR_POR_DEFECTO)
    ap.add_argument("--rehacer", action="store_true")
    ap.add_argument("--deshacer", action="store_true")
    ap.add_argument("--citas", action="store_true",
                    help="Enseña qué citas del catálogo son regionales y sale")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.citas:
        imprimir_citas()
        return

    decisions = json.loads(DECISIONS_FILE.read_text(encoding="utf-8")) \
        if DECISIONS_FILE.exists() else {}

    if args.deshacer:
        n = deshacer(decisions, args.group)
        if not args.dry_run:
            DECISIONS_FILE.write_text(json.dumps(decisions, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
        print(f"↩ {n} sugerencia(s) reabiertas" + (" (simulado)" if args.dry_run else ""))
        return

    if not AI_FILE.exists():
        raise SystemExit("Falta ai_suggestions.json. Ejecuta antes "
                         "scripts/phase_7_review/ai_suggestions.py")
    sug = json.loads(AI_FILE.read_text(encoding="utf-8"))["suggestions"]
    if args.group and args.group not in {s["group"] for s in sug.values()}:
        raise SystemExit(f"No hay sugerencias de IA para el grupo «{args.group}».\n"
                         "Grupos disponibles: "
                         + ", ".join(sorted({s["group"] for s in sug.values()})))

    elegibles, bloqueadas, sin_region = seleccionar(
        sug, decisions, nivel=args.nivel, incluir_baja=args.incluir_baja,
        group=args.group, rehacer=args.rehacer)

    baja_fuera = sum(1 for s in sug.values()
                     if s.get("confidence") == "baja"
                     and any(c["nivel"] in niveles_hasta(args.nivel)
                             for c in clasificar_citas(s.get("citations", []))))
    print(f"Regla: al menos una cita de «{fb_region.ETIQUETA[args.nivel]}» o más específica"
          + (f" · grupo «{args.group}»" if args.group else ""))
    print(f"  sugerencias que se aprobarían : {len(elegibles)} de {len(sug)}")
    print(f"  sin respaldo regional         : {len(sin_region)}  (quedan a revisión humana)")
    if not args.incluir_baja and baja_fuera:
        print(f"  confianza baja, excluidas     : {baja_fuera}  (la regla avisa de que el "
              f"campo es ambiguo para ese taxón)")
    print(f"  intactas (resueltas con otra fuente): {len(bloqueadas)}")
    por_nivel: dict[str, int] = {}
    por_valor: dict[str, int] = {}
    for s, regs in elegibles.values():
        m = fb_region.mejor(c["nivel"] for c in regs)
        por_nivel[m] = por_nivel.get(m, 0) + 1
        por_valor[s["value"]] = por_valor.get(s["value"], 0) + 1
    for niv in fb_region.NIVELES:
        if por_nivel.get(niv):
            print(f"    {fb_region.ETIQUETA[niv]:22s} {por_nivel[niv]:5d}")
    print(f"  valor propuesto: " + " · ".join(f"{k}={v}" for k, v in sorted(por_valor.items())))

    if args.dry_run:
        print("\n(simulado: no se ha escrito nada)")
        for item_id, (s, regs) in list(elegibles.items())[:10]:
            print(f"  {item_id:16s} {s['species'][:26]:28s} {s['value']:4s} "
                  f"{s['scope'][:24]:26s} ← {', '.join(c['key'] for c in regs)}")
        return

    aplicar(elegibles, decisions, args.reviewer.strip() or REVISOR_POR_DEFECTO, args.nivel)
    DECISIONS_FILE.write_text(json.dumps(decisions, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"\n✓ {len(elegibles)} sugerencia(s) aprobadas en "
          f"{DECISIONS_FILE.relative_to(ROOT)}")
    print("  para revertir sólo este lote:  --deshacer")


if __name__ == "__main__":
    main()
