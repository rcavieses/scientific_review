"""
Motor de consultas RAG híbrido: fusiona búsqueda semántica (FAISS) y
léxica (BM25) vía Reciprocal Rank Fusion (RRF).

La búsqueda semántica encuentra contenido relacionado por significado;
BM25 encuentra coincidencias léxicas exactas (nombres de especies,
números, términos técnicos) que el embedding puede no relacionar bien
con la pregunta — especialmente en tablas de datos densas en números,
donde el embedding de la tabla se parece poco a una pregunta en
lenguaje natural aunque sea la respuesta correcta.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from .bm25_index import BM25IndexManager
from .models import QueryResult, RAGSearchResult
from .query_engine import RAGQueryEngine
from .vector_db import VectorDBManager


class HybridRAGQueryEngine(RAGQueryEngine):
    """
    RAGQueryEngine que fusiona resultados semánticos y BM25 vía RRF.

    Reutiliza _build_context() y _call_llm() de RAGQueryEngine sin
    cambios; solo reemplaza la etapa de retrieval.

    Args adicionales respecto a RAGQueryEngine:
        bm25_index: BM25IndexManager ya cargado (ver build_bm25_index.py).
        metadata_store: dict completo de metadata_store.json, usado para
            resolver chunks que BM25 encuentra pero que no están en el
            top semántico (necesitamos su texto/metadatos completos).
        candidate_k: Cuántos candidatos pedir a CADA método antes de
            fusionar (default: 30). Debe ser >= top_k para que la fusión
            tenga margen real de encontrar cosas que el otro método no
            puso en su propio top_k.
        semantic_weight / keyword_weight: Pesos de cada señal en RRF.
        rrf_k: Constante de suavizado de RRF (60 es el valor estándar
            de la literatura: evita que el rank #1 domine totalmente).
    """

    def __init__(
        self,
        vector_db: VectorDBManager,
        bm25_index: BM25IndexManager,
        metadata_store: Dict[str, dict],
        embedding_generator=None,
        model: str = "claude-sonnet-4-6",
        top_k: int = 5,
        candidate_k: int = 30,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        rrf_k: int = 60,
        max_tokens: int = 1024,
        min_score: float = 0.0,
        verbose: bool = False,
        llm_provider=None,
        # ── Canal opcional de tablas ────────────────────────────────────
        table_vector_db: "VectorDBManager | None" = None,
        table_bm25_index: "BM25IndexManager | None" = None,
        table_candidate_k: int = 80,
        table_weight: float = 0.5,
        table_min_bm25_score: float = 5.0,
        table_reserved_slots: int = 2,
        table_reserved_min_bm25: float = 15.0,
    ):
        super().__init__(
            vector_db=vector_db,
            embedding_generator=embedding_generator,
            model=model,
            top_k=top_k,
            max_tokens=max_tokens,
            min_score=min_score,
            verbose=verbose,
            llm_provider=llm_provider,
        )
        self.bm25_index = bm25_index
        self.candidate_k = max(candidate_k, top_k)
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.rrf_k = rrf_k

        # chunk_id -> registro completo, para construir RAGSearchResult de
        # hits que BM25 encuentra pero que no vinieron en el top semántico.
        self._chunk_by_id = {rec["chunk_id"]: rec for rec in metadata_store.values()}

        # Canal de tablas: sub-índices restringidos a chunks que parecen
        # tablas de datos (ver table_detector.py). Si no se proveen,
        # el motor se comporta exactamente igual que sin este canal.
        self.table_vector_db = table_vector_db
        self.table_bm25_index = table_bm25_index
        self.table_candidate_k = table_candidate_k
        self.table_weight = table_weight
        self.table_min_bm25_score = table_min_bm25_score

        # Slots reservados: el/los mejor(es) candidato(s) del canal de
        # tablas se garantizan en el resultado final si su score BM25
        # (léxico, escala interpretable) supera este umbral de alta
        # confianza — sin competir contra chunks "generalistas" que
        # acumulan crédito de varios canales en el RRF ponderado, que
        # estructuralmente siempre les gana a un match fuerte en un solo
        # canal (ver hallazgo de la sesión: RRF ponderado por sí solo no
        # bastó para subir una tabla claramente relevante al top_k).
        self.table_reserved_slots = table_reserved_slots
        self.table_reserved_min_bm25 = table_reserved_min_bm25

    def query(self, question: str) -> QueryResult:
        question = question.strip()
        if not question:
            raise ValueError("La pregunta no puede estar vacía.")

        stats = self.vector_db.get_stats()
        if stats.total_chunks == 0:
            raise ValueError("El índice está vacío. Indexa PDFs primero.")

        # 1. Búsqueda semántica (FAISS)
        query_vector = self._get_embedding_generator().generate(question)
        semantic_results = self.vector_db.search(query_vector, top_k=self.candidate_k)

        # 2. Búsqueda léxica (BM25)
        bm25_results = self.bm25_index.search(question, top_k=self.candidate_k)

        # 3. Canal de tablas (opcional): mismo patrón, pero restringido al
        # sub-índice de chunks que parecen tabla, y con un piso de score
        # mínimo — sin esto, para preguntas SIN relación con tablas se
        # inyectaría igual "el mejor de los candidatos a tabla" aunque sea
        # un match débil, contaminando el contexto.
        table_ranked = self._search_table_channel(question, query_vector)
        table_chunk_ids = [cid for cid, _bm25_score in table_ranked]

        if self.verbose:
            print(
                f"[hybrid] semantic_candidates={len(semantic_results)} "
                f"bm25_candidates={len(bm25_results)} "
                f"table_candidates={len(table_chunk_ids)}"
            )

        # 4. Fusión RRF (participación normal en la competencia ponderada)
        fused = self._fuse(semantic_results, bm25_results, table_chunk_ids)
        fused = [r for r in fused if r.score >= self.min_score]
        fused_by_id = {r.chunk_id: r for r in fused}

        # 5. Slots reservados: un match de tabla con score BM25 muy alto
        # (alta confianza léxica) se garantiza en el resultado, sin tener
        # que ganar la competencia RRF contra chunks "generalistas" que
        # acumulan crédito de varios canales — eso estructuralmente
        # siempre favorece al generalista aunque el especialista de tabla
        # sea #1 en su propio canal (ver hallazgo empírico de hoy).
        reserved_ids = [
            cid for cid, bm25_score in table_ranked
            if bm25_score >= self.table_reserved_min_bm25 and cid in fused_by_id
        ][: self.table_reserved_slots]

        ordered_ids: List[str] = list(reserved_ids)
        for r in fused:
            if r.chunk_id not in ordered_ids:
                ordered_ids.append(r.chunk_id)
            if len(ordered_ids) >= self.top_k:
                break

        results = [fused_by_id[cid] for cid in ordered_ids[: self.top_k]]

        if self.verbose:
            print(
                f"[hybrid] reserved_table_slots={len(reserved_ids)} "
                f"fused_top_k={len(results)}"
            )

        # 6. Contexto + LLM (lógica heredada sin cambios)
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

    # ── Canal de tablas ──────────────────────────────────────────────────

    def _search_table_channel(self, question: str, query_vector) -> List[Tuple[str, float]]:
        """
        Busca en el sub-índice de tablas (si está configurado) y fusiona
        su propio semántico+BM25 internos por RRF (igual que el canal
        principal) antes de devolver una lista ordenada.

        La compuerta de relevancia usa principalmente BM25: su escala es
        interpretable (0 = sin términos en común; ~20-40 = solapamiento
        léxico real, calibrado empíricamente sobre este corpus). El score
        de similitud coseno del embedding, en cambio, se observó muy
        comprimido dentro del subíndice de tablas (~0.78-0.83 para casi
        cualquier query, relacionada o no) — un umbral fijo sobre esa
        escala no discrimina nada, por eso NO se usa como filtro
        principal, solo aporta señal de ranking una vez que BM25 ya
        confirmó relevancia léxica real.

        Returns:
            Lista de (chunk_id, bm25_score_crudo) ordenada por relevancia
            fusionada dentro del canal. El score BM25 crudo (no el RRF
            interno) se devuelve para poder decidir slots reservados en
            query() con un umbral de alta confianza interpretable.
        """
        if self.table_vector_db is None or self.table_bm25_index is None:
            return []

        table_stats = self.table_vector_db.get_stats()
        if table_stats.total_chunks == 0:
            return []

        bm25_hits = self.table_bm25_index.search(question, top_k=self.table_candidate_k)
        bm25_score_by_id = {cid: score for cid, score in bm25_hits if score >= self.table_min_bm25_score}
        bm25_ids = list(bm25_score_by_id.keys())

        if not bm25_ids:
            # Sin solapamiento léxico real con ningún chunk de tabla: no
            # hay evidencia de que esta pregunta tenga respuesta tabular.
            return []

        # Semántico se usa solo como RE-RANKER entre los que ya pasaron
        # la compuerta BM25 (intersección), no para introducir candidatos
        # nuevos sin ningún solapamiento léxico real con la pregunta.
        bm25_id_set = set(bm25_ids)
        sem_hits = self.table_vector_db.search(query_vector, top_k=self.table_candidate_k)
        sem_rank = {
            r.chunk_id: rank
            for rank, r in enumerate(sem_hits, start=1)
            if r.chunk_id in bm25_id_set
        }

        # RRF interno del canal (mismo rrf_k que la fusión externa, por
        # simplicidad; no es crítico que coincida exactamente).
        internal_scores: Dict[str, float] = {}
        for rank, chunk_id in enumerate(bm25_ids, start=1):
            internal_scores[chunk_id] = internal_scores.get(chunk_id, 0.0) + 1.0 / (self.rrf_k + rank)
        for chunk_id, rank in sem_rank.items():
            internal_scores[chunk_id] = internal_scores.get(chunk_id, 0.0) + 0.5 / (self.rrf_k + rank)

        ranked = sorted(internal_scores.items(), key=lambda x: x[1], reverse=True)
        return [(chunk_id, bm25_score_by_id[chunk_id]) for chunk_id, _score in ranked]

    # ── Fusión ───────────────────────────────────────────────────────────

    def _fuse(
        self,
        semantic_results: List[RAGSearchResult],
        bm25_results: List[Tuple[str, float]],
        table_chunk_ids: List[str] = (),
    ) -> List[RAGSearchResult]:
        """
        Fusiona las listas por Reciprocal Rank Fusion:

            score(chunk) = w_sem/(k+rank_sem) + w_kw/(k+rank_kw) + w_tbl/(k+rank_tbl)

        Un chunk que aparece en varias listas acumula varios términos; uno
        que solo aparece en una lista solo recibe ese término. Se usa el
        RANK (posición), no el score crudo de cada método — evita tener
        que normalizar escalas incompatibles entre sí (cosine similarity
        0-1, BM25 sin límite superior fijo, etc).
        """
        rrf_scores: Dict[str, float] = {}
        semantic_by_id: Dict[str, RAGSearchResult] = {}

        for rank, r in enumerate(semantic_results, start=1):
            rrf_scores[r.chunk_id] = (
                rrf_scores.get(r.chunk_id, 0.0) + self.semantic_weight / (self.rrf_k + rank)
            )
            semantic_by_id[r.chunk_id] = r

        for rank, (chunk_id, _bm25_score) in enumerate(bm25_results, start=1):
            rrf_scores[chunk_id] = (
                rrf_scores.get(chunk_id, 0.0) + self.keyword_weight / (self.rrf_k + rank)
            )

        for rank, chunk_id in enumerate(table_chunk_ids, start=1):
            rrf_scores[chunk_id] = (
                rrf_scores.get(chunk_id, 0.0) + self.table_weight / (self.rrf_k + rank)
            )

        ranked_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        fused: List[RAGSearchResult] = []
        for chunk_id, fused_score in ranked_ids:
            if chunk_id in semantic_by_id:
                base = semantic_by_id[chunk_id]
                fused.append(RAGSearchResult(
                    chunk_id=base.chunk_id,
                    paper_id=base.paper_id,
                    text=base.text,
                    score=fused_score,
                    page_number=base.page_number,
                    chunk_index=base.chunk_index,
                    source_pdf=base.source_pdf,
                    title=base.title,
                    authors=base.authors,
                    year=base.year,
                    doi=base.doi,
                ))
            else:
                rec = self._chunk_by_id.get(chunk_id)
                if not rec:
                    continue
                fused.append(RAGSearchResult(
                    chunk_id=rec["chunk_id"],
                    paper_id=rec["paper_id"],
                    text=rec["text"],
                    score=fused_score,
                    page_number=rec["page_number"],
                    chunk_index=rec["chunk_index"],
                    source_pdf=rec["source_pdf"],
                    title=rec.get("title"),
                    authors=rec.get("authors"),
                    year=rec.get("year"),
                    doi=rec.get("doi"),
                ))

        self._normalize_scores(fused)
        return fused

    @staticmethod
    def _normalize_scores(results: List[RAGSearchResult]) -> None:
        """
        Reescala los scores RRF (típicamente ~0.005-0.02) a un rango 0-1
        para que sigan siendo interpretables como "% de relevancia" en la
        UI, igual que los scores de similitud coseno puros. Es min-max
        dentro del propio batch: preserva el orden relativo, no pretende
        ser una probabilidad calibrada (el score crudo de RRF tampoco lo
        era el score coseno original en ese sentido).
        """
        if not results:
            return
        scores = [r.score for r in results]
        lo, hi = min(scores), max(scores)
        if hi <= lo:
            for r in results:
                r.score = 1.0
            return
        for r in results:
            r.score = (r.score - lo) / (hi - lo)
