"""
AnthropicProvider: Proveedor de Claude API de Anthropic.

Implementa LLMProvider usando la API de Claude. Mantiene compatibilidad
con el patrón existente de inyección de cliente para tests.
"""

import os
from pathlib import Path
from typing import Optional

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """
    Proveedor que usa la API de Claude de Anthropic.

    Lee la API key desde variables de entorno o archivo, e inyecta un cliente
    Anthropic para mantener compatibilidad con tests existentes.

    Args:
        model: Modelo de Claude a usar (default: claude-sonnet-4-6).
        client: Cliente anthropic.Anthropic() inyectable (útil para tests con mocks).
                Si es None, se inicializa lazy desde API key.
        verbose: Mostrar información de debug.

    Raises:
        ImportError: Si el paquete 'anthropic' no está instalado.
        RuntimeError: Si no se encuentra la API key de Anthropic.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        client=None,
        verbose: bool = False,
    ):
        self.model = model
        self._client = client
        self.verbose = verbose

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024
    ) -> str:
        """
        Genera una respuesta usando Claude API.

        Args:
            system_prompt: Instrucciones para Claude.
            user_message: Mensaje o contexto + pregunta.
            max_tokens: Límite de tokens en la respuesta.

        Returns:
            Texto de la respuesta de Claude.

        Raises:
            RuntimeError: Si la API falla.
        """
        try:
            client = self._get_client()
            message = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except Exception as e:
            raise RuntimeError(f"Error al llamar a Claude API: {e}") from e

    def get_model_name(self) -> str:
        """Retorna el nombre del modelo."""
        return self.model

    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor."""
        return "anthropic"

    # ── Inicialización lazy del cliente ──────────────────────────────────────

    def _get_client(self):
        """
        Retorna el cliente Anthropic, inicializándolo si es necesario.

        Busca la API key en este orden:
          1. Variable de entorno ANTHROPIC_API_KEY
          2. Archivo secrets/anthropic-apikey (relativo al CWD)

        Returns:
            Cliente anthropic.Anthropic() listo para usar.

        Raises:
            ImportError: Si 'anthropic' no está instalado.
            RuntimeError: Si no se encuentra la API key.
        """
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ImportError(
                    "El paquete 'anthropic' no está instalado. "
                    "Instálalo con: pip install anthropic"
                ) from e

            api_key = os.environ.get("ANTHROPIC_API_KEY")

            if not api_key:
                secrets_path = Path("secrets/anthropic-apikey")
                if secrets_path.exists():
                    api_key = secrets_path.read_text().strip()

            if not api_key:
                raise RuntimeError(
                    "No se encontró la API key de Anthropic. "
                    "Define ANTHROPIC_API_KEY o crea el archivo secrets/anthropic-apikey."
                )

            self._client = anthropic.Anthropic(api_key=api_key)
            if self.verbose:
                print(f"[AnthropicProvider] Cliente inicializado con modelo: {self.model}")

        return self._client
