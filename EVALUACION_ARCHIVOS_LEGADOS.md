# 📋 Evaluación de Archivos Legados - Actualización Necesaria

**Fecha**: 2026-08-04  
**Evaluación**: Análisis de archivos en raíz que requieren actualización

---

## 📊 RESUMEN EJECUTIVO

| Archivo | Estado | Acción |
|---------|--------|--------|
| **iniciar_rag.sh** | ❌ OBSOLETO | **Necesita reemplazo urgente** |
| **pipeline_demo.ipynb** | ⚠️ PARCIALMENTE OBSOLETO | Actualizar referencias |
| **requirements.txt** | ✅ OK | Mantener |
| **requirements-ocr-local.txt** | ✅ OK | Mantener |
| **requirements-dev.txt** | ⚠️ REVISAR | Puede estar desactualizado |
| **README_COLEGA.txt** | ❌ COMPLETAMENTE OBSOLETO | Reemplazar por INDEX.md |
| **monitorear.sh** | ❌ OBSOLETO | No aplica al nuevo pipeline |

---

## 🔍 ANÁLISIS DETALLADO

### 1. **iniciar_rag.sh** ❌ OBSOLETO

**Línea 31-34**:
```bash
# Verificar índice
if [ ! -d "outputs/rag_index_goc" ]; then
    echo -e "${RED}❌ Error: Índice RAG no encontrado${NC}"
    echo "Ejecuta primero: python3 scripts/phase_5_indexing/indexar.py"
```

**Problemas**:
- ✗ Busca índice en `outputs/rag_index_goc` (ANTIGUO)
- ✗ Intenta ejecutar `scripts/phase_5_indexing/indexar.py` (NO EXISTE)
- ✗ El nuevo sistema crea `outputs/rag_index_goc_full/`
- ✗ Ejecuta `scripts/phase_6_query/server_rag_api.py` (DESCONTINUADO)

**Línea 56**:
```bash
python3 scripts/phase_6_query/server_rag_api.py --host "$HOST" --port "$PORT"
```

**Problemas**:
- ✗ El script `phase_6_query/server_rag_api.py` ya no existe
- ✗ El nuevo pipeline NO tiene un servidor web integrado
- ✗ Las Fases 5 y 6 fueron descontinuadas

**Recomendación**: 
- **REEMPLAZAR COMPLETAMENTE** por un script que:
  1. Ejecute `verify_environment.py`
  2. Ejecute `run_exhaustive_rebuild.py` si no hay índice
  3. Proporcione interfaz para hacer queries (CLI, no web)

---

### 2. **pipeline_demo.ipynb** ⚠️ PARCIALMENTE OBSOLETO

**Estado de las celdas**:

✅ **OK - Funciona sin cambios**:
- Sección 0: Configuración
- Sección 1: Búsqueda de artículos (ScientificArticleSearcher)
- Fase 2: Generación de embeddings (EmbeddingGenerator)
- Fase 3.1: TextChunker
- Fase 3.2: PdfPlumberExtractor

⚠️ **REVISAR - Rutas/módulos pueden estar obsoletos**:
- Línea 96: `from pipeline.rag import PdfPlumberExtractor`
  - Verificar que `PdfPlumberExtractor` aún existe en `pipeline/rag/`
  
- Línea 130: `REAL_INDEX = ROOT / 'outputs' / 'rag_index'`
  - DEBERÍA ser: `ROOT / 'outputs' / 'rag_index_goc_full'`

- Línea 140-150: Referencias a scripts inexistentes
  - "indexar.py" → No existe en nuevo sistema
  - "scripts/phase_5_indexing/" → Descontinuado

❌ **DESCONTINUADO - Necesita actualización**:
- Sección "3.5 — Flujo completo con RAGPipelineOrchestrator"
  - Refiere a `buscar.py` y `indexar.py` (no existen)
  - Los comandos `python buscar.py ...` son obsoletos

**Recomendación**:
- Actualizar referencias a rutas correctas
- Reemplazar sección de "Fase 3.5" por ejemplos del nuevo pipeline
- Cambiar `rag_index` → `rag_index_goc_full`
- Actualizar comandos para usar `scripts/phase_*.py`

