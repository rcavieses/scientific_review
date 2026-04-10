"""
Tests para componentes de Foundation (Semana 1).
"""

import unittest
import sys
from pathlib import Path

# Agregar parent a path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scientific_search import Article
from pipeline.embeddings.models import ExtractedData, EmbeddingStats, SearchResult
from pipeline.embeddings.information_extractor import InformationExtractor
from pipeline.embeddings.text_processor import TextProcessor


class TestModels(unittest.TestCase):
    """Tests para modelos de datos."""

    def test_extracted_data_creation(self):
        """Test creación de ExtractedData."""
        data = ExtractedData(
            title="Deep Learning for Fishing Prediction",
            abstract="This paper proposes...",
            keywords=["deep learning", "fishing"],
            authors=["Smith, J.", "Lee, K."],
            year=2024,
            doi="10.1038/test"
        )

        self.assertEqual(data.title, "Deep Learning for Fishing Prediction")
        self.assertEqual(len(data.authors), 2)
        self.assertEqual(data.year, 2024)

    def test_extracted_data_without_title_raises(self):
        """Test que ExtractedData requiere título."""
        with self.assertRaises(ValueError):
            ExtractedData(title="")

    def test_extracted_data_combined_text_title_only(self):
        """Test combinación de texto con estrategia title_only."""
        data = ExtractedData(
            title="Title",
            abstract="Abstract content"
        )

        text = data.get_combined_text("title_only")
        self.assertEqual(text, "Title")

    def test_extracted_data_combined_text_title_abstract(self):
        """Test combinación de texto con estrategia title_abstract."""
        data = ExtractedData(
            title="Title",
            abstract="Abstract content"
        )

        text = data.get_combined_text("title_abstract")
        self.assertIn("Title", text)
        self.assertIn("Abstract content", text)

    def test_extracted_data_combined_text_rich(self):
        """Test combinación de texto con estrategia rich."""
        data = ExtractedData(
            title="Title",
            abstract="Abstract",
            keywords=["key1", "key2"],
            authors=["Author1", "Author2"]
        )

        text = data.get_combined_text("rich")
        self.assertIn("Title", text)
        self.assertIn("Abstract", text)
        self.assertIn("key1", text)
        self.assertIn("Author1", text)

    def test_embedding_stats_creation(self):
        """Test creación de EmbeddingStats."""
        stats = EmbeddingStats(
            total_documents=1000,
            embedding_model="all-MiniLM-L6-v2",
            embedding_dimension=384,
            vector_db_type="faiss",
            index_size_mb=250.5,
            memory_used_mb=512.0,
            index_age="2 days"
        )

        self.assertEqual(stats.total_documents, 1000)
        self.assertEqual(stats.embedding_dimension, 384)

    def test_search_result_creation(self):
        """Test creación de SearchResult."""
        result = SearchResult(
            vector_id="doc_001",
            title="Test Article",
            score=0.85,
            metadata={"source": "crossref"},
            doi="10.1038/test",
            year=2024
        )

        self.assertEqual(result.vector_id, "doc_001")
        self.assertAlmostEqual(result.score, 0.85)
        self.assertEqual(result.year, 2024)


class TestInformationExtractor(unittest.TestCase):
    """Tests para InformationExtractor."""

    def setUp(self):
        """Preparar tests."""
        self.extractor = InformationExtractor()

    def test_extract_from_article(self):
        """Test extracción básica de artículo."""
        article = Article(
            title="Test Article Title",
            authors=["Smith, J.", "Lee, K."],
            year=2024,
            doi="10.1038/test",
            url="https://example.com",
            abstract="Test abstract content",
            source="crossref"
        )

        extracted = self.extractor.extract_from_article(article)

        self.assertEqual(extracted.title, "Test Article Title")
        self.assertEqual(len(extracted.authors), 2)
        self.assertEqual(extracted.year, 2024)

    def test_extract_clean_text(self):
        """Test que el extractor limpia el texto."""
        article = Article(
            title="  Test   Title  With   Extra   Spaces  ",
            authors=[],
            source="test"
        )

        extracted = self.extractor.extract_from_article(article)

        # Debería remover espacios extra
        self.assertNotIn("   ", extracted.title)

    def test_extract_from_multiple(self):
        """Test extracción de múltiples artículos."""
        articles = [
            Article(
                title=f"Article {i}",
                authors=[],
                source="test"
            )
            for i in range(5)
        ]

        extracted_list, errors = self.extractor.extract_from_multiple(articles)

        self.assertEqual(len(extracted_list), 5)
        self.assertEqual(len(errors), 0)

    def test_extract_from_multiple_with_error(self):
        """Test extracción con errores (skip_errors=True)."""
        articles = [
            Article(title="Valid", authors=[], source="test"),
            Article(title="", authors=[], source="test"),  # Error
            Article(title="Valid2", authors=[], source="test"),
        ]

        extracted_list, errors = self.extractor.extract_from_multiple(
            articles, skip_errors=True
        )

        self.assertEqual(len(extracted_list), 2)
        self.assertEqual(len(errors), 1)

    def test_validate_extracted_data(self):
        """Test validación de datos extraídos."""
        valid_data = ExtractedData(
            title="Test",
            abstract="Abstract",
            authors=["Author"],
            year=2024
        )

        is_valid, problems = self.extractor.validate_extracted_data(valid_data)
        self.assertTrue(is_valid)

    def test_get_statistics(self):
        """Test estadísticas de extracción."""
        data_list = [
            ExtractedData(title=f"Article {i}", abstract="Test", year=2020+i)
            for i in range(10)
        ]

        stats = self.extractor.get_statistics(data_list)

        self.assertEqual(stats["total"], 10)
        self.assertEqual(stats["con_titulo"], 10)
        self.assertEqual(stats["con_abstract"], 10)


