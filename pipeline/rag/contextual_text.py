"""
Contextualización de chunks para retrieval (embeddings + BM25).

Problema: un chunk en medio de un documento (ej. una tabla de parámetros)
puede no repetir el sujeto del paper (nombre de especie, tema) que se
estableció en el título/abstract — ese contexto no "viaja" hacia chunks
posteriores del mismo documento. Esto hace que compita en desventaja
contra chunks de OTROS papers que comparten vocabulario genérico
(ej. "growth", "mortality", "parameters") pero son irrelevantes.

Solución: anteponer al texto usado para BUSCAR (embeddings + BM25) un
encabezado corto con el inicio del primer chunk del paper (que
normalmente contiene título + parte del abstract). El texto MOSTRADO al
usuario/LLM (ChunkData.text) permanece intacto — solo cambia lo que se
usa para indexar/buscar.
"""

from typing import Any, Dict

CONTEXT_HEADER_CHARS = 250


def build_search_texts(metadata_store: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Construye, para cada chunk_id, el texto a usar en embeddings/BM25:
    "<contexto del documento> <texto original del chunk>".

    El contexto de cada paper es el inicio (primeros CONTEXT_HEADER_CHARS
    caracteres) de su chunk con chunk_index == 0 (normalmente título +
    abstract). Si un paper no tiene chunk_index == 0 identificable, el
    chunk usa su propio texto sin encabezado adicional.

    Returns:
        Dict chunk_id -> search_text.
    """
    # 1. Encontrar el chunk_index==0 de cada paper
    context_by_paper: Dict[str, str] = {}
    for rec in metadata_store.values():
        if rec.get("chunk_index") == 0:
            context_by_paper[rec["paper_id"]] = rec["text"][:CONTEXT_HEADER_CHARS].strip()

    # 2. Construir search_text por chunk
    search_texts: Dict[str, str] = {}
    for rec in metadata_store.values():
        paper_id = rec["paper_id"]
        text = rec["text"]
        context = context_by_paper.get(paper_id)

        if context and context not in text:
            search_texts[rec["chunk_id"]] = f"{context} {text}"
        else:
            # Es el propio chunk 0, o no se encontró contexto: sin cambios.
            search_texts[rec["chunk_id"]] = text

    return search_texts
