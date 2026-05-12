"""
Factory function para crear instancias de LLMProvider.

Proporciona una forma centralizada y simple de instanciar el proveedor de LLM
correcto basado en parámetros de configuración.
"""

from typing import Optional

from .base import LLMProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider


def get_llm_provider(
    provider: str = "claude",
    model: Optional[str] = None,
    **kwargs
) -> LLMProvider:
    """
    Factory function para obtener un proveedor de LLM.

    Args:
        provider: Nombre del proveedor a usar.
                 Opciones: "claude", "anthropic", "ollama"
        model: Nombre del modelo a usar (defaults según provider):
               - Claude: "claude-sonnet-4-6"
               - Ollama: "llama3"
        **kwargs: Argumentos adicionales específicos del proveedor:
                 - AnthropicProvider: client=None, verbose=False
                 - OllamaProvider: host="http://localhost:11434", verbose=False

    Returns:
        Instancia de LLMProvider lista para usar.

    Raises:
        ValueError: Si el proveedor especificado no es válido.

    Examples:
        >>> # Usar Claude (default)
        >>> provider = get_llm_provider()
        >>> answer = provider.generate("Eres un asistente", "¿Hola?")

        >>> # Usar Ollama con modelo específico
        >>> provider = get_llm_provider("ollama", model="mistral")
        >>> answer = provider.generate("Eres un asistente", "¿Hola?")

        >>> # Usar Ollama con host personalizado
        >>> provider = get_llm_provider("ollama", host="http://192.168.1.100:11434")
    """
    # Normalizar nombre del proveedor
    provider_lower = provider.lower().strip()

    if provider_lower in ("claude", "anthropic"):
        model = model or "claude-sonnet-4-6"
        return AnthropicProvider(model=model, **kwargs)

    elif provider_lower == "ollama":
        model = model or "llama3"
        return OllamaProvider(model=model, **kwargs)

    else:
        raise ValueError(
            f"Proveedor de LLM inválido: '{provider}'. "
            f"Opciones válidas: 'claude', 'anthropic', 'ollama'"
        )
