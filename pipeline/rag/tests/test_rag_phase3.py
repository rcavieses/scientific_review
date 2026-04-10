"""
Tests para el pipeline RAG - Fase 3.

Cubre el flujo completo:
  1. TextChunker          — división de texto en chunks con overlap
  2. PdfPlumberExtractor  — extracción de texto de PDFs (pdfplumber mocked)
  3. VectorDBManager      — índice FAISS, búsqueda semántica, persistencia
  4. RAGPipelineOrchestrator — orquestación completa (extractor + gen mocked)
  5. Integración          — Article objects (búsqueda) → embeddings → índice → búsqueda semántica
"""

import sys
import json
import tempfile
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipeline.rag.models import ChunkData, ChunkVector, IndexStats, RAGSearchResult
from pipeline.rag.text_chunker import TextChunker
from pipeline.rag.pdf_extractor import PdfPlumberExtractor, PDFExtractionError
from pipeline.rag.vector_db import VectorDBManager
from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from scientific_search.models import Article


# ── Helpers ───────────────────────────────────────────────────────────────────

DIM = 8  # Dimensión pequeña para tests rápidos y deterministas


def make_chunk(
    chunk_id: str = "paper_a_chunk_000",
    paper_id: str = "paper_a",
    text: str = "This is a sample chunk of scientific text about marine biology.",
    chunk_index: int = 0,
    page_number: int = 1,
    title: str = "Sample Paper",
) -> ChunkData:
    """Crea un ChunkData de prueba con valores por defecto razonables."""
    return ChunkData(
        chunk_id=chunk_id,
        paper_id=paper_id,
        text=text,
        chunk_index=chunk_index,
        page_number=page_number,
        char_start=0,
        char_end=len(text),
        total_chunks=1,
        source_pdf=f"outputs/pdfs/{paper_id}.pdf",
        title=title,
        authors=["Smith, J.", "Doe, A."],
        year=2024,
        doi="10.1234/example",
    )


def make_chunk_vector(
    chunk: ChunkData,
    vector: np.ndarray,
    model: str = "test-model",
) -> ChunkVector:
    return ChunkVector(chunk=chunk, vector=vector, embedding_model=model)


def make_mock_embedding_generator(dim: int = DIM) -> Mock:
    """Crea un EmbeddingGenerator mock con dimensión fija y vectores normalizados."""
    gen = Mock()
    gen.get_dimension.return_value = dim
    gen.get_model_name.return_value = "mock-model"

    def batch_generate(texts, batch_size=32, show_progress=False):
        n = len(texts)
        rng = np.random.default_rng(seed=42)
        vecs = rng.random((n, dim)).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    gen.batch_generate.side_effect = batch_generate
    gen.generate.side_effect = batch_generate
    return gen


def random_unit_vec(dim: int = DIM, seed: int = None) -> np.ndarray:
    rng = np.random.default_rng(seed=seed)
    v = rng.random(dim).astype(np.float32)
    return v / np.linalg.norm(v)


# ── TestTextChunker ────────────────────────────────────────────────────────────

