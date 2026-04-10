# 📊 PLAN ARQUITECTÓNICO: SISTEMA DE EMBEDDINGS PARA RAGRAPH

## Visión General

Crear un sistema de embeddings escalable que transforme artículos científicos recolectados por `scientific_search` en vectores densos para búsquedas semánticas y posterior integración con RAGraph (Retrieval-Augmented Graph).

**Objetivo:** Pasar de búsquedas por palabras clave a búsquedas semánticas inteligentes.

---

## 1️⃣ ARQUITECTURA GENERAL

### Flujo de Datos Completo

```
scientific_search (artículos)
        ↓
[InformationExtractor] → Extrae: título, resumen, palabras clave, autores, DOI
        ↓
[TextProcessor] → Normaliza y limpia texto
        ↓
[EmbeddingGenerator] → Genera embeddings (SentenceTransformers / OpenAI)
        ↓
[VectorDatabase] → Almacena (FAISS / Chroma / Weaviate / Pinecone)
        ↓
[MetadataIndex] → Indexa para búsquedas rápidas
        ↓
[EmbeddingsManager] → API unificada
        ↓
RAGraph (búsquedas semánticas + grafo de conocimiento)
```

### Componentes Principales

```
📦 pipeline/embeddings/
├── __init__.py                    # EmbeddingsManager (orquestador)
├── config.py                      # Configuración unificada
├── information_extractor.py       # Extrae campos relevantes
├── text_processor.py              # Limpia y normaliza
├── embedding_generator.py         # Interfaz + impls (Local/OpenAI/HF)
├── vector_db_manager.py           # Interfaz + impls (FAISS/Chroma/etc)
├── metadata_index.py              # Índices secundarios
│
├── models/
│   ├── faiss_manager.py           # Implementación FAISS ⭐
│   ├── chroma_manager.py          # Implementación Chroma
│   └── ...
│
└── utils/
    ├── validators.py
    └── serializers.py
```

---

## 2️⃣ COMPONENTES DETALLADOS

### Information Extractor
**Responsabilidad:** Extraer campos relevantes del objeto `Article`

```python
Entrada:  Article(title="...", authors=[...], abstract="...", ...)
           ↓
Extrae:   - title (requerido)
          - abstract (muy importante)
          - keywords
          - authors
          - journal
          - year
          - doi
          - source
           ↓
Salida:   ExtractedData(texto_limpio, metadatos)
```

### Text Processor
**Responsabilidad:** Normalizar texto para embeddings

**Estrategias:**
- `STRATEGY_TITLE_ONLY` - Solo título (rápido)
- `STRATEGY_TITLE_ABSTRACT` - Título + resumen (recomendado)
- `STRATEGY_RICH` - Título + resumen + palabras clave + autores (completo)
- `STRATEGY_MULTI_FIELD` - Múltiples embeddings por campo

### Embedding Generator
**Responsabilidad:** Generar embeddings usando diferentes modelos

#### Opción 1: Local (SentenceTransformers) ⭐ RECOMENDADO
```python
Modelo: sentence-transformers/all-MiniLM-L6-v2
Dimensión: 384
Velocidad: ~1000 textos/seg (GPU) o ~100 (CPU)
Costo: Gratis
Privacidad: Total (sin enviar datos externos)
```

**Alternativa pro:** `all-mpnet-base-v2` (dimensión 768, mejor calidad, más lento)

#### Opción 2: OpenAI API
```python
Modelo: text-embedding-3-small
Dimensión: 512
Costo: $0.02 por 1M tokens
Ventaja: Mejor calidad general
```

#### Opción 3: HuggingFace Inference
```python
Serverless, escalable
Sin instalar localmente
```

### Vector Database Manager
**Responsabilidad:** Almacenar y buscar vectores

#### Opción 1: FAISS ⭐ RECOMENDADO PARA PRODUCCIÓN
```
Ventajas:
  - Sin servidor (máxima privacidad)
  - Muy rápido (~1M vectores en <100ms)
  - Escalable (sin límites)
  - Soporte GPU

Estructura de almacenamiento:
  data/
  ├── faiss_index.bin          # Índice vectorial
  ├── metadata.json            # Metadatos
  └── doi_to_vector_id.pkl     # Mapa de búsqueda
```

#### Opción 2: Chroma
```
Ligero, moderno, simple
Bueno para prototipos y equipos pequeños
SQLite como backend
```

#### Opción 3: Weaviate
```
GraphQL, escalable
Búsquedas complejas
Ideal para RAGraph avanzado
```

#### Opción 4: Pinecone
```
Serverless, sin mantenimiento
Escalabilidad automática
Para equipos con presupuesto
```

