"""
Tests para EmbeddingGenerator (Semana 2).
"""

import unittest
import sys
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Agregar parent a path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pipeline.embeddings.embedding_generator import (
    EmbeddingGenerator,
    LocalEmbeddingGenerator,
    OpenAIEmbeddingGenerator,
    get_embedding_generator
)


class TestEmbeddingGeneratorBase(unittest.TestCase):
    """Tests para interfaz base EmbeddingGenerator."""

    def test_cosine_similarity_identical(self):
        """Test similitud de coseno: vectores idénticos = 1.0"""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        similarity = EmbeddingGenerator.cosine_similarity(vec1, vec2)

        self.assertAlmostEqual(similarity, 1.0, places=5)

    def test_cosine_similarity_orthogonal(self):
        """Test similitud de coseno: vectores ortogonales ≈ 0.0"""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        similarity = EmbeddingGenerator.cosine_similarity(vec1, vec2)

        self.assertAlmostEqual(similarity, 0.0, places=5)

    def test_cosine_similarity_opposite(self):
        """Test similitud de coseno: vectores opuestos = -1.0"""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([-1.0, 0.0, 0.0], dtype=np.float32)

        similarity = EmbeddingGenerator.cosine_similarity(vec1, vec2)

        self.assertAlmostEqual(similarity, -1.0, places=5)


class TestLocalEmbeddingGenerator(unittest.TestCase):
    """Tests para LocalEmbeddingGenerator (mocked)."""

    def setUp(self):
        """Preparar tests con mock del modelo."""
        # Mockeamos el modelo de SentenceTransformer
        self.mock_model = Mock()
        self.patcher = patch(
            'pipeline.embeddings.embedding_generator.SentenceTransformer'
        )
        self.mock_st = self.patcher.start()
        self.mock_st.return_value = self.mock_model

    def tearDown(self):
        """Limpiar mocks."""
        self.patcher.stop()

    def test_initialization_with_default_model(self):
        """Test inicialización con modelo default."""
        # Configurar mock
        self.mock_model.get_sentence_embedding_dimension.return_value = 384

        generator = LocalEmbeddingGenerator(verbose=False)

        self.assertEqual(generator.model_name, "all-MiniLM-L6-v2")
        self.assertEqual(generator.get_dimension(), 384)

    def test_initialization_with_custom_model(self):
        """Test inicialización con modelo personalizado."""
        # Configurar mock
        self.mock_model.get_sentence_embedding_dimension.return_value = 768

        generator = LocalEmbeddingGenerator(
            model_name="all-mpnet-base-v2",
            verbose=False
        )

        self.assertEqual(generator.model_name, "all-mpnet-base-v2")
        self.assertEqual(generator.get_dimension(), 768)

    def test_generate_single_text(self):
        """Test generación de embedding para un texto."""
        # Configurar mock para retornar embedding (2D array)
        embedding = np.random.randn(1, 384).astype(np.float32)
        self.mock_model.encode.return_value = embedding

        generator = LocalEmbeddingGenerator(verbose=False)
        result = generator.generate(["test text"])

        self.assertEqual(result.shape, (1, 384))
        self.assertEqual(result.dtype, np.float32)

    def test_generate_multiple_texts(self):
        """Test generación de embeddings para múltiples textos."""
        # Configurar mock
        embeddings = np.random.randn(5, 384).astype(np.float32)
        self.mock_model.encode.return_value = embeddings

        generator = LocalEmbeddingGenerator(verbose=False)
        result = generator.generate([
            "text 1", "text 2", "text 3", "text 4", "text 5"
        ])

        self.assertEqual(result.shape, (5, 384))
        self.assertEqual(result.dtype, np.float32)

    def test_batch_generate(self):
        """Test generación en batches."""
        # Configurar mock para retornar embeddings con forma correcta según input
        def side_effect_encode(*args, **kwargs):
            texts = args[0] if args else kwargs.get('input', [])
            return np.random.randn(len(texts), 384).astype(np.float32)

        self.mock_model.encode.side_effect = side_effect_encode

        generator = LocalEmbeddingGenerator(verbose=False)

        texts = [f"text {i}" for i in range(10)]
        result = generator.batch_generate(texts, batch_size=3)

        self.assertEqual(result.shape, (10, 384))
        self.assertTrue(np.all(np.isfinite(result)))

    def test_get_model_name(self):
        """Test obtención del nombre del modelo."""
        generator = LocalEmbeddingGenerator(
            model_name="all-mpnet-base-v2",
            verbose=False
        )

        self.assertEqual(generator.get_model_name(), "all-mpnet-base-v2")

    def test_get_info(self):
        """Test obtención de información."""
        self.mock_model.get_sentence_embedding_dimension.return_value = 384

        generator = LocalEmbeddingGenerator(verbose=False)
        info = generator.get_info()

        self.assertIn("model", info)
        self.assertIn("dimension", info)
        self.assertIn("type", info)
        self.assertIn("device", info)
        self.assertEqual(info["type"], "LocalEmbeddingGenerator")

    def test_known_model_dimension(self):
        """Test que modelos conocidos retornan dimension correcta."""
        test_cases = [
            ("all-MiniLM-L6-v2", 384),
            ("all-mpnet-base-v2", 768),
            ("multilingual-e5-small", 384),
        ]

        for model_name, expected_dim in test_cases:
            generator = LocalEmbeddingGenerator(
                model_name=model_name,
                verbose=False
            )
            self.assertEqual(
                generator.get_dimension(),
                expected_dim,
                f"Modelo {model_name} debe tener {expected_dim} dims"
            )


