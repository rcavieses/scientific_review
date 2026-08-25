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
    # ── Grandes pelágicos y elasmobranquios oceánicos ───────────────────
    "block2011": {
        "ref": "Block, B.A., Jonsen, I.D., Jorgensen, S.J., Winship, A.J. et al. (2011). Tracking apex "
               "marine predator movements in a dynamic ocean. Nature 475: 86-90.",
        "url": "https://doi.org/10.1038/nature10082",
        "supports": "Rastreo satelital de 23 especies de depredadores ápice del Pacífico "
                    "nororiental (atunes, picudos, tiburones lámnidos): desplazamientos "
                    "estacionales de miles de kilómetros.",
    },
    "schaefer2007": {
        "ref": "Schaefer, K.M., Fuller, D.W. & Block, B.A. (2007). Movements, behavior, and habitat "
               "utilization of yellowfin tuna (Thunnus albacares) in the northeastern Pacific Ocean, "
               "ascertained through archival tag data. Marine Biology 152: 503-525.",
        "url": "https://doi.org/10.1007/s00227-007-0689-x",
        "supports": "Marcas archivadoras en atún aleta amarilla del Pacífico nororiental: "
                    "movimientos horizontales amplios y uso estacional del hábitat.",
    },
    "jorgensen2009": {
        "ref": "Jorgensen, S.J., Reeb, C.A., Chapple, T.K., Anderson, S. et al. (2009). Philopatry and "
               "migration of Pacific white sharks. Proceedings of the Royal Society B: Biological "
               "Sciences 277: 679-688.",
        "url": "https://doi.org/10.1098/rspb.2009.1155",
        "supports": "Tiburón blanco del Pacífico oriental: filopatría a zonas costeras combinada "
                    "con migración oceánica anual.",
    },
    "klimley1993goc": {
        "ref": "Klimley, A., Cabrera-Mancillas, I. & Castillo-Geniz, J. (1993). Horizontal and vertical "
               "movements of the scalloped hammerhead shark, Sphyrna lewini, in the southern Gulf Of "
               "California, Mexico. Ciencias Marinas 19: 95-115.",
        "url": "https://doi.org/10.7773/cm.v19i1.918",
        "supports": "Movimientos horizontales y verticales de Sphyrna lewini en el sur del Golfo de "
                    "California.",
    },
    "klimley1993mb": {
        "ref": "Klimley, A.P. (1993). Highly directional swimming by scalloped hammerhead sharks, "
               "Sphyrna lewini, and subsurface irradiance, temperature, bathymetry, and geomagnetic "
               "field. Marine Biology 117: 1-22.",
        "url": "https://doi.org/10.1007/bf00346421",
        "supports": "Natación direccional de largo alcance en Sphyrna lewini: navegación entre "
                    "montes submarinos.",
    },
    # ── Mamíferos marinos del Golfo ─────────────────────────────────────
    "rojasbracho2006": {
        "ref": "Rojas‐Bracho, L., Reeves, R.R. & Jaramillo‐Legorreta, A. (2006). Conservation of the "
               "vaquita Phocoena sinus. Mammal Review 36: 179-216.",
        "url": "https://doi.org/10.1111/j.1365-2907.2006.00088.x",
        "supports": "Vaquita: endemismo del Alto Golfo, con el ámbito de distribución más reducido "
                    "de cualquier cetáceo; sin migración.",
    },
    "cisnerosmata1995": {
        "ref": "Cisneros‐Mata, M.A., Montemayor‐López, G. & Román‐Rodríguez, M.J. (1995). Life History "
               "and Conservation of Totoaba macdonaldi. Conservation Biology 9: 806-814.",
        "url": "https://doi.org/10.1046/j.1523-1739.1995.09040806.x",
        "supports": "Totoaba macdonaldi: migración reproductiva anual hacia el delta del Río "
                    "Colorado.",
    },
    "erisman2012": {
        "ref": "Erisman, B., Aburto-Oropeza, O., Gonzalez-Abraham, C., Mascareñas-Osorio, I. et al. "
               "(2012). Spatio-temporal dynamics of a fish spawning aggregation and its fishery in the "
               "Gulf of California. Scientific Reports 2.",
        "url": "https://doi.org/10.1038/srep00284",
        "supports": "Curvina golfina: agregación reproductiva masiva y predecible en el delta del "
                    "Río Colorado, con desplazamiento estacional hacia ella.",
    },
    "berube2002": {
        "ref": "Bérubé, M., Urbán, J., Dizon, A.E., Brownell, R.L. et al. (2002). Genetic identification "
               "of a small and highly isolated population of fin whales (Balaenoptera physalus) in the "
               "Sea of Cortez, México. Conservation Genetics 3: 183-190.",
        "url": "https://doi.org/10.1023/a:1015224730394",
        "supports": "Rorcual común del Golfo de California: población pequeña, genéticamente "
                    "aislada y residente todo el año.",
    },
    "rice1971": {
        "ref": "Rice, D.W. & Wolman, A.A. (1971). The life history and ecology of the gray whale "
               "(Eschrichtius robustus).",
        "url": "https://doi.org/10.5962/bhl.title.39537",
        "supports": "Ballena gris: migración anual completa entre el Ártico y las lagunas de Baja "
                    "California.",
    },
    "palacios2021": {
        "ref": "Palacios, M.D., Hoyos-Padilla, E.M., Trejo-Ramírez, A., Croll, D.A. et al. (2021). "
               "Description of first nursery area for a pygmy devil ray species (Mobula munkiana) in the "
               "Gulf of California, Mexico. Scientific Reports 11.",
        "url": "https://doi.org/10.1038/s41598-020-80506-8",
        "supports": "Mobula munkiana en el Golfo de California: área de crianza y agregaciones "
                    "estacionales dentro del propio Golfo.",
    },
    "aurioles1994": {
        "ref": "Aurioles-Gamboa, D. & Zavala-González, A. (1994). Ecological factors that determine "
               "distribution and abundance of the California sea lion Zalophus Californianus in the Gulf "
               "Of California. Ciencias Marinas 20: 535-553.",
        "url": "https://doi.org/10.7773/cm.v20i4.976",
        "supports": "Lobo marino de California en el Golfo: distribución y abundancia ligadas a "
                    "colonias fijas, sin migración estacional.",
    },
    # ── Residencia y ámbito de hogar en arrecife ────────────────────────
    "welsh2011": {
        "ref": "Welsh, J.Q. & Bellwood, D.R. (2011). Spatial ecology of the steephead parrotfish "
               "(Chlorurus microrhinos): an evaluation using acoustic telemetry. Coral Reefs 31: 55-65.",
        "url": "https://doi.org/10.1007/s00338-011-0813-8",
        "supports": "Telemetría acústica en pez loro: ámbito de hogar acotado y alta fidelidad al "
                    "sitio.",
    },
    "meyer2005": {
        "ref": "Meyer, C.G. & Holland, K.N. (2005). Movement patterns, home range size and habitat "
               "utilization of the bluespine unicornfish, Naso unicornis (Acanthuridae) in a Hawaiian "
               "marine reserve. Environmental Biology of Fishes 73: 201-210.",
        "url": "https://doi.org/10.1007/s10641-005-0559-7",
        "supports": "Cirujano Naso unicornis: ámbito de hogar reducido y uso de hábitat estable "
                    "dentro de una reserva marina.",
    },
    "claro2003": {
        "ref": "Claro, R. & Lindeman, K.C. (2003). Spawning Aggregation Sites of Snapper and Grouper "
               "Species (Lutjanidae and Serranidae) on the Insular Shelf of Cuba. Gulf and Caribbean "
               "Research 14.",
        "url": "https://doi.org/10.18785/gcr.1402.07",
        "supports": "Pargos y meros: sitios fijos de agregación reproductiva en la plataforma; el "
                    "desplazamiento es hacia la agregación, no migración estacional entre zonas.",
    },
    # ── Peces planos ────────────────────────────────────────────────────
    "able2014": {
        "ref": "Able, K.W. & Joel Fodrie, F. (2014). Distribution and dynamics of habitat use by "
               "juvenile and adult flatfishes. Flatfishes: 242-282.",
        "url": "https://doi.org/10.1002/9781118501153.ch10",
        "supports": "Peces planos: uso del hábitat bentónico por juveniles y adultos, con "
                    "movimientos costa-afuera y sin migración estacional entre zonas.",
    },
    "gibson1994": {
        "ref": "Gibson, R. (1994). Impact of habitat quality and quantity on the recruitment of juvenile "
               "flatfishes. Netherlands Journal of Sea Research 32: 191-206.",
        "url": "https://doi.org/10.1016/0077-7579(94)90040-x",
        "supports": "Peces planos juveniles: dependencia de hábitats bentónicos someros concretos.",
    },
    # ── Pelágicos menores del Golfo ─────────────────────────────────────
    "nevarez1999": {
        "ref": "Nevárez-Martı́nez, M.O., Chávez, E.A., Cisneros-Mata, M.A. & Lluch-Belda, D. (1999). "
               "Modeling of the Pacific sardine Sardinops caeruleus fishery of the Gulf of California, "
               "Mexico. Fisheries Research 41: 273-283.",
        "url": "https://doi.org/10.1016/s0165-7836(99)00023-5",
        "supports": "Pesquería de sardina del Golfo de California: dinámica estacional del stock.",
    },
    "nevarez2001": {
        "ref": "Nevárez-Martı́nez, M.O., Lluch-Belda, D., Cisneros-Mata, M.A., Pablo Santos-Molina, J. "
               "et al. (2001). Distribution and abundance of the Pacific sardine (Sardinops sagax) in "
               "the Gulf of California and their relation with the environment. Progress in Oceanography "
               "49: 565-580.",
        "url": "https://doi.org/10.1016/s0079-6611(01)00041-6",
        "supports": "Sardina del Pacífico en el Golfo de California: la distribución y abundancia "
                    "se desplazan estacionalmente con el ambiente.",
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
    # ── Migradores reproductivos del Alto Golfo ─────────────────────────
    "Totoaba macdonaldi": ("Yes", "alta",
        "Totoaba: endémica del Golfo, hace una migración reproductiva anual hacia el delta del "
        "Río Colorado y regresa al sur; es un desplazamiento estacional entre zonas.",
        ("cisnerosmata1995",)),
    "Cynoscion othonopterus": ("Yes", "alta",
        "Curvina golfina: se concentra cada primavera en el delta del Río Colorado para desovar, "
        "en una agregación masiva y predecible, y se dispersa el resto del año.",
        ("erisman2012", "cisnerosmata1995")),
    # ── Mamíferos marinos ───────────────────────────────────────────────
    "Phocoena sinus": ("No", "alta",
        "Vaquita: endémica del Alto Golfo, con el ámbito de distribución más reducido de cualquier "
        "cetáceo; no migra.",
        ("rojasbracho2006",)),
    "Balaenoptera physalus": ("No", "alta",
        "Rorcual común del Golfo de California: población pequeña, genéticamente aislada del "
        "Pacífico y residente todo el año — a diferencia del resto de su género.",
        ("berube2002",)),
    "Eschrichtius robustus": ("Yes", "alta",
        "Ballena gris: migración anual completa entre las zonas de alimentación árticas y las "
        "lagunas de cría de Baja California.",
        ("rice1971",)),
    "Zalophus californianus": ("No", "media",
        "Lobo marino de California: colonias fijas en las islas del Golfo; dispersión de machos, "
        "sin migración estacional de la población.",
        ("aurioles1994",)),
    # ── Grandes pelágicos ───────────────────────────────────────────────
    "Carcharodon carcharias": ("Yes", "alta",
        "Tiburón blanco del Pacífico oriental: filopatría costera combinada con migración oceánica "
        "anual de ida y vuelta.",
        ("jorgensen2009", "block2011")),
    "Thunnus albacares": ("Yes", "alta",
        "Atún aleta amarilla: marcas archivadoras muestran desplazamientos horizontales amplios y "
        "uso estacional del hábitat en el Pacífico nororiental.",
        ("schaefer2007", "block2011")),
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
    # ── Grandes pelágicos: migradores de largo alcance ──────────────────
    "Scombridae":    ("Yes", "media", "Escómbridos: epipelágicos de nado continuo y desplazamiento estacional. Confianza media porque la familia mezcla atunes oceánicos con macarelas y sierras más costeras.",
                      ("block2011", "schaefer2007")),
    "Istiophoridae": ("Yes", "alta",  "Picudos: pelágicos oceánicos con migraciones estacionales de miles de km, seguidas por marcaje satelital.",
                      ("block2011",)),
    "Coryphaenidae": ("Yes", "media", "Dorados: epipelágicos oceánicos que siguen frentes térmicos estacionales; no marcados en el estudio regional, de ahí la confianza media.",
                      ("block2011",)),
    "Lamnidae":      ("Yes", "media", "Lámnidos: tiburón blanco, mako y marrajo salmón hacen migraciones oceánicas anuales.",
                      ("jorgensen2009", "block2011")),
    "Sphyrnidae":    ("Yes", "media", "Cornudas: en el Golfo se desplazan entre montes submarinos y zonas costeras con patrón estacional. Media porque parte del movimiento documentado es diario, no estacional.",
                      ("klimley1993goc", "klimley1993mb")),
    "Mobulidae":     ("No", "baja",  "Mobulas: forman agregaciones estacionales y áreas de crianza DENTRO del Golfo. El movimiento es regional, no una migración entre zonas del modelo — decidir con qué resolución espacial se define el campo antes de aceptar.",
                      ("palacios2021",)),
    # ── Pelágicos menores ───────────────────────────────────────────────
    "Engraulidae":   ("Yes", "media", "Anchoas: cardúmenes cuya distribución se desplaza estacionalmente con la temperatura dentro del Golfo.",
                      ("nevarez2001", "nevarez1999")),
    "Clupeidae":     ("Yes", "media", "Sardinas: la distribución y abundancia se desplazan estacionalmente con el ambiente en el Golfo.",
                      ("nevarez2001", "nevarez1999")),
    "Alosidae":      ("Yes", "media", "Sardina del Pacífico: desplazamiento estacional del stock ligado a la temperatura.",
                      ("nevarez2001", "nevarez1999")),
    "Dorosomatidae": ("Yes", "baja",  "Sardinas machete: clupeiformes costeros; el respaldo regional es de sardina y anchoa, no del género — confianza baja.",
                      ("nevarez2001",)),
    # ── Arrecife: residentes con ámbito de hogar acotado ────────────────
    "Scaridae":      ("No", "alta",  "Peces loro: telemetría acústica muestra ámbito de hogar acotado y alta fidelidad al sitio.",
                      ("welsh2011", "thomson2000")),
    "Acanthuridae":  ("No", "alta",  "Cirujanos: ámbito de hogar reducido y uso de hábitat estable dentro del arrecife.",
                      ("meyer2005", "thomson2000")),
    "Kyphosidae":    ("No", "media", "Chopas: herbívoras de arrecife rocoso, residentes con desplazamientos locales.",
                      ("kramer1999", "thomson2000")),
    "Lutjanidae":    ("No", "media", "Pargos: residentes de arrecife y fondo duro; forman agregaciones reproductivas en sitios fijos, que no equivalen a migración estacional.",
                      ("claro2003", "thomson2000")),
    "Epinephelidae": ("No", "media", "Meros: residentes de arrecife con agregaciones reproductivas en sitios fijos; mismo criterio que Serranidae.",
                      ("claro2003", "sala2003", "thomson2000")),
    "Balistidae":    ("No", "media", "Cochitos: asociados al arrecife, con ámbito de hogar acotado.",
                      ("kramer1999", "thomson2000")),
    "Monacanthidae": ("No", "media", "Lijas: crípticas y asociadas al arrecife o a fondos vegetados.",
                      ("thomson2000", "robertson2024")),
    "Ostraciidae":   ("No", "media", "Peces cofre: nado lento, residentes de arrecife.",
                      ("thomson2000", "robertson2024")),
    "Tetraodontidae":("No", "media", "Botetes: residentes de arrecife y fondo blando somero.",
                      ("thomson2000", "robertson2024")),
    "Diodontidae":   ("No", "media", "Peces erizo: residentes de arrecife, refugiados de día en grietas.",
                      ("thomson2000", "hobson1965")),
    "Apogonidae":    ("No", "alta",  "Cardenales: nocturnos, refugiados de día en el mismo grupo de grietas; movimiento trófico diario, no migración.",
                      ("hobson1965", "thomson2000")),
    "Chaetodontidae":("No", "alta",  "Mariposas: territoriales o en parejas fijas sobre un parche de arrecife.",
                      ("kramer1999", "thomson2000")),
    "Pomacanthidae": ("No", "alta",  "Ángeles: residentes de arrecife con ámbito de hogar acotado.",
                      ("kramer1999", "thomson2000")),
    "Cirrhitidae":   ("No", "alta",  "Halcones: posados sobre el sustrato, emboscadores sedentarios.",
                      ("hobson1968", "thomson2000")),
    "Holocentridae": ("No", "alta",  "Candiles: nocturnos, refugiados de día en cuevas fijas del arrecife.",
                      ("hobson1965", "thomson2000")),
    "Zanclidae":     ("No", "media", "Ídolo moro: asociado al arrecife, sin desplazamiento estacional.",
                      ("thomson2000", "robertson2024")),
    "Aulostomidae":  ("No", "media", "Trompetas: acechadores de arrecife, sedentarios.",
                      ("hobson1968", "thomson2000")),
    "Priacanthidae": ("No", "media", "Catalufas: nocturnas, asociadas a fondo duro.",
                      ("hobson1965", "thomson2000")),
    # ── Fondo blando y bentónicos ───────────────────────────────────────
    "Opistognathidae":("No", "alta", "Bocones: viven en una madriguera vertical que construyen y defienden; movilidad de metros.",
                      ("thomson2000", "robertson2024")),
    "Dactyloscopidae":("No", "alta", "Miraestrellas de arena: enterrados en el sustrato, prácticamente inmóviles.",
                      ("thomson2000", "robertson2024")),
    "Uranoscopidae": ("No", "alta",  "Miraestrellas: emboscadores enterrados en fondo blando.",
                      ("thomson2000", "robertson2024")),
    "Batrachoididae":("No", "alta",  "Peces sapo: bentónicos, con cuidado parental en nido fijo bajo roca.",
                      ("thomson2000", "robertson2024")),
    "Antennariidae": ("No", "alta",  "Peces rana: caminan sobre el sustrato, sin capacidad de desplazamiento estacional.",
                      ("thomson2000", "robertson2024")),
    "Ogcocephalidae":("No", "alta",  "Peces murciélago: bentónicos de fondo blando, se desplazan apoyados en las aletas.",
                      ("thomson2000", "robertson2024")),
    "Syngnathidae":  ("No", "alta",  "Peces pipa y caballitos: nado débil, asociados a pastos marinos o gorgonias concretas.",
                      ("thomson2000", "robertson2024")),
    "Malacanthidae": ("No", "media", "Blanquillos: excavan y ocupan madrigueras en fondo blando.",
                      ("thomson2000", "robertson2024")),
    "Triglidae":     ("No", "media", "Rubios: bentónicos de plataforma, con movimientos costa-afuera y no migración estacional.",
                      ("robertson2024", "able2014")),
    "Sebastidae":    ("No", "media", "Rocotes: asociados a fondo duro y profundo, muy sedentarios y longevos.",
                      ("thomson2000", "robertson2024")),
    "Ariidae":       ("No", "media", "Bagres marinos: costeros y estuarinos, con incubación bucal; movimientos locales.",
                      ("thomson2000", "robertson2024")),
    "Gerreidae":     ("No", "media", "Mojarras: costeras de fondo blando y estuario, con movimientos mareales locales.",
                      ("thomson2000", "robertson2024")),
    "Atherinopsidae":("No", "media", "Pejerreyes: cardúmenes costeros con desplazamientos locales hacia playas de desove.",
                      ("thomson2000", "robertson2024")),
    "Sciaenidae":    ("No", "media", "Corvinas y berrugatas: demersales costeras y residentes. Ojo: Totoaba macdonaldi y Cynoscion othonopterus SÍ migran a desovar al delta y llevan regla propia de especie.",
                      ("thomson2000", "robertson2024")),
    # ── Peces planos ────────────────────────────────────────────────────
    "Paralichthyidae":("No", "media","Lenguados: bentónicos; se mueven costa-afuera con la profundidad y la talla, no entre zonas de forma estacional.",
                      ("able2014", "gibson1994")),
    "Cynoglossidae": ("No", "media", "Lenguas: bentónicas de fondo blando, sedentarias.",
                      ("able2014", "gibson1994")),
    "Bothidae":      ("No", "media", "Lenguados bóthidos: bentónicos de plataforma.",
                      ("able2014", "gibson1994")),
    "Pleuronectidae":("No", "media", "Platijas: bentónicas, con movimientos costa-afuera ligados a profundidad.",
                      ("able2014", "gibson1994")),
    "Achiridae":     ("No", "media", "Suelas: bentónicas de fondo blando somero y estuario.",
                      ("able2014", "gibson1994")),
    "Cyclopsettidae":("No", "media", "Lenguados cyclopséttidos: bentónicos de plataforma.",
                      ("able2014", "gibson1994")),
    # ── Profundidad: migradores verticales, no horizontales ─────────────
    "Macrouridae":   ("No", "baja",  "Granaderos: bentopelágicos profundos. Mismo problema que los mictófidos: el campo no distingue vertical de horizontal.",
                      ("sutton2013",)),
    "Gonostomatidae":("No", "baja",  "Peces cerdilla: migradores verticales diarios, sin migración horizontal estacional.",
                      ("sutton2013",)),
    "Phosichthyidae":("No", "baja",  "Migradores verticales diarios, sin migración horizontal estacional.",
                      ("sutton2013",)),
    "Melamphaidae":  ("No", "baja",  "Mesopelágicos profundos; migración vertical, no horizontal.",
                      ("sutton2013",)),
    "Paralepididae": ("No", "baja",  "Barracudinas: mesopelágicas, migradoras verticales.",
                      ("sutton2013",)),
    "Scopelarchidae":("No", "baja",  "Ojos de perla: mesopelágicos, migradores verticales.",
                      ("sutton2013",)),
    "Microstomatidae":("No", "baja", "Mesopelágicos; migración vertical, no horizontal.",
                      ("sutton2013",)),
    "Alepocephalidae":("No", "baja", "Peces cabeza resbalosa: batipelágicos, sin migración vertical marcada ni horizontal.",
                      ("sutton2013",)),
    "Linophrynidae": ("No", "baja",  "Rapes abisales: batipelágicos de nado débil.",
                      ("sutton2013",)),
    "Synodontidae":  ("No", "media", "Chiles: bentónicos emboscadores sobre fondo blando.",
                      ("thomson2000", "robertson2024")),
    # ── Aves: migrantes y residentes ────────────────────────────────────
    "Gaviidae":      ("Yes", "alta", "Colimbos: crían en latitudes altas e invernan en el Golfo.",
                      ("howell1995",)),
    "Podicipedidae": ("Yes", "media","Zambullidores: varias especies invernan en el Golfo; algunas poblaciones son residentes.",
                      ("howell1995",)),
    "Alcidae":       ("Yes", "media","Alcidos: dispersión invernal amplia hacia el sur; el Golfo es límite de invernada.",
                      ("howell1995",)),
    "Diomedeidae":   ("Yes", "alta", "Albatros: migrantes pelágicos de escala oceánica.",
                      ("howell1995",)),
    "Recurvirostridae":("Yes","media","Avocetas y candeleros: migrantes parciales; el Golfo es zona de invernada.",
                      ("howell1995", "gomezsapiens2013")),
    "Haematopodidae":("No", "media", "Ostreros: residentes costeros con movimientos locales.",
                      ("howell1995",)),
    "Threskiornithidae":("No","media","Ibis y espátulas: residentes en humedales del noroeste con dispersión local.",
                      ("howell1995",)),
    "Phaethontidae": ("No", "media", "Rabijuncos: dispersión pelágica alrededor de colonias, sin migración estacional definida.",
                      ("howell1995",)),
    "Ciconiidae":    ("No", "media", "Cigüeñas: residentes o dispersivas en el noroeste de México.",
                      ("howell1995",)),
    "Phoenicopteridae":("No","media","Flamencos: no reproductor regular en el Golfo; registro divagante — verificar la fila antes de aceptar.",
                      ("howell1995",)),
    "Anhingidae":    ("No", "media", "Anhingas: residentes de humedal con movimientos locales.",
                      ("howell1995",)),
    # ── Peces mesopelágicos ─────────────────────────────────────────────
    "Myctophidae":   ("No", "baja",  "Linternillas: realizan migración vertical diaria de cientos de metros, pero NO migración horizontal estacional. El campo es ambiguo para este taxón — decidir qué mide antes de aceptar.",
                      ("sutton2013",)),
    "Bathylagidae":  ("No", "baja",  "Igual que los mictófidos: migración vertical diaria, no horizontal.",
                      ("sutton2013",)),
    "Stomiidae":     ("No", "baja",  "Peces dragón: migradores verticales, sin migración horizontal estacional.",
                      ("sutton2013",)),
}

