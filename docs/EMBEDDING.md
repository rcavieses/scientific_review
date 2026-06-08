# Sistema de Embeddings para GraphRAG

## Visión General

El sistema de embeddings transforma artículos científicos en vectores densos para búsquedas semánticas inteligentes, habilitando el pipeline GraphRAG.

**Antes:** búsqueda por palabras clave (imprecisa)  
**Después:** búsqueda semántica que entiende significado

## Arquitectura

```
scientific_search (artículos)
        ↓
[InformationExtractor] → título, resumen, palabras clave, autores, DOI
        ↓
[TextProcessor] → normaliza y limpia texto
        ↓
[EmbeddingGenerator] → vectores 384 dims (SentenceTransformers / OpenAI)
        ↓
[VectorDBManager] → FAISS index (local, rápido, privado)
        ↓
[MetadataRegistry] → indexa DOI → vector_id, autor → vector_ids, año
        ↓
RAGQueryEngine / GraphQueryEngine
```

### Módulos (`pipeline/embeddings/`)

| Módulo | Responsabilidad |
|--------|----------------|
| `information_extractor.py` | Extrae campos de objetos `Article` |
| `text_processor.py` | Normaliza texto para embedding |
| `embedding_generator.py` | Genera vectores (Local/OpenAI/HuggingFace) |
| `models.py` | Modelos de datos: `ExtractedData`, `EmbeddingVector`, etc. |

## Configuración

```python
# Opción recomendada — privacidad total, sin costo
embedding_provider = "local"
embedding_model    = "all-MiniLM-L6-v2"   # 384 dims
vector_db_type     = "faiss"

# Alternativa — mayor calidad
embedding_provider = "openai"
embedding_model    = "text-embedding-3-small"  # 512 dims, ~$0.02/1M tokens
```

Variables de entorno (`.env`):
```bash
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
VECTOR_DB_TYPE=faiss
OPENAI_API_KEY=sk-...   # solo si provider=openai
```

## Uso Rápido

```python
from scientific_search import ScientificArticleSearcher
from pipeline.embeddings import InformationExtractor, TextProcessor
from pipeline.embeddings.embedding_generator import get_embedding_generator

# 1. Buscar artículos
searcher = ScientificArticleSearcher()
results = searcher.search("Sardinops sagax Gulf of California", max_results=50)

# 2. Extraer información
extractor = InformationExtractor()
extracted, errors = extractor.extract_from_multiple(results.articles)

# 3. Procesar texto
processor = TextProcessor(strategy="title_abstract")
texts = processor.process_multiple(extracted)

# 4. Generar embeddings
gen = get_embedding_generator(provider="local")
embeddings = gen.batch_generate(texts, batch_size=32)
print(f"Shape: {embeddings.shape}")  # (n, 384)
```

## Modelos Disponibles

### Local (SentenceTransformers)
| Modelo | Dims | Velocidad | Calidad |
|--------|------|-----------|---------|
| all-MiniLM-L6-v2 | 384 | ⚡⚡⚡ | Buena |
| all-mpnet-base-v2 | 768 | ⚡⚡ | Muy buena |
| multilingual-e5-small | 384 | ⚡⚡⚡ | Buena (multilingüe) |

### OpenAI
| Modelo | Dims | Costo | Calidad |
|--------|------|-------|---------|
| text-embedding-3-small | 512 | $ | Muy buena |
| text-embedding-3-large | 3072 | $$ | Excelente |

## Rendimiento Esperado

| Métrica | Valor |
|---------|-------|
| Procesamiento 10K artículos (CPU) | < 10 min |
| Procesamiento 10K artículos (GPU) | < 1 min |
| Búsqueda en 100K artículos | < 100 ms |
| Tamaño índice 10K artículos | ~100 MB |

## Indexación Paralela para corpus grande

Para el corpus de ~42K PDFs se usa `indexar_paralelo.py` con `ProcessPoolExecutor`:

```bash
# Fase 1: Indexar en batches paralelos (8 workers)
python indexar_paralelo.py --workers 8 --batch-size 500

# Fase 2: Fusionar índices batch en índice maestro
python merge_indices.py

# Monitor de progreso (terminal separada)
python monitor_indexacion.py
```

La estrategia mixta de optimización combina:
- Provider local (2-3x más rápido que Ollama)
- Chunk size 1024 (30% menos embeddings)
- 8 procesos paralelos
- Índices temporales por batch (evita contención de locks)

Resultado: ~13 días para 42K PDFs en CPU, vs. 3+ meses single-thread.
