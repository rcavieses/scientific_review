"""
Tests para RAGQueryEngine - Fase 4.

Todos los tests usan mocks: no requieren índice FAISS real ni API key de Anthropic.

Cubre:
  1. TestQueryResult         — serialización y formateo del modelo de datos
  2. TestRAGQueryEngineCore  — lógica de consulta, construcción de contexto, filtrado por score
  3. TestRAGQueryEngineEdge  — casos borde: pregunta vacía, índice vacío, fallo de API
  4. TestRAGQueryEngineCLI   — función _build_context con distintas configuraciones
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipeline.rag.models import RAGSearchResult, QueryResult, IndexStats
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager


# ── Helpers ───────────────────────────────────────────────────────────────────

DIM = 8


def make_search_result(
    paper_id: str = "paper_a",
    score: float = 0.85,
    page: int = 1,
    title: str = "Sample Marine Biology Paper",
    year: int = 2024,
    authors: list = None,
) -> RAGSearchResult:
    """Crea un RAGSearchResult de prueba."""
    return RAGSearchResult(
        chunk_id=f"{paper_id}_chunk_000",
        paper_id=paper_id,
        text=(
            "The study found that Lutjanus peru is predominantly distributed along "
            "rocky reef systems in the Gulf of California at depths between 10-80m."
        ),
        score=score,
        page_number=page,
        chunk_index=0,
        source_pdf=f"outputs/pdfs/{paper_id}.pdf",
        title=title,
        authors=authors or ["Smith, J.", "Doe, A.", "García, M."],
        year=year,
        doi="10.1234/example",
    )


def make_index_stats(total_chunks: int = 100) -> IndexStats:
    """Crea un IndexStats de prueba."""
    return IndexStats(
        total_chunks=total_chunks,
        total_papers=3,
        embedding_model="all-MiniLM-L6-v2",
        embedding_dimension=DIM,
        index_size_mb=0.5,
        index_path="outputs/rag_index",
        last_updated=datetime.now(),
    )


def make_mock_db(results=None, total_chunks: int = 100) -> MagicMock:
    """Crea un VectorDBManager mockeado con search() preconfigurado."""
    db = MagicMock(spec=VectorDBManager)
    db.get_stats.return_value = make_index_stats(total_chunks=total_chunks)
    db.search.return_value = results if results is not None else [make_search_result()]
    return db


def make_mock_embedding_generator(dim: int = DIM) -> MagicMock:
    """Crea un EmbeddingGenerator mockeado que devuelve un vector unitario."""
    gen = MagicMock()
    gen.generate.return_value = np.ones(dim, dtype=np.float32) / np.sqrt(dim)
    return gen


def make_mock_claude_client(response_text: str = "Respuesta de prueba.") -> MagicMock:
    """Crea un cliente anthropic.Anthropic mockeado."""
    client = MagicMock()
    message = MagicMock()
    message.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = message
    return client


# ── 1. TestQueryResult ────────────────────────────────────────────────────────

class TestQueryResult(unittest.TestCase):
    """Tests del modelo de datos QueryResult."""

    def setUp(self):
        self.sources = [
            make_search_result("paper_a", score=0.9, title="Paper A", year=2024),
            make_search_result("paper_b", score=0.75, title="Paper B", year=2022),
        ]
        self.result = QueryResult(
            question="¿Dónde vive el Lutjanus peru?",
            answer="El Lutjanus peru habita zonas rocosas del Golfo de California.",
            sources=self.sources,
            chunks_used=2,
            model="claude-sonnet-4-6",
        )

    def test_str_contains_question_and_answer(self):
        text = str(self.result)
        self.assertIn("¿Dónde vive el Lutjanus peru?", text)
        self.assertIn("Golfo de California", text)

    def test_format_sources_deduplicates_papers(self):
        # Dos chunks del mismo paper → una sola entrada en fuentes
        same_paper = [
            make_search_result("paper_a", score=0.9),
            make_search_result("paper_a", score=0.8),
        ]
        result = QueryResult(
            question="q", answer="a", sources=same_paper,
            chunks_used=2, model="m",
        )
        formatted = result.format_sources()
        # Solo una entrada para paper_a
        self.assertEqual(formatted.count("•"), 1)

    def test_format_sources_two_distinct_papers(self):
        formatted = self.result.format_sources()
        self.assertEqual(formatted.count("•"), 2)

    def test_format_sources_empty(self):
        result = QueryResult(
            question="q", answer="a", sources=[],
            chunks_used=0, model="m",
        )
        self.assertEqual(result.format_sources(), "Sin fuentes.")

    def test_format_sources_truncates_authors_at_two(self):
        # Autores truncados con "et al." cuando hay más de 2
        formatted = self.result.format_sources()
        self.assertIn("et al.", formatted)

    def test_timestamp_is_datetime(self):
        self.assertIsInstance(self.result.timestamp, datetime)


# ── 2. TestRAGQueryEngineCore ─────────────────────────────────────────────────

class TestRAGQueryEngineCore(unittest.TestCase):
    """Tests del flujo principal de RAGQueryEngine."""

    def setUp(self):
        self.results = [make_search_result(score=0.85)]
        self.db = make_mock_db(results=self.results)
        self.emb = make_mock_embedding_generator()
        self.claude = make_mock_claude_client("El Lutjanus peru habita aguas tropicales.")
        self.engine = RAGQueryEngine(
            vector_db=self.db,
            embedding_generator=self.emb,
            client=self.claude,
            top_k=5,
            min_score=0.2,
            model="claude-sonnet-4-6",
        )

    def test_query_returns_query_result(self):
        result = self.engine.query("¿Dónde vive el Lutjanus peru?")
        self.assertIsInstance(result, QueryResult)

    def test_query_calls_embedding_generator(self):
        self.engine.query("test question")
        self.emb.generate.assert_called_once_with("test question")

    def test_query_calls_vector_db_search(self):
        self.engine.query("test question")
        self.db.search.assert_called_once()
        call_args = self.db.search.call_args
        # Verifica top_k
        self.assertEqual(call_args[1]["top_k"], 5)

    def test_query_calls_claude_api(self):
        self.engine.query("test question")
        self.claude.messages.create.assert_called_once()

    def test_query_result_has_correct_answer(self):
        result = self.engine.query("¿Dónde vive?")
        self.assertEqual(result.answer, "El Lutjanus peru habita aguas tropicales.")

    def test_query_result_has_sources(self):
        result = self.engine.query("question")
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(result.sources[0].paper_id, "paper_a")

    def test_query_result_model_name(self):
        result = self.engine.query("question")
        self.assertEqual(result.model, "claude-sonnet-4-6")

    def test_query_strips_whitespace(self):
        result = self.engine.query("  question with spaces  ")
        self.emb.generate.assert_called_once_with("question with spaces")

    def test_claude_receives_system_prompt(self):
        self.engine.query("question")
        call_kwargs = self.claude.messages.create.call_args[1]
        self.assertIn("system", call_kwargs)
        self.assertIn("asistente científico", call_kwargs["system"])

    def test_claude_receives_context_in_user_message(self):
        self.engine.query("question")
        call_kwargs = self.claude.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        user_content = messages[0]["content"]
        # El contexto incluye el texto del chunk
        self.assertIn("Lutjanus peru", user_content)


# ── 3. TestRAGQueryEngineFiltering ───────────────────────────────────────────

class TestRAGQueryEngineFiltering(unittest.TestCase):
    """Tests del filtrado por score mínimo."""

    def _make_engine(self, results, min_score=0.5):
        db = make_mock_db(results=results)
        emb = make_mock_embedding_generator()
        claude = make_mock_claude_client("respuesta")
        return RAGQueryEngine(
            vector_db=db,
            embedding_generator=emb,
            client=claude,
            min_score=min_score,
        )

    def test_chunks_below_min_score_are_excluded(self):
        results = [
            make_search_result("paper_a", score=0.8),
            make_search_result("paper_b", score=0.3),  # bajo el umbral
        ]
        engine = self._make_engine(results, min_score=0.5)
        result = engine.query("question")
        self.assertEqual(result.chunks_used, 1)
        self.assertEqual(result.sources[0].paper_id, "paper_a")

    def test_all_chunks_pass_when_all_above_min_score(self):
        results = [
            make_search_result("paper_a", score=0.9),
            make_search_result("paper_b", score=0.7),
        ]
        engine = self._make_engine(results, min_score=0.5)
        result = engine.query("question")
        self.assertEqual(result.chunks_used, 2)

    def test_zero_chunks_when_all_below_min_score(self):
        results = [make_search_result(score=0.1)]
        engine = self._make_engine(results, min_score=0.5)
        result = engine.query("question")
        self.assertEqual(result.chunks_used, 0)
        self.assertEqual(result.sources, [])


# ── 4. TestRAGQueryEngineEdgeCases ───────────────────────────────────────────

class TestRAGQueryEngineEdgeCases(unittest.TestCase):
    """Tests de casos borde y manejo de errores."""

    def test_raises_on_empty_question(self):
        db = make_mock_db()
        engine = RAGQueryEngine(vector_db=db, client=MagicMock())
        with self.assertRaises(ValueError):
            engine.query("")

    def test_raises_on_whitespace_only_question(self):
        db = make_mock_db()
        engine = RAGQueryEngine(vector_db=db, client=MagicMock())
        with self.assertRaises(ValueError):
            engine.query("   ")

    def test_raises_when_index_is_empty(self):
        db = make_mock_db(total_chunks=0)
        engine = RAGQueryEngine(vector_db=db, client=MagicMock())
        with self.assertRaises(ValueError):
            engine.query("question")

    def test_raises_runtime_error_on_api_failure(self):
        db = make_mock_db()
        emb = make_mock_embedding_generator()
        claude = MagicMock()
        claude.messages.create.side_effect = Exception("API timeout")
        engine = RAGQueryEngine(
            vector_db=db, embedding_generator=emb, client=claude
        )
        with self.assertRaises(RuntimeError):
            engine.query("question")

    def test_context_with_no_results_shows_message(self):
        engine = RAGQueryEngine(vector_db=MagicMock(), client=MagicMock())
        context = engine._build_context([])
        self.assertIn("No se encontraron fragmentos", context)


# ── 5. TestBuildContext ───────────────────────────────────────────────────────

class TestBuildContext(unittest.TestCase):
    """Tests de _build_context: formato del contexto enviado a Claude."""

    def setUp(self):
        self.engine = RAGQueryEngine(
            vector_db=MagicMock(), client=MagicMock()
        )

    def test_context_contains_chunk_text(self):
        results = [make_search_result(score=0.9)]
        context = self.engine._build_context(results)
        self.assertIn("Lutjanus peru", context)

    def test_context_contains_score(self):
        results = [make_search_result(score=0.876)]
        context = self.engine._build_context(results)
        self.assertIn("0.876", context)

    def test_context_contains_page_number(self):
        results = [make_search_result(page=7)]
        context = self.engine._build_context(results)
        self.assertIn("p.7", context)

    def test_context_contains_title_and_year(self):
        results = [make_search_result(title="Deep Sea Fish", year=2021)]
        context = self.engine._build_context(results)
        self.assertIn("Deep Sea Fish", context)
        self.assertIn("2021", context)

    def test_context_numbers_fragments(self):
        results = [
            make_search_result("paper_a"),
            make_search_result("paper_b"),
        ]
        context = self.engine._build_context(results)
        self.assertIn("Fragmento 1", context)
        self.assertIn("Fragmento 2", context)

    def test_context_truncates_authors_at_three(self):
        r = make_search_result(authors=["A", "B", "C", "D", "E"])
        context = self.engine._build_context([r])
        self.assertIn("et al.", context)

    def test_context_handles_missing_title(self):
        r = make_search_result()
        r.title = None
        context = self.engine._build_context([r])
        # Usa paper_id como fallback
        self.assertIn("paper_a", context)

    def test_context_handles_missing_year(self):
        r = make_search_result()
        r.year = None
        context = self.engine._build_context([r])
        self.assertIn("N/A", context)


if __name__ == "__main__":
    unittest.main(verbosity=2)
