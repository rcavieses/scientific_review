"""
Modelos de datos para el pipeline RAG de papers científicos.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any, TYPE_CHECKING

import numpy as np


@dataclass
class ChunkData:
    """Un chunk de texto extraído de un PDF científico."""

    chunk_id: str
    """Identificador único: '{paper_id}_chunk_{index:03d}'"""

    paper_id: str
    """Derivado del nombre del archivo PDF (sin extensión, normalizado)."""

    text: str
    """Texto del chunk."""

    chunk_index: int
    """Posición ordinal del chunk en el paper (0-based)."""

    page_number: int
    """Página de origen (1-based). -1 si no se puede determinar."""

    char_start: int
    """Posición de inicio en el texto completo del paper."""

    char_end: int
    """Posición de fin en el texto completo del paper."""

    total_chunks: int
    """Total de chunks generados para este paper."""

    source_pdf: str
    """Ruta al PDF fuente (relativa al directorio del proyecto)."""

    title: Optional[str] = None
    """Título del artículo (si se pudo vincular al metadato)."""

    authors: Optional[List[str]] = None
    """Autores del artículo."""

    year: Optional[int] = None
    """Año de publicación."""

    doi: Optional[str] = None
    """DOI del artículo."""

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario compatible con JSON."""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkData":
        """Deserializa desde diccionario."""
        return cls(**data)

    def __len__(self) -> int:
        return len(self.text)

    def __str__(self) -> str:
        return (
            f"ChunkData(id={self.chunk_id}, page={self.page_number}, "
            f"chars={len(self.text)}, paper={self.paper_id})"
        )


@dataclass
class ChunkVector:
    """Chunk de texto con su vector de embedding."""

    chunk: ChunkData
    """Datos del chunk."""

    vector: np.ndarray
    """Vector float32, shape (embedding_dim,)."""

    embedding_model: str
    """Nombre del modelo usado para generar el embedding."""

    faiss_id: int = -1
    """ID asignado por FAISS (entero auto-incremental). -1 antes de insertar."""

    def __str__(self) -> str:
        return (
            f"ChunkVector(id={self.chunk.chunk_id}, faiss_id={self.faiss_id}, "
            f"dim={self.vector.shape[0]})"
        )


@dataclass
class IndexStats:
    """Estadísticas del índice FAISS."""

    total_chunks: int
    """Total de chunks almacenados en el índice."""

    total_papers: int
    """Número de papers distintos indexados."""

    embedding_model: str
    """Modelo de embedding usado."""

    embedding_dimension: int
    """Dimensión de los vectores."""

    index_size_mb: float
    """Tamaño del archivo index.faiss en MB."""

    index_path: str
    """Ruta al directorio del índice."""

    last_updated: datetime
    """Fecha y hora de la última actualización."""

    def __str__(self) -> str:
        return (
            f"IndexStats({self.total_chunks} chunks, {self.total_papers} papers, "
            f"dim={self.embedding_dimension}, {self.index_size_mb:.1f} MB)"
        )


@dataclass
class RAGSearchResult:
    """Resultado de búsqueda semántica sobre el índice FAISS."""

    chunk_id: str
    """ID del chunk recuperado."""

    paper_id: str
    """ID del paper del que proviene el chunk."""

    text: str
    """Texto del chunk."""

    score: float
    """Similitud coseno (0.0 a 1.0). Mayor = más relevante."""

    page_number: int
    """Página del paper donde se encuentra el chunk."""

    chunk_index: int
    """Posición ordinal del chunk en el paper."""

    source_pdf: str
    """Ruta al PDF fuente."""

    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None

    def __str__(self) -> str:
        authors_str = ", ".join(self.authors[:2]) if self.authors else "N/A"
        if self.authors and len(self.authors) > 2:
            authors_str += " et al."
        return (
            f"[{self.score:.3f}] {self.chunk_id} | p.{self.page_number}\n"
            f"  {self.title or self.paper_id} ({self.year or 'N/A'}) — {authors_str}\n"
            f"  {self.text[:120]}..."
        )


@dataclass
class QueryResult:
    """Resultado completo de una consulta al RAG Query Engine."""

    question: str
    """Pregunta original del usuario."""

    answer: str
    """Respuesta generada por Claude con base en los chunks recuperados."""

    sources: List[RAGSearchResult]
    """Chunks recuperados de FAISS usados para construir el contexto."""

    chunks_used: int
    """Número de chunks incluidos en el contexto enviado a Claude."""

    model: str
    """ID del modelo de Claude usado para generar la respuesta."""

    timestamp: datetime = field(default_factory=datetime.now)
    """Momento en que se generó la respuesta."""

    def format_sources(self) -> str:
        """Devuelve un bloque de texto con las fuentes citadas, listo para mostrar."""
        if not self.sources:
            return "Sin fuentes."
        lines = []
        seen_papers: set = set()
        for r in self.sources:
            if r.paper_id in seen_papers:
                continue
            seen_papers.add(r.paper_id)
            authors_str = ", ".join(r.authors[:2]) if r.authors else "N/A"
            if r.authors and len(r.authors) > 2:
                authors_str += " et al."
            lines.append(
                f"  • {r.title or r.paper_id} ({r.year or 'N/A'}) — {authors_str}"
            )
        return "\n".join(lines)

    def __str__(self) -> str:
        return (
            f"Pregunta: {self.question}\n\n"
            f"{self.answer}\n\n"
            f"Fuentes ({len(set(r.paper_id for r in self.sources))} papers):\n"
            f"{self.format_sources()}"
        )