# ── Reglas por género ───────────────────────────────────────────────────
# Nivel intermedio, necesario donde la familia mezcla historias de vida
# opuestas: Laridae junta gaviotas residentes con charranes migrantes, y
# Carangidae junta jureles de arrecife con especies epipelágicas. Una regla
# de familia ahí no sería una simplificación, sería falsa.

GENUS_RULES = {
    # ── Laridae: gaviotas residentes vs. charranes migrantes ────────────
    "Sterna":        ("Yes", "alta",  "Charranes: migrantes de larga distancia; el Golfo es zona de cría o de paso.", ("howell1995",)),
    "Thalasseus":    ("Yes", "alta",  "Charranes crestados: migrantes, con colonias estacionales en el Golfo.", ("howell1995",)),
    "Sternula":      ("Yes", "alta",  "Charrancito: migrante de larga distancia.", ("howell1995",)),
    "Hydroprogne":   ("Yes", "media", "Charrán caspia: migrante parcial, inverna en el noroeste de México.", ("howell1995",)),
    "Gelochelidon":  ("Yes", "media", "Charrán picogrueso: migrante parcial.", ("howell1995",)),
    "Chlidonias":    ("Yes", "alta",  "Charranes negros: migrantes transcontinentales.", ("howell1995",)),
    "Onychoprion":   ("Yes", "alta",  "Charranes oscuros: pelágicos migrantes fuera de la temporada de cría.", ("howell1995",)),
    "Xema":          ("Yes", "alta",  "Gaviota de Sabine: migrante ártica de larga distancia.", ("howell1995",)),
    "Rissa":         ("Yes", "alta",  "Gaviota tridáctila: pelágica migrante, invernante rara en el Golfo.", ("howell1995",)),
    "Hydrocoloeus":  ("Yes", "alta",  "Gaviota mínima: migrante de larga distancia.", ("howell1995",)),
    "Chroicocephalus":("Yes","media", "Gaviota de Bonaparte y afines: migrantes invernantes.", ("howell1995",)),
    "Leucophaeus":   ("Yes", "media", "Gaviotas del género Leucophaeus: migrantes o dispersivas según especie; el Golfo es invernada.", ("howell1995",)),
    "Larus":         ("No",  "media", "Gaviotas Larus del Golfo: en su mayoría residentes o dispersivas. Excepción con regla propia: Larus heermanni.", ("howell1995", "bow_yefgul")),
    "Rynchops":      ("No",  "media", "Rayador americano: residente costero con dispersión local.", ("howell1995",)),
    "Anous":         ("No",  "media", "Tiñosas: residentes de colonias tropicales, forrajeo de gran radio sin migración estacional.", ("howell1995",)),
    # ── Carangidae: jureles costeros vs. epipelágicos ───────────────────
    "Caranx":        ("No",  "media", "Jureles: asociados a arrecife y costa, con ámbito de hogar amplio pero sin migración estacional entre zonas.", ("thomson2000", "robertson2024")),
    "Carangoides":   ("No",  "media", "Jureles costeros de arrecife.", ("thomson2000", "robertson2024")),
    "Gnathanodon":   ("No",  "media", "Jurel dorado: costero, asociado a fondos someros.", ("thomson2000", "robertson2024")),
    "Hemicaranx":    ("No",  "media", "Jureles costeros de fondo blando.", ("thomson2000", "robertson2024")),
    "Selene":        ("No",  "media", "Jorobados: costeros de plataforma y estuario.", ("thomson2000", "robertson2024")),
    "Oligoplites":   ("No",  "media", "Piguas: costeras, asociadas a manglar y estuario.", ("thomson2000", "robertson2024")),
    "Trachinotus":   ("No",  "media", "Pámpanos: costeros de zona de rompiente.", ("thomson2000", "robertson2024")),
    "Chloroscombrus":("No",  "media", "Casabe: costero de plataforma somera.", ("thomson2000", "robertson2024")),
    "Alectis":       ("No",  "baja",  "Jurel penacho: costero; historia de vida poco documentada en la región.", ("robertson2024",)),
    "Uraspis":       ("No",  "baja",  "Jurel de boca blanca: poco documentado regionalmente.", ("robertson2024",)),
    # ── Grandes pelágicos por género ────────────────────────────────────
    "Thunnus":       ("Yes", "alta",  "Atunes del género Thunnus: migradores oceánicos de largo alcance, documentados por marcaje archivador y satelital.", ("schaefer2007", "block2011")),
    "Katsuwonus":    ("Yes", "alta",  "Barrilete: epipelágico oceánico con desplazamientos estacionales de gran escala.", ("block2011",)),
    "Prionace":      ("Yes", "alta",  "Tiburón azul: pelágico oceánico con migración estacional, seguido por marcaje satelital.", ("block2011",)),
    "Sphyrna":       ("Yes", "media", "Cornudas: se desplazan entre montes submarinos y costa en el Golfo con patrón estacional.", ("klimley1993goc", "klimley1993mb")),
    # ── Mamíferos marinos por género ────────────────────────────────────
    "Eschrichtius":  ("Yes", "alta",  "Ballena gris: migración anual entre el Ártico y las lagunas de Baja California.", ("rice1971",)),
    "Zalophus":      ("No",  "media", "Lobo marino de California: colonias fijas en el Golfo, sin migración estacional.", ("aurioles1994",)),
    "Phocoena":      ("No",  "alta",  "Vaquita: endémica del Alto Golfo, sin migración.", ("rojasbracho2006",)),
    # ── Sciaenidae por género ───────────────────────────────────────────
    "Totoaba":       ("Yes", "alta",  "Totoaba: migración reproductiva anual al delta del Río Colorado.", ("cisnerosmata1995",)),
}

