# Scientific Review Pipeline — Golfo de California

Pipeline automatizado de búsqueda, descarga e indexación de literatura científica para especies marinas del Golfo de California y Pacífico Mexicano, orientado a construir un sistema GraphRAG consultable.

---

## Descripción

El proyecto procesa una lista de **~11,800 especies** marinas (de `final_taxonomy_occ.csv`) y ejecuta un pipeline de 6 fases:

```
Fase 1: Clasificación de hábitats  →  Filtrar species marinas (WoRMS + GBIF)
Fase 2: Búsqueda de artículos      →  PubMed, CrossRef, Scopus, ScienceDirect, ArXiv
Fase 3: Descarga de PDFs           →  Unpaywall, PMC, doi2pdf, acceso directo
Fase 4: Canonización               →  Limpieza y organización de resultados por especie
Fase 5: Indexación RAG             →  FAISS + embeddings (SentenceTransformers)
Fase 6: Consulta GraphRAG          →  Búsqueda semántica + grafo de conocimiento + FishBase
```

---

## Instalación

```bash
# Clonar el repositorio
git clone <repo-url>
cd scientific_review

# Crear entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copiar y completar variables de entorno
cp .env.example .env
```

### Variables de entorno (`.env`)

| Variable | Descripción |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API (fases 5-6, grafo de conocimiento) |
| `SCOPUS_API_KEY` | Elsevier Scopus API |
| `SCIENCEDIRECT_API_KEY` | Elsevier ScienceDirect API |
| `EMBEDDING_PROVIDER` | `local` (default) o `openai` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` (default) |

Las API keys de Scopus y ScienceDirect también pueden colocarse en `secrets/scopus_apikey.txt` y `secrets/sciencedirect_apikey.txt`.

---

## Estructura del proyecto

```
scientific_review/
│
├── README.md                          # Este archivo
├── .env.example                       # Plantilla de variables de entorno
├── requirements.txt                   # Dependencias Python
├── requirements-dev.txt               # Dependencias de desarrollo
│
├── # ── Datos ─────────────────────────────────────────────────
├── data/                              # Archivos de entrada
│   ├── input/                         # Datos de entrada (gitignored)
│   │   ├── final_taxonomy_occ.csv     # ~11,800 especies (INPUT principal)
│   │   ├── occurrence_data_revised_taxonomy.csv
│   │   └── species_occurrence_database_goc_May_2026.zip
│   └── references/                    # Documentos de referencia
│
├── # ── Librería del pipeline ──────────────────────────────────
├── scientific_search/                 # Módulo de búsqueda multi-fuente
│   ├── adapters.py                    # CrossRef, PubMed, ArXiv, Scopus, ScienceDirect, bioRxiv
│   ├── searcher.py                    # Orquestador de búsqueda unificada
│   ├── downloader.py                  # Descarga de PDFs vía Unpaywall/PMC/ArXiv
│   ├── pdf_downloder.py               # Descarga vía doi2pdf (artículos de pago)
│   ├── models.py                      # Modelos de datos: Article, SearchResult
│   └── registry.py                    # Persistencia de resultados en CSV
│
├── pipeline/                          # Motor RAG y GraphRAG
│   ├── rag/                           # Indexación y consulta FAISS
│   │   ├── rag_pipeline.py            # Orquestador: PDF → chunks → embeddings → FAISS
│   │   ├── pdf_extractor.py           # Extracción de texto de PDFs multi-columna
│   │   ├── text_chunker.py            # Chunking con ventana deslizante
│   │   ├── vector_db.py               # Gestor del índice FAISS
│   │   ├── query_engine.py            # Motor de consulta RAG + Claude API
│   │   └── graph/                     # GraphRAG
│   ├── embeddings/                    # Generación de embeddings
│   ├── llm/                           # Abstracción de proveedores LLM
│   └── pipeline_executor.py           # Orquestador de fases (legacy)
│
├── database_connectors/               # Conectores a bases de datos externas
│   └── fishbase_adapter.py            # FishBase API (parámetros poblacionales)
│
├── analysis_species/                  # Fase 1: clasificación de hábitats
│   ├── extraer_species_unicas.py      # Extrae especies únicas de data/input/final_taxonomy_occ.csv
│   └── clasificar_habitats.py         # Clasifica como marina/terrestre (WoRMS + GBIF)
│
├── scripts/                           # Scripts del pipeline organizados por fase
│   ├── setup/                         # Scripts de configuración
│   │   ├── activate.sh
│   │   ├── setup_env.sh
│   │   └── setup_env.bat
│   ├── phase_2_search/                # Fase 2: búsqueda de artículos
│   │   ├── run_new_species_pipeline.py
│   │   ├── run_scopus_search.py
│   │   ├── run_search_missing_species.py
│   │   ├── search_articles.py
│   │   └── (otros scripts de búsqueda)
│   ├── phase_3_download/              # Fase 3: descarga de PDFs
│   │   ├── download_pdfs.py
│   │   ├── download_goc_pdfs.py
│   │   ├── run_sciencedirect_download.py
│   │   ├── run_rescan_empty_species.py
│   │   └── sciencedirect_batch_downloader/  # Descargador institucional ScienceDirect
│   │       ├── download_sciencedirect_api.py
│   │       ├── test_api.py
│   │       ├── run.sh
│   │       ├── config.json
│   │       └── README.md
│   ├── phase_5_indexing/              # Fase 5: indexación RAG
│   │   ├── indexar.py
│   │   ├── indexar_paralelo.py
│   │   ├── monitor_indexacion.py
│   │   ├── merge_indices.py
│   │   └── (otros scripts de indexación)
│   ├── phase_6_query/                 # Fase 6: consulta GraphRAG
│   │   ├── buscar_rag.py
│   │   ├── construir_grafo.py
│   │   ├── visualizar_grafo.py
│   │   └── consultar_parametros_rag.py
│   ├── utils/                         # Scripts de utilidad
│   │   ├── check_setup.py
│   │   ├── cli.py
│   │   ├── server.py
│   │   ├── pipeline_manager.py
│   │   └── (otros scripts auxiliares)
│   ├── legacy/                        # Scripts archivados
│   ├── run_complete_pipeline.sh       # Shell scripts principales
│   ├── run_server.sh
│   └── run_steps_3_4.sh
│
├── docs/                              # Documentación técnica
│   ├── ARCHITECTURE.md                # Arquitectura del sistema y API server
│   ├── EMBEDDING.md                   # Sistema de embeddings y indexación paralela
│   ├── PARALLEL_INDEXING.md           # Estrategia de indexación paralela para corpus grande
│   ├── OPEN_ACCESS_SEARCH.md          # Búsqueda open access (bioRxiv, PLOS, PMC)
│   ├── PIPELINE_SPECIES.md            # Pipeline para las 12 especies representativas GOC
│   ├── PROJECT_PROGRESS.md            # Estado de avance del proyecto
│   ├── diagrams/                      # Diagramas y visualizaciones
│   │   └── pipeline_rag_diagrama.svg
│   ├── references/                    # Documentos de referencia
│   │   └── Rojo_Acosta_2025.pdf
│   └── pipeline_presentation.pptx     # Presentación del pipeline
│
├── outputs/                           # Generado por el pipeline (gitignored)
│   ├── state/                         # Archivos de progreso y estado del pipeline
│   ├── pdfs/                          # PDFs organizados por especie (PDF, PDF_GOC)
│   ├── rag_index/                     # Índice FAISS fusionado (maestro) + batch indices
│   ├── search_results/                # CSVs de resultados por especie (búsqueda multi-fuente)
│   ├── search_results_canonical/      # Resultados canonizados por especies del pipeline
│   ├── scopus_results/                # Resultados Scopus (búsqueda paralela)
│   ├── sciencedirect_results/         # Resultados ScienceDirect
│   └── reports/                       # Reportes generados
```

---

## Uso

### Verificar entorno

```bash
python scripts/utils/check_setup.py
```

### Fase 1: Extraer y clasificar especies

```bash
# Extrae especies únicas de data/input/final_taxonomy_occ.csv
python analysis_species/extraer_species_unicas.py