class TestOpenAIEmbeddingGenerator(unittest.TestCase):
    """Tests para OpenAIEmbeddingGenerator (mocked)."""

    def setUp(self):
        """Preparar tests con mock de OpenAI."""
        self.patcher = patch(
            'pipeline.embeddings.embedding_generator.OpenAI'
        )
        self.mock_openai = self.patcher.start()

        # Mock del cliente
        self.mock_client = Mock()
        self.mock_openai.return_value = self.mock_client

    def tearDown(self):
        """Limpiar mocks."""
        self.patcher.stop()

    def test_initialization_with_api_key(self):
        """Test inicialización con API key proporcionada."""
        generator = OpenAIEmbeddingGenerator(
            api_key="sk-test-key",
            verbose=False
        )

        self.assertEqual(generator.model_name, "text-embedding-3-small")
        self.assertIsNotNone(generator.client)

    def test_initialization_without_api_key_raises(self):
        """Test que falla sin API key."""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIEmbeddingGenerator(verbose=False)

    def test_generate_embeddings(self):
        """Test generación de embeddings vía OpenAI."""
        # Configurar mock
        mock_response = Mock()
        mock_item_1 = Mock(embedding=[0.1, 0.2, 0.3])
        mock_item_2 = Mock(embedding=[0.4, 0.5, 0.6])
        mock_response.data = [mock_item_1, mock_item_2]

        self.mock_client.embeddings.create.return_value = mock_response

        generator = OpenAIEmbeddingGenerator(
            api_key="sk-test",
            verbose=False
        )
        result = generator.generate(["text 1", "text 2"])

        self.assertEqual(result.shape, (2, 3))
        self.assertEqual(result.dtype, np.float32)

    def test_known_model_dimension(self):
        """Test que modelos conocidos retornan dimension correcta."""
        test_cases = [
            ("text-embedding-3-small", 512),
            ("text-embedding-3-large", 3072),
            ("text-embedding-ada-002", 1536),
        ]

        for model_name, expected_dim in test_cases:
            generator = OpenAIEmbeddingGenerator(
                model_name=model_name,
                api_key="sk-test",
                verbose=False
            )
            self.assertEqual(
                generator.get_dimension(),
                expected_dim,
                f"Modelo {model_name} debe tener {expected_dim} dims"
            )


class TestEmbeddingGeneratorFactory(unittest.TestCase):
    """Tests para factory function."""

    def setUp(self):
        """Preparar mocks."""
        self.patcher_st = patch(
            'pipeline.embeddings.embedding_generator.SentenceTransformer'
        )
        self.patcher_openai = patch(
            'pipeline.embeddings.embedding_generator.OpenAI'
        )

        self.mock_st = self.patcher_st.start()
        self.mock_openai = self.patcher_openai.start()

        self.mock_st.return_value = Mock()
        self.mock_openai.return_value = Mock()

    def tearDown(self):
        """Limpiar mocks."""
        self.patcher_st.stop()
        self.patcher_openai.stop()

    def test_factory_local(self):
        """Test factory con provider local."""
        generator = get_embedding_generator(provider="local", verbose=False)

        self.assertIsInstance(generator, LocalEmbeddingGenerator)

    def test_factory_openai(self):
        """Test factory con provider openai."""
        generator = get_embedding_generator(
            provider="openai",
            api_key="sk-test",
            verbose=False
        )

        self.assertIsInstance(generator, OpenAIEmbeddingGenerator)

    def test_factory_invalid_provider_raises(self):
        """Test que provider inválido genera error."""
        with self.assertRaises(ValueError):
            get_embedding_generator(provider="invalid", verbose=False)

    def test_factory_custom_model(self):
        """Test factory con modelo personalizado."""
        generator = get_embedding_generator(
            provider="local",
            model="all-mpnet-base-v2",
            verbose=False
        )

        self.assertEqual(
            generator.get_model_name(),
            "all-mpnet-base-v2"
        )


class TestEmbeddingQuality(unittest.TestCase):
    """Tests de calidad de embeddings."""

    def setUp(self):
        """Preparar tests."""
        self.patcher = patch(
            'pipeline.embeddings.embedding_generator.SentenceTransformer'
        )
        self.mock_st = self.patcher.start()
        self.mock_model = Mock()
        self.mock_st.return_value = self.mock_model

    def tearDown(self):
        """Limpiar mocks."""
        self.patcher.stop()

    def test_normalized_embeddings_unit_norm(self):
        """Test que embeddings normalizados tienen norm = 1."""
        # Crear embeddings normalizados
        embedding = np.array([0.8, 0.6], dtype=np.float32)  # Norm = 1
        self.mock_model.encode.return_value = embedding.reshape(1, -1)

        generator = LocalEmbeddingGenerator(
            normalize_embeddings=True,
            verbose=False
        )
        result = generator.generate(["test"])

        norm = np.linalg.norm(result[0])
        # Norm debería ser aproximadamente 1 si está normalizado
        self.assertAlmostEqual(norm, 1.0, places=4)

    def test_similarity_symmetric(self):
        """Test que similitud es simétrica."""
        vec1 = np.array([1.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.7071, 0.7071], dtype=np.float32)

        sim_1_2 = EmbeddingGenerator.cosine_similarity(vec1, vec2)
        sim_2_1 = EmbeddingGenerator.cosine_similarity(vec2, vec1)

        self.assertAlmostEqual(sim_1_2, sim_2_1, places=5)


def run_tests():
    """Ejecuta todos los tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestEmbeddingGeneratorBase))
    suite.addTests(loader.loadTestsFromTestCase(TestLocalEmbeddingGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestOpenAIEmbeddingGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestEmbeddingGeneratorFactory))
    suite.addTests(loader.loadTestsFromTestCase(TestEmbeddingQuality))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
