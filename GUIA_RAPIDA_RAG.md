# ⚡ Guía Rápida - Sistema RAG Golfo de California

## 🎯 Qué está sucediendo ahora

✅ **Reconstrucción exhaustiva en progreso** (~35 minutos)

```
Fase 0: Limpieza y Validación          ▓▓░░░░░░░░ 2-3 min
Fase 1: Reconstrucción de Índice       ░░░░░░░░░░ 15-20 min (ACTUAL)
Fase 2: Enriquecimiento de Metadatos   ░░░░░░░░░░ 5-10 min
Fase 3: Optimización de Retrieval      ░░░░░░░░░░ 3-5 min
```

---

## 📊 Monitorear Progreso

### Opción 1: Ver logs en tiempo real
```bash
# Terminal 1: Ver fase actual
tail -f outputs/logs/phase_*.log

# Terminal 2: Ver reportes generados
ls -ltr outputs/reports/
```

### Opción 2: Revisar output del proceso
```bash
# Ver archivo de output completo
tail -100 /tmp/claude-1000/-home-atlantis-scientific-review/b691827d-5a79-4934-afdf-85e4ba663c00/tasks/bc1jr747r.output
```

---

## 💡 Lo Que Obtendrás

Después de completar, tendrás:

### 1. **Índice FAISS Optimizado** 
```
outputs/rag_index_goc_full/
├── index.faiss              # 15-20 MB: vectores de 10,500+ chunks
├── metadata_store.json      # 20-25 MB: información bibliográfica
└── index_config.json        # Configuración del índice
```

### 2. **Metadatos Enriquecidos**
Cada chunk tendrá:
- `paper_title`: Título del artículo
- `paper_authors`: Lista de autores
- `paper_year`: Año de publicación
- `paper_doi`: DOI (si disponible)

### 3. **Reportes Detallados**
```
outputs/reports/
├── phase_0_validation_report.json       # Validación de PDFs
├── phase_1_rebuild_stats.json           # Estadísticas de indexación
├── phase_2_metadata_enrichment.json     # Completitud de metadatos
└── phase_3_retrieval_optimization.json  # Calidad de búsqueda
```

### 4. **Logs Completos**
Cada fase genera logs detallados para auditoría y debugging.

---

## 🔍 Después: Cómo Usar el Índice

### Búsqueda Simple (Ejemplo 1)
```python
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

# Cargar
vector_db = VectorDBManager(
    index_dir="outputs/rag_index_goc_full",
    embedding_dim=384
)
vector_db.load()

query_engine = RAGQueryEngine(vector_db=vector_db)

# Consultar
result = query_engine.query(
    "¿Cuáles son los parámetros poblacionales del pargo rojo?"
)
print(result.answer)
print(result.sources)  # Con citas
```

### Búsqueda Directa (Ejemplo 2)
```python
from pipeline.embeddings.embedding_generator import get_embedding_generator

embedder = get_embedding_generator(
    provider="local",
    model="all-MiniLM-L6-v2"
)

# Query
embedding = embedder.batch_generate(
    ["parámetros poblacionales pargo"]
)[0]

# Top 5 resultados
results, scores = vector_db.search(embedding, k=5)

for chunk_id, score in zip(results, scores):
    chunk = vector_db._metadata[str(chunk_id)]
    print(f"[{score:.3f}] {chunk['text'][:100]}...")
    print(f"  Autores: {chunk['metadata']['paper_authors']}")
    print(f"  Año: {chunk['metadata']['paper_year']}\n")
```

### Búsqueda con Filtros (Ejemplo 3)
```python
# Filtrar por año
recent_papers = {
    chunk_id: data 
    for chunk_id, data in vector_db._metadata.items()
    if data.get('metadata', {}).get('paper_year', 0) >= 2020
}

# Filtrar por autor
cervantes_papers = {
    chunk_id: data
    for chunk_id, data in vector_db._metadata.items()
    if 'Cervantes' in str(data.get('metadata', {}).get('paper_authors', []))
}
```

---

## 📈 Qué Esperar en Reportes

### Phase 0: Validación
```json
{
  "grobid_validation": {
    "successful": 10,      // 10/10 PDFs de muestra
    "failed": 0
  }
}
```
✅ Si `successful == total_tested` → GROBID funciona perfectamente