class TestTextChunker(unittest.TestCase):
    """Tests unitarios para TextChunker."""

    def setUp(self):
        self.chunker = TextChunker(chunk_size=200, overlap=40, min_chunk_size=20)

    # -- Comportamiento básico --

    def test_chunk_basic_generates_chunks(self):
        """Texto suficientemente largo genera al menos un chunk."""
        text = "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 20
        chunks = self.chunker.chunk_text(text, "paper_a", "paper_a.pdf")
        self.assertGreater(len(chunks), 0)

    def test_chunk_returns_chunk_data_instances(self):
        """Cada elemento de la lista es una instancia de ChunkData."""
        text = "Scientific text about fish species. " * 15
        chunks = self.chunker.chunk_text(text, "paper_a", "paper_a.pdf")
        for c in chunks:
            self.assertIsInstance(c, ChunkData)

    def test_chunk_ids_are_unique(self):
        """Todos los chunk_id son únicos dentro del mismo paper."""
        text = "Sentence with content about marine biology. " * 30
        chunks = self.chunker.chunk_text(text, "paper_a", "paper_a.pdf")
        ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_chunk_id_format(self):
        """chunk_id sigue el formato '{paper_id}_chunk_{index:03d}'."""
        text = "Sample scientific text for testing chunk id format. " * 10
        chunks = self.chunker.chunk_text(text, "my_paper", "my_paper.pdf")
        for i, c in enumerate(chunks):
            self.assertEqual(c.chunk_id, f"my_paper_chunk_{i:03d}")

    # -- Metadatos propagados --

    def test_paper_id_propagated_to_all_chunks(self):
        """paper_id se propaga correctamente a todos los chunks."""
        text = "Scientific content about ocean currents. " * 20
        chunks = self.chunker.chunk_text(text, "test_paper", "test.pdf")
        for c in chunks:
            self.assertEqual(c.paper_id, "test_paper")

    def test_source_pdf_propagated_to_all_chunks(self):
        """source_pdf se propaga correctamente a todos los chunks."""
        text = "Content for source pdf propagation test. " * 20
        chunks = self.chunker.chunk_text(text, "p", "outputs/papers/p.pdf")
        for c in chunks:
            self.assertEqual(c.source_pdf, "outputs/papers/p.pdf")

    def test_total_chunks_consistent(self):
        """total_chunks es igual en todos los chunks y coincide con len(chunks)."""
        text = "Chunk text for total consistency test. " * 30
        chunks = self.chunker.chunk_text(text, "paper_a", "paper_a.pdf")
        totals = {c.total_chunks for c in chunks}
        self.assertEqual(len(totals), 1, "total_chunks debe ser el mismo en todos los chunks")
        self.assertEqual(list(totals)[0], len(chunks))

    # -- Casos límite --

    def test_empty_text_returns_empty_list(self):
        """Texto vacío devuelve lista vacía."""
        chunks = self.chunker.chunk_text("", "paper_a", "paper_a.pdf")
        self.assertEqual(chunks, [])

    def test_text_below_min_chunk_size_returns_empty(self):
        """Texto más corto que min_chunk_size devuelve lista vacía."""
        chunker = TextChunker(chunk_size=200, overlap=40, min_chunk_size=100)
        chunks = chunker.chunk_text("Short.", "paper_a", "paper_a.pdf")
        self.assertEqual(chunks, [])

    def test_overlap_equal_to_chunk_size_raises(self):
        """overlap >= chunk_size lanza ValueError."""
        with self.assertRaises(ValueError):
            TextChunker(chunk_size=100, overlap=100)

    def test_overlap_greater_than_chunk_size_raises(self):
        """overlap > chunk_size también lanza ValueError."""
        with self.assertRaises(ValueError):
            TextChunker(chunk_size=100, overlap=150)

    # -- chunk_size respetado --

    def test_chunks_do_not_exceed_chunk_size_plus_margin(self):
        """Ningún chunk excede chunk_size + overlap (margen de búsqueda de límite)."""
        chunk_size = 200
        chunker = TextChunker(chunk_size=chunk_size, overlap=40, min_chunk_size=20)
        text = "Word number something interesting. " * 200
        chunks = chunker.chunk_text(text, "p", "p.pdf")
        margin = chunk_size + 40
        for c in chunks:
            self.assertLessEqual(
                len(c.text), margin,
                f"Chunk demasiado largo: {len(c.text)} > {margin}",
            )

    # -- chunk_pages --

    def test_chunk_pages_assigns_page_numbers(self):
        """chunk_pages asigna page_number >= 1 cuando hay page_map."""
        pages = [
            (1, "Page one has some scientific content about species. " * 10),
            (2, "Page two continues the analysis of population data. " * 10),
        ]
        chunker = TextChunker(chunk_size=150, overlap=30, min_chunk_size=20)
        chunks = chunker.chunk_pages(pages, "paper_b", "paper_b.pdf")
        self.assertTrue(len(chunks) > 0)
        for c in chunks:
            self.assertGreaterEqual(c.page_number, 1)

    def test_chunk_pages_empty_returns_empty(self):
        """Lista de páginas vacía devuelve lista vacía."""
        chunks = self.chunker.chunk_pages([], "paper_a", "paper_a.pdf")
        self.assertEqual(chunks, [])

    # -- get_stats --

    def test_get_stats_returns_expected_keys(self):
        """get_stats retorna diccionario con claves esperadas."""
        text = "Content for statistics test. " * 30
        chunks = self.chunker.chunk_text(text, "p", "p.pdf")
        stats = self.chunker.get_stats(chunks)
        self.assertEqual(stats["total"], len(chunks))
        for key in ("chars_min", "chars_max", "chars_avg", "chars_total"):
            self.assertIn(key, stats)

    def test_get_stats_empty_list(self):
        """get_stats con lista vacía devuelve total=0."""
        stats = self.chunker.get_stats([])
        self.assertEqual(stats["total"], 0)


# ── TestPdfPlumberExtractor ────────────────────────────────────────────────────

