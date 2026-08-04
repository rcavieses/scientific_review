# 📐 Plan: Sistema Dual de Indexación con Extracción a Markdown

**Fecha**: 2026-08-04  
**Objetivo**: Crear sistema paralelo de indexación con mejor extracción de texto

---

## 🎯 Visión General

```
PDF → Markdown (extracción mejorada)
  ├─ Índice 1: FAISS Semántico (búsqueda por significado)
  ├─ Índice 2: BM25 Keyword-based (búsqueda por palabras)
  └─ Query Engine: Fusion inteligente de ambos → respuesta mejorada
```

### Ventajas
✅ **Mejor extracción**: Markdown preserva estructura  
✅ **Búsqueda dual**: Semántica + Keywords (cobertura máxima)  
✅ **Respuestas híbridas**: Combina puntos de vista  
✅ **Escalable**: Fácil agregar más índices  
✅ **Paralelo**: Ambas búsquedas simultáneas  

---

## 📋 Componentes Propuestos

### 1. **Extracción PDF → Markdown**

#### Opción A: `marker` (RECOMENDADO para papers científicos)
```
Ventajas:
  ✓ ML-based, diseñado para papers académicos
  ✓ Preserva tablas, fórmulas, estructura
  ✓ Salida Markdown limpia
  ✓ Rápido (~1-2 seg por PDF)

Desventaja:
  ✗ Requiere GPU o CPU potente para OCR

Instalación:
  pip install marker-pdf
```

#### Opción B: `pymupdf` (Rápida y confiable)
```
Ventajas:
  ✓ Ultra rápida (~0.1 seg por PDF)
  ✓ Sin requisitos especiales
  ✓ Preserva básicamente la estructura

Desventaja:
  ✗ Menos precisa con layouts complejos

Instalación:
  pip install pymupdf
```

#### Opción C: `nougat` (Vision transformer)
```
Ventajas:
  ✓ Excelente con fórmulas matemáticas
  ✓ Preserva structure científica
  ✓ Bueno para papers complejos

Desventaja:
  ✗ Lento (~30 seg por PDF)
  ✗ Requiere GPU

Instalación:
  pip install nougat-ocr
```

**RECOMENDACIÓN**: Empezar con `pymupdf` (rápida), luego `marker` si es necesario.

---

### 2. **Sistema Dual de Indexación**

#### Índice A: FAISS Semántico (Ya existe)
```
Componentes:
  • Extractor: PDF → Markdown → Chunks
  • Embeddings: all-MiniLM-L6-v2 (384 dims)
  • Index: FAISS FlatIP (cosine similarity)
  • Output: Top-k resultados ordenados por similitud

Velocidad: ~100ms para búsqueda
Memoria: ~40-50 MB para 10k chunks
```

#### Índice B: BM25 Keyword-based (NUEVO)
```
Componentes:
  • Extractor: Markdown → Tokens + stemming
  • Algoritmo: BM25 (best match 25)
  • Index: Inverted index + term frequencies
  • Output: Top-k resultados ordenados por relevancia

Velocidad: ~50ms para búsqueda
Memoria: ~20-30 MB para 10k chunks

Ventaja: Excelente para:
  - Nombres específicos (especies, autores)
  - Términos técnicos exactos
  - Números y referencias
```

---

### 3. **Query Engine Dual**

#### Flujo de búsqueda paralela:
```
Pregunta del usuario
  │
  ├─ Path 1 (Paralelo):
  │  • Generar embedding
  │  • Búsqueda FAISS semántica
  │  • Obtener top-10 semánticos
  │  └─ Score: similitud coseno (0-1)
  │
  ├─ Path 2 (Paralelo):
  │  • Tokenizar pregunta
  │  • Búsqueda BM25 keywords
  │  • Obtener top-10 keywords
  │  └─ Score: BM25 relevancia (0-100+)
  │
  └─ Fusión:
     • Normalizar scores (0-1)
     • Ponderar: 60% semántico + 40% keywords
     • Reordenar por score combinado
     • Generar respuesta única con ambas perspectivas
```

#### Pseudocódigo:
```python
def query_dual(question: str, top_k: int = 5) -> RAGResult:
    # Búsqueda paralela
    semantic_results = faiss_search(question, k=10)
    keyword_results = bm25_search(question, k=10)
    
    # Normalizar scores
    sem_scores = [r.score for r in semantic_results]  # 0-1
    kw_scores = normalize_bm25([r.score for r in keyword_results])  # 0-1
    
    # Fusión RRF (Reciprocal Rank Fusion)
    fused = rrf_fusion(
        semantic_results, 
        keyword_results,
        weights={'semantic': 0.6, 'keyword': 0.4}
    )
    
    # Generar respuesta
    chunks = [r.chunk for r in fused[:top_k]]
    answer = claude_synthesize(question, chunks)
    
    return RAGResult(
        answer=answer,
        sources_semantic=[r.chunk_id for r in semantic_results[:3]],
        sources_keyword=[r.chunk_id for r in keyword_results[:3]],
        fusion_score=fused_score
    )
```

