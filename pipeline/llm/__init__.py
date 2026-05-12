"""
pipeline.llm: Abstracción de proveedores de modelos de lenguaje.

Proporciona una interfaz unificada para usar diferentes proveedores de LLM
(Claude API, Ollama, etc.) en los componentes RAG del proyecto.

Ejemplo:
    >>> from pipeline.llm import get_llm_provider
    >>> provider = get_llm_provider(provider="ollama", model="llama3")
    >>> response = provider.generate("Eres un asistente", "¿Qué es Ollama?")
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
