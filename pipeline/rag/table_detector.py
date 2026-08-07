"""
Heurístico para detectar chunks que son (o contienen mayormente) datos de
tabla, de forma retroactiva sobre chunks ya generados — no requiere
re-extraer ni re-chunkear PDFs.

Motivación: tablas de datos densas en números/nombres de especies (ej.
"Species X 10 2 29 4 5 4 9...") embeben semánticamente muy distinto a una
pregunta en lenguaje natural, aunque contengan la respuesta exacta. Un
canal de búsqueda restringido solo a estos chunks reduce drásticamente el
"ruido" de prosa y sube el ranking del chunk correcto (validado
empíricamente: rank 42/11730 en el corpus completo → rank 5/1040 dentro
del subconjunto filtrado, para la misma query).
"""

import re
from typing import Dict, Any

_NUMERIC_TOKEN = re.compile(r"\b\d+[.,]?\d*\b")
_TABLE_CAPTION = re.compile(r"^\s*(Table|Tabla)\s*\d", re.IGNORECASE)


def table_score(text: str) -> float:
    """
    Puntúa qué tan "tabla" se ve un chunk de texto.

    Combina densidad de dígitos, densidad de tokens numéricos, y si
    empieza con una leyenda tipo "Table N" / "Tabla N". No es un
    clasificador binario perfecto — es un filtro de recall alto para
    reducir el espacio de búsqueda antes de aplicar retrieval semántico
    o BM25 dentro del subconjunto resultante.
    """
    n = len(text)
    if n == 0:
        return 0.0

    digits = sum(c.isdigit() for c in text)
    digit_ratio = digits / n

    tokens = text.split()
    numeric_tokens = len(_NUMERIC_TOKEN.findall(text))
    numeric_token_ratio = numeric_tokens / len(tokens) if tokens else 0.0

    starts_with_caption = bool(_TABLE_CAPTION.match(text))

    return digit_ratio * 2 + numeric_token_ratio * 2 + (1.0 if starts_with_caption else 0.0)


def is_table_chunk(text: str, threshold: float = 1.0) -> bool:
    """True si el chunk supera el umbral de table_score."""
    return table_score(text) >= threshold


def filter_table_chunks(
    metadata_store: Dict[str, Dict[str, Any]], threshold: float = 1.0
) -> Dict[str, Dict[str, Any]]:
    """
    Filtra un metadata_store completo, devolviendo solo los registros que
    parecen chunks de tabla. Preserva las claves originales (faiss_id str).
    """
    return {
        key: rec
        for key, rec in metadata_store.items()
        if is_table_chunk(rec.get("text", ""), threshold=threshold)
    }
