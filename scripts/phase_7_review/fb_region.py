#!/usr/bin/env python3
"""¿De dónde salió este número? Clasificación regional de los registros de FishBase.

POR QUÉ EXISTE
==============
FishBase agrega estudios de todo el mundo. Para un modelo del Golfo de
California, un K medido en el Mar del Norte y otro medido en Guaymas no valen
lo mismo, aunque la base los liste en la misma tabla. Este módulo lee la
procedencia de cada registro —su `Locality`, su código de país y el título de
su referencia primaria— y dice si el dato es de la región que se está
modelando.

Cuando lo es, el valor deja de ser «una mediana mundial que habrá que
comprobar» y pasa a ser evidencia local: el revisor puede aprobarlo como
validado sin ir al paper, porque la procedencia ya lo respalda.

TRES NIVELES, NO UNO
--------------------
Se distingue el Golfo de California del Pacífico mexicano y éste del Pacífico
oriental completo, porque no son la misma afirmación. Un t₀ del Golfo describe
el sistema modelado; uno de Perú describe una población del mismo océano bajo
otro régimen térmico. Los tres se aceptan como regionales, pero el tablero
enseña cuál es cuál y el aprobado automático se puede restringir al nivel que
el modelador considere suficiente.

LO QUE NO HACE
--------------
No lee el paper. Clasifica el texto de procedencia que FishBase registra, que
a veces está vacío o es genérico («Pacific coast»). Un registro sin región
detectada NO significa que no sea regional: significa que la base no lo dice.
Por eso la ausencia de región nunca descarta nada, sólo deja la celda como
estaba: pendiente de revisión humana.
"""
from __future__ import annotations

import re

# Los tres niveles, del más específico al más amplio. El orden importa: se
# devuelve el primero que casa, así «Guaymas, Gulf of California» es Golfo y no
# se queda en el genérico Pacífico oriental.
NIVELES = ("golfo_california", "pacifico_mexicano", "pacifico_oriental")

ETIQUETA = {
    "golfo_california": "Golfo de California",
    "pacifico_mexicano": "Pacífico mexicano",
    "pacifico_oriental": "Pacífico oriental",
}

# Marca visual corta para la tabla del tablero.
SIGLA = {"golfo_california": "GC", "pacifico_mexicano": "PM", "pacifico_oriental": "PO"}

_TERMINOS: dict[str, tuple[str, ...]] = {
    "golfo_california": (
        r"gulf of california", r"golfo de california", r"sea of cort[eé][sz]",
        r"mar de cort[eé][sz]", r"cortez sea", r"alto golfo", r"upper gulf",
        r"colorado river delta", r"delta del r[ií]o colorado", r"isla rasa",
        r"guaymas", r"mazatl[aá]n", r"topolobampo", r"yavaros", r"agiabampo",
        r"puerto pe[ñn]asco", r"san felipe", r"bah[ií]a de los [aá]ngeles",
        r"santa rosal[ií]a", r"loreto", r"la paz", r"bah[ií]a kino", r"altata",
        r"navachiste", r"sonora", r"sinaloa",
    ),
    "pacifico_mexicano": (
        r"mexican pacific", r"pac[ií]fico mexicano", r"pacific coast of mexico",
        r"west coast of mexico", r"aguas mexicanas del pac[ií]fico",
        r"baja california", r"nayarit", r"jalisco", r"colima", r"manzanillo",
        r"michoac[aá]n", r"guerrero", r"acapulco", r"oaxaca", r"salina cruz",
        r"huatulco", r"chiapas", r"puerto vallarta", r"tres mar[ií]as",
        r"revillagigedo", r"socorro island", r"bah[ií]a magdalena",
        r"magdalena bay", r"huizache", r"caimanero", r"teacap[aá]n",
        r"tehuantepec",
    ),
    "pacifico_oriental": (
        r"eastern pacific", r"east pacific", r"pac[ií]fico oriental",
        r"pac[ií]fico este", r"eastern tropical pacific", r"eastern central pacific",
        r"north-?east(ern)? pacific", r"ne pacific", r"south-?east(ern)? pacific",
        r"se pacific", r"california current", r"california bight", r"californian?",
        r"oregon", r"puget sound", r"british columbia", r"gulf of alaska",
        r"humboldt current", r"gal[aá]pagos", r"gulf of guayaquil", r"ecuador(ian)?",
        r"per[uú](vian)?", r"chile(an)?", r"colombian pacific", r"pacific coast of colombia",
        r"gulf of panama", r"golfo de panam[aá]", r"pacific coast of costa rica",
    ),
}

# Mares que comparten palabras con la región pero no son la región. «Gulf of
# Mexico» y «Campeche» son Atlántico; sin este filtro, cualquier búsqueda por
# «Mexico» los arrastraría dentro.
_VETO = (
    r"gulf of mexico", r"golfo de m[eé]xico", r"campeche", r"yucat[aá]n",
    r"veracruz", r"tamaulipas", r"tamiahua", r"caribbean", r"caribe",
    r"atlantic", r"atl[aá]ntico", r"quintana roo", r"florida", r"west indies",
    r"mediterranean", r"north sea", r"baltic",
)

