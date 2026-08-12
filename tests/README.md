# Suite de Tests RAG - Golfo de California

## Tests Críticos (7 tests)

Implementación rápida de tests CRÍTICOS para validar funcionalidad core.

### Tests Implementados

| # | Test | Archivo | Criticidad |
|---|------|---------|-----------|
| 2 | test_faiss_search_returns_top_k | unit/test_critical_faiss.py | 🔴 CRÍTICA |
| 5 | test_index_save_load_roundtrip | unit/test_critical_faiss.py | 🔴 CRÍTICA |
| 7 | test_pdf_to_chunks_to_vectors_pipeline | integration/test_critical_pipeline.py | 🔴 CRÍTICA |
| 11 | test_llm_call_success_with_retrieved_chunks | integration/test_critical_pipeline.py | 🔴 CRÍTICA |
| 12 | test_species_name_query_retrieves_species_content | quality/test_critical_content.py | 🔴 CRÍTICA |
| 16 | test_answer_statements_traceable_to_chunks | quality/test_critical_content.py | 🔴 CRÍTICA |
| 20 | test_new_pdfs_dont_degrade_existing_retrieval | quality/test_critical_content.py | 🔴 CRÍTICA |

## Ejecución

### Ejecutar solo tests CRÍTICOS (rápido ~5-10 min)
```bash
cd /home/atlantis/scientific_review
pytest tests -m critical -v --tb=short
```

### Ejecutar con details
```bash
pytest tests -m critical -v --tb=long --capture=no
```

### Ejecutar un test específico
```bash
pytest tests/unit/test_critical_faiss.py::test_faiss_search_returns_top_k -v
```

### Ejecutar con coverage
```bash
pytest tests -m critical --cov=pipeline --cov-report=html
```

### Ejecutar en modo strict (cualquier warning = error)
```bash
pytest tests -m critical -v --strict-markers -W error
```

## Estructura

```
tests/
├── conftest.py                          # Fixtures compartidas
├── pytest.ini                           # Configuración
├── README.md                            # Este archivo
├── unit/
│   ├── __init__.py
│   └── test_critical_faiss.py          # Tests #2, #5
├── integration/
│   ├── __init__.py
│   └── test_critical_pipeline.py       # Tests #7, #11
└── quality/
    ├── __init__.py
    └── test_critical_content.py        # Tests #12, #16, #20
```

## Fixtures Disponibles

### index_dir
Directorio del índice RAG actual
```python
def test_example(index_dir):
    assert (index_dir / "index.faiss").exists()
```

### vector_db_manager
VectorDBManager con índice cargado
```python
def test_example(vector_db_manager):
    results = vector_db_manager.search(embedding, top_k=5)
```

### embedding_generator
EmbeddingGenerator local (all-MiniLM-L6-v2)
```python
def test_example(embedding_generator):
    embedding = embedding_generator.encode("query text")
```

### test_queries
Queries estándar de prueba
```python
def test_example(test_queries):
    query = test_queries["species_query"]
```

### index_snapshot
Captura del estado actual del índice
```python
def test_example(index_snapshot):
    chunks_before = index_snapshot["total_chunks_before"]
```

## Success Criteria

✓ **test_faiss_search_returns_top_k**: Returns exactly k results, sorted by score
✓ **test_index_save_load_roundtrip**: 100% data preservation after save/load
✓ **test_pdf_to_chunks_to_vectors_pipeline**: 18,080+ chunks indexed correctly
✓ **test_llm_call_success_with_retrieved_chunks**: Claude API generates answer
✓ **test_species_name_query_retrieves_species_content**: Top result score > 0.6
✓ **test_answer_statements_traceable_to_chunks**: Answer grounded in sources
✓ **test_new_pdfs_dont_degrade_existing_retrieval**: Consistency check passes

## Próximos Pasos

Después de tests CRÍTICOS exitosos:

1. **Implementar tests ALTOS** (9 tests, ~1-2h)
   - Tests de embeddings
   - Tests multilingües  
   - Tests de performance

2. **Implementar tests MEDIA** (4 tests, ~1h)
   - Edge cases
   - Robustness

3. **CI/CD Integration**
   - GitHub Actions
   - Pre-commit hooks
   - Automated testing on commits
