"""
Pipeline RAG para papers científicos.

Flujo:
  PDF → PDFExtractor → TextChunker → EmbeddingGenerator → VectorDBManager

Para búsqueda semántica posterior (RAG query engine, fase futura):
  query → EmbeddingGenerator → VectorDBManager.search() → RAGSearchResult[]
"""

from .models import ChunkData, ChunkVector, IndexStats, RAGSearchResult
from .pdf_extractor import PDFExtractor, PdfPlumberExtractor, PDFExtractionError
from .text_chunker import TextChunker
from .vector_db import VectorDBManager
from .rag_pipeline import RAGPipelineOrchestrator

__version__ = "1.0.0"

__all__ = [
    # Modelos
    "ChunkData",
    "ChunkVector",
    "IndexStats",
    "RAGSearchResult",
    # Componentes
    "PDFExtractor",
    "PdfPlumberExtractor",
    "PDFExtractionError",
    "TextChunker",
    "VectorDBManager",
    "RAGPipelineOrchestrator",
]
