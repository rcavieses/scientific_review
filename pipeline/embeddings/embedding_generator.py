"""
Generadores de embeddings para diferentes modelos y APIs.

Proporciona interfaz base y implementaciones específicas para:
- Local: SentenceTransformers
- OpenAI: API de OpenAI (opcional)
- HuggingFace: Inference API (opcional)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import numpy as np
from pathlib import Path
import logging


logger = logging.getLogger(__name__)

# Importar dependencias opcionales para que puedan ser mockeadas en tests
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class EmbeddingGenerator(ABC):
    """
    Interfaz base para generadores de embeddings.

    Define la API que deben cumplir todos los generadores,
    independientemente de la fuente (local, API, etc.)
    """

    @abstractmethod
    def generate(self, texts: List[str]) -> np.ndarray:
        """
        Genera embeddings para una lista de textos.

        Args:
            texts: Lista de textos a embedificar.

        Returns:
            Array numpy de shape (len(texts), dimension)
            con dtype float32.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Retorna la dimensión de los embeddings.

        Returns:
            Número de dimensiones (ej: 384, 512, 768, etc.)
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Retorna el nombre del modelo usado.

        Returns:
            Nombre del modelo (ej: "all-MiniLM-L6-v2")
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """
        Obtiene información del generador.

        Returns:
            Diccionario con información.
        """
        return {
            "model": self.get_model_name(),
            "dimension": self.get_dimension(),
            "type": self.__class__.__name__
        }

    def batch_generate(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Genera embeddings en batches (más eficiente para grandes datasets).

        Args:
            texts: Lista de textos a embedificar.
            batch_size: Tamaño de cada batch.
            show_progress: Mostrar barra de progreso.

        Returns:
            Array numpy de embeddings.
        """
        all_embeddings = []

        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.generate(batch)
            all_embeddings.append(batch_embeddings)

            if show_progress:
                current_batch = (i // batch_size) + 1
                print(f"  Procesados {current_batch}/{total_batches} batches")

        # Concatenar todos los embeddings
        result = np.vstack(all_embeddings)
        return result

    @staticmethod
    def cosine_similarity(
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Calcula similitud de coseno entre dos embeddings.

        Args:
            embedding1: Primer embedding (1D array).
            embedding2: Segundo embedding (1D array).

        Returns:
            Similitud entre -1 y 1.
        """
        # Normalizar a 1D si es necesario
        e1 = embedding1.flatten()
        e2 = embedding2.flatten()

        # Calcular producto punto y normas
        dot_product = np.dot(e1, e2)
        norm1 = np.linalg.norm(e1)
        norm2 = np.linalg.norm(e2)

        # Evitar división por cero
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(similarity)


class LocalEmbeddingGenerator(EmbeddingGenerator):
    """
    Generador de embeddings usando SentenceTransformers localmente.

    No requiere API keys, máxima privacidad,
    puede usar GPU si está disponible.

    Modelos recomendados:
    - "all-MiniLM-L6-v2" (384 dims, rápido)
    - "all-mpnet-base-v2" (768 dims, mejor calidad)
    - "multilingual-e5-small" (384 dims, multilingüe)
    """

    # Mapeo de modelos a dimensiones
    MODEL_DIMENSIONS = {
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "all-mpnet-base-v1": 768,
        "all-distilroberta-v1": 768,
        "multilingual-e5-small": 384,
        "multilingual-e5-base": 768,
        "multilingual-e5-large": 1024,
        "paraphrase-MiniLM-L6-v2": 384,
        "paraphrase-mpnet-base-v2": 768,
    }

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        cache_folder: Optional[str] = None,
        normalize_embeddings: bool = True,
        verbose: bool = False
    ):
        """
        Inicializa el generador local.

        Args:
            model_name: Nombre del modelo SentenceTransformer.
            device: "cpu" o "cuda" (detecta automáticamente si hay GPU).
            cache_folder: Folder para cachear modelos descargados.
            normalize_embeddings: Normalizar a unit norm (importante para similitud).
            verbose: Mostrar mensajes de debug.

        Raises:
            ImportError: Si SentenceTransformers no está instalado.
            ValueError: Si model_name no es reconocido.
        """
        if SentenceTransformer is None:
            raise ImportError(
                "SentenceTransformers no está instalado. "
                "Instala con: pip install sentence-transformers"
            )

        self.model_name = model_name
        self.device = device
        self.cache_folder = cache_folder
        self.normalize_embeddings = normalize_embeddings
        self.verbose = verbose

        # Validar modelo
        if model_name not in self.MODEL_DIMENSIONS:
            logger.warning(
                f"Modelo '{model_name}' no está en lista conocida. "
                f"Dimensión se determinará al cargar."
            )

        # Auto-detectar GPU
        if device == "cpu":
            try:
                import torch
                if torch.cuda.is_available():
                    self.device = "cuda"
                    if verbose:
                        print(f"GPU detectada, usando: {torch.cuda.get_device_name(0)}")
            except ImportError:
                pass

        # Cargar modelo
        if verbose:
            print(f"Cargando modelo: {model_name}")

        try:
            self.model = SentenceTransformer(
                model_name,
                device=self.device,
                cache_folder=cache_folder
            )

            if verbose:
                print(f"Modelo cargado en: {self.device}")

        except Exception as e:
            raise ValueError(
                f"Error cargando modelo '{model_name}': {str(e)}"
            )

    def generate(self, texts: List[str]) -> np.ndarray:
        """
        Genera embeddings para textos.

        Args:
            texts: Lista de textos.

        Returns:
            Array numpy de embeddings (float32).
        """
        if not texts:
            raise ValueError("Lista de textos vacía")

        # Codificar textos
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=self.verbose
        )

        # Asegurar tipo float32
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32)

        return embeddings

    def get_dimension(self) -> int:
        """Retorna dimensión del modelo."""
        if self.model_name in self.MODEL_DIMENSIONS:
            return self.MODEL_DIMENSIONS[self.model_name]

        # Si no está en la lista conocida, obtener del modelo
        try:
            return self.model.get_sentence_embedding_dimension()
        except Exception:
            # Fallback: hacer embedding de prueba
            test_embedding = self.model.encode("test", convert_to_numpy=True)
            return len(test_embedding)

    def get_model_name(self) -> str:
        """Retorna nombre del modelo."""
        return self.model_name

    def get_info(self) -> Dict[str, Any]:
        """Obtiene información completa del generador."""
        info = super().get_info()
        info.update({
            "device": self.device,
            "normalize_embeddings": self.normalize_embeddings,
            "dimension": self.get_dimension()
        })
        return info


