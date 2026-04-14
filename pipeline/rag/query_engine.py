"""
RAG Query Engine: consulta semántica sobre el índice FAISS + respuesta vía Claude API.

Flujo por cada pregunta:
  1. EmbeddingGenerator.generate()   → vector de la pregunta
  2. VectorDBManager.search(top_k)   → chunks más relevantes
  3. _build_context()                → contexto formateado para el prompt
  4. Claude API (Messages)           → respuesta con fuentes citadas
  5. QueryResult                     → respuesta + metadatos de fuentes
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

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
    Motor de consultas RAG: recupera chunks relevantes y genera una respuesta usando Claude API.

    Args:
        vector_db: VectorDBManager con el índice FAISS ya cargado.
        embedding_generator: EmbeddingGenerator para vectorizar la pregunta.
        model: Modelo de Claude a usar (default: claude-sonnet-4-6).
        top_k: Número de chunks a recuperar de FAISS (default: 5).
        max_tokens: Límite de tokens en la respuesta de Claude (default: 1024).
        min_score: Similitud coseno mínima para incluir un chunk (default: 0.2).
        verbose: Mostrar información de depuración.
        client: Cliente anthropic.Anthropic() inyectable (útil para tests con mocks).
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
        client=None,
    ):
        self.vector_db = vector_db
        self.model = model
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.min_score = min_score
        self.verbose = verbose

        self._embedding_generator = embedding_generator
        self._client = client  # Se inicializa lazy en _get_client()

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

        # 4. Llamar a Claude
        if self.verbose:
            print(f"[query_engine] Llamando a {self.model} con {len(results)} chunks...")
        answer = self._call_claude(question, context)

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

    # ── Llamada a Claude API ─────────────────────────────────────────────────

    def _call_claude(self, question: str, context: str) -> str:
        """
        Envía el contexto + pregunta a Claude y retorna la respuesta en texto plano.

        Raises:
            RuntimeError: Si la API devuelve un error inesperado.
        """
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
        """
        Retorna el cliente Anthropic, inicializándolo si es necesario.

        Busca la API key en este orden:
          1. Variable de entorno ANTHROPIC_API_KEY
          2. Archivo secrets/anthropic-apikey (relativo al CWD)
        """
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ImportError(
                    "El paquete 'anthropic' no está instalado. "
                    "Instálalo con: pip install anthropic"
                ) from e

            import os
            from pathlib import Path

            api_key = os.environ.get("ANTHROPIC_API_KEY")

            if not api_key:
                secrets_path = Path("secrets/anthropic-apikey")
                if secrets_path.exists():
                    api_key = secrets_path.read_text().strip()

            if not api_key:
                raise RuntimeError(
                    "No se encontró la API key de Anthropic. "
                    "Define ANTHROPIC_API_KEY o crea el archivo secrets/anthropic-apikey."
                )

            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def _get_embedding_generator(self):
        """Retorna el EmbeddingGenerator, inicializándolo si es necesario."""
        if self._embedding_generator is None:
            from pipeline.embeddings.embedding_generator import get_embedding_generator
            self._embedding_generator = get_embedding_generator(provider="local", verbose=self.verbose)
        return self._embedding_generator
