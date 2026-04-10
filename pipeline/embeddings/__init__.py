"""
Pipeline de embeddings para artículos científicos.

Este módulo proporciona funcionalidad para:
- Extraer información de artículos
- Procesar texto para embeddings
- Generar embeddings usando diferentes modelos
- Almacenar y buscar en bases de datos vectoriales
- Exportar para RAGraph
"""

from .models import (
    ExtractedData,
    EmbeddingVector,
    SearchResult,
    EmbeddingStats,
    EmbeddedArticle,
)

from .information_extractor import InformationExtractor
from .text_processor import TextProcessor

__version__ = "1.0.0"

__all__ = [
    # Modelos
    "ExtractedData",
    "EmbeddingVector",
    "SearchResult",
    "EmbeddingStats",
    "EmbeddedArticle",
    # Componentes
    "InformationExtractor",
    "TextProcessor",
]
