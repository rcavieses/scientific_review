"""
RAG Query Engine: consulta semántica sobre el índice FAISS + respuesta vía LLM.

Flujo por cada pregunta:
  1. EmbeddingGenerator.generate()   → vector de la pregunta
  2. VectorDBManager.search(top_k)   → chunks más relevantes
  3. _build_context()                → contexto formateado para el prompt
  4. LLMProvider.generate()          → respuesta con fuentes citadas (Claude o Ollama)
  5. QueryResult                     → respuesta + metadatos de fuentes

Soporta múltiples proveedores de LLM via LLMProvider (Claude API, Ollama, etc.)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pipeline.llm import LLMProvider, get_llm_provider

from .models import RAGSearchResult, QueryResult
from .vector_db import VectorDBManager


# Prompt de sistema: instruye a Claude a responder SOLO desde el contexto
_SYSTEM_PROMPT = """\
Eres un asistente científico especializado en revisión de literatura. \
Responde la pregunta del usuario basándote ÚNICAMENTE en los fragmentos de papers científicos \
que se te proporcionan en el contexto. \
Si la información no está en los fragmentos, indícalo explícitamente en lugar de inventar datos. \
Cita siempre las fuentes usando el formato [Autor et al., Año] al final de cada afirmación relevante. \
Responde en el mismo idioma que la pregunta.\
"""


class RAGQueryEngine:
    """
    Motor de consultas RAG: recupera chunks relevantes y genera una respuesta usando LLM.

    Soporta múltiples proveedores de LLM (Claude API, Ollama, etc.) via LLMProvider.

    Args:
        vector_db: VectorDBManager con el índice FAISS ya cargado.
        embedding_generator: EmbeddingGenerator para vectorizar la pregunta.
        model: Modelo a usar (default: "claude-sonnet-4-6" para Claude).
        top_k: Número de chunks a recuperar de FAISS (default: 5).
        max_tokens: Límite de tokens en la respuesta (default: 1024).
        min_score: Similitud coseno mínima para incluir un chunk (default: 0.2).
        verbose: Mostrar información de depuración.
        llm_provider: LLMProvider inyectable (default: None, usa Claude).
        client: (Deprecated) Cliente anthropic.Anthropic() inyectable.
                Mantener solo para backward compat con tests existentes.
    """

    def __init__(
        self,
        vector_db: VectorDBManager,
        embedding_generator=None,
        model: str = "claude-sonnet-4-6",
        top_k: int = 5,
        max_tokens: int = 1024,
        min_score: float = 0.2,
        verbose: bool = False,
        llm_provider: Optional[LLMProvider] = None,
        client=None,
    ):
        self.vector_db = vector_db
        self.model = model
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.min_score = min_score
        self.verbose = verbose

        self._embedding_generator = embedding_generator
        self._llm_provider = llm_provider
        self._client = client  # Backward compat: si se pasa client, crea AnthropicProvider

    # ── API pública ──────────────────────────────────────────────────────────

    def query(self, question: str) -> QueryResult:
        """
        Realiza una consulta completa: embedding → FAISS → Claude → QueryResult.

        Args:
            question: Pregunta en lenguaje natural.

        Returns:
            QueryResult con la respuesta generada y los chunks/fuentes usados.

        Raises:
            ValueError: Si la pregunta está vacía o el índice no tiene chunks.
            RuntimeError: Si la llamada a Claude API falla.
        """
        question = question.strip()
        if not question:
            raise ValueError("La pregunta no puede estar vacía.")

        stats = self.vector_db.get_stats()
        if stats.total_chunks == 0:
            raise ValueError("El índice FAISS está vacío. Indexa PDFs primero con indexar.py.")

        # 1. Vectorizar la pregunta
        if self.verbose:
            print(f"[query_engine] Generando embedding para: '{question[:80]}...'")
        query_vector = self._get_embedding_generator().generate(question)

        # 2. Recuperar chunks relevantes
        results: List[RAGSearchResult] = self.vector_db.search(query_vector, top_k=self.top_k)

        # Filtrar por score mínimo
        results = [r for r in results if r.score >= self.min_score]

        if self.verbose:
            print(f"[query_engine] {len(results)} chunks recuperados (min_score={self.min_score})")

        # 3. Armar contexto
        context = self._build_context(results)

        # 4. Llamar al LLM
        if self.verbose:
            provider = self._get_llm_provider()
            print(f"[query_engine] Llamando a {provider.get_provider_name()} ({self.model}) con {len(results)} chunks...")
        answer = self._call_llm(question, context)

        return QueryResult(
            question=question,
            answer=answer,
            sources=results,
            chunks_used=len(results),
            model=self.model,
            timestamp=datetime.now(),
        )

    # ── Construcción del contexto ────────────────────────────────────────────

    def _build_context(self, results: List[RAGSearchResult]) -> str:
        """
        Formatea los chunks recuperados en un bloque de contexto para el prompt.

        Cada fragmento incluye su referencia (título, año, página) para que
        Claude pueda citarlo correctamente en la respuesta.
        """
        if not results:
            return "No se encontraron fragmentos relevantes en el índice."

        parts = ["## Fragmentos de papers científicos relevantes\n"]
        for i, r in enumerate(results, 1):
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

        return "\n".join(parts)

    # ── Llamada al LLM ──────────────────────────────────────────────────────

    def _call_llm(self, question: str, context: str) -> str:
        """
        Envía el contexto + pregunta al LLM y retorna la respuesta en texto plano.

        Raises:
            RuntimeError: Si el LLM retorna un error.
        """
        user_message = f"{context}\n\n---\n\n**Pregunta:** {question}"

        try:
            provider = self._get_llm_provider()
            return provider.generate(_SYSTEM_PROMPT, user_message, self.max_tokens)
        except Exception as e:
            raise RuntimeError(f"Error al llamar al LLM: {e}") from e

    # ── Inicialización lazy ──────────────────────────────────────────────────

    def _get_llm_provider(self) -> LLMProvider:
        """
        Retorna el proveedor de LLM, inicializándolo si es necesario.

        Si se pasó llm_provider en __init__, lo retorna.
        Si se pasó client en __init__, lo usa como AnthropicProvider (backward compat).
        Si no, crea un AnthropicProvider lazy con el modelo configurado.
        """
        if self._llm_provider is None:
            from pipeline.llm import AnthropicProvider
            self._llm_provider = AnthropicProvider(
                model=self.model,
                client=self._client,
                verbose=self.verbose
            )
        return self._llm_provider

    def _get_embedding_generator(self):
        """Retorna el EmbeddingGenerator, inicializándolo si es necesario."""
        if self._embedding_generator is None:
            from pipeline.embeddings.embedding_generator import get_embedding_generator
            self._embedding_generator = get_embedding_generator(provider="local", verbose=self.verbose)
        return self._embedding_generator