# Aguas continentales: un dato de la presa del Infiernillo es mexicano pero no
# es del Pacífico. La palabra «laguna» no entra aquí a propósito —las lagunas
# costeras de Sinaloa y Nayarit sí son el sistema— y por eso se exige que el
# texto no traiga además una marca marina.
_CONTINENTAL = (r"lakes?", r"lagos?", r"dams?", r"presas?", r"reservoirs?",
                r"embalses?", r"aquarium", r"aquaria", r"ponds?", r"rivers?",
                r"r[ií]os?", r"freshwater")

_MARINO = (r"gulf", r"golfo", r"pacific", r"pac[ií]fico", r"coast\w*", r"costa\w*",
           r"lagoon", r"laguna", r"estuar\w*", r"bah[ií]a", r"bay", r"sea",
           r"marine", r"offshore", r"upwelling", r"delta", r"isla", r"island")

# Nombres de instituciones y revistas que contienen un topónimo sin hablar de
# él. «California Academy of Sciences» es dónde se publicó el trabajo, no dónde
# se midió nada: sin esto, una monografía mundial de anguilas quedaba
# clasificada como Pacífico oriental por su pie de imprenta.
_EDITORIAL = (
    r"california academy of sciences",
    r"universit(y|é|at|ies) of california[\w\s,]*",
    r"california state universit\w*",
    r"scripps institution\w*",
    r"gulf and caribbean research",
    r"gulf of mexico science",
    r"universit(y|ies) of texas press",
)
# CalCOFI queda fuera de esta lista a propósito: no es sólo un pie de imprenta,
# es un programa de muestreo de la corriente de California, y una referencia
# suya sí habla de dónde se midió.

def _rx(termino: str) -> re.Pattern:
    """Compila un término exigiendo palabra completa.

    Sin esto «kino» casaba dentro de «Loch Kinord» y «la paz» dentro de
    cualquier palabra que los contuviera: una localidad escocesa acababa
    clasificada como Golfo de California.
    """
    return re.compile(rf"(?<!\w)(?:{termino})(?!\w)", re.I)


_COMPILADO = {n: [_rx(t) for t in ts] for n, ts in _TERMINOS.items()}
_VETO_RX = [_rx(t) for t in _VETO]
_CONT_RX = [_rx(t) for t in _CONTINENTAL]
_MAR_RX = [_rx(t) for t in _MARINO]
_EDIT_RX = [_rx(t) for t in _EDITORIAL]

MX_CCODE = "484"          # México, en la codificación de países de FishBase


def _casa(rxs, txt: str) -> str | None:
    for rx in rxs:
        m = rx.search(txt)
        if m:
            return m.group(0)
    return None


def clasificar(*textos: str) -> tuple[str | None, str | None]:
    """Clasifica uno o más textos de procedencia.

    Devuelve `(nivel, fragmento)`: el nivel más específico que casa y el trozo
    de texto que lo justifica, para que el tablero pueda enseñar por qué se
    marcó. `(None, None)` si no hay señal regional.
    """
    txt = " · ".join(t for t in textos if isinstance(t, str) and t.strip())
    if not txt:
        return None, None
    for rx in _EDIT_RX:          # el pie de imprenta no es una localidad
        txt = rx.sub(" ", txt)
    # Continental sin ninguna marca marina: fuera, aunque el estado sea costero.
    if _casa(_CONT_RX, txt) and not _casa(_MAR_RX, txt):
        return None, None
    veto = _casa(_VETO_RX, txt)
    for nivel in NIVELES:
        frag = _casa(_COMPILADO[nivel], txt)
        if not frag:
            continue
        # Un texto que nombra las dos cuencas («Alaska to Peru including the
        # Gulf of California») sigue siendo regional: el veto sólo manda cuando
        # es lo único que hay. Pero si el veto es más específico que la señal
        # —«Gulf of Mexico» frente a un genérico «coast»— no se fuerza.
        if veto and nivel == "pacifico_oriental" and len(frag) <= len(veto) // 2:
            return None, None
        return nivel, frag
    return None, None


def clasificar_registro(locality, c_code, *refs: str) -> tuple[str | None, str | None, str]:
    """Clasifica un registro de FishBase: su localidad y sus referencias.

    Devuelve `(nivel, fragmento, de_dónde_salió)`. La localidad manda, porque
    describe dónde se midió; el título de la referencia primaria sólo entra si
    la localidad calla, y entonces la señal es más débil —el título habla del
    paper entero, no necesariamente del registro— así que el origen viaja con
    el resultado para que el tablero pueda decirlo.

    El código de país NO se usa como señal propia: `C_Code` = México cubre por
    igual el Golfo de California y el Golfo de México, que es Atlántico. Sin
    localidad, marcar México como Pacífico sería adivinar.
    """
    loc = locality if isinstance(locality, str) else ""
    nivel, frag = clasificar(loc)
    if nivel:
        return nivel, frag, "localidad"
    nivel, frag = clasificar(*refs)
    if nivel:
        return nivel, frag, "referencia"
    return None, None, ""


def mejor(niveles) -> str | None:
    """El nivel más específico de una colección de niveles."""
    presentes = {n for n in niveles if n}
    for n in NIVELES:
        if n in presentes:
            return n
    return None