class TestPdfPlumberExtractor(unittest.TestCase):
    """Tests para PdfPlumberExtractor con pdfplumber mocked."""

    def _make_mock_page(self, text: str, page_num: int) -> Mock:
        page = Mock()
        page.page_number = page_num
        page.extract_text.return_value = text
        return page

    def _make_mock_pdf_ctx(self, pages_text: list) -> Mock:
        """Context manager mock que simula pdfplumber.open()."""
        mock_pages = [
            self._make_mock_page(text, i + 1)
            for i, text in enumerate(pages_text)
        ]
        mock_pdf = Mock()
        mock_pdf.pages = mock_pages
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)
        return mock_pdf

    # -- Extracción básica --

    def test_extract_by_pages_returns_correct_page_numbers(self):
        """Devuelve tuplas (page_num, text) con numeración 1-based."""
        extractor = PdfPlumberExtractor(min_page_chars=10)
        pages_text = ["Page one content enough.", "Page two content enough."]

        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value = self._make_mock_pdf_ctx(pages_text)
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                result = extractor.extract_by_pages(Path(tmp.name))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], 1)
        self.assertEqual(result[1][0], 2)

    def test_extract_by_pages_text_content_preserved(self):
        """El texto extraído contiene el contenido de las páginas."""
        extractor = PdfPlumberExtractor(min_page_chars=5)
        pages_text = ["Scientific findings here.", "More analysis data."]

        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value = self._make_mock_pdf_ctx(pages_text)
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                result = extractor.extract_by_pages(Path(tmp.name))

        self.assertIn("Scientific", result[0][1])
        self.assertIn("analysis", result[1][1])

    def test_short_pages_filtered_out(self):
        """Páginas con menos de min_page_chars caracteres se descartan."""
        extractor = PdfPlumberExtractor(min_page_chars=50)
        pages_text = [
            "Short.",  # descartada
            "This page has more than fifty characters of valid scientific content here.",
        ]

        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value = self._make_mock_pdf_ctx(pages_text)
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                result = extractor.extract_by_pages(Path(tmp.name))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 2)

    # -- Errores --

    def test_raises_file_not_found(self):
        """FileNotFoundError si el PDF no existe."""
        extractor = PdfPlumberExtractor()
        with self.assertRaises(FileNotFoundError):
            extractor.extract_by_pages(Path("/nonexistent/path/file.pdf"))

    def test_raises_pdf_extraction_error_on_corrupt(self):
        """PDFExtractionError si pdfplumber lanza excepción interna."""
        extractor = PdfPlumberExtractor()
        with patch("pdfplumber.open", side_effect=Exception("corrupted pdf")):
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                with self.assertRaises(PDFExtractionError):
                    extractor.extract_by_pages(Path(tmp.name))

    def test_raises_if_no_valid_pages(self):
        """PDFExtractionError si todas las páginas tienen menos de min_page_chars."""
        extractor = PdfPlumberExtractor(min_page_chars=1000)
        pages_text = ["Too short."]

        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value = self._make_mock_pdf_ctx(pages_text)
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                with self.assertRaises(PDFExtractionError):
                    extractor.extract_by_pages(Path(tmp.name))

    # -- Limpieza de texto --

    def test_clean_text_joins_hyphenated_words(self):
        """Palabras cortadas con guión al final de línea se unen."""
        extractor = PdfPlumberExtractor()
        text = "This is a hy-\nphen test for word joining."
        result = extractor._clean_extracted_text(text)
        self.assertIn("hyphen", result)
        self.assertNotIn("hy-\n", result)

    def test_clean_text_collapses_multiple_spaces(self):
        """Espacios múltiples se colapsan a uno solo."""
        extractor = PdfPlumberExtractor()
        text = "Word  with   multiple    spaces."
        result = extractor._clean_extracted_text(text)
        self.assertNotIn("  ", result)

    def test_extract_full_text_concatenates_pages(self):
        """extract() concatena texto de todas las páginas."""
        extractor = PdfPlumberExtractor(min_page_chars=5)
        pages_text = ["Page one content.", "Page two content."]

        with patch("pdfplumber.open") as mock_open:
            mock_open.return_value = self._make_mock_pdf_ctx(pages_text)
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                result = extractor.extract(Path(tmp.name))

        self.assertIn("Page one", result)
        self.assertIn("Page two", result)


# ── TestVectorDBManager ────────────────────────────────────────────────────────

