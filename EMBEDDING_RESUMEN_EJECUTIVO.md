# 🚀 EMBEDDING PLAN - RESUMEN EJECUTIVO

## ¿Qué es?
Un sistema que **transforma artículos científicos en vectores** para búsquedas semánticas inteligentes.

**Antes:** "machine learning" → búsqueda por palabras (imprecisa)
**Después:** "machine learning" → búsqueda semántica (entiende significado)

---

## 📊 Visión de 30 Segundos

```
Artículos científicos
      ↓
Extraer: título, resumen, palabras clave
      ↓
Generar embeddings (384 dimensiones)
      ↓
Almacenar en FAISS (rápido, local, privado)
      ↓
Búsquedas semánticas + RAGraph
```

---

## 🎯 Objetivos

| Objetivo | Métrica |
|----------|---------|
| Búsqueda semántica | Query → 10 artículos relevantes en < 100ms |
| Precisión | Precision@10 > 0.7 |
| Escalabilidad | Soportar 100K+ artículos |
| Privacidad | Datos locales (sin cloud) |
| Costo | Gratis (modelo local) |

---

## 🏗️ Arquitectura Simple

```
scientific_search (artículos)
    ↓
┌─────────────────────────────┐
│   EMBEDDING PIPELINE        │
├─────────────────────────────┤
│ 1. InformationExtractor     │ ← Extrae campos
│ 2. TextProcessor            │ ← Limpia
│ 3. EmbeddingGenerator       │ ← Vectoriza
│ 4. VectorDatabase (FAISS)   │ ← Almacena
│ 5. MetadataIndex            │ ← Indexa
└─────────────────────────────┘
    ↓
RAGraph (búsquedas + grafo)
```

---

## 🔧 Componentes Principales

### 1️⃣ Information Extractor
**¿Qué hace?** Obtiene los campos importantes del artículo
```
Entrada:  Article(title="...", abstract="...", ...)
Salida:   "Deep Learning-Based Fishing Ground Prediction... [text limpio]"
```

### 2️⃣ Text Processor
**¿Qué hace?** Normaliza el texto
```
Antes:  "DEEP  LEARNING   for  PREDICTION..."
Después: "deep learning for prediction..."
```

### 3️⃣ Embedding Generator
**¿Qué hace?** Convierte texto a vector de 384 números
```
Entrada:  "deep learning for fishing prediction"
Salida:   [0.123, 0.456, 0.789, ...]  # 384 dimensiones
```

**Opciones:**
- ✅ **Local (SentenceTransformers):** Gratis, sin enviar datos
- 💰 **OpenAI:** Mejor calidad, costo bajo
- ☁️ **HuggingFace:** Serverless, simple

### 4️⃣ Vector Database (FAISS)
**¿Qué hace?** Almacena y busca vectores rápidamente
```
Almacena:  1,000,000 artículos
Búsqueda:  < 100 ms
Costo:     Gratis
Privacidad: Total (sin cloud)
```

### 5️⃣ Metadata Index
**¿Qué hace?** Indexa para búsquedas rápidas por DOI, autor, año
```
DOI → vector_id
Autor → [vector_ids]
Año → [vector_ids]
```

---

## 💻 API Pública (Lo que usarás)

```python
from pipeline.embeddings import EmbeddingsManager

manager = EmbeddingsManager(config)

# 1. Procesar artículos
manager.process_articles(articles)

# 2. Buscar similares
results = manager.search_similar(
    query="machine learning prediction",
    k=10,
    filters={"year_min": 2023}
)

# 3. Exportar para RAGraph
manager.export_for_ragraph("output.json")
```

---

## 📋 Plan de Implementación

| Semana | Tareas | Entregables |
|--------|--------|------------|
| **1** | Foundation | Estructura + InformationExtractor |
| **2-3** | Embeddings | GeneradorLocal + GeneradorOpenAI |
| **3-4** | Vector DB | FAISS Manager + MetadataIndex |
| **4-5** | Orquestación | EmbeddingsManager + Integración |
| **5** | Exportación | RAGraph Exporter |
| **6** | Tests + Docs | QA + Documentación |

---

## 🎛️ Configuración Recomendada

