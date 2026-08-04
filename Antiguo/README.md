# 📦 Archivos Antiguos - Limpieza de Proyecto

Esta carpeta contiene todos los archivos, scripts y documentación que **ya no se utilizan** en el nuevo pipeline de reconstrucción exhaustiva del RAG.

## 📋 Por Qué Fue Movido

El proyecto ha sido **completamente reorganizado** con un nuevo pipeline modular de 4 fases:

### Pipeline Nuevo (Mantener)
```
scripts/
├── phase_0_cleanup_and_validate.py      ✅ NUEVO
├── phase_1_rebuild_index_optimized.py   ✅ NUEVO
├── phase_2_enrich_metadata.py           ✅ NUEVO
├── phase_3_optimize_retrieval.py        ✅ NUEVO
├── run_exhaustive_rebuild.py            ✅ NUEVO
├── verify_environment.py                ✅ NUEVO
└── rebuild_index_final.py               ✅ NUEVO
```

### Sistema Antiguo (Movido aquí)
```
Antiguo/
├── scripts/                             ← Scripts antiguos de reconstrucción
├── modules/                             ← Módulos de búsqueda/análisis antiguos
├── outputs/                             ← Índices y resultados antiguos
└── [Documentación antigua]              ← Docs de sistema anterior
```

---

## 📂 Estructura de Esta Carpeta

```
Antiguo/
├── scripts/                    # Scripts antiguos de RAG y testing
│   ├── clean_noisy_results.py
│   ├── demo_claude_vision_ocr.py
│   ├── enrich_index_with_grobid_metadata.py
│   ├── estimate_ocr_cost.py
│   ├── full_extraction_pipeline.py
│   ├── query_rag.py
│   ├── rebuild_index_*.py         # Múltiples versiones antiguas
│   ├── server_rag.py
│   ├── test_*.py
│   └── legacy/                    # Scripts de fases antiguas
│
├── modules/                    # Módulos del sistema anterior
│   ├── pipeline/                # Pipeline executor antiguo
│   ├── analysis_species/        # Análisis de especies (no usado)
│   ├── scientific_search/       # Búsqueda científica (descontinuada)
│   └── database_connectors/     # Conectores BD antiguos
│
├── outputs/                    # Índices y resultados antiguos
│   ├── rag_index_grobid_200/   # Índice incompleto
│   ├── rag_index_grobid_450/   # Índice incompleto
│   ├── search_results_*/       # Resultados de búsqueda caducos
│   └── scopus_results/         # Resultados de Scopus antiguo
│
└── [Documentos]               # Documentación de sistema anterior
    ├── ACCESO_RAG.md
    ├── GROBID_BRANCH_SUMMARY.md
    ├── INICIO_RAPIDO.md
    ├── RAG_SYSTEM_READY.md
    ├── VSCODE_PORT_FORWARDING.md
    └── docs/                  # Documentación técnica antigua
```

---

## 🔍 Qué Contiene Cada Subcarpeta

### `scripts/`
Scripts de testing y reconstrucción que fueron reemplazados por el nuevo pipeline:
- **Rebuild scripts antiguos**: `rebuild_index_*.py` (versiones 1-4 obsoletas)
- **Testing**: `test_*.py` y `demo_*.py` (pruebas de funciones específicas)
- **Funciones descontinuadas**: `server_rag.py`, `query_rag.py` (reemplazados por Phase 3)
- **Limpieza de datos**: `clean_noisy_results.py`, `reorganize_*.py`

### `modules/`
Módulos que implementaban funcionalidades antiguas del pipeline:
- **analysis_species/**: Clasificación de hábitats (no necesaria para este RAG)
- **scientific_search/**: Búsqueda en múltiples APIs (descontinuada)
- **database_connectors/**: Conectores a BD (no necesarios para FAISS local)
- **pipeline/**: Ejecutores antiguos del pipeline (reemplazados)

### `outputs/`
Artefactos generados por el sistema anterior:
- **Índices incompletos**: `rag_index_grobid_200/`, `rag_index_grobid_450/`
  - Solo 200-450 chunks vs. ~10,500 esperados en el nuevo sistema
  - Descartados por calidad insuficiente
- **Resultados de búsqueda**: Archivos CSV/JSON de búsquedas API antiguas
  - Scopus, ScienceDirect, etc. (descontinuados)
  - Reemplazados por PDFs directos en `/outputs/PDF_GOC/PDF/`

### Documentación Antigua
Documentos que describen el sistema anterior:
- Guías de setup y configuración obsoletas
- Arquitectura de sistema anterior
- Procedimientos de búsqueda/descarga antiguos

---

## ⚠️ Cuidado

**NO ELIMINES esta carpeta inmediatamente**. Guárdala por si necesitas:
1. Revisar código antiguo para referencia
2. Recuperar parámetros o configuraciones específicas
3. Auditar cambios del sistema

**Pero puedes eliminarla después de**:
- ✅ Validar que el nuevo pipeline funciona correctamente
- ✅ Completar todas las pruebas del nuevo sistema
- ✅ Tener backups de los cambios en git

---

## 🚀 Nuevo Sistema

El nuevo pipeline limpio está en:

```
/home/atlantis/scientific_review/
├── pipeline/                   ← Core del RAG (limpio)
├── scripts/                    ← 7 scripts nuevos solamente
│   ├── phase_0_*.py
│   ├── phase_1_*.py
│   ├── phase_2_*.py
│   ├── phase_3_*.py
│   ├── run_exhaustive_rebuild.py
│   └── verify_environment.py
├── outputs/rag_index_goc_full/ ← Nuevo índice optimizado
├── outputs/PDF_GOC/            ← PDFs fuente
└── outputs/logs/               ← Logs del nuevo sistema
```

---

## 📝 Migración de Código

Si necesitas recuperar algo de este sistema antiguo:

1. **Encontrar el archivo**: Busca en esta carpeta
2. **Revisar el código**: Estudio si tiene lógica útil
3. **Adaptar si es necesario**: Integra en el nuevo pipeline si es relevante
4. **NO restaurar archivos completos**: Solo copia/adapta fragmentos si es necesario

---

## 🗑️ Cuando Puedas Eliminar

Después de **2-4 semanas** de que el nuevo sistema esté en producción:

```bash
# Verificar que el nuevo sistema funciona
python3 scripts/verify_environment.py
python3 scripts/run_exhaustive_rebuild.py --dry-run

# Si todo OK, puedes eliminar
rm -rf Antiguo/
```

---

## 📞 Referencia

- **Nuevo Pipeline**: `RAG_EXHAUSTIVE_REBUILD.md` (en raíz)
- **Guía Rápida**: `GUIA_RAPIDA_RAG.md` (en raíz)
- **Resumen de Sesión**: `TRABAJO_REALIZADO.md` (en raíz)

---

**Archivo movido**: 2026-08-04  
**Reason**: Limpieza de proyecto para nuevo pipeline de 4 fases
