# 🚀 Sistema RAG Optimizado - Reconstrucción Exhaustiva

## Visión General

Este documento describe la **reconstrucción completa y optimizada** del sistema RAG para consulta de parámetros poblacionales de especies marinas del Golfo de California.

**Entrada**: 433 PDFs científicos (843 MB)  
**Salida**: Índice FAISS optimizado + Metadatos enriquecidos + Retrieval inteligente

---

## 📋 Las 4 Fases de Reconstrucción

### FASE 0️⃣: Limpieza y Validación ✅
**Archivo**: `scripts/phase_0_cleanup_and_validate.py`

**Objetivos**:
- Eliminar índices viejos e incompletos
- Validar que los 433 PDFs sean accesibles
- Probar GROBID en muestra de 10 PDFs
- Validar extracción de metadatos
- Generar reporte de calidad

**Salida**:
- `reports/phase_0_validation_report.json` → Estado de validación
- `logs/phase_0_validation.log` → Detalles de ejecución

**Duración estimada**: 2-3 minutos

---

### FASE 1️⃣: Reconstrucción de Índice 📦
**Archivo**: `scripts/phase_1_rebuild_index_optimized.py`

**Objetivos**:
- Extracción GROBID de todos los PDFs (con fallback a pdfplumber)
- Chunking semántico inteligente
  - Divide por párrafos y oraciones
  - Preserva contexto semántico
  - Tamaño: 2000 caracteres con 200 caracteres de overlap
- Generación de embeddings (all-MiniLM-L6-v2, 384 dimensiones)
- Indexación FAISS (FlatIP para similitud coseno)

**Componentes utilizados**:
```python
TextChunker:
  - chunk_size: 2000 chars
  - overlap: 200 chars
  - min_chunk_size: 100 chars

EmbeddingGenerator:
  - model: all-MiniLM-L6-v2
  - dimension: 384
  - provider: local

VectorDBManager:
  - index_type: FlatIP (cosine similarity)
  - batch_size: 64
```

**Salida**:
- `outputs/rag_index_goc_full/index.faiss` → Índice binario de vectores
- `outputs/rag_index_goc_full/metadata_store.json` → Metadatos de chunks
- `outputs/rag_index_goc_full/index_config.json` → Configuración del índice
- `reports/phase_1_rebuild_stats.json` → Estadísticas de indexación

**Duración estimada**: 15-20 minutos para 433 PDFs

**Resultado esperado**:
- ~10,500+ chunks
- Tamaño del índice: ~15-20 MB
- 0 errores de extracción

---

### FASE 2️⃣: Enriquecimiento de Metadatos 📚
**Archivo**: `scripts/phase_2_enrich_metadata.py`

**Objetivos**:
- Extraer de cada PDF:
  - Título del artículo
  - Autores
  - Año de publicación
  - DOI
  - Abstract (primeras 500 caracteres)
- Agregar esta información a cada chunk
- Validar completitud de metadatos

**Campos añadidos a cada chunk**:
```json
{
  "metadata": {
    "source_pdf": "Nevares2026.pdf",
    "paper_title": "Dinámica poblacional del pargo rojo...",
    "paper_authors": ["Nevares, J.", "López, M."],
    "paper_year": 2026,
    "paper_doi": "10.1234/xxx"
  }
}
```

**Salida**:
- `outputs/rag_index_goc_full/metadata_store.json` (actualizado)
- `reports/phase_2_metadata_enrichment.json` → Estadísticas de enriquecimiento

**Duración estimada**: 5-10 minutos

**Resultado esperado**:
- >95% de chunks con título
- >90% de chunks con autores
- >85% de chunks con año
- 20-30% de chunks con DOI

---

### FASE 3️⃣: Optimización de Retrieval 🔧
**Archivo**: `scripts/phase_3_optimize_retrieval.py`

**Objetivos**:
- Validar integridad del índice
- Detectar chunks duplicados o muy similares
- Implementar re-ranking inteligente
- Probar retrieval con 5 queries de ejemplo
- Generar métricas de calidad

**Re-ranking implementado**:
```
final_score = 
  + similitud_semántica (base: 0-1)
  + bonus_metadatos (titulo: +0.02, autores: +0.02, año: +0.02, doi: +0.01)
  + bonus_recencia ((año - 2000) * 0.001)
```