class TestTextProcessor(unittest.TestCase):
    """Tests para TextProcessor."""

    def test_text_processor_creation(self):
        """Test creación de TextProcessor."""
        processor = TextProcessor(strategy="title_abstract")
        self.assertEqual(processor.strategy, "title_abstract")

    def test_invalid_strategy_raises(self):
        """Test que estrategia inválida genera error."""
        with self.assertRaises(ValueError):
            TextProcessor(strategy="invalid_strategy")

    def test_normalize_text(self):
        """Test normalización de texto."""
        processor = TextProcessor()

        # Test acentos
        text = processor.normalize("café résumé naïve")
        # Debería simplificar acentos
        self.assertNotIn("é", text)

    def test_clean_text(self):
        """Test limpieza de texto."""
        processor = TextProcessor()

        # Test remoción de URLs
        text = "Check this: http://example.com for more info"
        cleaned = processor.clean(text)
        self.assertNotIn("http", cleaned)

        # Test remoción de referencias [1]
        text = "Some text[1] more text[2]"
        cleaned = processor.clean(text)
        self.assertNotIn("[1]", cleaned)
        self.assertNotIn("[2]", cleaned)

    def test_process_extracted_data_title_only(self):
        """Test procesamiento con estrategia title_only."""
        processor = TextProcessor(strategy="title_only")

        data = ExtractedData(
            title="Test Article Title",
            abstract="Long abstract text"
        )

        processed = processor.process_extracted_data(data)

        # Debería contener título pero no necesariamente el abstract completo
        self.assertIn("test", processed.lower())

    def test_process_extracted_data_title_abstract(self):
        """Test procesamiento con estrategia title_abstract."""
        processor = TextProcessor(strategy="title_abstract")

        data = ExtractedData(
            title="Title",
            abstract="Abstract content"
        )

        processed = processor.process_extracted_data(data)

        # Debería contener ambos
        self.assertIn("title", processed.lower())
        self.assertIn("abstract", processed.lower())

    def test_max_length(self):
        """Test límite de longitud."""
        processor = TextProcessor(max_length=50)

        data = ExtractedData(
            title="This is a very long title that should be truncated"
        )

        processed = processor.process_extracted_data(data)
        self.assertLessEqual(len(processed), 50)

    def test_process_multiple(self):
        """Test procesamiento de múltiples datos."""
        processor = TextProcessor()

        data_list = [
            ExtractedData(title=f"Article {i}")
            for i in range(5)
        ]

        processed = processor.process_multiple(data_list)

        self.assertEqual(len(processed), 5)
        self.assertTrue(all(isinstance(p, str) for p in processed))

    def test_get_statistics(self):
        """Test estadísticas de procesamiento."""
        processor = TextProcessor()

        data_list = [
            ExtractedData(title="Short title"),
            ExtractedData(title="A much longer title for this article"),
        ]

        stats = processor.get_statistics(data_list)

        self.assertEqual(stats["total"], 2)
        self.assertIn("longitud_promedio", stats)
        self.assertGreater(stats["longitud_max"], stats["longitud_min"])

    def test_compare_strategies(self):
        """Test comparación de estrategias."""
        data = ExtractedData(
            title="Title",
            abstract="Abstract",
            keywords=["key1", "key2"],
            authors=["Author1"]
        )

        results = TextProcessor.compare_strategies(data, verbose=False)

        self.assertEqual(len(results), 4)  # 4 estrategias
        self.assertIn("title_only", results)
        self.assertIn("rich", results)

        # Rich debería ser más largo que title_only
        self.assertGreater(len(results["rich"]), len(results["title_only"]))


class TestIntegration(unittest.TestCase):
    """Tests de integración Foundation."""

    def test_end_to_end_extraction_and_processing(self):
        """Test flujo completo: extraer → procesar."""
        # Crear artículo
        article = Article(
            title="  Deep Learning for Fishing Prediction  ",
            abstract="This paper proposes a deep learning approach...",
            keywords=["deep learning", "fishing", "prediction"],
            authors=["Smith, J.", "Lee, K."],
            year=2024,
            doi="10.1038/test",
            source="crossref"
        )

        # Extraer
        extractor = InformationExtractor()
        extracted = extractor.extract_from_article(article)

        # Procesar
        processor = TextProcessor(strategy="title_abstract")
        processed = processor.process_extracted_data(extracted)

        # Validaciones
        self.assertIsNotNone(processed)
        self.assertGreater(len(processed), 0)
        self.assertNotIn("   ", processed)  # Sin espacios múltiples


def run_tests():
    """Ejecuta todos los tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestModels))
    suite.addTests(loader.loadTestsFromTestCase(TestInformationExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestTextProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
