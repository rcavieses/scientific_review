#!/usr/bin/env python3
"""Motor RAG que relega los chunks de bibliografía en la recuperación.

Problema medido sobre el índice de producción: el 32 % de las consultas por
especie arrastra al menos una lista de referencias al top-10. Esos chunks gastan
contexto y, peor, inducen al modelo a citar papers que no contienen el dato.

Estrategia — relegar, nunca descartar:
  1. se pide `top_k × overfetch` candidatos al índice,
  2. se apartan los etiquetados como `references` / `references_likely`
     (ver scripts/label_chunk_sections.py),
  3. se devuelven los mejores `top_k` del resto,
  4. si no alcanzan, se rellena con los apartados por orden de score.

Así el número de fragmentos que ve el LLM nunca baja: en el peor caso el
comportamiento es idéntico al motor original.

No modifica pipeline/rag/: extiende RAGQueryEngine por herencia.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from pipeline.rag.models import QueryResult, RAGSearchResult   # noqa: E402
from pipeline.rag.query_engine import RAGQueryEngine           # noqa: E402

logger = logging.getLogger(__name__)

DEMOTED_SECTIONS = frozenset({"references", "references_likely"})


def load_sections(index_dir: Path) -> dict:
    """Carga chunk_sections.json; si no existe, devuelve {} (sin efecto)."""
    path = Path(index_dir) / "chunk_sections.json"
    if not path.exists():
        logger.warning("Sin chunk_sections.json en %s: se recupera sin relegar. "
                       "Ejecuta: python3 scripts/label_chunk_sections.py", index_dir)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class SectionAwareRAGQueryEngine(RAGQueryEngine):
    """RAGQueryEngine que aparta las listas de referencias del contexto."""

    def __init__(self, *args, sections: Optional[dict] = None,
                 demote: Iterable[str] = DEMOTED_SECTIONS,
                 overfetch: float = 2.5, max_candidates: int = 40, **kwargs):
        super().__init__(*args, **kwargs)
        self.sections = sections or {}
        self.demote = frozenset(demote)
        self.overfetch = overfetch
        self.max_candidates = max_candidates
        self.last_demoted: List[RAGSearchResult] = []

    def section_of(self, chunk_id: str) -> str:
        return (self.sections.get(chunk_id) or {}).get("section", "body")

    def query(self, question: str) -> QueryResult:
        question = question.strip()
        if not question:
            raise ValueError("La pregunta no puede estar vacía.")
        if self.vector_db.get_stats().total_chunks == 0:
            raise ValueError("El índice FAISS está vacío.")

        query_vector = self._get_embedding_generator().generate(question)

        candidate_k = min(int(self.top_k * self.overfetch), self.max_candidates)
        candidates = self.vector_db.search(query_vector, top_k=candidate_k)
        candidates = [r for r in candidates if r.score >= self.min_score]

        keep, demoted = [], []
        for result in candidates:
            (demoted if self.section_of(result.chunk_id) in self.demote else keep).append(result)

        results = keep[: self.top_k]
        if len(results) < self.top_k:                      # nunca devolver menos que antes
            results += demoted[: self.top_k - len(results)]

        self.last_demoted = [d for d in demoted if d not in results]
        if self.last_demoted and self.verbose:
            logger.info("Relegados %d chunks de bibliografía", len(self.last_demoted))

        context = self._build_context(results)
        answer = self._call_llm(question, context)

        return QueryResult(
            question=question,
            answer=answer,
            sources=results,
            chunks_used=len(results),
            model=self.model,
            timestamp=datetime.now(),
        )
