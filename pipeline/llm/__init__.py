"""
pipeline.llm: Abstraction layer for language model providers.

Provides a unified interface to use different LLM providers
(Claude API, Ollama, etc.) in the project's RAG components.

Example:
    >>> from pipeline.llm import get_llm_provider
    >>> provider = get_llm_provider(provider="ollama", model="llama3")
    >>> response = provider.generate("You are a helpful assistant", "What is Ollama?")
"""

from .base import LLMProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider
from .factory import get_llm_provider

__all__ = [
    "LLMProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "get_llm_provider",
]
