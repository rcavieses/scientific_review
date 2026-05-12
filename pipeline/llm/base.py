"""
LLMProvider: Interfaz base para proveedores de modelos de lenguaje.

Define el contrato que deben cumplir todos los proveedores (Claude API, Ollama, etc.)
para ser intercambiables en la arquitectura RAG del proyecto.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class LLMProvider(ABC):
    """
    Interfaz base para proveedores de modelos de lenguaje.

    Define los métodos que todo proveedor debe implementar para ser usado
    en los componentes RAG, GraphRAG y extracción de entidades.

    Implementaciones concretas:
    - AnthropicProvider: Usa Claude API de Anthropic
    - OllamaProvider: Usa modelos locales via Ollama
    """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024
    ) -> str:
        """
        Genera una respuesta de texto usando el modelo LLM.

        Args:
            system_prompt: Instrucciones para el modelo (rol, contexto, etc.)
            user_message: Mensaje del usuario (pregunta, contexto + pregunta, etc.)
            max_tokens: Límite máximo de tokens en la respuesta.

        Returns:
            Texto de la respuesta del modelo.

        Raises:
            RuntimeError: Si hay error en la API o conexión.
            ImportError: Si la dependencia requerida no está instalada.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Retorna el nombre del modelo siendo usado.

        Returns:
            Nombre del modelo (ej: "claude-sonnet-4-6", "llama3")
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Retorna el nombre del proveedor.

        Returns:
            Nombre del proveedor (ej: "anthropic", "ollama")
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """
        Obtiene información del proveedor y modelo.

        Returns:
            Diccionario con información (nombre del proveedor, modelo, etc.)
        """
        return {
            "provider": self.get_provider_name(),
            "model": self.get_model_name(),
            "type": self.__class__.__name__,
        }
