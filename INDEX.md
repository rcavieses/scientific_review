# 📑 ÍNDICE DEL PROYECTO - Sistema RAG Golfo de California v2.0

**Estado**: ✅ En construcción (Fase 1 en progreso)  
**Última actualización**: 2026-08-04 17:32 UTC

---

## 🚀 Inicio Rápido (30 segundos)

```bash
# 1. Verificar entorno está listo
python3 scripts/verify_environment.py

# 2. Ver qué se va a ejecutar (sin correr)
python3 scripts/run_exhaustive_rebuild.py --dry-run

# 3. Ejecutar reconstrucción completa
python3 scripts/run_exhaustive_rebuild.py
```

---

## 📂 Estructura del Proyecto

```
/home/atlantis/scientific_review/
│
├── 📖 DOCUMENTACIÓN (Leer primero)
│   ├── INDEX.md                         ← Tú estás aquí
│   ├── TRABAJO_REALIZADO.md             ← Resumen de sesión
│   ├── RAG_EXHAUSTIVE_REBUILD.md        ← Documentación técnica completa
│   ├── GUIA_RAPIDA_RAG.md               ← Ejemplos de código
│   ├── RECONSTRUCCION_PLAN.md           ← Plan visual
│   └── SESION_RESUMEN.md                ← Detalles de implementación
│
├── 🔧 SCRIPTS (El nuevo pipeline de 4 fases)
│   ├── scripts/phase_0_cleanup_and_validate.py    (2-3 min)
│   ├── scripts/phase_1_rebuild_index_optimized.py (20-25 min) ⏳ EN PROGRESO
│   ├── scripts/phase_2_enrich_metadata.py         (5-10 min)
│   ├── scripts/phase_3_optimize_retrieval.py      (3-5 min)
│   ├── scripts/run_exhaustive_rebuild.py          ← ORQUESTADOR PRINCIPAL
│   ├── scripts/verify_environment.py              ← PRE-VALIDACIÓN
│   └── scripts/rebuild_index_final.py             ← RECONSTRUCCIÓN DIRECTA
│
├── 🧠 PIPELINE CORE (Módulos de RAG)
│   └── pipeline/
│       ├── rag/                         ← Core RAG
│       ├── ocr/                         ← Extractores (GROBID, pdfplumber, etc.)
│       ├── embeddings/                  ← Generador de embeddings
│       └── ...
│
├── 📊 DATOS DE ENTRADA
│   └── outputs/PDF_GOC/PDF/             ← 433 PDFs científicos (843 MB)
│
├── 📈 DATOS DE SALIDA (Nuevo sistema)
│   ├── outputs/rag_index_goc_full/      ← Índice FAISS optimizado (⏳ EN CONSTRUCCIÓN)
│   │   ├── index.faiss                  (~15-20 MB)
│   │   ├── metadata_store.json          (~20-25 MB)
│   │   └── index_config.json
│   │
│   ├── outputs/logs/                    ← Logs de ejecución
│   │   ├── phase_0_validation.log       ✅ COMPLETADO
│   │   ├── phase_1_rebuild.log          ⏳ EN PROGRESO
│   │   ├── phase_2_enrichment.log       📋 PENDIENTE
│   │   ├── phase_3_retrieval.log        📋 PENDIENTE
│   │   └── rebuild_final.log
│   │
│   └── outputs/reports/                 ← Reportes JSON
│       ├── phase_0_validation_report.json       ✅
│       ├── phase_1_rebuild_stats.json           ⏳
│       ├── phase_2_metadata_enrichment.json     📋
│       └── phase_3_retrieval_optimization.json  📋
│
└── 📦 ANTIGUO (Sistema anterior - NO USAR)
    └── Antiguo/                         ← Archivos descontinuados (30+ scripts, 19 docs)
```

---

## 🎯 Qué Contiene Cada Sección

### 📖 Documentación

| Archivo | Contenido | Leer si... |
|---------|-----------|-----------|
| **TRABAJO_REALIZADO.md** | Resumen de toda la sesión | Quieres saber qué se hizo |
| **RAG_EXHAUSTIVE_REBUILD.md** | Documentación técnica completa (500 líneas) | Necesitas detalles técnicos |
| **GUIA_RAPIDA_RAG.md** | Ejemplos de código funcional | Quieres usar el sistema |
| **RECONSTRUCCION_PLAN.md** | Plan visual de las 4 fases | Quieres entender el flujo |
| **SESION_RESUMEN.md** | Detalles de implementación | Quieres auditar qué se hizo |
| **INDEX.md** | Este archivo | Necesitas navegar el proyecto |