ORDER_RULES = {
    "Anguilliformes": ("No", "media", "Anguiliformes bentónicos del Golfo: residentes de madriguera o grieta.",
                       ("mccosker1977", "thomson2000")),
    "Gobiesociformes":("No", "alta",  "Peces piedra: adheridos al sustrato, sin desplazamiento.",
                       ("briggs1955", "thomson2000")),
}


# ── Control de congruencia taxonómica ───────────────────────────────────
# Antes de sugerir nada hay que poder confiar en la fila. Varias filas del
# CSV base traen una taxonomía que contradice de plano a su grupo funcional:
# un murciélago en «Benthic Grazers», una paloma en «Pelagic Bacteria». Son
# emparejamientos fallidos de la búsqueda, no especies del modelo. En esas
# filas se retiene la sugerencia —inferir IsMigratory sobre un taxón
# equivocado sólo propaga el error— y se emite una alerta para el revisor.

GROUP_EXPECTED_CLASS = {
    "Benthic Grazers": "invertebrado o pez",
    "Jellyfish": "invertebrado (Cnidaria)",
    "Pelagic Bacteria": "bacteria",
    "Loggerhead Turtle": "reptil (Testudines)",
    "Vaquita": "mamífero (Cetacea)",
    "California Sea Lion": "mamífero (Carnivora)",
    "Gray Whale": "mamífero (Cetacea)",
}