# Clasifica como marina/terrestre (requiere acceso a internet)
python analysis_species/clasificar_habitats.py
```

### Fase 2: Búsqueda de artículos

```bash
# Pipeline completo para todas las especies (reanudable, ejecutar en background)
nohup python scripts/phase_2_search/run_new_species_pipeline.py > outputs/logs/pipeline_new_species.log 2>&1 &

# Buscar especies que aún no tienen resultados
nohup python scripts/phase_2_search/run_search_missing_species.py > outputs/logs/missing_search.log 2>&1 &

# Búsqueda adicional con Scopus (paralela)
nohup python scripts/phase_2_search/run_scopus_search.py > outputs/logs/scopus_search.log 2>&1 &

# Búsqueda manual por especie (CLI interactivo)
python scripts/utils/buscar.py "Sardinops sagax" --sources pubmed,crossref,arxiv
```

### Fase 3: Descarga de PDFs

```bash
# Descargar PDFs (acceso abierto + doi2pdf)
nohup python scripts/phase_3_download/download_pdfs.py > outputs/logs/pdf_download.log 2>&1 &

# Descargar artículos del Golfo de California
python scripts/phase_3_download/download_goc_pdfs.py

# Descargar resultados de ScienceDirect
python scripts/phase_3_download/run_sciencedirect_download.py
```

### Fase 4: Canonización y limpieza

```bash
# Organizar resultados por especie canónica
python scripts/reorganize_canonical_search_results.py