### 🔧 Scripts (Pipeline de 4 Fases)

**FASE 0**: Limpieza y Validación (2-3 min)
```bash
python3 scripts/phase_0_cleanup_and_validate.py
```
- Elimina índices viejos
- Valida 433 PDFs
- Prueba GROBID en muestra
- Genera `reports/phase_0_validation_report.json`

**FASE 1**: Reconstrucción de Índice (20-25 min) ⏳ **EN PROGRESO**
```bash
python3 scripts/phase_1_rebuild_index_optimized.py
# O directamente (más simple):
python3 scripts/rebuild_index_final.py
```
- Extrae texto de PDFs
- Chunking semántico
- Genera embeddings (384 dims)
- Indexa en FAISS
- Salida: `outputs/rag_index_goc_full/`

**FASE 2**: Enriquecimiento de Metadatos (5-10 min)
```bash
python3 scripts/phase_2_enrich_metadata.py
```
- Extrae título, autores, año, DOI
- Enriquece cada chunk con metadatos
- Genera `reports/phase_2_metadata_enrichment.json`

**FASE 3**: Optimización de Retrieval (3-5 min)
```bash
python3 scripts/phase_3_optimize_retrieval.py
```
- Valida integridad del índice
- Detecta duplicados
- Implementa re-ranking
- Prueba 5 queries de ejemplo
- Genera `reports/phase_3_retrieval_optimization.json`

**ORQUESTADOR**: Ejecuta las 4 fases automáticamente
```bash
# Ejecutar todas las fases
python3 scripts/run_exhaustive_rebuild.py

# Solo fase 1
python3 scripts/run_exhaustive_rebuild.py --phase 1

# Ver qué haría sin ejecutar
python3 scripts/run_exhaustive_rebuild.py --dry-run

# Con output completo
python3 scripts/run_exhaustive_rebuild.py --verbose
```

**VALIDACIÓN PREVIA**: Verifica que todo está listo
```bash
python3 scripts/verify_environment.py
```

### 🧠 Pipeline Core

El código RAG real está en `/pipeline/`:
- `pipeline/rag/` — Orquestador, extractor, chunker, vector DB
- `pipeline/ocr/` — Extractores: GROBID, pdfplumber, etc.
- `pipeline/embeddings/` — Generador de embeddings local
- `pipeline/logger.py` — Logging

**NO MODIFICAR** estos archivos a menos que entiendas el sistema.

### 📊 Datos de Entrada

```
outputs/PDF_GOC/PDF/
├── Nevares2026.pdf
├── Lopez-2026.pdf
├── clague2011.pdf
├── cartamil2011.pdf
├── ... (433 PDFs totales)
└── Reyes_bonilla-2026.pdf
```

**Total**: 433 PDFs, 841.7 MB

### 📈 Datos de Salida

**NUEVO ÍNDICE** (se está construyendo):
```
outputs/rag_index_goc_full/
├── index.faiss           (15-20 MB: vectores)
├── metadata_store.json   (20-25 MB: información bibliográfica)
└── index_config.json     (< 1 KB: configuración)
```

**LOGS**:
```
outputs/logs/
├── phase_0_validation.log    ✅
├── phase_1_rebuild.log       ⏳
├── rebuild_final.log         ⏳
└── ...
```

**REPORTES**:
```
outputs/reports/
├── phase_0_validation_report.json       ✅
├── phase_1_rebuild_stats.json           ⏳
├── phase_2_metadata_enrichment.json     📋
└── phase_3_retrieval_optimization.json  📋
```

---

## 💻 Cómo Usar el Sistema

### 1. Verificar que todo está listo
```bash
python3 scripts/verify_environment.py
```

### 2. Ejecutar reconstrucción (recomendado)
```bash
python3 scripts/run_exhaustive_rebuild.py
# Toma ~35-40 minutos para 433 PDFs
```