class TestVectorDBManager(unittest.TestCase):
    """Tests para VectorDBManager con índice FAISS en tempdir."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.index_dir = Path(self.tmp_dir.name) / "rag_index"
        self.dim = DIM
        self.db = VectorDBManager(index_dir=self.index_dir, embedding_dim=self.dim)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _unit_vec(self, direction: int) -> np.ndarray:
        """Vector unitario en la dirección indicada (0-based)."""
        v = np.zeros(self.dim, dtype=np.float32)
        v[direction] = 1.0
        return v

    def _make_chunk_vectors(self, n: int, paper_id: str = "paper_a") -> list:
        result = []
        for i in range(n):
            chunk = make_chunk(
                chunk_id=f"{paper_id}_chunk_{i:03d}",
                paper_id=paper_id,
                chunk_index=i,
            )
            vec = random_unit_vec(self.dim, seed=i)
            result.append(make_chunk_vector(chunk, vec))
        return result

    # -- add_chunks --

    def test_add_chunks_returns_count(self):
        """add_chunks devuelve el número de chunks agregados."""
        cvs = self._make_chunk_vectors(5)
        count = self.db.add_chunks(cvs)
        self.assertEqual(count, 5)

    def test_add_chunks_updates_faiss_index(self):
        """El total del índice FAISS crece con cada inserción."""
        self.db.add_chunks(self._make_chunk_vectors(3))
        self.assertEqual(self.db._index.ntotal, 3)
        self.db.add_chunks(self._make_chunk_vectors(2, "paper_b"))
        self.assertEqual(self.db._index.ntotal, 5)

    def test_add_chunks_assigns_faiss_ids_sequentially(self):
        """add_chunks asigna faiss_id secuenciales a cada ChunkVector."""
        cvs = self._make_chunk_vectors(3)
        self.db.add_chunks(cvs)
        for i, cv in enumerate(cvs):
            self.assertEqual(cv.faiss_id, i)

    def test_add_chunks_empty_list_returns_zero(self):
        """add_chunks con lista vacía devuelve 0 sin modificar el índice."""
        count = self.db.add_chunks([])
        self.assertEqual(count, 0)
        self.assertEqual(self.db._index.ntotal, 0)

    # -- search --

    def test_search_returns_rag_search_results(self):
        """search devuelve instancias de RAGSearchResult."""
        self.db.add_chunks(self._make_chunk_vectors(5))
        results = self.db.search(random_unit_vec(self.dim, seed=99), top_k=3)
        for r in results:
            self.assertIsInstance(r, RAGSearchResult)

    def test_search_score_range(self):
        """Scores están en el rango [0, 1]."""
        self.db.add_chunks(self._make_chunk_vectors(5))
        results = self.db.search(random_unit_vec(self.dim, seed=99), top_k=5)
        for r in results:
            self.assertGreaterEqual(r.score, 0.0)
            self.assertLessEqual(r.score, 1.0)

    def test_search_results_ordered_descending(self):
        """Resultados ordenados de mayor a menor score."""
        self.db.add_chunks(self._make_chunk_vectors(5))
        results = self.db.search(random_unit_vec(self.dim, seed=99), top_k=5)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_search_respects_top_k(self):
        """search devuelve como máximo top_k resultados."""
        self.db.add_chunks(self._make_chunk_vectors(10))
        results = self.db.search(random_unit_vec(self.dim, seed=1), top_k=3)
        self.assertLessEqual(len(results), 3)

    def test_search_empty_index_returns_empty_list(self):
        """search en índice vacío devuelve lista vacía."""
        results = self.db.search(random_unit_vec(self.dim, seed=0), top_k=5)
        self.assertEqual(results, [])

    def test_search_exact_match_scores_highest(self):
        """Un query idéntico al vector indexado obtiene el score más alto."""
        target = self._unit_vec(0)  # [1, 0, 0, 0, ...]
        chunk = make_chunk(chunk_id="target_chunk_000", paper_id="target")
        self.db.add_chunks([make_chunk_vector(chunk, target)])

        # Agregar vectores ortogonales
        for i in range(1, min(self.dim, 4)):
            other = self._unit_vec(i)
            c = make_chunk(chunk_id=f"other_chunk_{i:03d}", paper_id=f"other_{i}", chunk_index=i)
            self.db.add_chunks([make_chunk_vector(c, other)])

        results = self.db.search(target, top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, "target_chunk_000")
        self.assertGreater(results[0].score, 0.95)

    # -- is_paper_indexed / get_papers_indexed --

    def test_is_paper_indexed_true(self):
        """is_paper_indexed retorna True para un paper indexado."""
        self.db.add_chunks(self._make_chunk_vectors(2, "indexed_paper"))
        self.assertTrue(self.db.is_paper_indexed("indexed_paper"))

    def test_is_paper_indexed_false(self):
        """is_paper_indexed retorna False para un paper no indexado."""
        self.assertFalse(self.db.is_paper_indexed("unknown_paper"))

    def test_get_papers_indexed_returns_unique_ids(self):
        """get_papers_indexed lista los paper_ids únicos."""
        self.db.add_chunks(self._make_chunk_vectors(2, "paper_a"))
        self.db.add_chunks(self._make_chunk_vectors(3, "paper_b"))
        papers = self.db.get_papers_indexed()
        self.assertEqual(sorted(papers), ["paper_a", "paper_b"])

    # -- save / load --

    def test_save_creates_expected_files(self):
        """save() crea index.faiss, metadata_store.json y index_config.json."""
        self.db.add_chunks(self._make_chunk_vectors(2))
        self.db.save()
        self.assertTrue((self.index_dir / "index.faiss").exists())
        self.assertTrue((self.index_dir / "metadata_store.json").exists())
        self.assertTrue((self.index_dir / "index_config.json").exists())

    def test_save_load_roundtrip_preserves_chunks(self):
        """Guardar y cargar en nueva instancia preserva todos los chunks."""
        self.db.add_chunks(self._make_chunk_vectors(4))
        self.db.save()

        db2 = VectorDBManager(index_dir=self.index_dir, embedding_dim=self.dim)
        loaded = db2.load()
        self.assertTrue(loaded)
        self.assertEqual(db2._index.ntotal, 4)
        self.assertEqual(len(db2._metadata), 4)

    def test_load_returns_false_without_saved_index(self):
        """load() retorna False si no hay índice guardado en disco."""
        self.assertFalse(self.db.load())

    # -- get_stats --

    def test_get_stats_returns_index_stats(self):
        """get_stats retorna IndexStats con valores correctos."""
        self.db.add_chunks(self._make_chunk_vectors(3))
        self.db.save()
        stats = self.db.get_stats()
        self.assertIsInstance(stats, IndexStats)
        self.assertEqual(stats.total_chunks, 3)
        self.assertEqual(stats.embedding_dimension, self.dim)

    # -- delete_paper --

    def test_delete_paper_removes_chunks(self):
        """delete_paper elimina exactamente los chunks del paper indicado."""
        self.db.add_chunks(self._make_chunk_vectors(3, "paper_a"))
        self.db.add_chunks(self._make_chunk_vectors(2, "paper_b"))
        deleted = self.db.delete_paper("paper_a")
        self.assertEqual(deleted, 3)
        self.assertFalse(self.db.is_paper_indexed("paper_a"))
        self.assertTrue(self.db.is_paper_indexed("paper_b"))
        self.assertEqual(self.db._index.ntotal, 2)

    def test_delete_paper_not_found_returns_zero(self):
        """delete_paper retorna 0 si el paper no existe."""
        deleted = self.db.delete_paper("nonexistent_paper")
        self.assertEqual(deleted, 0)

    # -- _normalize --

    def test_normalize_produces_unit_vectors(self):
        """_normalize produce vectores de norma 1."""
        vecs = np.array([[3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                         [0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        normalized = VectorDBManager._normalize(vecs)
        norms = np.linalg.norm(normalized, axis=1)
        np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-6)

    def test_normalize_zero_vector_no_nan(self):
        """_normalize no produce NaN para el vector cero."""
        vecs = np.zeros((1, self.dim), dtype=np.float32)
        result = VectorDBManager._normalize(vecs)
        self.assertFalse(np.isnan(result).any())


# ── TestRAGPipelineOrchestrator ────────────────────────────────────────────────

class TestRAGPipelineOrchestrator(unittest.TestCase):
    """Tests para RAGPipelineOrchestrator con extractor y embedding generator mocked."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.pdf_dir = Path(self.tmp_dir.name) / "pdfs"
        self.index_dir = Path(self.tmp_dir.name) / "rag_index"
        self.pdf_dir.mkdir(parents=True)

        self.mock_extractor = Mock()
        self.mock_chunker = Mock()
        self.mock_gen = make_mock_embedding_generator(DIM)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _make_orchestrator(self, **kwargs) -> RAGPipelineOrchestrator:
        return RAGPipelineOrchestrator(
            pdf_dir=self.pdf_dir,
            index_dir=self.index_dir,
            extractor=self.mock_extractor,
            chunker=self.mock_chunker,
            embedding_generator=self.mock_gen,
            verbose=False,
            **kwargs,
        )

    def _setup_mocks(self, paper_id: str, n_chunks: int = 3):
        """Configura extractor y chunker para simular procesamiento de un PDF."""
        pages = [(1, "Page one has content about fish. " * 20)]
        self.mock_extractor.extract_by_pages.return_value = pages

        chunks = [
            make_chunk(
                chunk_id=f"{paper_id}_chunk_{i:03d}",
                paper_id=paper_id,
                chunk_index=i,
            )
            for i in range(n_chunks)
        ]
        self.mock_chunker.chunk_pages.return_value = chunks
        return chunks

    # -- index_single_pdf --

    def test_index_single_pdf_returns_chunk_vectors(self):
        """index_single_pdf retorna la lista de ChunkVector generados."""
        pdf_path = self.pdf_dir / "paper_a.pdf"
        pdf_path.touch()
        self._setup_mocks("paper_a", n_chunks=4)

        orchestrator = self._make_orchestrator()
        result = orchestrator.index_single_pdf(pdf_path)

        self.assertEqual(len(result), 4)
        for cv in result:
            self.assertIsInstance(cv, ChunkVector)
            self.assertEqual(cv.vector.shape[0], DIM)

    def test_index_single_pdf_calls_extractor_with_path(self):
        """index_single_pdf llama al extractor con la ruta correcta."""
        pdf_path = self.pdf_dir / "paper_b.pdf"
        pdf_path.touch()
        self._setup_mocks("paper_b")

        orchestrator = self._make_orchestrator()
        orchestrator.index_single_pdf(pdf_path)

        self.mock_extractor.extract_by_pages.assert_called_once_with(pdf_path)

    def test_index_single_pdf_calls_chunker(self):
        """index_single_pdf llama al chunker pasándole las páginas extraídas."""
        pdf_path = self.pdf_dir / "paper_c.pdf"
        pdf_path.touch()
        self._setup_mocks("paper_c")

        orchestrator = self._make_orchestrator()
        orchestrator.index_single_pdf(pdf_path)

        self.mock_chunker.chunk_pages.assert_called_once()

    def test_index_single_pdf_calls_batch_generate_with_chunk_texts(self):
        """index_single_pdf llama a batch_generate con los textos de los chunks."""
        pdf_path = self.pdf_dir / "paper_d.pdf"
        pdf_path.touch()
        self._setup_mocks("paper_d", n_chunks=3)

        orchestrator = self._make_orchestrator()
        orchestrator.index_single_pdf(pdf_path)

        self.mock_gen.batch_generate.assert_called_once()
        texts_arg = self.mock_gen.batch_generate.call_args[0][0]
        self.assertEqual(len(texts_arg), 3)

    def test_index_single_pdf_empty_chunks_returns_empty(self):
        """index_single_pdf retorna [] si el chunker no genera chunks."""
        pdf_path = self.pdf_dir / "empty.pdf"
        pdf_path.touch()
        self.mock_extractor.extract_by_pages.return_value = [(1, "Minimal text.")]
        self.mock_chunker.chunk_pages.return_value = []

        orchestrator = self._make_orchestrator()
        result = orchestrator.index_single_pdf(pdf_path)

        self.assertEqual(result, [])
        self.mock_gen.batch_generate.assert_not_called()

    # -- run --

    def test_run_returns_stats_dict(self):
        """run() devuelve un dict con las claves esperadas."""
        for i in range(2):
            (self.pdf_dir / f"paper_{i}.pdf").touch()

        self.mock_extractor.extract_by_pages.return_value = [(1, "Content " * 30)]
        self.mock_chunker.chunk_pages.return_value = [
            make_chunk(chunk_id="p_chunk_000", paper_id="p")
        ]

        orchestrator = self._make_orchestrator()
        result = orchestrator.run()

        for key in ("processed", "skipped", "failed", "total_chunks"):
            self.assertIn(key, result)

    def test_run_skip_indexed_omits_already_indexed_pdf(self):
        """run() con skip_indexed=True no reprocesa PDFs ya indexados."""
        pdf_path = self.pdf_dir / "paper_e.pdf"
        pdf_path.touch()
        self._setup_mocks("paper_e")

        orchestrator = self._make_orchestrator(skip_indexed=True)
        # Primera pasada: indexar
        orchestrator.index_single_pdf(pdf_path)
        orchestrator._db.save()

        # Segunda pasada: debe omitir
        self.mock_extractor.extract_by_pages.reset_mock()
        result = orchestrator.run(pdf_paths=[pdf_path])

        self.mock_extractor.extract_by_pages.assert_not_called()
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["processed"], 0)

    def test_run_no_pdfs_returns_zero_processed(self):
        """run() con directorio vacío retorna processed=0."""
        orchestrator = self._make_orchestrator()
        result = orchestrator.run(pdf_paths=[])
        self.assertEqual(result["processed"], 0)

    # -- _derive_paper_id --

    def test_derive_paper_id_replaces_special_chars(self):
        """_derive_paper_id reemplaza caracteres especiales por guiones bajos."""
        path = Path("outputs/pdfs/2024_Smith et al._Marine Biology.pdf")
        paper_id = RAGPipelineOrchestrator._derive_paper_id(path)
        self.assertNotIn(" ", paper_id)
        self.assertRegex(paper_id, r"^[\w\-]+$")

    def test_derive_paper_id_normalizes_unicode(self):
        """_derive_paper_id normaliza caracteres unicode a ASCII."""
        path = Path("outputs/pdfs/García_2024_Análisis.pdf")
        paper_id = RAGPipelineOrchestrator._derive_paper_id(path)
        self.assertTrue(paper_id.isascii())

    def test_derive_paper_id_fallback_for_empty_stem(self):
        """_derive_paper_id retorna 'paper' si el stem queda vacío tras normalización."""
        path = Path("___.pdf")  # stem = "___" → strip("_") = "" → fallback
        paper_id = RAGPipelineOrchestrator._derive_paper_id(path)
        self.assertEqual(paper_id, "paper")