**Queries de prueba**:
1. "parámetros poblacionales pargo rojo Golfo de California"
2. "biodiversidad marina arrecifes coralinos"
3. "población talla madurez reproducción peces"
4. "especies pelágicas migratorias Pacífico"
5. "dinámica poblacional depredadores marinos"

**Salida**:
- `reports/phase_3_retrieval_optimization.json` → Resultados de optimización
- `logs/phase_3_retrieval.log` → Detalles de ejecución

**Duración estimada**: 3-5 minutos

**Resultado esperado**:
- Índice íntegro y validado
- >95% de queries exitosas
- Re-ranking funcionando correctamente

---

## 🚀 Cómo Ejecutar

### Opción A: Ejecución Completa (Recomendado)
```bash
cd /home/atlantis/scientific_review
python3 scripts/run_exhaustive_rebuild.py
```

**Tiempo total**: ~25-40 minutos
**Resultado**: Sistema RAG completamente reconstruido y optimizado

### Opción B: Ejecutar una Fase Específica
```bash
# Solo fase 1 (reconstrucción de índice)
python3 scripts/run_exhaustive_rebuild.py --phase 1

# Solo fase 2 (enriquecimiento de metadatos)
python3 scripts/run_exhaustive_rebuild.py --phase 2
```

### Opción C: Saltar una Fase
```bash
# Ejecutar todas excepto fase 0 (útil si ya validaste)
python3 scripts/run_exhaustive_rebuild.py --skip-phase 0
```

### Opción D: Modo Dry-Run (Ver qué se ejecutaría)
```bash
python3 scripts/run_exhaustive_rebuild.py --dry-run
```

---

## 📊 Reportes y Logs

Después de la ejecución, encontrarás:

```
outputs/
├── reports/
│   ├── phase_0_validation_report.json         # Validación de PDFs
│   ├── phase_1_rebuild_stats.json             # Estadísticas de indexación
│   ├── phase_2_metadata_enrichment.json       # Completitud de metadatos
│   └── phase_3_retrieval_optimization.json    # Calidad de retrieval
│
├── logs/
│   ├── phase_0_validation.log
│   ├── phase_1_rebuild.log
│   ├── phase_2_enrichment.log
│   └── phase_3_retrieval.log
│
└── rag_index_goc_full/                        # ⭐ ÍNDICE FINAL
    ├── index.faiss                            # Índice vectorial
    ├── metadata_store.json                    # Metadatos de chunks
    └── index_config.json                      # Configuración
```

---

## 💻 Usando el Índice Construido

### Búsqueda Simple
```python
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

# Cargar índice
vector_db = VectorDBManager(
    index_dir="outputs/rag_index_goc_full",
    embedding_dim=384
)
vector_db.load()

# Crear motor de queries
query_engine = RAGQueryEngine(
    vector_db=vector_db,
    model="claude-haiku-4-5-20251001"
)

# Hacer una pregunta
result = query_engine.query(
    "¿Cuáles son los parámetros poblacionales del pargo rojo en el Golfo de California?"
)

print(result.answer)
print(result.sources)  # Referencias citadas
```

### Búsqueda Directa en Vector DB
```python
from pipeline.embeddings.embedding_generator import get_embedding_generator

# Generador de embeddings
embedder = get_embedding_generator(
    provider="local",
    model="all-MiniLM-L6-v2"
)

# Query
query_text = "talla madurez pargo"
query_embedding = embedder.batch_generate([query_text])[0]

# Búsqueda
results, scores = vector_db.search(query_embedding, k=5)

for chunk_id, score in zip(results, scores):
    chunk = vector_db._metadata[str(chunk_id)]
    print(f"[{score:.3f}] {chunk['text'][:100]}...")
    print(f"  Año: {chunk['metadata'].get('paper_year')}")
    print(f"  Autores: {chunk['metadata'].get('paper_authors')}")
```

### Búsqueda con Filtros
```python
# Los metadatos permiten filtrar:
# - Por año: chunk['metadata']['paper_year']
# - Por autor: chunk['metadata']['paper_authors']
# - Por DOI: chunk['metadata']['paper_doi']
# - Por título: chunk['metadata']['paper_title']
```

---

## ⚙️ Parámetros Estándar