### 3. Una vez completado, usar el índice
```python
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

# Cargar
vector_db = VectorDBManager("outputs/rag_index_goc_full", embedding_dim=384)
vector_db.load()

# Crear motor de queries
query_engine = RAGQueryEngine(vector_db=vector_db, model="claude-haiku-4-5-20251001")

# Hacer una pregunta
result = query_engine.query("¿Parámetros poblacionales del pargo rojo en el Golfo?")
print(result.answer)
print(result.sources)  # Con citas
```

---

## 📊 Estado de Ejecución

```
FASE 0: Limpieza y Validación         ✅ COMPLETADA (2-3 min)
FASE 1: Reconstrucción de Índice     ⏳ EN PROGRESO (20-25 min)
FASE 2: Enriquecimiento de Metadatos  📋 PENDIENTE (5-10 min)
FASE 3: Optimización de Retrieval     📋 PENDIENTE (3-5 min)
─────────────────────────────────────────────────────
TIEMPO TOTAL ESTIMADO: ~35-40 minutos

Fase 1 Status:
  Task ID: bw79124cx
  Progreso: Procesando PDFs 1-433
  ETA: 20-25 minutos
```

---

## 🎯 Parámetros Clave

```python
# Chunking
chunk_size: 2000 characters      (~512 tokens)
overlap: 200 characters          (10% for context)
min_chunk_size: 100 characters   (discard trivial)

# Embeddings
model: all-MiniLM-L6-v2
dimension: 384
provider: local (no API calls)

# Indexing
index_type: FlatIP (cosine similarity)
batch_size: 64

# Expected Output
total_chunks: ~10,500
avg_chunk_size: ~1,850 chars
completeness: >80%
```

---

## ⚠️ Archivos Antiguos

Todo el sistema anterior fue movido a **`Antiguo/`**:
- 30+ scripts antiguos
- 17+ módulos descontinuados
- 19 documentos de sistema anterior
- Índices incompletos (199, 450 chunks)

**NO NECESITAS REVISAR** estos archivos. El nuevo sistema es completamente independiente.

Lee `Antiguo/README.md` si necesitas contexto histórico.

---

## 🔍 Monitorear Progreso (Mientras se ejecuta Fase 1)

```bash
# Ver logs en vivo
tail -f outputs/logs/rebuild_final.log

# Ver chunks acumulados
watch 'python3 -c "import json; print(f\"Chunks: {len(json.load(open(\"outputs/rag_index_goc_full/metadata_store.json\")))}\") 2>/dev/null || echo Esperando..."'

# Ver tamaño del índice
watch 'du -sh outputs/rag_index_goc_full/ 2>/dev/null || echo Esperando...'
```

---

## ✅ Checklist

- [ ] Leí `TRABAJO_REALIZADO.md` (resumen de sesión)
- [ ] Ejecuté `verify_environment.py` (todo OK)
- [ ] Ejecuté `run_exhaustive_rebuild.py` o `rebuild_index_final.py`
- [ ] Esperé ~35-40 minutos a que se complete
- [ ] Revisé `outputs/reports/` para validar
- [ ] Probé una query con el código de arriba
- [ ] Sistema funcionando correctamente ✅

---

## 🆘 Troubleshooting

| Problema | Solución |
|----------|----------|
| "Directorio PDF no encontrado" | Verifica: `ls outputs/PDF_GOC/PDF/` |
| "GROBID no disponible" | Fallback automático a pdfplumber |
| "Embeddings lentos" | Normal primera vez, se cachean después |
| "Proceso interrumpido" | Ejecuta `rebuild_index_final.py` directamente |
| "Quiero ver detalles" | `tail -f outputs/logs/rebuild_final.log` |

---

## 📞 Documentación Rápida

- **¿Cómo usar?** → `GUIA_RAPIDA_RAG.md`
- **¿Qué se hizo?** → `TRABAJO_REALIZADO.md`
- **¿Detalles técnicos?** → `RAG_EXHAUSTIVE_REBUILD.md`
- **¿Plan de trabajo?** → `RECONSTRUCCION_PLAN.md`
- **¿Historial?** → `SESION_RESUMEN.md`

---

**Proyecto**: Reconstrucción Exhaustiva RAG - Golfo de California  
**Versión**: 2.0 (Nueva arquitectura de 4 fases)  
**Estado**: ✅ En construcción (Fase 1 en progreso)  
**Fecha**: 2026-08-04  
**Usuario**: rcavieses  