### Metadata Index
**Responsabilidad:** Búsquedas rápidas por DOI, autor, año, etc.

```json
{
  "vector_id_001": {
    "doi": "10.1038/...",
    "title": "...",
    "authors": ["..."],
    "year": 2025,
    "journal": "...",
    "keywords": ["..."]
  }
}
```

**Índices secundarios para búsqueda rápida:**
- `doi_to_vector_id` - Búsqueda por DOI
- `author_to_vector_ids` - Búsqueda por autor
- `year_to_vector_ids` - Filtrado por año

---

## 3️⃣ API PÚBLICA (EmbeddingsManager)

```python
from pipeline.embeddings import EmbeddingsManager

# Inicializar
manager = EmbeddingsManager(config)

# Procesar artículos
count = manager.process_articles(articles: List[Article]) → int

# Búsqueda semántica
results = manager.search_similar(
    query: str,
    k: int = 10,
    filters: Dict = None
) → List[SearchResult]

# Búsqueda por DOI
article = manager.search_by_doi(doi: str) → Optional[Article]

# Estadísticas
stats = manager.get_stats() → EmbeddingStats

# Exportar para RAGraph
export = manager.export_for_ragraph(output_path: str) → Dict

# Reconstruir índices
manager.rebuild_index()
```

---

## 4️⃣ CONFIGURACIÓN

```python
@dataclass
class EmbeddingConfig:
    # Modelo de embeddings
    embedding_provider: str = "local"  # "local", "openai", "huggingface"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    embedding_fallback: Optional[str] = None  # Fallback si falla

    # Base de datos vectorial
    vector_db_type: str = "faiss"  # "faiss", "chroma", "weaviate", "pinecone"
    vector_db_path: str = "./data/vectors"  # Para local

    # Procesamiento
    text_strategy: str = "title_abstract"  # Qué campos incluir
    batch_size: int = 32
    use_gpu: bool = False

    # Filtros y búsqueda
    search_top_k: int = 10
    min_similarity_score: float = 0.3
```

**Línea de comandos integrada:**
```bash
python master_script.py --only-embeddings
python master_script.py --embedding-provider=openai --embedding-model=text-embedding-3-small
python master_script.py --vector-db=chroma
```

---

## 5️⃣ PLAN DE IMPLEMENTACIÓN (6 SEMANAS)

### Semana 1: Foundation
- [ ] Crear estructura de directorios
- [ ] Definir modelos de datos (`EmbeddedArticle`, `EmbeddingStats`)
- [ ] Implementar `InformationExtractor`
- [ ] Tests unitarios

### Semana 2-3: Generación de Embeddings
- [ ] Interfaz `EmbeddingGenerator` base
- [ ] Implementar generador local (SentenceTransformers)
- [ ] Implementar generador OpenAI (opcional)
- [ ] Tests y benchmarks

### Semana 3-4: Vector Database
- [ ] Interfaz `VectorDBManager` base
- [ ] Implementar FAISS Manager ⭐
- [ ] Implementar Metadata Index
- [ ] Agregar soporte Chroma/Weaviate (opcional)

### Semana 4-5: Orquestación
- [ ] Crear `EmbeddingsManager` (coordinador)
- [ ] Integrar en `pipeline/phase_runner.py`
- [ ] Actualizar `config_manager.py`
- [ ] Tests de integración

### Semana 5: Exportación
- [ ] Crear exportador para RAGraph
- [ ] Validar formato de salida
- [ ] Documentación

### Semana 6: Tests y Optimización
- [ ] Tests unitarios y de integración
- [ ] Benchmarks de rendimiento
- [ ] Documentación completa

---

## 6️⃣ DEPENDENCIAS

```txt
# Core
numpy>=1.21.0
sentence-transformers>=2.2.0
scikit-learn>=1.0.0

# FAISS (Vector DB)
faiss-cpu>=1.7.0  # O faiss-gpu para GPU

# Alternativas (opcional)
chromadb>=0.3.21
weaviate-client>=3.0.0
pinecone-client>=2.2.0

# OpenAI (opcional)
openai>=1.0.0

# Utilidades
python-dotenv>=0.19.0
tqdm>=4.62.0
```

**Variables de entorno (.env):**
```bash
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
VECTOR_DB_TYPE=faiss
VECTOR_DB_PATH=./data/vectors

# Si usas OpenAI
OPENAI_API_KEY=sk-...
```

---

## 7️⃣ CASOS DE USO

### Caso 1: Búsqueda Semántica Simple
```python
query = "Deep learning para predicción de pesca"
results = manager.search_similar(query, k=10)

for result in results:
    print(f"{result.title} (similitud: {result.score:.3f})")
```