---

### 3. **README_COLEGA.txt** ❌ COMPLETAMENTE OBSOLETO

**Problemas evidentes**:

**Línea 14-15**:
```
Bienvenido! Aquí encontrarás 10,500 fragmentos indexados de 429 papers
sobre ecología marina del Golfo de California.
```
- ✗ Números desactualizados
- ✗ El nuevo sistema aún está en construcción

**Línea 33**:
```
Ejecuta primero: python3 scripts/phase_5_indexing/indexar.py
```
- ✗ Script no existe

**Línea 45-46**:
```
LEE ESTOS PRIMERO:
  • INICIO_RAPIDO.md     → Guía rápida (2 min lectura)
  • ACCESO_RAG.md        → Guía completa (10 min lectura)
```
- ✗ INICIO_RAPIDO.md está en `Antiguo/`
- ✗ ACCESO_RAG.md está en `Antiguo/`
- ✓ Debería apuntar a: INDEX.md, RAG_EXHAUSTIVE_REBUILD.md, etc.

**Línea 96**:
```
$ python3 scripts/phase_6_query/buscar_rag_con_fishbase.py --interactive
```
- ✗ Script no existe en nuevo sistema

**Línea 137-140**:
```
Índice:
  • 10,500 chunks indexados
  • 429 papers de investigación
  • Modelo de embeddings: all-MiniLM-L6-v2
```
- ⚠️ Números pueden ser inexactos (el nuevo índice tiene ~10,500+ chunks)

**Recomendación**: 
- **REEMPLAZAR COMPLETAMENTE** por `INDEX.md` (que ya existe y está actualizado)
- O actualizar con información del nuevo pipeline

---

### 4. **monitorear.sh** ❌ OBSOLETO

**Problemas**:

**Línea 25**:
```bash
if ! python3 cli.py status > /dev/null 2>&1; then
```
- ✗ `cli.py` no existe en nuevo sistema
- ✗ No hay servidor running que monitorear

**Línea 46**:
```bash
status_json=$(curl -s http://127.0.0.1:8000/status 2>/dev/null || echo "{}")
```
- ✗ No hay endpoint `/status` en nuevo sistema
- ✗ Asume servidor web (no existe)

**Línea 61-82**: Monitorea fases del pipeline antiguo
```bash
case "$stage" in
    "idle")
    "classifying_habitats")
    "filtering_marine")
    "searching_articles")
    "downloading_pdfs")
    "indexing_rag")
    "generating_report")
```
- ✗ Refieren a pipeline de 6+ fases (descontinuado)
- ✗ Nuevo pipeline tiene 4 fases (phase_0, 1, 2, 3)

**Recomendación**: 
- **ELIMINAR O REEMPLAZAR** por script que monitoree logs en tiempo real
- Alternativa: `tail -f outputs/logs/rebuild_final.log`

---

### 5. **requirements.txt** ✅ OK

**Contenido**:
```
faiss-cpu>=1.7.4
pdfplumber>=0.9.0
sentence-transformers>=2.2.0
requests>=2.28.0
numpy>=1.23.0
python-dotenv>=0.20.0
anthropic>=0.7.0
```

**Estado**: 
- ✅ Todas las dependencias son actuales
- ✅ Verions no están pinned (es un pro para flexibilidad)
- ✅ Incluye `anthropic` (necesario para Claude API)

**Recomendación**: 
- Mantener como está
- Opcional: actualizar versiones si hay bugs conocidos

---

### 6. **requirements-ocr-local.txt** ✅ OK

**Contenido**:
```
torch>=2.0.0
torchvision>=0.15.0
transformers>=4.30.0
paddleocr>=2.7.0
```

**Estado**:
- ✅ Para OCR local (Paddle, Transformers)
- ✅ Necesario si se implementa OCR local
- ✅ Actualmente NO se usa (usando GROBID + pdfplumber)

**Recomendación**: 
- Mantener para referencia futura
- Documentar que es opcional

---

### 7. **requirements-dev.txt** ⚠️ REVISAR

**Contenido esperado**: 
- Dependencias para desarrollo (pytest, black, flake8, etc.)
- Dependencias para notebook (jupyter, ipykernel)

