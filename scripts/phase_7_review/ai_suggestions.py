#!/usr/bin/env python3
"""Sugerencias de IA por celda, para revisión humana.

AVISO DE PROCEDENCIA — leer antes de usar
=========================================
Esto NO es extracción del corpus. Son inferencias taxonómicas basadas en el
conocimiento general del modelo: exactamente el mecanismo que en B5 rellenó
parámetros de especies que los papers ni mencionan.

La diferencia no está en el método, está en el etiquetado y en el destino:
  · nunca entran en las columnas de valor,
  · viajan por un canal propio (`sugerencia_ia`) con confianza y razonamiento,
  · solo se convierten en dato si un revisor las acepta explícitamente,
  · al exportar quedan como `revisado_sugerencia_ia`, distinguibles del corpus.

Cada regla dice de qué taxón habla, por qué, y contra qué literatura se puede
comprobar: toda regla lleva al menos una cita académica verificable (DOI o
enlace estable) en `CITATIONS`. La cita respalda la afirmación biológica
—residencia, territorialidad, estatus migratorio— no la codificación del campo
de Atlantis, que sigue siendo un juicio del revisor. Si una regla es
discutible, se marca con confianza baja y el porqué queda escrito.

Uso:
    python3 scripts/phase_7_review/ai_suggestions.py --top-groups 6
    python3 scripts/phase_7_review/ai_suggestions.py --groups "Reef Carnivores"
    python3 scripts/phase_7_review/ai_suggestions.py --bibliografia
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "output"
OUT = ROOT / "outputs" / "review" / "ai_suggestions.json"
BASE_CSV = DATA / "Atlantis_GOC_parametros_biologicos_BUSQUEDA1.csv"

AUTHOR = "Claude Opus 5 — inferencia taxonómica, respaldada por cita, sin extracción del corpus"

# ── Registro de citas ───────────────────────────────────────────────────
# Literatura académica verificable que respalda cada regla. Una cita puede
# dar servicio a varias familias: el registro está separado de las reglas
# justamente para eso. Cada entrada lleva `supports`: qué afirmación
# sostiene, para que el revisor sepa qué ir a comprobar.

CITATIONS = {
    # ── Peces: referencias regionales y de movimiento ───────────────────
    "thomson2000": {
        "ref": "Thomson, D. A., Findley, L. T. & Kerstitch, A. N. (2000). Reef Fishes of the "
               "Sea of Cortez: The Rocky-Shore Fishes of the Gulf of California, ed. rev. "
               "Austin: University of Texas Press.",
        "url": "https://doi.org/10.7560/781542",
        "supports": "Hábitos, residencia y fidelidad al sitio de los peces de arrecife rocoso "
                    "del Golfo de California, familia por familia.",
    },
    "robertson2024": {
        "ref": "Robertson, D. R. & Allen, G. R. (2024). Shorefishes of the Tropical Eastern "
               "Pacific: online information system, v3.0. Balboa: Smithsonian Tropical "
               "Research Institute.",
        "url": "https://biogeodb.stri.si.edu/sftep/",
        "supports": "Hábitat y distribución de las 1 287 especies costeras del Pacífico "
                    "oriental tropical, incluido el Golfo.",
    },
    "hobson1965": {
        "ref": "Hobson, E. S. (1965). Diurnal-nocturnal activity of some inshore fishes in the "
               "Gulf of California. Copeia 1965(3): 291–302.",
        "url": "https://doi.org/10.2307/1440790",
        "supports": "Los desplazamientos diarios entre refugio y área de alimentación son "
                    "tróficos y de escala local: no son migración estacional.",
    },
    "hobson1968": {
        "ref": "Hobson, E. S. (1968). Predatory behavior of some shore fishes in the Gulf of "
               "California. U.S. Fish and Wildlife Service, Research Report 73. 92 pp.",
        "url": "",
        "supports": "Conducta de emboscada y sedentarismo de los depredadores bentónicos "
                    "del arrecife rocoso del Golfo.",
    },
    "kramer1999": {
        "ref": "Kramer, D. L. & Chapman, M. R. (1999). Implications of fish home range size and "
               "relocation for marine reserve function. Environmental Biology of Fishes 55: 65–79.",
        "url": "https://doi.org/10.1023/A:1007481206399",
        "supports": "Marco de referencia sobre ámbito de hogar en peces de arrecife: la mayoría "
                    "opera en escalas de metros a cientos de metros, sin relocalización estacional.",
    },
    "chapman2000": {
        "ref": "Chapman, M. R. & Kramer, D. L. (2000). Movements of fishes within and among "
               "fringing coral reefs in Barbados. Environmental Biology of Fishes 57: 11–24.",
        "url": "https://doi.org/10.1023/A:1004545724503",
        "supports": "Medición directa de movimiento en peces de arrecife: residencia alta y "
                    "desplazamientos acotados al parche, lábridos incluidos.",
    },
    "brandl2018": {
        "ref": "Brandl, S. J., Goatley, C. H. R., Bellwood, D. R. & Tornabene, L. (2018). The "
               "hidden half: ecology and evolution of cryptobenthic fishes on coral reefs. "
               "Biological Reviews 93: 1846–1873.",
        "url": "https://doi.org/10.1111/brv.12423",
        "supports": "Los peces criptobentónicos (blénidos, trambollos, gobios) tienen ámbitos "
                    "de hogar restringidos y asociación estrecha al microhábitat.",
    },
    "depczynski2003": {
        "ref": "Depczynski, M. & Bellwood, D. R. (2003). The role of cryptobenthic reef fishes "
               "in coral reef trophodynamics. Marine Ecology Progress Series 256: 183–191.",
        "url": "https://doi.org/10.3354/meps256183",
        "supports": "Gobios y criptobentónicos: talla pequeña, ciclo rápido y ámbito de hogar "
                    "muy reducido.",
    },
    "hastings2019": {
        "ref": "Hastings, P. A. (2019). Evolution of sexual dimorphism in tube blennies "
               "(Teleostei: Chaenopsidae). Integrative Organismal Biology 1(1): obz003.",
        "url": "https://doi.org/10.1093/iob/obz003",
        "supports": "Los chaenópsidos ocupan un refugio fijo (tubo o concha vacía) que defienden "
                    "y del que depende su reproducción: movilidad de metros.",
    },
    "feary2006": {
        "ref": "Feary, D. A. & Clements, K. D. (2006). Habitat use by triplefin species "
               "(Tripterygiidae) on rocky reefs in New Zealand. Journal of Fish Biology 69: 1031–1046.",
        "url": "https://doi.org/10.1111/j.1095-8649.2006.01178.x",
        "supports": "Los tripterígidos son filopátricos y fieles al microhábitat a lo largo "
                    "de toda su ontogenia.",
    },
    "ceccarelli2007": {
        "ref": "Ceccarelli, D. M. (2007). Modification of benthic communities by territorial "
               "damselfish: a multi-species comparison. Coral Reefs 26: 853–866.",
        "url": "https://doi.org/10.1007/s00338-007-0275-1",
        "supports": "Las damiselas mantienen y defienden territorios fijos de forma persistente, "
                    "hasta modificar la comunidad bentónica dentro de ellos.",
    },
    "kendall2021": {
        "ref": "Kendall, M. S., Siceloff, L., Ruffo, A., Winship, A. & Monaco, M. E. (2021). "
               "Green morays (Gymnothorax funebris) have sedentary ways in mangrove bays, but "
               "also ontogenetic forays to reef enclaves. Environmental Biology of Fishes 104: 1–15.",
        "url": "https://doi.org/10.1007/s10641-021-01137-0",
        "supports": "Telemetría acústica de 11 meses: fidelidad alta al sitio y ámbito de hogar "
                    "de pocas hectáreas en morenas.",
    },
    "sala2003": {
        "ref": "Sala, E., Aburto-Oropeza, O., Paredes, G. & Thompson, G. (2003). Spawning "
               "aggregations and reproductive behavior of reef fishes in the Gulf of California. "
               "Bulletin of Marine Science 72(1): 103–121.",
        "url": "",
        "supports": "Los serránidos del Golfo forman agregaciones reproductivas en sitios "
                    "concretos: desplazamiento reproductivo local, no migración estacional.",
    },
    "domeier1997": {
        "ref": "Domeier, M. L. & Colin, P. L. (1997). Tropical reef fish spawning aggregations: "
               "defined and reviewed. Bulletin of Marine Science 60(3): 698–726.",
        "url": "https://www.ingentaconnect.com/content/umrsmas/bullmar/1997/00000060/00000003/art00006",
        "supports": "Definición formal que separa la agregación reproductiva (residente o "
                    "transitoria) de la migración estacional.",
    },
    "ogden1977": {
        "ref": "Ogden, J. C. & Ehrlich, P. R. (1977). The behavior of heterotypic resting schools "
               "of juvenile grunts (Pomadasyidae). Marine Biology 42: 273–280.",
        "url": "https://doi.org/10.1007/BF00397751",
        "supports": "Los burros descansan en cardumen sobre el arrecife de día y se dispersan "
                    "100–300 m a alimentarse al anochecer: movimiento trófico diario.",
    },
    "nielsen1999": {
        "ref": "Nielsen, J. G., Cohen, D. M., Markle, D. F. & Robins, C. R. (1999). Ophidiiform "
               "fishes of the world (Order Ophidiiformes). FAO Fisheries Synopsis 125(18). "
               "Roma: FAO. 178 pp.",
        "url": "https://www.fao.org/4/x3930e/x3930e00.htm",
        "supports": "Catálogo anotado de brótulas y congriperlas: hábitos bentónicos de fondo "
                    "blando, cueva o madriguera.",
    },
    "mccosker1977": {
        "ref": "McCosker, J. E. (1977). The osteology, classification, and relationships of the "
               "eel family Ophichthidae. Proceedings of the California Academy of Sciences "
               "41(1): 1–123.",
        "url": "https://www.biodiversitylibrary.org/part/52341",
        "supports": "Morfología excavadora de los ofíctidos y su modo de vida enterrado en "
                    "fondo blando.",
    },
    "briggs1955": {
        "ref": "Briggs, J. C. (1955). A monograph of the clingfishes (Order Xenopterygii). "
               "Stanford Ichthyological Bulletin 6: 1–224.",
        "url": "",
        "supports": "Disco adhesivo ventral de los gobiesócidos y su adherencia permanente "
                    "al sustrato.",
    },
    "sutton2013": {
        "ref": "Sutton, T. T. (2013). Vertical ecology of the pelagic ocean: classical patterns "
               "and new perspectives. Journal of Fish Biology 83: 1508–1527.",
        "url": "https://doi.org/10.1111/jfb.12263",
        "supports": "Los peces mesopelágicos migran verticalmente cada día; ese eje es "
                    "vertical, no un desplazamiento horizontal estacional.",
    },

    # ── Aves ────────────────────────────────────────────────────────────
    "howell1995": {
        "ref": "Howell, S. N. G. & Webb, S. (1995). A Guide to the Birds of Mexico and Northern "
               "Central America. Oxford: Oxford University Press. 851 pp.",
        "url": "https://global.oup.com/academic/product/9780198540120",
        "supports": "Estatus residente / migratorio / invernante de todas las aves de México, "
                    "especificado por especie y región.",
    },
    "gomezsapiens2013": {
        "ref": "Gómez-Sapiens, M. M., Soto-Montoya, E. & Hinojosa-Huerta, O. (2013). Shorebird "
               "abundance and species diversity in natural intertidal and non-tidal anthropogenic "
               "wetlands of the Colorado River delta, Mexico. Ecological Engineering 59: 74–83.",
        "url": "https://doi.org/10.1016/j.ecoleng.2013.03.004",
        "supports": "El Alto Golfo y el delta del Colorado funcionan como escala e invernada "
                    "para playeros (Scolopacidae, Charadriidae) del corredor del Pacífico.",
    },
    "velarde2018": {
        "ref": "Velarde, E. & Ezcurra, E. (2018). Are seabirds' life history traits maladaptive "
               "under present oceanographic variability? The case of Heermann's Gull "
               "(Larus heermanni). The Condor 120: 388–401.",
        "url": "https://doi.org/10.1650/condor-17-5.1",
        "supports": "Larus heermanni cría casi por completo en Isla Rasa y abandona el Golfo "
                    "tras la reproducción.",
    },
    "bow_yefgul": {
        "ref": "Birds of the World: Yellow-footed Gull (Larus livens). Ithaca: Cornell Lab of "
               "Ornithology.",
        "url": "https://birdsoftheworld.org/bow/species/yefgul/cur/introduction",
        "supports": "Endemismo del Golfo de California y condición de residente permanente, "
                    "con dispersión posreproductiva menor al Salton Sea.",
    },
    "bow_heegul": {
        "ref": "Birds of the World: Heermann's Gull (Larus heermanni). Ithaca: Cornell Lab of "
               "Ornithology.",
        "url": "https://birdsoftheworld.org/bow/species/heegul/cur/introduction",
        "supports": "Migración posreproductiva hacia el norte por la costa del Pacífico, hasta "
                    "la Columbia Británica.",
    },
    "bow_bfoboo": {
        "ref": "Birds of the World: Blue-footed Booby (Sula nebouxii). Ithaca: Cornell Lab of "
               "Ornithology.",
        "url": "https://birdsoftheworld.org/bow/species/bfoboo/cur/introduction",
        "supports": "Los bobos del Golfo se dispersan tras criar en lugar de migrar "
                    "estacionalmente.",
    },
    "anderson2017": {
        "ref": "Anderson, D. W., Godínez-Reyes, C. R., Velarde, E., Avalos-Téllez, R., "
               "Ramírez-Delgado, D., Moreno-Prado, H. & Meltzer, L. (2017). Brown Pelicans, "
               "Pelecanus occidentalis californicus (Aves: Pelecanidae): five decades with ENSO, "
               "dynamic nesting, and contemporary breeding status in the Gulf of California. "
               "Ciencias Marinas 43(1): 1–34.",
        "url": "https://doi.org/10.7773/cm.v43i1.2710",
        "supports": "Cinco décadas de seguimiento: el pelícano pardo del Golfo es residente con "
                    "dispersión posreproductiva, no migrante estricto.",
    },
}

# ── Reglas para IsMigratory ─────────────────────────────────────────────
# «Migratoria» se interpreta como en Atlantis: desplazamiento horizontal
# estacional entre zonas, no movimientos tróficos diarios ni migración vertical.
# (species, family, order, class) → (valor, confianza, razonamiento, citas)

SPECIES_RULES = {
    "Larus livens": ("No", "alta",
        "Gaviota pata amarilla: endémica residente del Golfo de California, no migratoria, "
        "a diferencia de la mayoría de los láridos del grupo.",
        ("bow_yefgul", "howell1995")),
    "Larus heermanni": ("Yes", "alta",
        "Gaviota de Heermann: cría en Isla Rasa (Golfo de California) y migra al norte por la "
        "costa del Pacífico tras la reproducción.",
        ("velarde2018", "bow_heegul", "howell1995")),
}

FAMILY_RULES = {
    # ── Peces de arrecife territoriales y crípticos: sedentarios ────────
    "Chaenopsidae":  ("No", "alta",  "Trambollos tubícolas: ocupan tubos de gusano o conchas vacías y defienden ese refugio; movilidad de metros.",
                      ("hastings2019", "thomson2000")),
    "Labrisomidae":  ("No", "alta",  "Trambollos crípticos, bentónicos y territoriales, asociados de por vida a un parche de arrecife.",
                      ("brandl2018", "thomson2000", "hobson1968")),
    "Tripterygiidae":("No", "alta",  "Tres aletas: crípticos, sedentarios, ámbito de hogar de escala métrica.",
                      ("feary2006", "brandl2018")),
    "Blenniidae":    ("No", "alta",  "Blénidos: bentónicos y territoriales, sin desplazamiento estacional.",
                      ("brandl2018", "thomson2000")),
    "Gobiidae":      ("No", "alta",  "Gobios: bentónicos, muchos comensales de invertebrados; ámbito de hogar muy reducido.",
                      ("depczynski2003", "brandl2018")),
    "Gobiesocidae":  ("No", "alta",  "Peces piedra: adheridos al sustrato por disco ventral, prácticamente sésiles.",
                      ("briggs1955", "thomson2000")),
    "Muraenidae":    ("No", "alta",  "Morenas: residentes de guarida, fieles al sitio durante años.",
                      ("kendall2021", "thomson2000")),
    "Labridae":      ("No", "media", "Lábridos: en su mayoría residentes de arrecife con ámbito de hogar acotado; algunos grandes hacen desplazamientos locales.",
                      ("chapman2000", "kramer1999", "thomson2000")),
    "Pomacentridae": ("No", "alta",  "Damiselas: territoriales, defienden un área fija del arrecife.",
                      ("ceccarelli2007", "thomson2000")),
    "Scorpaenidae":  ("No", "alta",  "Escorpiónidos: emboscadores bentónicos, sedentarios.",
                      ("hobson1968", "thomson2000")),
    "Serranidae":    ("No", "media", "Meros y cabrillas: residentes de arrecife. Muchos forman agregaciones reproductivas —desplazamientos de decenas de km— que no equivalen a migración estacional.",
                      ("sala2003", "domeier1997", "thomson2000")),
    "Haemulidae":    ("No", "media", "Burros: forman cardúmenes diurnos en el arrecife y se dispersan de noche a alimentarse; movimiento trófico diario, no migración.",
                      ("ogden1977", "hobson1965")),
    "Ophidiidae":    ("No", "media", "Brótulas: bentónicas de fondo blando o cuevas, sedentarias.",
                      ("nielsen1999",)),
    "Ophichthidae":  ("No", "alta",  "Anguilas de fondo: excavadoras, sedentarias.",
                      ("mccosker1977", "thomson2000")),
    "Congridae":     ("No", "media", "Congrios: bentónicos, residentes de madriguera.",
                      ("thomson2000", "robertson2024")),
    # ── Aves ────────────────────────────────────────────────────────────
    "Scolopacidae":  ("Yes", "alta", "Playeros y correlimos: migrantes de larga distancia; el Golfo es zona de invernada o escala.",
                      ("howell1995", "gomezsapiens2013")),
    "Charadriidae":  ("Yes", "alta", "Chorlos: migrantes de larga distancia con invernada en el noroeste de México.",
                      ("howell1995", "gomezsapiens2013")),
    "Anatidae":      ("Yes", "alta", "Patos y gansos: migrantes; el Golfo recibe poblaciones invernantes.",
                      ("howell1995", "gomezsapiens2013")),
    "Stercorariidae":("Yes", "alta", "Págalos y salteadores: migrantes transoceánicos.",
                      ("howell1995",)),
    "Procellariidae":("Yes", "alta", "Pardelas y petreles: migrantes pelágicos de largo alcance.",
                      ("howell1995",)),
    "Hydrobatidae":  ("Yes", "media","Paíños: dispersión pelágica amplia; varias especies migran, otras son residentes de sus colonias.",
                      ("howell1995",)),
    "Sulidae":       ("No", "media", "Bobos: residentes o dispersivos alrededor de sus colonias en el Golfo, sin migración estacional definida.",
                      ("bow_bfoboo", "howell1995")),
    "Pelecanidae":   ("No", "media", "Pelícano pardo: residente con dispersión posreproductiva; no es migrante estricto.",
                      ("anderson2017", "howell1995")),
    "Ardeidae":      ("No", "media", "Garzas: en su mayoría residentes en el Golfo, con dispersión local.",
                      ("howell1995",)),
    "Phalacrocoracidae": ("No", "media", "Cormoranes: residentes con movimientos locales.",
                      ("howell1995",)),
    "Fregatidae":    ("No", "media", "Fragatas: residentes de colonia con forrajeo de gran radio, no migración estacional.",
                      ("howell1995",)),
    # ── Peces mesopelágicos ─────────────────────────────────────────────
    "Myctophidae":   ("No", "baja",  "Linternillas: realizan migración vertical diaria de cientos de metros, pero NO migración horizontal estacional. El campo es ambiguo para este taxón — decidir qué mide antes de aceptar.",
                      ("sutton2013",)),
    "Bathylagidae":  ("No", "baja",  "Igual que los mictófidos: migración vertical diaria, no horizontal.",
                      ("sutton2013",)),
    "Stomiidae":     ("No", "baja",  "Peces dragón: migradores verticales, sin migración horizontal estacional.",
                      ("sutton2013",)),
}

ORDER_RULES = {
    "Anguilliformes": ("No", "media", "Anguiliformes bentónicos del Golfo: residentes de madriguera o grieta.",
                       ("mccosker1977", "thomson2000")),
    "Gobiesociformes":("No", "alta",  "Peces piedra: adheridos al sustrato, sin desplazamiento.",
                       ("briggs1955", "thomson2000")),
}


def cite_block(keys) -> list[dict]:
    """Expande claves de cita a entradas completas; falla si alguna no existe."""
    out = []
    for k in keys:
        if k not in CITATIONS:
            raise KeyError(f"cita desconocida: {k!r}")
        c = CITATIONS[k]
        out.append({"key": k, "ref": c["ref"], "url": c["url"], "supports": c["supports"]})
    return out


def rule_for(row) -> tuple[str, str, str, str, tuple[str, ...]] | None:
    """Devuelve (valor, confianza, razonamiento, ámbito de la regla, citas)."""
    sp = str(row.Species)
    if sp in SPECIES_RULES:
        v, c, r, cites = SPECIES_RULES[sp]
        return v, c, r, f"especie {sp}", cites
    fam = str(row.Family)
    if fam in FAMILY_RULES:
        v, c, r, cites = FAMILY_RULES[fam]
        return v, c, r, f"familia {fam}", cites
    order = str(row.Order)
    if order in ORDER_RULES:
        v, c, r, cites = ORDER_RULES[order]
        return v, c, r, f"orden {order}", cites
    return None


def print_bibliografia() -> None:
    """Imprime la bibliografía y qué reglas se apoyan en cada entrada."""
    usos: dict[str, list[str]] = {}
    for d, etiqueta in ((SPECIES_RULES, "especie"), (FAMILY_RULES, "familia"), (ORDER_RULES, "orden")):
        for taxon, (_, _, _, cites) in d.items():
            for k in cites:
                usos.setdefault(k, []).append(f"{etiqueta} {taxon}")
    for k in sorted(CITATIONS, key=lambda k: CITATIONS[k]["ref"]):
        c = CITATIONS[k]
        print(f"\n[{k}] {c['ref']}\n    {c['url']}\n    sostiene: {c['supports']}")
        print(f"    usada en: {', '.join(usos.get(k, ['(sin uso)']))}")
    huerfanas = sorted(set(CITATIONS) - set(usos))
    if huerfanas:
        print(f"\n⚠ citas sin regla que las use: {', '.join(huerfanas)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top-groups", type=int, default=6, help="Nº de grupos más grandes a cubrir")
    ap.add_argument("--groups", help="Lista explícita de grupos, separada por coma")
    ap.add_argument("--bibliografia", action="store_true",
                    help="Imprime la bibliografía y las reglas que se apoyan en cada cita")
    args = ap.parse_args()

    if args.bibliografia:
        print_bibliografia()
        return

    base = pd.read_csv(BASE_CSV)
    if args.groups:
        groups = [g.strip() for g in args.groups.split(",")]
    else:
        groups = base.groupby("Group").size().sort_values(ascending=False).head(args.top_groups).index.tolist()

    suggestions = {}
    by_group = {}
    citas_usadas = set()
    for row in base.itertuples():
        if row.Group not in groups:
            continue
        hit = rule_for(row)
        if not hit:
            continue
        value, confidence, rationale, scope, cites = hit
        citas_usadas.update(cites)
        suggestions[f"{row.Index}:IsMigratory"] = {
            "param": "IsMigratory",
            "species": str(row.Species),
            "group": str(row.Group),
            "value": value,
            "confidence": confidence,
            "basis": "inferencia_taxonomica_con_cita",
            "scope": scope,
            "rationale": rationale,
            "citations": cite_block(cites),
            "author": AUTHOR,
        }
        by_group[str(row.Group)] = by_group.get(str(row.Group), 0) + 1

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "author": AUTHOR,
        "warning": ("Inferencia taxonómica respaldada por literatura académica, no extracción del "
                    "corpus del proyecto. La cita sostiene la afirmación biológica (residencia, "
                    "territorialidad, estatus migratorio), no la codificación del campo de "
                    "Atlantis. Requiere aceptación humana explícita para convertirse en dato."),
        "groups_covered": groups,
        "bibliography": {k: CITATIONS[k] for k in sorted(citas_usadas)},
        "suggestions": suggestions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"✓ {OUT.relative_to(ROOT)}  ({len(suggestions)} sugerencias)")
    for g, n in sorted(by_group.items(), key=lambda kv: -kv[1]):
        total = int((base['Group'] == g).sum())
        print(f"   {g[:34]:36s} {n:4d} de {total} especies")
    conf = pd.Series([s["confidence"] for s in suggestions.values()]).value_counts()
    print("\n   por confianza: " + " · ".join(f"{k}={v}" for k, v in conf.items()))
    vals = pd.Series([s["value"] for s in suggestions.values()]).value_counts()
    print("   por valor:     " + " · ".join(f"{k}={v}" for k, v in vals.items()))
    sin_cita = [k for k, s in suggestions.items() if not s["citations"]]
    print(f"   citas:         {len(citas_usadas)} referencias distintas, "
          f"{len(sin_cita)} sugerencias sin cita")


if __name__ == "__main__":
    main()