```python
# Opción 1: MÁXIMA PRIVACIDAD (Recomendada)
config = EmbeddingConfig(
    embedding_provider="local",
    embedding_model="all-MiniLM-L6-v2",  # 384 dim
    vector_db_type="faiss",
    vector_db_path="./data/vectors"
)
# Costo: Gratis | Privacidad: Total | Velocidad: Rápida

# Opción 2: MEJOR CALIDAD
config = EmbeddingConfig(
    embedding_provider="openai",
    embedding_model="text-embedding-3-small",  # 512 dim
    vector_db_type="faiss"
)
# Costo: $0.02/1M tokens | Privacidad: Datos a OpenAI

# Opción 3: ESCALABILIDAD CLOUD
config = EmbeddingConfig(
    embedding_provider="local",
    vector_db_type="pinecone"
)
# Costo: $0.25/M vectores/mes | Mantenimiento: Ninguno
```

---

## 📊 Comparativa: Vector Databases

| DB | Privacidad | Escalabilidad | Costo | Setup |
|----|-----------|--------------|-------|-------|
| **FAISS** ⭐ | Total | 10M+ | Gratis | Local |
| Chroma | Total | 1M | Gratis | Local |
| Weaviate | Opción | Ilimitado | Gratis (self) | Docker |
| Pinecone | Cloud | Automática | $0.25/M | API |

---

## 🔍 Casos de Uso

### Búsqueda Semántica
```python
results = manager.search_similar("deep learning for fishing")
# Retorna artículos relacionados, aunque no contengan
# exactamente esas palabras
```

### Búsqueda Inteligente con Filtros
```python
results = manager.search_similar(
    "neural networks",
    k=20,
    filters={"year_min": 2023, "journal": "Nature"}
)
```

### Encontrar Artículos Relacionados
```python
related = manager.search_similar(
    f"{article.title} {article.abstract}",
    k=10
)
```

### Exportar para RAGraph
```python
data = manager.export_for_ragraph("output.json")
# Genera documento con 10,000+ artículos + embeddings
# Listo para construir knowledge graph
```

---

## 📈 Rendimiento Esperado

| Métrica | Valor |
|---------|-------|
| Tiempo procesamiento (10K artículos) | < 10 min (CPU) |
| Tiempo procesamiento (10K artículos) | < 1 min (GPU) |
| Tiempo búsqueda (100K artículos) | < 100 ms |
| Tamaño índice (10K artículos) | ~100 MB |
| Precisión (Precision@10) | > 0.7 |
| Recall | > 0.8 |

---

## 🚀 Próximos Pasos

1. **Hoy:** Revisar este plan
2. **Mañana:** Decidir configuración (Local FAISS vs Cloud)
3. **Esta semana:** Comenzar Semana 1 (Foundation)
4. **En 6 semanas:** Sistema completo + RAGraph integrado

---

## ❓ Preguntas Frecuentes

**P: ¿Dónde se guardan los datos?**
R: Todo local en `./data/vectors/` (tu máquina)

**P: ¿Necesito GPU?**
R: No, funciona en CPU. GPU acelera 10x (opcional)

**P: ¿Qué pasa con los datos privados?**
R: Nunca salen de tu máquina (con opción "local")

**P: ¿Qué tan preciso es?**
R: ~70% Precision@10, suficiente para RAGraph

**P: ¿Cuánto cuesta?**
R: Gratis con opción "local", ~$0.02/1M tokens con OpenAI

---

## 📚 Recursos

- **Plan Completo:** `EMBEDDING_PLAN.md` (detallado, 10 páginas)
- **Code Template:** Se creará en Semana 1
- **Documentation:** Incluída en cada módulo
- **Tests:** 15+ tests unitarios

---

## ✅ Resumen

| Aspecto | Respuesta |
|--------|-----------|
| **¿Qué es?** | Sistema de embeddings para búsquedas semánticas |
| **¿Por qué?** | RAGraph necesita embeddings para funcionar |
| **¿Dónde?** | Local en FAISS (recomendado) |
| **¿Cuándo?** | 6 semanas |
| **¿Cuánto cuesta?** | Gratis (con opción local) |
| **¿Difícil?** | No, plan arquitectónico completo |

---

**Status:** ✅ Plan listo para implementar
**Siguiente:** Leer `EMBEDDING_PLAN.md` completo y comenzar Semana 1
