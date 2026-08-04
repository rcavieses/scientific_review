# Pipeline de Búsqueda: 12 Especies del Golfo de California

## Descripción General

Este pipeline ejecuta búsquedas automatizadas de artículos científicos para 12 especies importantes del Golfo de California. Integra múltiples fuentes académicas (CrossRef, PubMed, Scopus, arXiv) y proporciona análisis comparativo de dinámicas poblacionales y pesquería.

## Especies Incluidas

1. **Sardina Pacific** (Sardinops sagax) - Pesca comercial clave
2. **Calamar Gigante** (Dosidicus gigas) - Recurso emergente
3. **Atún Aleta Amarilla** (Thunnus albacares) - Pesca internacional
4. **Atún Ojo Grande** (Thunnus obesus) - Especie migradora
5. **Bonito Pacífico** (Sarda chiliensis) - Pesca comercial
6. **Pargo Colorado** (Lutjanus peru) - Especie demersal
7. **Mero** (Mycteroperca spp.) - Pesca selectiva
8. **Camarón Blanco** (Litopenaeus vannamei) - Acuacultura
9. **Caballa Pacífica** (Scomber japonicus) - Pequeños pelágicos
10. **Dorado** (Coryphaena hippurus) - Migraciones
11. **Jurel del Pacífico** (Trachurus murphyi) - Recurso transfronterizo
12. **Pez León** (Pterois spp.) - Especie invasora

## Instalación

```bash
# Dependencias principales
pip install crossref-commons pubmed-parser arxiv-python scopus
```

## Uso

### Opción 1: Ejecutar todas las especies

```bash
python pipeline_especies.py
```

### Opción 2: Ejecutar una especie específica

```bash
python pipeline_especies.py --especie 1
python pipeline_especies.py --especie 6  # Pargo Colorado
```

### Opción 3: Descargar PDFs en acceso abierto

```bash
python pipeline_especies.py --download
```

Esto descargará automáticamente los PDFs disponibles en:
- arXiv
- PubMed Central
- Unpaywall (acceso abierto)
- Repositorios institucionales

### Opción 4: Indexar PDFs descargados para RAG

```bash
python pipeline_especies.py --download --index
```

Esto:
1. Descarga los PDFs
2. Extrae texto de los PDFs
3. Crea embeddings usando FAISS
4. Permite búsqueda semántica avanzada

### Opciones Avanzadas

```bash
# Cambiar rango de años
python pipeline_especies.py --year-start 2018

# Limitar resultados
python pipeline_especies.py --max-results 25

# Combinación completa
python pipeline_especies.py --max-results 20 --year-start 2020 --download --index
```

## Parámetros

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `--especie` | int | Todas | Número de especie (1-12) |
| `--max-results` | int | 15 | Resultados máximos por fuente |
| `--year-start` | int | 2015 | Año inicial de búsqueda |
| `--download` | flag | False | Descargar PDFs en acceso abierto |
| `--index` | flag | False | Indexar PDFs descargados (requiere --download) |

## Estructura de Salida

```
outputs/
├── search_results/
│   ├── search_Sardinops_sagax_*.csv        # Resultados tabulados
│   ├── search_Sardinops_sagax_*_summary.txt
│   └── search_Sardinops_sagax_*_full_log.json
├── pdfs/                                    # PDFs descargados (con --download)
│   ├── sardinops_sagax_2021_*.pdf
│   └── ...
├── rag_index/                               # Índices FAISS (con --index)
│   ├── index_config.json
│   └── metadata_store.json
└── pipeline_report_*.json                   # Reporte de ejecución
```

## Archivos de Resultados

### CSV (search_*_*.csv)
Tabla con columnas:
- **DOI**: Identificador único del artículo
- **title**: Título del artículo
- **authors**: Lista de autores
- **year**: Año de publicación
- **source**: Fuente de información (CrossRef, PubMed, etc.)
- **relevance_score**: Puntuación de relevancia (0-1)
- **abstract**: Resumen del artículo
- **url**: Enlace al artículo

### Reporte JSON (pipeline_report_*.json)
Estructura:
```json
{
  "timestamp": "2026-04-29T20:49:37...",
  "total_especies": 12,
  "parametros": {
    "max_results": 15,
    "year_start": 2015,
    "download": false,
    "index": false
  },
  "especies": [
    {
      "nombre": "Sardina Pacific",
      "nombre_cientifico": "Sardinops sagax",
      "exito": true
    }
  ]
}
```

## Análisis Posterior

### 1. Análisis Bibliométrico

```python
import pandas as pd

# Cargar resultados
df = pd.read_csv('outputs/search_results/search_Sardinops_sagax_*.csv')

# Análisis por año
df['year'].value_counts().sort_index().plot()

# Autores más publicados
all_authors = df['authors'].str.split(',').explode()
all_authors.value_counts().head(10)
```

### 2. Búsqueda Semántica RAG

```python
from pipeline.rag import RAGPipelineOrchestrator

orchestrator = RAGPipelineOrchestrator(index_dir='outputs/rag_index')
results = orchestrator.query(
    query="population dynamics of sardines in Gulf of California",
    k=5  # top 5 resultados más relevantes
)
```

### 3. Construcción de Grafo de Conocimiento

```bash
python construir_grafo.py --species "Sardinops sagax" --min-relevance 0.5
```

## Troubleshooting

### Problema: Credenciales de Scopus
```bash
# Crear archivo con API key
echo "YOUR_SCOPUS_API_KEY" > secrets/scopus_apikey.txt
python pipeline_especies.py
```

### Problema: Descarga lenta
```bash
# Aumentar timeout o usar menos resultados
python pipeline_especies.py --max-results 10 --download
```

### Problema: Error de codificación UTF-8
```bash
# Asegurar codificación correcta
export PYTHONIOENCODING=utf-8
python pipeline_especies.py
```

## Próximas Mejoras Propuestas

- [ ] Integración con FishBase para parámetros poblacionales
- [ ] Análisis de redes de co-autores
- [ ] Mapeo de regiones geográficas mencionadas en artículos
- [ ] Extracción automática de parámetros poblacionales (K, r, M)
- [ ] Comparación con estadísticas de captura (FAO)
- [ ] Análisis de sentimiento sobre conservación vs. explotación

## Referencias Clave

- **CrossRef**: https://www.crossref.org/
- **PubMed**: https://pubmed.ncbi.nlm.nih.gov/
- **Scopus**: https://www.scopus.com/
- **arXiv**: https://arxiv.org/
- **Gulf of California Initiative**: https://www.gulfofcalifornia.org/

## Contacto

**Responsable del Proyecto**: rcavieses@gmail.com  
**Fecha de Creación**: 2026-04-29  
**Versión**: 2.0

---

**Nota**: Este pipeline es parte del proyecto Scientific Review para modelado ecosistémico del Golfo de California usando RAG (Recuperación Aumentada por Generación).