# ── TestSearchToRAGIntegration ─────────────────────────────────────────────────

class TestSearchToRAGIntegration(unittest.TestCase):
    """
    Tests de integración: Article objects (búsqueda) → embeddings → índice → búsqueda semántica.

    Flujo simulado:
      1. Crear Article objects (simula resultados de ScientificArticleSearcher)
      2. Extraer texto (título + abstract)
      3. Generar embeddings (mock determinista por tema)
      4. Indexar en VectorDBManager
      5. Búsqueda semántica y verificación de relevancia
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.index_dir = Path(self.tmp_dir.name) / "rag_index"
        self.dim = DIM

    def tearDown(self):
        self.tmp_dir.cleanup()

    # -- Fixtures --

    def _make_articles(self) -> list:
        """Tres artículos de muestra: 2 de biología marina, 1 de clima."""
        return [
            Article(
                title="Deep learning for fish species identification in underwater images",
                authors=["Smith, J.", "Garcia, M."],
                year=2023,
                doi="10.1234/fish.001",
                abstract=(
                    "We present a convolutional neural network for automatic identification "
                    "of marine fish species from underwater images. The model achieves 95% "
                    "accuracy on benchmark datasets of tropical fish."
                ),
                source="crossref",
            ),
            Article(
                title="Population dynamics of Lutjanus peru in the Gulf of California",
                authors=["Ramirez, A.", "Torres, B."],
                year=2022,
                doi="10.1234/fish.002",
                abstract=(
                    "This study analyzes the population structure and reproductive biology "
                    "of Pacific red snapper (Lutjanus peru) in the eastern Pacific Ocean "
                    "using length-frequency data collected over five years."
                ),
                source="pubmed",
            ),
            Article(
                title="Machine learning methods for climate change prediction",
                authors=["Johnson, C."],
                year=2024,
                doi="10.1234/climate.001",
                abstract=(
                    "We review machine learning approaches for predicting climate change "
                    "impacts, including temperature forecasting and extreme weather event "
                    "detection using satellite data and atmospheric models."
                ),
                source="arxiv",
            ),
        ]

    def _build_texts(self, articles: list) -> list:
        """Combina título + abstract de cada artículo en un texto único."""
        return [
            " ".join(filter(None, [a.title, a.abstract]))
            for a in articles
        ]

    def _make_semantic_mock_gen(self) -> Mock:
        """
        EmbeddingGenerator mock con vectores semánticamente significativos.

        Textos con términos marinos → vector orientado a dirección 0.
        Textos con términos de clima → vector orientado a dirección 1.
        Otros                        → vector mixto.
        """
        marine_kw = {"fish", "snapper", "marine", "lutjanus", "species", "underwater"}
        climate_kw = {"climate", "weather", "temperature", "satellite", "atmospheric"}
        dim = self.dim

        def classify(text: str) -> np.ndarray:
            text_l = text.lower()
            is_marine = any(kw in text_l for kw in marine_kw)
            is_climate = any(kw in text_l for kw in climate_kw)
            vec = np.zeros(dim, dtype=np.float32)
            if is_marine:
                vec[0] = 0.95
                vec[1] = 0.05
            elif is_climate:
                vec[0] = 0.05
                vec[1] = 0.95
            else:
                vec[0] = 0.5
                vec[1] = 0.5
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec

        gen = Mock()
        gen.get_dimension.return_value = dim
        gen.get_model_name.return_value = "mock-semantic-model"

        def batch_generate(texts, batch_size=32, show_progress=False):
            return np.vstack([classify(t) for t in texts])

        gen.batch_generate.side_effect = batch_generate
        gen.generate.side_effect = batch_generate
        return gen

    def _build_db_from_articles(
        self, articles: list, gen: Mock
    ) -> VectorDBManager:
        """Indexa una lista de artículos en un VectorDB y lo retorna."""
        texts = self._build_texts(articles)
        vectors = gen.batch_generate(texts)

        db = VectorDBManager(index_dir=self.index_dir, embedding_dim=self.dim)
        chunk_vectors = []
        for i, (article, vector) in enumerate(zip(articles, vectors)):
            chunk = ChunkData(
                chunk_id=f"art_{i:03d}_chunk_000",
                paper_id=f"art_{i:03d}",
                text=texts[i],
                chunk_index=0,
                page_number=-1,
                char_start=0,
                char_end=len(texts[i]),
                total_chunks=1,
                source_pdf="",
                title=article.title,
                authors=article.authors,
                year=article.year,
                doi=article.doi,
            )
            chunk_vectors.append(ChunkVector(
                chunk=chunk,
                vector=vector,
                embedding_model="mock-semantic-model",
            ))
        db.add_chunks(chunk_vectors)
        return db

    # -- Tests --

    def test_text_extraction_from_articles(self):
        """Extrae texto de artículos incluyendo título y abstract."""
        articles = self._make_articles()
        texts = self._build_texts(articles)
        self.assertEqual(len(texts), 3)
        for text, article in zip(texts, articles):
            self.assertIn(article.title, text)
            if article.abstract:
                self.assertIn(article.abstract[:30], text)

    def test_all_articles_indexed_in_db(self):
        """Todos los artículos de búsqueda quedan indexados en el VectorDB."""
        articles = self._make_articles()
        gen = self._make_semantic_mock_gen()
        db = self._build_db_from_articles(articles, gen)

        papers = db.get_papers_indexed()
        self.assertEqual(len(papers), len(articles))

    def test_marine_query_returns_marine_articles_first(self):
        """
        Query sobre pesca marina retorna artículos marinos antes que de clima.

        Verifica que el sistema de búsqueda semántica discrimina por tema.
        """
        articles = self._make_articles()
        gen = self._make_semantic_mock_gen()
        db = self._build_db_from_articles(articles, gen)

        # Query con términos marinos
        marine_query = "fish species identification marine biology"
        query_vec = gen.batch_generate([marine_query])[0]
        results = db.search(query_vec, top_k=3)

        self.assertGreater(len(results), 0)
        # El resultado más relevante NO debe ser el artículo de clima
        top_result = results[0]
        self.assertNotIn("climate", top_result.title.lower())

    def test_article_metadata_preserved_after_indexing(self):
        """Los metadatos del artículo (título, autores, año, DOI) se preservan."""
        articles = self._make_articles()[:1]
        gen = make_mock_embedding_generator(self.dim)
        db = self._build_db_from_articles(articles, gen)

        texts = self._build_texts(articles)
        query_vec = gen.batch_generate(texts)[0]
        results = db.search(query_vec, top_k=1)

        self.assertEqual(len(results), 1)
        r = results[0]
        a = articles[0]
        self.assertEqual(r.title, a.title)
        self.assertEqual(r.authors, a.authors)
        self.assertEqual(r.year, a.year)
        self.assertEqual(r.doi, a.doi)

    def test_save_load_preserves_search_capability(self):
        """Guardar y recargar el índice mantiene la búsqueda semántica funcional."""
        articles = self._make_articles()
        gen = make_mock_embedding_generator(self.dim)
        db = self._build_db_from_articles(articles, gen)
        db.save()

        # Recargar en nueva instancia
        db2 = VectorDBManager(index_dir=self.index_dir, embedding_dim=self.dim)
        db2.load()

        # Buscar con el vector del primer artículo (debe tener score ~1.0)
        texts = self._build_texts(articles)
        original_vec = gen.batch_generate(texts)[0]
        results = db2.search(original_vec, top_k=3)

        self.assertGreater(len(results), 0)
        self.assertGreater(results[0].score, 0.9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