# Familias estrictamente dulceacuícolas: en un modelo del Golfo son señal de
# que la búsqueda emparejó un homónimo de agua dulce.
FRESHWATER_FAMILIES = {
    "Leuciscidae", "Cyprinidae", "Centrarchidae", "Percidae", "Cichlidae",
    "Acipenseridae", "Salmonidae",
}

# Géneros que no son animales: contaminación evidente del emparejamiento.
NON_ANIMAL_GENERA = {"Carex", "Cajanus"}


def anomalia(row) -> str | None:
    """Motivo por el que la fila no es fiable, o None si es congruente."""
    grp, cls = str(row.Group), str(row.Class)
    fam, gen, order = str(row.Family), str(row.Genus), str(row.Order)
    if gen in NON_ANIMAL_GENERA:
        return f"el género {gen} es una planta, no un animal marino"
    esperada = GROUP_EXPECTED_CLASS.get(grp)
    if esperada:
        ok = (("mamífero" in esperada and cls == "Mammalia")
              or ("reptil" in esperada and order == "Testudines")
              or ("invertebrado" in esperada and cls not in ("Mammalia", "Aves", "Teleostei",
                                                            "Actinopterygii", "Chondrichthyes"))
              or ("bacteria" in esperada and cls not in ("Mammalia", "Aves", "Teleostei",
                                                        "Actinopterygii", "Chondrichthyes")))
        if not ok:
            return (f"el grupo «{grp}» implica {esperada}, pero la fila trae "
                    f"{cls} / {order} / {fam}")
    if cls == "Aves" and "Seabird" not in grp and "Bird" not in grp:
        return f"ave ({fam}) asignada al grupo no aviar «{grp}»"
    if cls == "Mammalia" and grp not in ("Dolphins", "Toothed Whales", "Baleen Whales",
                                         "Migratory Baleen Whales", "Gray Whale", "Orcas",
                                         "Vaquita", "California Sea Lion", "Other Pinnipeds"):
        return f"mamífero ({fam}) asignado al grupo «{grp}»"
    if fam in FRESHWATER_FAMILIES:
        return f"{fam} es una familia dulceacuícola: probable homónimo de agua dulce"
    return None


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
    if anomalia(row):
        return None            # fila no fiable: no se infiere nada sobre ella
    sp = str(row.Species)
    if sp in SPECIES_RULES:
        v, c, r, cites = SPECIES_RULES[sp]
        return v, c, r, f"especie {sp}", cites
    gen = str(row.Genus).strip()
    if gen in GENUS_RULES:
        v, c, r, cites = GENUS_RULES[gen]
        return v, c, r, f"género {gen}", cites
    fam = str(row.Family).strip()
    if fam in FAMILY_RULES:
        v, c, r, cites = FAMILY_RULES[fam]
        return v, c, r, f"familia {fam}", cites
    order = str(row.Order).strip()
    if order in ORDER_RULES:
        v, c, r, cites = ORDER_RULES[order]
        return v, c, r, f"orden {order}", cites
    return None


