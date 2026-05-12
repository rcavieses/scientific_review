"""
OllamaProvider: Proveedor de modelos locales via Ollama.

Implementa LLMProvider usando modelos locales ejecutados a través de Ollama.
Permite trabajar 100% offline con máxima privacidad, sin costos de API.
"""

from typing import Optional

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """
    Proveedor que usa modelos locales via Ollama.

    Ollama ejecuta modelos de lenguaje abiertos en la máquina local.
    Requiere que Ollama esté instalado y corriendo en el puerto especificado.

    Modelos recomendados:
    - "llama3" — 8B, buen balance velocidad/calidad
    - "mistral" — 7B, muy rápido
    - "neural-chat" — 7B, optimizado para chat
    - "orca-mini" — 3B, muy ligero
    - "dolphin-mixtral" — 8x7B, alta calidad pero lento

    Args:
        model: Nombre del modelo en Ollama (default: "llama3").
        host: URL del servidor Ollama (default: "http://localhost:11434").
        verbose: Mostrar información de debug.

    Raises:
        ImportError: Si el paquete 'ollama' no está instalado.
        RuntimeError: Si no se puede conectar al servidor Ollama.
    """

    def __init__(
        self,
        model: str = "llama3",
        host: str = "http://localhost:11434",
        verbose: bool = False,
    ):
        self.model = model
        self.host = host
        self.verbose = verbose
        self._client = None

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024
    ) -> str:
        """
        Genera una respuesta usando un modelo local de Ollama.

        Args:
            system_prompt: Instrucciones para el modelo.
            user_message: Mensaje o contexto + pregunta.
            max_tokens: Límite de tokens en la respuesta.

        Returns:
            Texto de la respuesta del modelo.

        Raises:
            RuntimeError: Si hay error en la conexión o en el modelo.
        """
        try:
            client = self._get_client()
            response = client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=False,
                options={"num_predict": max_tokens},
            )
            return response["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Error al llamar a Ollama: {e}") from e

    def get_model_name(self) -> str:
        """Retorna el nombre del modelo."""
        return self.model

    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor."""
        return "ollama"

    # ── Inicialización del cliente ───────────────────────────────────────────

    def _get_client(self):
        """
        Retorna el cliente Ollama, inicializándolo si es necesario.

        Returns:
            Cliente de Ollama listo para usar.

        Raises:
            ImportError: Si 'ollama' no está instalado.
            RuntimeError: Si no se puede conectar al servidor.
        """
        if self._client is None:
            try:
                import ollama
            except ImportError as e:
                raise ImportError(
                    "El paquete 'ollama' no está instalado. "
                    "Instálalo con: pip install ollama\n"
                    "Descarga Ollama desde: https://ollama.com"
                ) from e

            # Configurar cliente con el host especificado
            self._client = ollama.Client(host=self.host)

            # Verificar conexión y que el modelo esté disponible (si verbose)
            if self.verbose:
                try:
                    models = self._client.list()
                    available_models = [m["name"] for m in models.get("models", [])]
                    if self.model in available_models:
                        print(f"[OllamaProvider] Modelo '{self.model}' disponible")
                    else:
                        print(
                            f"[OllamaProvider] Modelo '{self.model}' no encontrado. "
                            f"Modelos disponibles: {available_models}"
                        )
                except Exception as e:
                    if self.verbose:
                        print(f"[OllamaProvider] Advertencia al verificar modelos: {e}")

        return self._client
