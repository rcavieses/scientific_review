"""
Pipeline RAG para papers científicos.

Flujo de indexado (Fase 3):
  PDF → PDFExtractor → TextChunker → EmbeddingGenerator → VectorDBManager

Flujo de consulta (Fase 4):
  query → EmbeddingGenerator → VectorDBManager.search() → RAGQueryEngine → QueryResult
"""

from .models import ChunkData, ChunkVector, IndexStats, RAGSearchResult, QueryResult
from .pdf_extractor import PDFExtractor, PdfPlumberExtractor, PDFExtractionError
from .text_chunker import TextChunker
from .vector_db import VectorDBManager
from .rag_pipeline import RAGPipelineOrchestrator
from .query_engine import RAGQueryEngine

__version__ = "2.0.0"

__all__ = [
    # Modelos
    "ChunkData",
    "ChunkVector",
    "IndexStats",
    "RAGSearchResult",
    "QueryResult",
    # Componentes de indexado
    "PDFExtractor",
    "PdfPlumberExtractor",
    "PDFExtractionError",
    "TextChunker",
    "VectorDBManager",
    "RAGPipelineOrchestrator",
    # Fase 4: Query Engine
    "RAGQueryEngine",
]
