"""
Pytest fixtures para suite de testing RAG
"""
import pytest
import json
import tempfile
from pathlib import Path
import numpy as np
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def index_dir():
    """Directorio del índice RAG actual"""
    return PROJECT_ROOT / "outputs" / "rag_index_goc_full"


@pytest.fixture(scope="session")
def pdf_dir():
    """Directorio de PDFs"""
    return PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"


@pytest.fixture
def temp_index_dir():
    """Directorio temporal para tests de índice"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def vector_db_manager(index_dir):
    """VectorDBManager con índice actual cargado"""
    try:
        from pipeline.rag.vector_db import VectorDBManager

        vdb = VectorDBManager(
            index_dir=str(index_dir),
            embedding_dim=384
        )
        vdb.load()
        return vdb
    except Exception as e:
        pytest.skip(f"No se pudo cargar índice: {e}")


@pytest.fixture
def embedding_generator():
    """EmbeddingGenerator local"""
    try:
        from pipeline.embeddings.embedding_generator import get_embedding_generator

        generator = get_embedding_generator(
            model="all-MiniLM-L6-v2",
            provider="local"
        )
        return generator
    except Exception as e:
        pytest.skip(f"No se pudo cargar embedding generator: {e}")


@pytest.fixture
def test_queries():
    """Queries de prueba estándar"""
    return {
        "species_query": "Lutjanus peru parámetros poblacionales Golfo de California",
        "ecology_query": "biodiversidad marina arrecifes coralinos",
        "reproduction_query": "población talla madurez reproducción peces",
        "migration_query": "especies pelágicas migratorias Pacífico",
        "predators_query": "dinámica poblacional depredadores marinos",
    }


@pytest.fixture
def sample_metadata():
    """Metadatos de prueba"""
    return {
        "chunk_id": "test_paper_chunk_001",
        "paper_id": "test_paper",
        "source_pdf": "/path/to/test.pdf",
        "page_number": 1,
        "char_start": 0,
        "char_end": 100,
        "title": "Test Paper Title",
        "authors": ["Test Author 1", "Test Author 2"],
        "year": 2024,
        "doi": "10.1234/test.doi",
    }


@pytest.fixture
def index_config(index_dir):
    """Cargar configuración actual del índice"""
    config_file = index_dir / "index_config.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return None


@pytest.fixture
def index_snapshot(index_dir):
    """
    Captura estado actual del índice para regression testing
    Retorna: (total_chunks, ntotal_before)
    """
    try:
        from pipeline.rag.vector_db import VectorDBManager

        vdb = VectorDBManager(str(index_dir), embedding_dim=384)
        vdb.load()

        stats = vdb.get_stats()
        return {
            "total_chunks_before": stats.get("total_chunks", 0),
            "ntotal_before": stats.get("ntotal", 0),
            "metadata_count_before": len(vdb.metadata) if hasattr(vdb, 'metadata') else 0,
        }
    except Exception as e:
        pytest.skip(f"No se pudo capturar snapshot: {e}")


# Marcadores personalizados
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "critical: tests críticos para estabilidad core"
    )
    config.addinivalue_line(
        "markers", "integration: tests de integración pipeline"
    )
    config.addinivalue_line(
        "markers", "quality: tests de calidad de contenido"
    )
    config.addinivalue_line(
        "markers", "slow: tests que tardan >2 segundos"
    )