---

## 🔧 Implementación por Fases

### Fase 0: Extracción a Markdown
```
Entrada:  outputs/PDF_GOC/PDF/*.pdf (433 files)
Proceso:  PDF → Markdown con preservación de estructura
Salida:   outputs/markdown_goc/*.md
Tiempo:   ~10-15 min

Flujo:
  1. Cargar cada PDF
  2. Extraer con marker/pymupdf
  3. Guardar como Markdown
  4. Validar estructura (headers, tablas, etc.)
  5. Crear índice de mapeo PDF → MD
```

### Fase 1A: Indexación Semántica (Paralelo)
```
Entrada:  outputs/markdown_goc/*.md
Proceso:  MD → Chunks semánticos → Embeddings → FAISS
Salida:   outputs/rag_index_goc_semantic/
Tiempo:   ~20 min
```

### Fase 1B: Indexación BM25 (Paralelo)
```
Entrada:  outputs/markdown_goc/*.md
Proceso:  MD → Chunks → Tokenize → BM25 Index
Salida:   outputs/rag_index_goc_bm25/
Tiempo:   ~5 min (muy rápido)
```

### Fase 2: Query Engine Dual
```
Entrada:  Pregunta del usuario
Proceso:  Búsqueda paralela + Fusión
Salida:   Respuesta mejorada con contexto dual
```

---

## 📊 Comparativa de Métodos de Extracción

| Método | Velocidad | Calidad | GPU | Tablas | Fórmulas | Costo |
|--------|-----------|---------|-----|--------|----------|-------|
| **pdfplumber** | ⚡⚡⚡ | ⭐⭐ | No | ⚠️ | ❌ | Gratis |
| **pymupdf** | ⚡⚡⚡ | ⭐⭐⭐ | No | ✅ | ⚠️ | Gratis |
| **marker** | ⚡⚡ | ⭐⭐⭐⭐ | Sí | ✅ | ✅ | Gratis |
| **nougat** | ⚡ | ⭐⭐⭐⭐⭐ | Sí | ✅ | ✅✅ | Gratis |

---

## 🎯 Arquitectura Final

```
outputs/
├── PDF_GOC/PDF/              (433 PDFs originales)
├── markdown_goc/             (433 Markdown extractos)
├── rag_index_goc_semantic/   (FAISS + Embeddings)
│   ├── index.faiss
│   ├── metadata_store.json
│   └── index_config.json
├── rag_index_goc_bm25/       (BM25 inverted index)
│   ├── index.pkl
│   └── metadata.json
├── logs/
│   ├── phase_0_extraction.log
│   ├── phase_1a_semantic.log
│   └── phase_1b_bm25.log
└── reports/
    ├── phase_0_extraction_report.json
    ├── phase_1a_semantic_report.json
    └── phase_1b_bm25_report.json
```

---

## 💻 Scripts a Crear

### 1. `scripts/phase_0_pdf_to_markdown.py`
```python
# Extraer PDFs a Markdown
# Entrada: outputs/PDF_GOC/PDF/*.pdf
# Salida: outputs/markdown_goc/*.md

def extract_pdf_to_markdown(pdf_path: Path) -> str:
    """Extrae PDF y lo convierte a Markdown"""
    # Usar marker o pymupdf
    pass
```

### 2. `scripts/phase_1a_index_semantic.py`
```python
# Indexación FAISS (similar a actual, pero desde Markdown)
```

### 3. `scripts/phase_1b_index_bm25.py`
```python
# Indexación BM25
# Entrada: outputs/markdown_goc/*.md
# Salida: outputs/rag_index_goc_bm25/

from rank_bm25 import BM25Okapi
import pickle

def build_bm25_index(markdown_dir: Path) -> None:
    """Construye índice BM25 desde Markdown"""
    corpus = []
    for md_file in markdown_dir.glob("*.md"):
        chunks = chunk_markdown(md_file)
        corpus.extend(chunks)
    
    # Tokenize
    tokenized = [chunk.split() for chunk in corpus]
    
    # Build BM25
    bm25 = BM25Okapi(tokenized)
    
    # Save
    with open("outputs/rag_index_goc_bm25/index.pkl", "wb") as f:
        pickle.dump(bm25, f)
```

