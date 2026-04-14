"""
Motor de consultas GraphRAG: combina búsqueda vectorial (FAISS) + grafo de conocimiento.

Flujo por cada pregunta:
  1. Extrae candidatos de entidades de la pregunta (heurística de tokens capitalizados)
  2. KnowledgeGraphStore.search_entities()  → entidades relevantes
  3. get_neighborhood()                     → vecindad de cada entidad
  4. VectorDBManager.search()               → chunks semánticos relevantes
  5. _build_combined_context()              → grafo + fragmentos → prompt
  6. Claude API                             → respuesta con fuentes y relaciones
  7. GraphQueryResult                       → respuesta + metadatos
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pipeline.rag.models import RAGSearchResult
from pipeline.rag.vector_db import VectorDBManager
from .graph_store import KnowledgeGraphStore
from .models import GraphQueryResult, GraphSearchResult


_SYSTEM_PROMPT = """\
Eres un asistente científico especializado en revisión de literatura. \
Recibirás dos tipos de contexto: (1) un grafo de conocimiento con entidades y relaciones \
extraídas de papers científicos, y (2) fragmentos de texto de los propios papers. \
Responde la pregunta del usuario integrando AMBAS fuentes de información. \
Si la información no está en el contexto proporcionado, indícalo explícitamente. \
Cita las fuentes usando el formato [Autor et al., Año] al final de cada afirmación. \
Responde en el mismo idioma que la pregunta.\
"""


class GraphQueryEngine:
    """
    Motor de consultas que combina el grafo de conocimiento con búsqueda vectorial.

    Args:
        graph_store: KnowledgeGraphStore con el grafo ya cargado.
        vector_db: VectorDBManager con el índice FAISS ya cargado.
        embedding_generator: EmbeddingGenerator para vectorizar la pregunta.
        model: Modelo de Claude para la respuesta (default: claude-sonnet-4-6).
        top_k: Chunks FAISS a recuperar (default: 5).
        max_tokens: Límite de tokens en la respuesta (default: 1024).
        min_score: Score mínimo para chunks FAISS (default: 0.2).
        graph_hops: Profundidad de vecindad en el grafo (default: 1).
        max_graph_entities: Máximo de entidades del grafo en el contexto (default: 3).
        verbose: Debug detallado.
        client: Cliente anthropic.Anthropic() inyectable para tests.
    """

    def __init__(
        self,
        graph_store: KnowledgeGraphStore,
        vector_db: VectorDBManager,
        embedding_generator=None,
        model: str = "claude-sonnet-4-6",
        top_k: int = 5,
        max_tokens: int = 1024,
        min_score: float = 0.2,
        graph_hops: int = 1,
        max_graph_entities: int = 3,
        verbose: bool = False,
        client=None,
    ):
        self.graph_store = graph_store
        self.vector_db = vector_db
        self.model = model
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.min_score = min_score
        self.graph_hops = graph_hops
        self.max_graph_entities = max_graph_entities
        self.verbose = verbose

        self._embedding_generator = embedding_generator
        self._client = client

    # ── API pública ──────────────────────────────────────────────────────────

    def query(self, question: str) -> GraphQueryResult:
        """
        Consulta combinada: grafo + FAISS → Claude → GraphQueryResult.

        Args:
            question: Pregunta en lenguaje natural.

        Returns:
            GraphQueryResult con respuesta, fuentes vectoriales y entidades del grafo.

        Raises:
            ValueError: Si la pregunta está vacía o el índice FAISS está vacío.
            RuntimeError: Si la llamada a Claude API falla.
        """
        question = question.strip()
        if not question:
            raise ValueError("La pregunta no puede estar vacía.")

        stats = self.vector_db.get_stats()
        if stats.total_chunks == 0:
            raise ValueError("El índice FAISS está vacío. Indexa PDFs primero.")

        # 1. Búsqueda en el grafo (heurística de tokens capitalizados)
        graph_results = self._search_graph(question)
        if self.verbose:
            print(f"[graph_query] {len(graph_results)} entidades del grafo recuperadas")

        # 2. Búsqueda vectorial
        query_vector = self._get_embedding_generator().generate(question)
        vector_results: List[RAGSearchResult] = self.vector_db.search(
            query_vector, top_k=self.top_k
        )
        vector_results = [r for r in vector_results if r.score >= self.min_score]
        if self.verbose:
            print(f"[graph_query] {len(vector_results)} chunks recuperados de FAISS")

        # 3. Construir contexto combinado
        context = self._build_combined_context(graph_results, vector_results)

        # 4. Llamar a Claude
        answer = self._call_claude(question, context)

        return GraphQueryResult(
            question=question,
            answer=answer,
            sources=vector_results,
            graph_results=graph_results,
            chunks_used=len(vector_results),
            graph_entities_used=len(graph_results),
            model=self.model,
            timestamp=datetime.now(),
        )

    # ── Búsqueda en el grafo ─────────────────────────────────────────────────

    def _search_graph(self, question: str) -> List[GraphSearchResult]:
        """
        Extrae candidatos de la pregunta (tokens capitalizados + runs de palabras)
        y busca en el grafo. Sin API extra — es puramente heurístico.
        """
        stats = self.graph_store.get_stats()
        if stats.total_entities == 0:
            return []

        # Extraer frases candidatas: runs de palabras con al menos una mayúscula
        candidates: List[str] = []

        # Frases de 2-4 palabras con al menos una capitalizada
        tokens = question.split()
        for length in (4, 3, 2, 1):
            for i in range(len(tokens) - length + 1):
                phrase = " ".join(tokens[i:i + length])
                if any(w[0].isupper() for w in tokens[i:i + length] if w):
                    candidates.append(phrase)

        # Buscar entidades para cada candidato
        seen_ids: set = set()
        results: List[GraphSearchResult] = []

        for candidate in candidates:
            if len(results) >= self.max_graph_entities:
                break
            entities = self.graph_store.search_entities(candidate, top_k=1)
            for entity in entities:
                if entity.entity_id not in seen_ids:
                    seen_ids.add(entity.entity_id)
                    gr = self.graph_store.build_graph_search_result(
                        entity, hops=self.graph_hops
                    )
                    results.append(gr)

        return results[:self.max_graph_entities]

    # ── Construcción del contexto combinado ─────────────────────────────────

    def _build_combined_context(
        self,
        graph_results: List[GraphSearchResult],
        vector_results: List[RAGSearchResult],
    ) -> str:
        """
        Combina contexto del grafo + fragmentos FAISS en un único bloque para Claude.

        El grafo aparece primero para "primar" el razonamiento de Claude antes
        de los fragmentos de texto crudo.
        """
        parts: List[str] = []

        # Sección del grafo (si hay entidades)
        if graph_results:
            parts.append("## Grafo de conocimiento\n")
            for gr in graph_results:
                parts.append(gr.format_as_context())
            parts.append("")

        # Sección de fragmentos FAISS
        if vector_results:
            parts.append("## Fragmentos de papers científicos\n")
            for i, r in enumerate(vector_results, 1):
                authors_str = ", ".join(r.authors[:3]) if r.authors else "Autores desconocidos"
                if r.authors and len(r.authors) > 3:
                    authors_str += " et al."
                header = (
                    f"### Fragmento {i} "
                    f"[score={r.score:.3f}, p.{r.page_number}]\n"
                    f"**Fuente:** {r.title or r.paper_id} "
                    f"({r.year or 'N/A'}) — {authors_str}"
                )
                parts.append(f"{header}\n\n{r.text}\n")
        else:
            parts.append("No se encontraron fragmentos relevantes en el índice.")

        return "\n".join(parts)

    # ── Llamada a Claude ─────────────────────────────────────────────────────

    def _call_claude(self, question: str, context: str) -> str:
        """Envía el contexto + pregunta a Claude y retorna la respuesta."""
        user_message = f"{context}\n\n---\n\n**Pregunta:** {question}"

        try:
            client = self._get_client()
            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except Exception as e:
            raise RuntimeError(f"Error al llamar a Claude API: {e}") from e

    # ── Inicialización lazy ──────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ImportError("Instala el paquete 'anthropic': pip install anthropic") from e

            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                secrets_path = Path("secrets/anthropic-apikey")
                if secrets_path.exists():
                    api_key = secrets_path.read_text().strip()
            if not api_key:
                raise RuntimeError(
                    "No se encontró la API key de Anthropic. "
                    "Define ANTHROPIC_API_KEY o crea secrets/anthropic-apikey."
                )
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def _get_embedding_generator(self):
        if self._embedding_generator is None:
            from pipeline.embeddings.embedding_generator import get_embedding_generator
            self._embedding_generator = get_embedding_generator(
                provider="local", verbose=self.verbose
            )
        return self._embedding_generator