class OpenAIEmbeddingGenerator(EmbeddingGenerator):
    """
    Generador de embeddings usando OpenAI API.

    Requiere API key de OpenAI.
    Modelos disponibles:
    - "text-embedding-3-small" (512 dims, más barato)
    - "text-embedding-3-large" (3072 dims, mejor calidad)
    - "text-embedding-ada-002" (1536 dims, legacy)
    """

    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 512,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Inicializa el generador OpenAI.

        Args:
            model_name: Modelo a usar.
            api_key: API key de OpenAI (si no, usa OPENAI_API_KEY env).
            verbose: Mostrar mensajes de debug.

        Raises:
            ImportError: Si openai no está instalado.
            ValueError: Si no hay API key disponible.
        """
        if OpenAI is None:
            raise ImportError(
                "OpenAI SDK no está instalado. "
                "Instala con: pip install openai"
            )

        self.model_name = model_name
        self.verbose = verbose

        # Obtener API key
        if not api_key:
            import os
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY no definida. "
                "Proporciona api_key o set OPENAI_API_KEY env variable."
            )

        self.client = OpenAI(api_key=api_key)

        if verbose:
            print(f"OpenAI client inicializado con modelo: {model_name}")

    def generate(self, texts: List[str]) -> np.ndarray:
        """
        Genera embeddings usando OpenAI API.

        Args:
            texts: Lista de textos (máximo 2000 por request).

        Returns:
            Array numpy de embeddings.
        """
        if not texts:
            raise ValueError("Lista de textos vacía")

        # OpenAI tiene límite de 2000 items por request
        if len(texts) > 2000:
            logger.warning(
                f"Más de 2000 textos. Procesando en múltiples requests."
            )
            return self.batch_generate(texts, batch_size=2000)

        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.model_name
            )

            # Extraer embeddings
            embeddings = np.array(
                [item.embedding for item in response.data],
                dtype=np.float32
            )

            return embeddings

        except Exception as e:
            raise RuntimeError(f"Error en OpenAI API: {str(e)}")

    def get_dimension(self) -> int:
        """Retorna dimensión del modelo."""
        if self.model_name in self.MODEL_DIMENSIONS:
            return self.MODEL_DIMENSIONS[self.model_name]

        raise ValueError(f"Modelo desconocido: {self.model_name}")

    def get_model_name(self) -> str:
        """Retorna nombre del modelo."""
        return self.model_name


def get_embedding_generator(
    provider: str = "local",
    model: Optional[str] = None,
    verbose: bool = False,
    **kwargs
) -> EmbeddingGenerator:
    """
    Factory function para obtener un generador de embeddings.

    Args:
        provider: "local", "openai", o "huggingface".
        model: Nombre del modelo (defaults según provider).
        verbose: Mostrar mensajes.
        **kwargs: Argumentos adicionales para el generador.

    Returns:
        Instancia de EmbeddingGenerator.

    Raises:
        ValueError: Si provider no es válido.
    """
    if provider == "local":
        model = model or "all-MiniLM-L6-v2"
        return LocalEmbeddingGenerator(model, verbose=verbose, **kwargs)

    elif provider == "openai":
        model = model or "text-embedding-3-small"
        return OpenAIEmbeddingGenerator(model, verbose=verbose, **kwargs)

    else:
        raise ValueError(
            f"Provider inválido: {provider}. "
            f"Opciones: 'local', 'openai'"
        )
