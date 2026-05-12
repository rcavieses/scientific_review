"""
Extractor de entidades y relaciones desde chunks científicos usando LLM.

Usa un modelo ligero (claude-haiku o similar) para procesar cada chunk eficientemente.
Soporta múltiples proveedores de LLM via LLMProvider.
La salida es JSON estructurado que luego ingesta KnowledgeGraphStore.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from pipeline.llm import LLMProvider, get_llm_provider
from pipeline.rag.models import ChunkData


_SYSTEM_PROMPT = """\
You are a scientific information extraction assistant.
Extract named entities and relations from the provided scientific text fragment.
Output ONLY valid JSON — no explanation, no markdown fences, no extra text.

Entity types allowed: Species, Method, Location, Concept, Author, Paper
Relation types allowed: studies, found_in, interacts_with, measured_by, published_in, co_occurs_with

Return exactly this JSON schema:
{
  "entities": [
    {
      "name": "canonical English name",
      "type": "Species|Method|Location|Concept|Author|Paper",
      "aliases": ["alternative name 1", "alternative name 2"],
      "properties": {}
    }
  ],
  "relations": [
    {
      "subject": "entity name (must match a name in entities)",
      "relation": "one of the allowed relation types",
      "object": "entity name (must match a name in entities)",
      "confidence": 0.0,
      "context": "short quote ≤200 chars where this relation was found"
    }
  ]
}

Rules:
- Use canonical scientific names where applicable (e.g. "Lutjanus peru" not "L. peru")
- Only extract entities and relations EXPLICITLY present in the text
- subject and object in relations MUST exactly match a name field in entities
- If nothing found, return: {"entities": [], "relations": []}
- Do NOT invent or infer information not in the text
"""


class GraphExtractor:
    """
    Extrae entidades y relaciones de chunks científicos vía LLM.

    Soporta múltiples proveedores de LLM (Claude API, Ollama, etc.) via LLMProvider.

    Args:
        model: Modelo a usar (default: "claude-haiku-4-5-20251001" para eficiencia).
        max_tokens: Límite de tokens en la respuesta (default: 4096).
        request_delay: Segundos entre llamadas al LLM (default: 0.3).
        verbose: Mostrar progreso detallado.
        llm_provider: LLMProvider inyectable (default: None, usa Claude).
        client: (Deprecated) Cliente anthropic.Anthropic() inyectable.
                Mantener solo para backward compat con tests existentes.
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        max_tokens: int = 4096,
        request_delay: float = 0.3,
        verbose: bool = False,
        llm_provider: Optional[LLMProvider] = None,
        client=None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.request_delay = request_delay
        self.verbose = verbose
        self._llm_provider = llm_provider
        self._client = client

    # ── API pública ──────────────────────────────────────────────────────────

    def extract_from_chunk(self, chunk: ChunkData) -> Dict[str, Any]:
        """
        Llama al LLM una vez para extraer entidades y relaciones del chunk.

        Args:
            chunk: Chunk de texto científico.

        Returns:
            Dict con keys 'entities' y 'relations'.
            En caso de JSON inválido retorna {"entities": [], "relations": []}.

        Raises:
            RuntimeError: Si la llamada al LLM falla.
        """
        user_message = self._build_user_message(chunk)

        try:
            provider = self._get_llm_provider()
            raw_text = provider.generate(_SYSTEM_PROMPT, user_message, self.max_tokens).strip()
        except Exception as e:
            raise RuntimeError(f"Error al llamar al LLM: {e}") from e

        return self._parse_response(raw_text, chunk.chunk_id)

    def extract_from_chunks(
        self,
        chunks: List[ChunkData],
        show_progress: bool = False,
        skip_chunk_ids: Optional[set] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extrae entidades y relaciones de una lista de chunks.

        Args:
            chunks: Lista de ChunkData a procesar.
            show_progress: Mostrar barra de progreso textual.
            skip_chunk_ids: Conjunto de chunk_ids ya procesados (extracción incremental).

        Returns:
            Lista de dicts (uno por chunk procesado), con 'chunk_id' añadido al dict.
        """
        skip_chunk_ids = skip_chunk_ids or set()
        results: List[Dict[str, Any]] = []
        to_process = [c for c in chunks if c.chunk_id not in skip_chunk_ids]

        if show_progress:
            print(f"  Extrayendo entidades de {len(to_process)} chunks "
                  f"({len(chunks) - len(to_process)} ya procesados)...")

        for i, chunk in enumerate(to_process, 1):
            if show_progress:
                print(f"  [{i}/{len(to_process)}] {chunk.chunk_id}", end=" ... ", flush=True)

            extraction = self.extract_from_chunk(chunk)
            extraction["chunk_id"] = chunk.chunk_id
            extraction["paper_id"] = chunk.paper_id
            results.append(extraction)

            n_ent = len(extraction.get("entities", []))
            n_rel = len(extraction.get("relations", []))

            if show_progress:
                print(f"{n_ent} entidades, {n_rel} relaciones")

            # Respetar rate limits
            if i < len(to_process) and self.request_delay > 0:
                time.sleep(self.request_delay)

        return results

    # ── Construcción del mensaje ─────────────────────────────────────────────

    @staticmethod
    def _build_user_message(chunk: ChunkData) -> str:
        """Formatea el chunk como mensaje de usuario para Claude."""
        header_parts = []
        if chunk.title:
            header_parts.append(f"Paper: {chunk.title}")
        if chunk.year:
            header_parts.append(f"Year: {chunk.year}")
        if chunk.authors:
            authors_str = ", ".join(chunk.authors[:3])
            if len(chunk.authors) > 3:
                authors_str += " et al."
            header_parts.append(f"Authors: {authors_str}")
        header_parts.append(f"Page: {chunk.page_number}")

        header = "\n".join(header_parts)
        return f"{header}\n\nTEXT:\n{chunk.text}"

    # ── Parsing defensivo ────────────────────────────────────────────────────

    def _parse_response(self, raw_text: str, chunk_id: str) -> Dict[str, Any]:
        """
        Parsea el JSON de Claude con manejo defensivo.

        Si Claude devuelve JSON inválido (a veces envuelve en ```json...```),
        intenta limpiar antes de fallar. En caso de fallo retorna dict vacío.
        """
        # Limpiar posibles markdown fences
        text = raw_text
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("El JSON no es un objeto")
            result.setdefault("entities", [])
            result.setdefault("relations", [])
            return result
        except (json.JSONDecodeError, ValueError) as e:
            if self.verbose:
                print(f"    [parse_error] chunk={chunk_id}: {e}")
                print(f"    raw={raw_text[:200]}")
            return {"entities": [], "relations": []}

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