| Componente | Parámetro | Valor | Razón |
|-----------|-----------|-------|-------|
| **TextChunker** | chunk_size | 2000 chars | ~512 tokens, contexto suficiente |
| | overlap | 200 chars | Continuidad entre chunks |
| | min_chunk_size | 100 chars | Evita fragmentos triviales |
| **SemanticChunker** | similarity_threshold | 0.5 | Detecta cambios de tema |
| | min_chunk_size | 300 chars | Mayor que TextChunker |
| | max_chunk_size | 1000 chars | Limit semántico |
| **Embeddings** | model | all-MiniLM-L6-v2 | Rápido, 384 dims, eficiente |
| **FAISS** | index_type | FlatIP | Similitud coseno, búsqueda exacta |
| | batch_size | 64 | Balance entre velocidad y memoria |

---

## 🔍 Validación de Calidad

Cada fase genera un reporte JSON que puedes revisar:

### Fase 0: Validación
```json
{
  "grobid_validation": {
    "successful": 10,    // 10/10 PDFs procesados correctamente
    "failed": 0
  }
}
```

### Fase 1: Indexación
```json
{
  "output": {
    "processed_pdfs": 433,
    "failed_pdfs": 0,
    "total_chunks": 10524,
    "avg_chunk_size": 1847
  }
}
```

### Fase 2: Metadatos
```json
{
  "metadata_statistics": {
    "chunks_with_title": 10420,      // 99.0%
    "chunks_with_authors": 10250,    // 97.4%
    "chunks_with_year": 10100,       // 96.0%
    "chunks_with_doi": 3250,         // 30.9%
    "completeness_pct": 80.8
  }
}
```

### Fase 3: Retrieval
```json
{
  "test_results": {
    "total_queries": 5,
    "successful_queries": 5,    // 100% exitosas
    "queries": [
      {
        "query": "parámetros poblacionales pargo rojo...",
        "total_results": 847,
        "top_5_results": [...]
      }
    ]
  }
}
```

---

## 🐛 Troubleshooting

### Problema: "GROBID no disponible"
**Solución**: Verifica que GROBID esté corriendo
```bash
curl http://localhost:8070/api/isalive
```

Si no está disponible, el sistema automáticamente usa pdfplumber como fallback.

### Problema: "No hay PDFs encontrados"
**Solución**: Verifica que los PDFs están en el directorio correcto
```bash
ls -la /home/atlantis/scientific_review/outputs/PDF_GOC/PDF/ | head -10
```

### Problema: "Errores de extracción en algunos PDFs"
**Solución**: Normal. Algunos PDFs pueden ser imágenes o estar corruptos. El sistema reporta qué PDFs fallaron en los reportes.

### Problema: "Indexación muy lenta"
**Solución**: Aumenta `batch_size` en fase 1 (usa más memoria pero es más rápido).

---

## 📈 Rendimiento Esperado

| Métrica | Valor |
|---------|-------|
| **Tiempo total** | 25-40 minutos |
| **Velocidad de extracción** | 0.5-1.0 PDFs/seg |
| **Velocidad de indexación** | 100+ chunks/seg |
| **Tiempo de query** | 2-3 segundos (incluyendo LLM) |
| **Tasa de éxito** | >95% de queries exitosas |
| **Tamaño del índice** | ~15-20 MB |

---

## 📝 Notas Importantes

1. **Integridad de datos**: El sistema verifica que todos los 433 PDFs se procesen correctamente
2. **Re-indexación**: Si algo falla, puedes volver a ejecutar la fase específica
3. **Escalabilidad**: El sistema está diseñado para 433-500 PDFs. Para más, considera particionar
4. **Actualizaciones**: Para agregar nuevos PDFs, copia a `outputs/PDF_GOC/PDF/` y re-ejecuta fase 1

---

## 🎯 Siguientes Pasos (Opcional)

### Mejoras futuras posibles:
1. **Integración de web UI**: Crear interfaz web para consultas
2. **Filtrado avanzado**: Filtros por año, autor, especie específica
3. **Re-ranking con LLM**: Usar Claude para calificar relevancia
4. **Exportación**: Guardar resultados en formatos (CSV, JSON, PDF)
5. **Multiidioma**: Soportar queries en inglés además de español

---

## 📞 Soporte

Para problemas o preguntas:
1. Revisa los logs en `outputs/logs/phase_*.log`
2. Consulta los reportes en `outputs/reports/phase_*.json`
3. Verifica la documentación de componentes específicos

---

**Última actualización**: 2026-08-04  
**Sistema**: RAG Golfo de California v2.0 (Exhaustive Rebuild)