### 4. `scripts/query_dual.py`
```python
# Query engine dual
# Busca en ambos índices en paralelo

from concurrent.futures import ThreadPoolExecutor

def query_dual(question: str) -> RAGResult:
    with ThreadPoolExecutor(max_workers=2) as executor:
        semantic_future = executor.submit(query_semantic, question)
        keyword_future = executor.submit(query_bm25, question)
        
        semantic_results = semantic_future.result()
        keyword_results = keyword_future.result()
    
    # Fusión
    fused = rrf_fusion(semantic_results, keyword_results)
    
    # Generar respuesta
    return generate_response(question, fused)
```

---

## 🚀 Plan de Implementación

### Semana 1: Extracción a Markdown
- [ ] Evaluar métodos (pymupdf vs marker vs nougat)
- [ ] Implementar fase 0
- [ ] Procesar 433 PDFs
- [ ] Validar calidad de Markdown

### Semana 2: Indexación Dual
- [ ] Implementar fase 1A (FAISS)
- [ ] Implementar fase 1B (BM25)
- [ ] Crear query engine dual
- [ ] Benchmarking vs single index

### Semana 3: Optimización
- [ ] Ajustar pesos de fusión
- [ ] Mejorar prompt de síntesis
- [ ] Validación con queries reales
- [ ] Documentación final

---

## 📈 Beneficios Esperados

### Cobertura de Búsqueda
```
ANTES (Solo FAISS):
  - Encuentra: "Lutjanus peru population dynamics"
  - No encuentra: "Red snapper", "pargo rojo"
  - Score: 0.75

DESPUÉS (FAISS + BM25):
  - Encuentra: "Lutjanus peru population dynamics" (semántico)
  - Encuentra: "Red snapper", "pargo rojo" (keywords)
  - Encuentra: Combinación óptima
  - Score: 0.92 (mejor)
```

### Tipos de Queries que Mejoran
✅ **Nombres exactos**: Especies, autores, locaciones  
✅ **Números**: Referencias, años, valores  
✅ **Acrónimos**: GOC, FAISS, BM25  
✅ **Jerga técnica**: Parámetros científicos  
✅ **Preguntas abiertas**: Síntesis mejorada  

---

## ⚖️ Trade-offs

| Factor | Single FAISS | Dual FAISS+BM25 |
|--------|------------|-----------------|
| Memoria | 40 MB | 60 MB (+50%) |
| Velocidad búsqueda | 100ms | 150ms (+50%) |
| Cobertura | 80% | 95% (+19%) |
| Complejidad | Baja | Media |
| Mantenimiento | Simple | Dos índices |

---

## 🔗 Alternativas Consideradas

### Opción 1: Triple Indexación
```
FAISS + BM25 + Elasticsearch
Ventaja: Máxima potencia
Desventaja: Complejidad, recursos
```

### Opción 2: Solo Markdown + BM25
```
Sin FAISS, solo keywords mejorados
Ventaja: Rápido, simple
Desventaja: Menos semántica
```

### Opción 3: Reranking con LLM
```
FAISS → Top-20 → LLM rerank
Ventaja: Máxima precisión
Desventaja: Costo API alto
```

**RECOMENDACIÓN**: Opción 1 (FAISS + BM25) es el balance óptimo.

---

## ✅ Próximos Pasos

1. **Hoy**: Completar Fase 1 actual (FAISS en progreso)
2. **Mañana**: Implementar extracción a Markdown (fase 0)
3. **Esta semana**: Implementar BM25 (fase 1B)
4. **Próxima semana**: Query engine dual + testing

---

## 📝 Notas Técnicas

### Por qué Markdown
- Preserva estructura lógica del documento
- Headers → mejor chunking semántico
- Tablas → extracción de datos estructurados
- Legibilidad → mejor para LLM
- Estándar → compatible con cualquier herramienta

### Por qué BM25
- Probado por décadas (Search engines)
- Excelente para keywords específicos
- Ultra rápido
- Sin necesidad de training
- Complementario a embedding semánticos

### Estrategia de Fusión
**RRF (Reciprocal Rank Fusion)**:
```
combined_score = 
  0.6 * (1 / (k + rank_semantic)) +
  0.4 * (1 / (k + rank_bm25))

Donde k=60 (constante de normalización)
```

Esto balancear ambos métodos equitativamente.

---

**Estado**: Plan propuesto, listo para implementación  
**Próximo**: Esperar completarse Fase 1 actual, luego iniciar limpieza PDF → Markdown
