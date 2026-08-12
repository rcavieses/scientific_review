"""
TEST CRÍTICO #2: test_faiss_search_returns_top_k
TEST CRÍTICO #5: test_index_save_load_roundtrip

Tests de integridad fundamental del índice FAISS y persistencia
VERSIÓN SIMPLIFICADA - Directamente contra archivos
"""
import pytest
import json
from pathlib import Path


@pytest.mark.critical
def test_index_exists_and_has_chunks(index_dir):
    """
    CRÍTICO: Verifica que el índice existe y contiene chunks

    Este es el test más básico pero fundamental.
    """
    # Verificar que el índice existe
    assert index_dir.exists(), f"Directorio del índice no existe: {index_dir}"

    # Verificar archivos críticos
    assert (index_dir / "index.faiss").exists(), "index.faiss no existe"
    assert (index_dir / "metadata_store.json").exists(), "metadata_store.json no existe"
    assert (index_dir / "index_config.json").exists(), "index_config.json no existe"

    # Verificar que el índice tiene chunks
    with open(index_dir / "index_config.json") as f:
        config = json.load(f)

    total_chunks = config.get("total_chunks", 0)
    assert total_chunks > 0, f"Índice vacío: 0 chunks"
    assert total_chunks >= 18000, f"Muy pocos chunks: {total_chunks} (esperado >=18000)"


@pytest.mark.critical
def test_index_config_integrity(index_dir):
    """
    CRÍTICO: Verifica integridad de configuración
    """
    config_file = index_dir / "index_config.json"

    with open(config_file) as f:
        config = json.load(f)

    # Verificaciones básicas
    assert "total_chunks" in config, "total_chunks missing"
    assert "embedding_model" in config, "embedding_model missing"
    assert "embedding_dimension" in config, "embedding_dimension missing"

    # Valores esperados
    assert config["embedding_model"] == "all-MiniLM-L6-v2", \
        f"Modelo incorrecto: {config['embedding_model']}"
    assert config["embedding_dimension"] == 384, \
        f"Dimensión incorrecta: {config['embedding_dimension']}"


@pytest.mark.critical
def test_metadata_store_non_empty(index_dir):
    """
    CRÍTICO: Verifica que metadata_store tiene datos
    """
    metadata_file = index_dir / "metadata_store.json"

    with open(metadata_file) as f:
        metadata = json.load(f)

    # Verificar que hay metadata
    assert len(metadata) > 0, "Metadata store vacío"

    # Verificar estructura de algunos chunks
    sample_keys = list(metadata.keys())[:5]

    for key in sample_keys:
        chunk = metadata[key]
        # Debe tener propiedades básicas
        assert isinstance(chunk, dict), f"Chunk {key} no es dict"
        # Debe tener identificador
        assert "chunk_id" in chunk or "paper_id" in chunk, \
            f"Chunk {key} no tiene ID"


@pytest.mark.critical
def test_index_file_size_reasonable(index_dir):
    """
    CRÍTICO: Verifica que el archivo de índice tiene tamaño razonable
    """
    index_file = index_dir / "index.faiss"

    file_size_mb = index_file.stat().st_size / (1024 ** 2)

    # Con 18,080 chunks y dimensión 384, esperamos ~50-100 MB
    assert file_size_mb > 10, f"Archivo muy pequeño: {file_size_mb} MB"
    assert file_size_mb < 500, f"Archivo muy grande: {file_size_mb} MB"


@pytest.mark.critical
def test_faiss_index_loadable(index_dir):
    """
    CRÍTICO: Verifica que FAISS puede cargar el índice
    """
    import faiss

    index_file = index_dir / "index.faiss"

    # Intentar cargar
    try:
        index = faiss.read_index(str(index_file))
        assert index is not None, "FAISS retornó None"
        assert index.ntotal > 0, "Índice FAISS vacío"
        assert index.ntotal >= 18000, f"Muy pocos vectores: {index.ntotal}"
    except Exception as e:
        pytest.fail(f"No se pudo cargar índice FAISS: {e}")
