"""
Tests for LLM providers (Claude API, Ollama, etc.)

Tests the abstraction layer for LLMProvider and all concrete implementations.
"""

import unittest
from unittest.mock import MagicMock, patch

from pipeline.llm import (
    LLMProvider,
    AnthropicProvider,
    OllamaProvider,
    get_llm_provider,
)


def make_mock_anthropic_client(response_text: str = "Test response") -> MagicMock:
    """Create a mock Anthropic client for testing."""
    client = MagicMock()
    message = MagicMock()
    message.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = message
    return client


class TestLLMProviderInterface(unittest.TestCase):
    """Test the abstract LLMProvider interface."""

    def test_llm_provider_is_abc(self):
        """LLMProvider should be an abstract base class."""
        with self.assertRaises(TypeError):
            LLMProvider()

    def test_get_info_provides_defaults(self):
        """LLMProvider.get_info() provides default metadata."""
        mock_client = make_mock_anthropic_client()
        provider = AnthropicProvider(client=mock_client)
        info = provider.get_info()

        self.assertIn("provider", info)
        self.assertIn("model", info)
        self.assertIn("type", info)


class TestAnthropicProvider(unittest.TestCase):
    """Test AnthropicProvider implementation."""

    def test_init_with_mock_client(self):
        """AnthropicProvider should accept injected client."""
        mock_client = make_mock_anthropic_client()
        provider = AnthropicProvider(model="claude-sonnet-4-6", client=mock_client)

        self.assertEqual(provider.get_model_name(), "claude-sonnet-4-6")
        self.assertEqual(provider.get_provider_name(), "anthropic")

    def test_generate_calls_claude_api(self):
        """AnthropicProvider.generate() should call Claude API."""
        mock_client = make_mock_anthropic_client("Claude response")
        provider = AnthropicProvider(client=mock_client)

        response = provider.generate(
            system_prompt="You are helpful.",
            user_message="Hello",
            max_tokens=100
        )

        self.assertEqual(response, "Claude response")
        mock_client.messages.create.assert_called_once()

        # Verify API call structure
        call_kwargs = mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["model"], "claude-sonnet-4-6")
        self.assertEqual(call_kwargs["max_tokens"], 100)
        self.assertEqual(call_kwargs["system"], "You are helpful.")
        self.assertEqual(len(call_kwargs["messages"]), 1)
        self.assertEqual(call_kwargs["messages"][0]["role"], "user")

    def test_generate_raises_on_api_error(self):
        """AnthropicProvider.generate() should raise RuntimeError on API failure."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API timeout")
        provider = AnthropicProvider(client=mock_client)

        with self.assertRaises(RuntimeError) as ctx:
            provider.generate("system", "user message")

        self.assertIn("Error al llamar a Claude API", str(ctx.exception))

    def test_get_info_includes_model(self):
        """AnthropicProvider.get_info() should include model info."""
        mock_client = make_mock_anthropic_client()
        provider = AnthropicProvider(model="claude-haiku-4-5", client=mock_client)
        info = provider.get_info()

        self.assertEqual(info["provider"], "anthropic")
        self.assertEqual(info["model"], "claude-haiku-4-5")


class TestOllamaProvider(unittest.TestCase):
    """Test OllamaProvider implementation."""

    @patch("pipeline.llm.ollama_provider.ollama")
    def test_init_with_ollama(self, mock_ollama):
        """OllamaProvider should initialize with Ollama client."""
        mock_client = MagicMock()
        mock_ollama.Client.return_value = mock_client

        provider = OllamaProvider(model="llama3")

        self.assertEqual(provider.get_model_name(), "llama3")
        self.assertEqual(provider.get_provider_name(), "ollama")

    @patch("pipeline.llm.ollama_provider.ollama")
    def test_generate_calls_ollama(self, mock_ollama):
        """OllamaProvider.generate() should call Ollama API."""
        mock_client = MagicMock()
        mock_client.chat.return_value = {
            "message": {"content": "Ollama response"}
        }
        mock_ollama.Client.return_value = mock_client

        provider = OllamaProvider(model="llama3")
        response = provider.generate(
            system_prompt="You are helpful.",
            user_message="Hello",
            max_tokens=100
        )

        self.assertEqual(response, "Ollama response")
        mock_client.chat.assert_called_once()

        # Verify API call structure
        call_kwargs = mock_client.chat.call_args[1]
        self.assertEqual(call_kwargs["model"], "llama3")
        self.assertEqual(call_kwargs["stream"], False)
        self.assertEqual(len(call_kwargs["messages"]), 2)
        self.assertEqual(call_kwargs["messages"][0]["role"], "system")
        self.assertEqual(call_kwargs["messages"][1]["role"], "user")

    @patch("pipeline.llm.ollama_provider.ollama")
    def test_generate_raises_on_connection_error(self, mock_ollama):
        """OllamaProvider.generate() should raise RuntimeError on connection error."""
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("Connection refused")
        mock_ollama.Client.return_value = mock_client

        provider = OllamaProvider()

        with self.assertRaises(RuntimeError) as ctx:
            provider.generate("system", "user message")

        self.assertIn("Error al llamar a Ollama", str(ctx.exception))

    @patch("pipeline.llm.ollama_provider.ollama")
    def test_custom_host(self, mock_ollama):
        """OllamaProvider should accept custom host."""
        mock_client = MagicMock()
        mock_ollama.Client.return_value = mock_client

        provider = OllamaProvider(host="http://192.168.1.100:11434")

        # Verify Client was called with custom host
        mock_ollama.Client.assert_called_once_with(host="http://192.168.1.100:11434")


class TestLLMProviderFactory(unittest.TestCase):
    """Test get_llm_provider() factory function."""

    def test_factory_creates_anthropic_by_default(self):
        """get_llm_provider() should create AnthropicProvider by default."""
        mock_client = make_mock_anthropic_client()
        provider = get_llm_provider(client=mock_client)

        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(provider.get_provider_name(), "anthropic")

    def test_factory_accepts_claude_alias(self):
        """get_llm_provider('claude') should work like default."""
        mock_client = make_mock_anthropic_client()
        provider = get_llm_provider(provider="claude", client=mock_client)

        self.assertIsInstance(provider, AnthropicProvider)

    @patch("pipeline.llm.ollama_provider.ollama")
    def test_factory_creates_ollama(self, mock_ollama):
        """get_llm_provider('ollama') should create OllamaProvider."""
        mock_client = MagicMock()
        mock_ollama.Client.return_value = mock_client

        provider = get_llm_provider(provider="ollama")

        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.get_provider_name(), "ollama")

    def test_factory_sets_model_from_provider(self):
        """get_llm_provider() should use default model per provider."""
        mock_client = make_mock_anthropic_client()
        provider = get_llm_provider(provider="claude", client=mock_client)

        # Default for Claude
        self.assertEqual(provider.get_model_name(), "claude-sonnet-4-6")

    def test_factory_accepts_custom_model(self):
        """get_llm_provider() should accept custom model name."""
        mock_client = make_mock_anthropic_client()
        provider = get_llm_provider(
            provider="claude",
            model="claude-haiku-4-5",
            client=mock_client
        )

        self.assertEqual(provider.get_model_name(), "claude-haiku-4-5")

    def test_factory_rejects_invalid_provider(self):
        """get_llm_provider() should raise ValueError for invalid provider."""
        with self.assertRaises(ValueError) as ctx:
            get_llm_provider(provider="invalid")

        self.assertIn("Proveedor de LLM inválido", str(ctx.exception))

    def test_factory_case_insensitive(self):
        """get_llm_provider() should accept case variations."""
        mock_client = make_mock_anthropic_client()
        provider1 = get_llm_provider(provider="CLAUDE", client=mock_client)
        provider2 = get_llm_provider(provider="ClAuDe", client=mock_client)

        self.assertIsInstance(provider1, AnthropicProvider)
        self.assertIsInstance(provider2, AnthropicProvider)


class TestIntegrationRAGQueryEngine(unittest.TestCase):
    """Integration tests: RAGQueryEngine with different LLM providers."""

    def test_query_engine_accepts_llm_provider(self):
        """RAGQueryEngine should accept LLMProvider injection."""
        from pipeline.rag.query_engine import RAGQueryEngine
        from pipeline.rag.vector_db import VectorDBManager

        # Mock dependencies
        mock_db = MagicMock(spec=VectorDBManager)
        mock_db.get_stats.return_value = MagicMock(total_chunks=10)
        mock_db.search.return_value = [
            MagicMock(
                text="Sample chunk",
                score=0.8,
                page_number=1,
                authors=["Author"],
                title="Title",
                year=2024,
                paper_id="p1"
            )
        ]

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "Generated answer"

        # Create engine with provider
        engine = RAGQueryEngine(
            vector_db=mock_db,
            llm_provider=mock_provider
        )

        # Query should work
        result = engine.query("Test question")

        self.assertEqual(result.answer, "Generated answer")
        mock_provider.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