### Phase 1: Indexación
```json
{
  "output": {
    "processed_pdfs": 433,        // Todos los PDFs
    "failed_pdfs": 0,              // 0 errores
    "total_chunks": 10524,         // ~10,500 chunks
    "index_stats": {
      "avg_chunk_size": 1847       // Tamaño promedio OK
    }
  }
}
```
✅ Si `failed_pdfs == 0` → Extracción perfecta

### Phase 2: Metadatos
```json
{
  "metadata_statistics": {
    "chunks_with_title": 10420,    // 99.0%
    "chunks_with_authors": 10250,  // 97.4%
    "chunks_with_year": 10100,     // 96.0%
    "chunks_with_doi": 3250,       // 30.9%
    "completeness_pct": 80.8       // Meta general
  }
}
```
✅ Si `completeness_pct > 75%` → Metadatos buenos

### Phase 3: Retrieval
```json
{
  "test_results": {
    "total_queries": 5,
    "successful_queries": 5,       // 100% exitosas
    "queries": [
      {
        "query": "parámetros poblacionales pargo...",
        "total_results": 847,       // Chunks encontrados
        "top_5_results": [...]      // Re-ranked
      }
    ]
  }
}
```
✅ Si `successful_queries == total_queries` → Sistema listo

---

## 🐛 Si Algo Falla

### Revisar logs
```bash
# Ver último error
tail -50 outputs/logs/phase_*.log | grep -i error

# Ver fase específica
cat outputs/logs/phase_1_rebuild.log
```

### Errores comunes

**"GROBID no disponible"**
- Verificar: `curl http://localhost:8070/api/isalive`
- Sistema usa pdfplumber automáticamente como fallback

**"PDF extraction failed"**
- Normal en 1-2 PDFs corruptos de 433
- Sistema reporta cuáles fallaron en `failed_pdfs`

**"Out of memory"**
- Reduce `batch_size` en Fase 1 (de 64 a 32)
- Editar: `scripts/phase_1_rebuild_index_optimized.py`

---

## 🎓 Parámetros Clave (Referencia)

```python
TextChunker:
  chunk_size: 2000        # ~512 tokens
  overlap: 200            # 10% overlap
  min_chunk_size: 100     # Evita fragmentos

EmbeddingGenerator:
  model: all-MiniLM-L6-v2 # 384 dimensiones
  
FAISS Index:
  type: FlatIP            # Inner product (cosine)
  
Re-ranking:
  base_score: similitud_semántica (0-1)
  + metadata_bonus (0.02 por campo)
  + recency_bonus ((año - 2000) * 0.001)
```

---

## 🔗 Archivos Importantes

| Archivo | Propósito |
|---------|-----------|
| `scripts/run_exhaustive_rebuild.py` | Orquestador principal |
| `scripts/phase_0_cleanup_and_validate.py` | Validación |
| `scripts/phase_1_rebuild_index_optimized.py` | Indexación |
| `scripts/phase_2_enrich_metadata.py` | Enriquecimiento |
| `scripts/phase_3_optimize_retrieval.py` | Optimización |
| `RAG_EXHAUSTIVE_REBUILD.md` | Documentación completa |
| `RECONSTRUCCION_PLAN.md` | Resumen del plan |

---

## ✅ Checklist Post-Reconstrucción

Después que termine (~35 minutos):

- [ ] Revisar `outputs/reports/phase_*.json` (todos los 4 reportes)
- [ ] Verificar `outputs/rag_index_goc_full/` existe y tiene archivos
- [ ] Probar una query simple (código arriba)
- [ ] Revisar `outputs/logs/` para cualquier advertencia
- [ ] Validar que `total_chunks > 10,000`
- [ ] Validar que `failed_pdfs == 0`
- [ ] Validar que `completeness_pct > 75%`

---

## 🎯 Próximas Tareas (Opcionales)

1. **Web UI**: Crear interfaz para queries interactivas
2. **Filtrados**: Agregar filtros por año, autor, especie
3. **Exportación**: Guardar resultados en CSV/JSON
4. **Análisis**: Topic modeling de la colección
5. **Escalado**: Agregar más PDFs en el futuro

---

## 📞 Contacto / Soporte

Para problemas:
1. Revisar logs en `outputs/logs/`
2. Consultar reportes en `outputs/reports/`
3. Revisar documentación completa en `RAG_EXHAUSTIVE_REBUILD.md`

---

**Tiempo estimado de ejecución**: 25-40 minutos  
**Estado**: En progreso... ⏳
