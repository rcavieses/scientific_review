"""
Modelos de datos para el pipeline de embeddings.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np


@dataclass
class ExtractedData:
    """Datos extraídos de un artículo para embedding."""

    title: str
    """Título del artículo (requerido)."""

    abstract: Optional[str] = None
    """Resumen del artículo."""

    keywords: Optional[List[str]] = None
    """Palabras clave."""

    authors: Optional[List[str]] = None
    """Lista de autores."""

    journal: Optional[str] = None
    """Nombre del journal/revista."""

    year: Optional[int] = None
    """Año de publicación."""

    doi: Optional[str] = None
    """Digital Object Identifier."""

    source: str = "unknown"
    """Fuente del artículo (crossref, pubmed, arxiv)."""

    combined_text: Optional[str] = None
    """Texto combinado listo para embedding."""

    def __post_init__(self):
        """Valida que al menos tenga título."""
        if not self.title or not self.title.strip():
            raise ValueError("El título es requerido")

    def get_combined_text(
        self,
        strategy: str = "title_abstract"
    ) -> str:
        """
        Obtiene texto combinado según estrategia.

        Args:
            strategy: Estrategia de combinación
                - "title_only": Solo título
                - "title_abstract": Título + resumen
                - "rich": Título + resumen + palabras clave + autores
                - "multi_field": Mantiene campos separados

        Returns:
            Texto combinado.
        """
        if self.combined_text and strategy != "multi_field":
            return self.combined_text

        parts = [self.title]

        if strategy in ("title_abstract", "rich"):
            if self.abstract:
                parts.append(self.abstract)

        if strategy == "rich":
            if self.keywords:
                keywords_str = ", ".join(self.keywords)
                parts.append(f"Keywords: {keywords_str}")

            if self.authors:
                authors_str = ", ".join(self.authors[:5])  # Max 5 autores
                parts.append(f"Authors: {authors_str}")

        return " ".join(parts)


@dataclass
class EmbeddingVector:
    """Resultado de un embedding."""

    vector_id: str
    """ID único del documento."""

    article_id: str
    """ID del artículo original."""

    vector: np.ndarray
    """Array de embedding (float32)."""

    text: str
    """Texto que fue embeddeado."""

    metadata: Dict[str, Any]
    """Metadatos asociados."""

    embedding_model: str
    """Modelo usado para generar el embedding."""

    created_at: datetime = field(default_factory=datetime.now)
    """Fecha de creación."""

    def get_dimension(self) -> int:
        """Obtiene la dimensión del embedding."""
        return len(self.vector)

    def get_similarity(self, other: 'EmbeddingVector') -> float:
        """
        Calcula similitud de coseno con otro embedding.

        Args:
            other: Otro EmbeddingVector.

        Returns:
            Similitud entre 0 y 1.
        """
        from sklearn.metrics.pairwise import cosine_similarity

        similarity = cosine_similarity(
            self.vector.reshape(1, -1),
            other.vector.reshape(1, -1)
        )[0][0]

        return float(similarity)


@dataclass
class SearchResult:
    """Resultado de una búsqueda semántica."""

    vector_id: str
    """ID del documento encontrado."""

    title: str
    """Título del artículo."""

    score: float
    """Score de similitud (0-1)."""

    metadata: Dict[str, Any]
    """Metadatos del artículo."""

    doi: Optional[str] = None
    """DOI si está disponible."""

    year: Optional[int] = None
    """Año de publicación."""

    source: str = "unknown"
    """Fuente del artículo."""

    def __str__(self) -> str:
        """Representación en string."""
        return (
            f"{self.title}\n"
            f"  Score: {self.score:.3f} | "
            f"Año: {self.year} | "
            f"Fuente: {self.source}"
        )


@dataclass
class EmbeddingStats:
    """Estadísticas del índice de embeddings."""

    total_documents: int
    """Número total de documentos embeddeados."""

    embedding_model: str
    """Modelo usado para embeddings."""

    embedding_dimension: int
    """Dimensión de los embeddings."""

    vector_db_type: str
    """Tipo de base de datos vectorial."""

    index_size_mb: float
    """Tamaño del índice en MB."""

    memory_used_mb: float
    """Memoria usada en MB."""

    index_age: str
    """Edad del índice (e.g., '2 days, 3 hours')."""

    last_update: datetime = field(default_factory=datetime.now)
    """Última fecha de actualización."""

    documents_by_source: Dict[str, int] = field(default_factory=dict)
    """Conteo de documentos por fuente."""

    documents_by_year: Dict[int, int] = field(default_factory=dict)
    """Conteo de documentos por año."""

    average_similarity_score: Optional[float] = None
    """Score promedio de búsquedas (estadística)."""

    def __str__(self) -> str:
        """Representación en string."""
        return (
            f"=== Estadísticas de Embeddings ===\n"
            f"Total documentos: {self.total_documents:,}\n"
            f"Modelo: {self.embedding_model}\n"
            f"Dimensión: {self.embedding_dimension}\n"
            f"Vector DB: {self.vector_db_type}\n"
            f"Tamaño índice: {self.index_size_mb:.2f} MB\n"
            f"Memoria usada: {self.memory_used_mb:.2f} MB\n"
            f"Edad del índice: {self.index_age}\n"
            f"Documentos por fuente: {self.documents_by_source}\n"
            f"Documentos por año: {self.documents_by_year}"
        )


@dataclass
class EmbeddedArticle:
    """Artículo completo con su embedding."""

    article_id: str
    """ID del artículo."""

    title: str
    """Título del artículo."""

    authors: List[str]
    """Lista de autores."""

    year: Optional[int] = None
    """Año de publicación."""

    doi: Optional[str] = None
    """DOI del artículo."""

    url: Optional[str] = None
    """URL del artículo."""

    abstract: Optional[str] = None
    """Resumen del artículo."""

    keywords: Optional[List[str]] = None
    """Palabras clave."""

    journal: Optional[str] = None
    """Journal/revista."""

    source: str = "unknown"
    """Fuente de donde viene (crossref, pubmed, arxiv)."""

    embedding_vector: Optional[np.ndarray] = None
    """Vector de embedding (si está disponible)."""

    embedding_model: Optional[str] = None
    """Modelo usado para el embedding."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Metadatos adicionales."""

    def to_search_result(self, score: float = 1.0) -> SearchResult:
        """Convierte a SearchResult."""
        return SearchResult(
            vector_id=self.article_id,
            title=self.title,
            score=score,
            metadata=self.metadata,
            doi=self.doi,
            year=self.year,
            source=self.source
        )

    def __str__(self) -> str:
        """Representación en string."""
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += f" +{len(self.authors) - 3}"

        return (
            f"{self.title}\n"
            f"  {authors_str} ({self.year})\n"
            f"  [{self.source}]"
        )