**Recomendación**:
- Revisar que versiones sean actuales
- Actualizar si está desactualizado

---

## ✅ PLAN DE ACCIÓN

### URGENTE (Hacer ahora):

1. **Reemplazar `iniciar_rag.sh`**
   ```bash
   # Nuevo iniciar_rag.sh debe:
   - Verificar ambiente con verify_environment.py
   - Ofrecer opción de reconstruir índice si no existe
   - Proporcionar interfaz para queries (CLI básica)
   - NO asumir servidor web
   ```

2. **Actualizar `pipeline_demo.ipynb`**
   - Cambiar `rag_index` → `rag_index_goc_full`
   - Actualizar referencias a scripts inexistentes
   - Añadir ejemplos de nuevo pipeline (phase_0, 1, 2, 3)

3. **Reemplazar `README_COLEGA.txt`**
   - Usar `INDEX.md` como punto de entrada principal
   - O actualizar completamente con info del nuevo sistema

### IMPORTANTE (Hacer pronto):

4. **Remover/actualizar `monitorear.sh`**
   - O crear versión que monitoree logs de Fase 1

### MANTENER:

5. **requirements.txt** — OK
6. **requirements-ocr-local.txt** — OK (referencia)

---

## 📝 PROPUESTA: Nuevo `iniciar_rag.sh`

```bash
#!/bin/bash
# Script para iniciar el sistema RAG del Golfo de California (v2.0)

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   🐟 Sistema RAG - Golfo de California v2.0           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Verificar ambiente
echo -e "${YELLOW}📋 Verificando ambiente...${NC}"
python3 scripts/verify_environment.py
echo ""

# 2. Verificar si índice existe
INDEX_DIR="outputs/rag_index_goc_full"
if [ ! -d "$INDEX_DIR" ] || [ -z "$(ls -A $INDEX_DIR 2>/dev/null)" ]; then
    echo -e "${YELLOW}⚠️  Índice no encontrado${NC}"
    read -p "¿Reconstruir índice? (s/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo -e "${YELLOW}🔨 Reconstruyendo índice...${NC}"
        python3 scripts/run_exhaustive_rebuild.py
    else
        echo -e "${RED}❌ Índice requerido para continuar${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Sistema listo${NC}"
echo ""
echo -e "${BLUE}📖 Documentación:${NC}"
echo -e "  • ${YELLOW}INDEX.md${NC} - Navegación del proyecto"
echo -e "  • ${YELLOW}GUIA_RAPIDA_RAG.md${NC} - Ejemplos de uso"
echo ""
echo -e "${BLUE}💡 Hacer una consulta:${NC}"
echo ""
echo "  from pipeline.rag.query_engine import RAGQueryEngine"
echo "  from pipeline.rag.vector_db import VectorDBManager"
echo ""
echo "  vector_db = VectorDBManager('$INDEX_DIR', embedding_dim=384)"
echo "  vector_db.load()"
echo ""
echo "  engine = RAGQueryEngine(vector_db=vector_db)"
echo "  result = engine.query('¿Parámetros del pargo rojo?')"
echo "  print(result.answer)"
echo ""
```

---

## 🎯 RESUMEN FINAL

| Archivo | Acción | Prioridad |
|---------|--------|-----------|
| iniciar_rag.sh | **REEMPLAZAR** | 🔴 URGENTE |
| pipeline_demo.ipynb | **ACTUALIZAR** | 🟡 IMPORTANTE |
| README_COLEGA.txt | **REEMPLAZAR por INDEX.md** | 🟡 IMPORTANTE |
| monitorear.sh | **REMOVER O REEMPLAZAR** | 🟡 IMPORTANTE |
| requirements.txt | MANTENER | 🟢 OK |
| requirements-ocr-local.txt | MANTENER | 🟢 OK |
| requirements-dev.txt | REVISAR | 🟢 OK |

---

**Conclusión**: La mayoría de estos archivos refieren al pipeline antiguo (Fases 5-6, scripts descontinuados).  
El nuevo sistema es completamente diferente y requiere actualización de estos puntos de entrada.

Recomendación principal: **Usar `INDEX.md` como punto de entrada único**, que ya está actualizado.