# Limpiar filas ruidosas (CrossRef/ArXiv sin coincidencia de especie)
python scripts/clean_noisy_results.py
```

### Fase 5: Indexación RAG

```bash
# Indexación paralela (recomendado para corpus grande)
python scripts/phase_5_indexing/indexar_paralelo.py --workers 8

# Monitorear progreso (terminal separada)
python scripts/phase_5_indexing/monitor_indexacion.py

# Fusionar índices batch en índice maestro
python scripts/phase_5_indexing/merge_indices.py

# Indexación simple (corpus pequeño)
python scripts/phase_5_indexing/indexar.py
```

### Fase 6: Consulta GraphRAG

```bash
# Consulta RAG semántica interactiva
python scripts/phase_6_query/buscar_rag.py

# Construir grafo de conocimiento desde chunks indexados
python scripts/phase_6_query/construir_grafo.py

# Visualizar grafo (genera HTML interactivo)
python scripts/phase_6_query/visualizar_grafo.py

# Consultar parámetros poblacionales por especie (RAG + FishBase)
python scripts/phase_6_query/consultar_parametros_rag.py --species "Sardinops sagax"
```

### Servidor API (opcional)

```bash
# Iniciar servidor FastAPI en background
python scripts/utils/cli.py start

# Ver estado del pipeline
python scripts/utils/cli.py status

# Disparar pipeline via HTTP
python scripts/utils/cli.py trigger-pipeline

# Detener servidor
python scripts/utils/cli.py stop
```

---

## Datos de entrada

| Archivo | Descripción |
|---------|-------------|
| `data/input/final_taxonomy_occ.csv` | Lista canónica de ~11,800 especies marinas (INPUT principal) |
| `data/input/occurrence_data_revised_taxonomy.csv` | Base de datos de ocurrencia con taxonomía revisada |
| `outputs/pdfs/` | PDFs organizados por especie para indexación |

---

## Archivos de estado

El pipeline genera archivos de progreso en `outputs/state/` para ser reanudable:

| Archivo | Generado por |
|---------|-------------|
| `search_progress.json` | `search_articles.py`, `run_new_species_pipeline.py` |
| `download_progress.json` | `download_pdfs.py` |
| `missing_search_progress.json` | `run_search_missing_species.py` |
| `scopus_search_state.json` | `run_scopus_search.py` |
| `sciencedirect_download_state.json` | `run_sciencedirect_download.py` |
| `pipeline_state.json` | `pipeline_manager.py` |

Estos archivos son **gitignored** — no se versionan.

---

## Reportes

Los reportes generados se guardan en `outputs/reports/`:

```bash
# Generar reporte de descarga e indexación
python generar_reporte.py
```

---

## Tests

```bash
# Ejecutar todos los tests
pytest pipeline/ database_connectors/ -v

# Con cobertura
pytest --cov=pipeline --cov=scientific_search -v
```

---

## Documentación adicional

| Documento | Contenido |
|-----------|-----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitectura del sistema, API server, ciclo de vida |
| [docs/EMBEDDING.md](docs/EMBEDDING.md) | Sistema de embeddings, modelos, indexación paralela |
| [docs/PARALLEL_INDEXING.md](docs/PARALLEL_INDEXING.md) | Estrategia para indexar corpus de 42K+ PDFs |
| [docs/OPEN_ACCESS_SEARCH.md](docs/OPEN_ACCESS_SEARCH.md) | Búsqueda open access (bioRxiv, PLOS, PMC) |
| [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md) | Estado de avance del proyecto |

---

## Licencia

Ver [LICENSE](LICENSE).