def print_bibliografia() -> None:
    """Imprime la bibliografía y qué reglas se apoyan en cada entrada."""
    usos: dict[str, list[str]] = {}
    for d, etiqueta in ((SPECIES_RULES, "especie"), (GENUS_RULES, "género"),
                        (FAMILY_RULES, "familia"), (ORDER_RULES, "orden")):
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
    anomalias = []
    for row in base.itertuples():
        if row.Group not in groups:
            continue
        motivo = anomalia(row)
        if motivo:
            anomalias.append({
                "row": int(row.Index),
                "group": str(row.Group),
                "species": str(row.Species),
                "taxon": f"{row.Class} / {row.Order} / {row.Family}",
                "issue": motivo,
            })
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
        "anomalies": anomalias,
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
    if anomalias:
        print(f"\n   ⚠ {len(anomalias)} filas con taxonomía incongruente (sin sugerencia):")
        for a in anomalias[:12]:
            print(f"     fila {a['row']:4d}  {a['group'][:26]:28s} {a['issue'][:70]}")
        if len(anomalias) > 12:
            print(f"     … y {len(anomalias) - 12} más (ver 'anomalies' en el JSON)")
    sin_cita = [k for k, s in suggestions.items() if not s["citations"]]
    print(f"   citas:         {len(citas_usadas)} referencias distintas, "
          f"{len(sin_cita)} sugerencias sin cita")


if __name__ == "__main__":
    main()