### Caso 2: Búsqueda con Filtros
```python
results = manager.search_similar(
    query="Machine learning",
    k=20,
    filters={
        "year_min": 2023,
        "journal": "Nature",
        "authors_contain": "Smith"
    }
)
```

### Caso 3: Artículos Relacionados
```python
article = manager.search_by_doi("10.1038/s41598-025-93071-9")

if article:
    related = manager.search_similar(
        f"{article.title} {article.abstract}",
        k=5
    )
```

### Caso 4: Exportar para RAGraph
```python
export_data = manager.export_for_ragraph("./data/ragraph_inputs.json")

# Estructura:
# {
#     "documents": [{
#         "id": "doc_001",
#         "title": "...",
#         "content": "...",
#         "embedding": [...384-dim...],
#         "metadata": {doi, year, journal, authors, ...}
#     }],
#     "index": {...},
#     "stats": {...}
# }
```

---

## 8️⃣ MÉTRICAS DE ÉXITO

### Implementación
- [ ] Extractor obtiene 100% de campos disponibles
- [ ] Processor normaliza sin perder información
- [ ] Generator procesa 1000+ textos/min (CPU)
- [ ] Vector DB busca en < 100ms (100K docs)
- [ ] Metadata Index busca en < 10ms

### Post-Implementación
- [ ] Búsquedas semánticas devuelven resultados relevantes
- [ ] Precision@10 > 0.7 en pruebas manuales
- [ ] Índice ocupa < 500 MB para 10K artículos
- [ ] Procesamiento < 1 hora para 10K artículos
- [ ] Exportación RAGraph válida y verificable

---

## 9️⃣ RECOMENDACIONES

### Para Empezar
✅ **Opción Recomendada:**
- Embedding: `sentence-transformers/all-MiniLM-L6-v2` (local)
- Vector DB: FAISS
- Razón: Sin dependencias externas, privacidad total, escalable

### Para Producción
✅ **Pequeña escala (<50K):** FAISS local
✅ **Mediana (50K-1M):** FAISS en máquina dedicada o Chroma
✅ **Grande (>1M):** Weaviate o Pinecone serverless

### Para Máxima Calidad
✅ **Cambiar a OpenAI** si necesitas mejor precisión
✅ **Aumentar dimensión** a 768 con `all-mpnet-base-v2`
✅ **Usar estrategia RICH** incluyendo más campos

---

## 🔟 INTEGRACIÓN CON RAGRAPH

### Formato de Salida
```json
{
  "documents": [
    {
      "id": "doc_001",
      "title": "Deep Learning-Based Fishing Ground Prediction",
      "content": "Deep Learning-Based Fishing Ground Prediction... [full text]",
      "embedding": [0.123, 0.456, 0.789, ...],  // 384 dimensiones
      "metadata": {
        "doi": "10.1038/s41598-025-93071-9",
        "authors": ["M Xie", "B Liu"],
        "year": 2024,
        "journal": "Fishes",
        "source": "Google Scholar",
        "keywords": ["deep learning", "fishing", "prediction"]
      }
    }
  ],
  "index_metadata": {
    "total_documents": 1234,
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_dimension": 384,
    "vector_db_type": "faiss",
    "generation_timestamp": "2025-03-31T10:30:00Z"
  }
}
```

### Integración Completa
```
Fase 1: SearchPhase → Artículos en integrated_search.json
        ↓
Fase 2: EmbeddingsPhase → Vectores en FAISS + metadatos
        ↓
Fase 3: ExportPhase → documents.json con embeddings
        ↓
Fase 4: RAGraph → Búsquedas semánticas + grafo de conocimiento
```

---

## 📋 CHECKLIST DE INICIO

- [ ] Leer este plan completo
- [ ] Decidir: ¿Local (FAISS) o Cloud (Pinecone/Weaviate)?
- [ ] Crear estructura de directorios
- [ ] Implementar InformationExtractor
- [ ] Implementar TextProcessor
- [ ] Implementar EmbeddingGenerator local
- [ ] Implementar FAISS Manager
- [ ] Crear EmbeddingsManager orquestador
- [ ] Integrar en pipeline
- [ ] Tests y benchmarks
- [ ] Documentación
- [ ] Exportador RAGraph
- [ ] Validación final

---

## 📚 REFERENCIAS

- [Sentence Transformers](https://www.sbert.net/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss/wiki)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Chroma](https://docs.trychroma.com/)
- [Weaviate](https://weaviate.io/developers/weaviate/)
- [Pinecone](https://docs.pinecone.io/)

---

**Versión:** 1.0
**Fecha:** Marzo 31, 2025
**Status:** Plan Arquitectónico Completo ✅
