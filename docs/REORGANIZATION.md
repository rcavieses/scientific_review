# Reorganización de la Estructura del Proyecto

## Resumen

Se ha reorganizado la estructura del proyecto para mejorar la claridad y mantenibilidad. Todos los scripts sueltos en la raíz han sido organizados en subcarpetas temáticas bajo `scripts/`, y los archivos de datos han sido movidos a `data/`.

## Cambios principales

### 1. **Datos movidos a `data/`**
   - `final_taxonomy_occ.csv` → `data/input/`
   - `occurrence_data_revised_taxonomy.csv` → `data/input/`
   - `species_occurrence_database_goc_May_2026.zip` → `data/input/`
   - `Rojo_Acosta_2025.pdf` → `docs/references/`

### 2. **Scripts organizados por fase en `scripts/`**

#### `scripts/setup/`
   - Archivos de configuración del entorno
   - `activate.sh`, `setup_env.sh`, `setup_env.bat`

#### `scripts/phase_2_search/`
   - Scripts de búsqueda de artículos (Fase 2)
   - `run_new_species_pipeline.py`
   - `run_scopus_search.py`
   - `search_articles.py`
   - Otros scripts de búsqueda

#### `scripts/phase_3_download/`
   - Scripts de descarga de PDFs (Fase 3)
   - `download_pdfs.py`
   - `download_goc_pdfs.py`
   - `run_sciencedirect_download.py`
   - `run_rescan_empty_species.py`

#### `scripts/phase_5_indexing/`
   - Scripts de indexación RAG (Fase 5)
   - `indexar.py`, `indexar_paralelo.py`
   - `monitor_indexacion.py`, `merge_indices.py`
   - `run_rag_indexing.py`

#### `scripts/phase_6_query/`
   - Scripts de consulta GraphRAG (Fase 6)
   - `buscar_rag.py`, `construir_grafo.py`
   - `visualizar_grafo.py`, `consultar_parametros_rag.py`

#### `scripts/utils/`
   - Scripts de utilidad y soporte
   - `check_setup.py`, `cli.py`, `server.py`
   - `pipeline_manager.py`, `generar_reporte.py`
   - `buscar.py` (búsqueda interactiva)

#### `scripts/legacy/`
   - Scripts archivados
   - `build_articulo.mjs` y otros deprecated

### 3. **Salida (outputs) reorganizada**
   - Logs: `outputs/logs/`
   - Resultados: `outputs/results/`
   - Estado: `outputs/state/`

### 4. **Documentación**
   - Diagramas: `docs/diagrams/`
   - Referencias: `docs/references/`

## Actualización de imports

Todos los scripts han sido actualizados para:

1. **Usar rutas correctas a datos de entrada**
   - Cambio: `final_taxonomy_occ.csv` → `data/input/final_taxonomy_occ.csv`
   - Cambio: `occurrence_data_revised_taxonomy.csv` → `data/input/occurrence_data_revised_taxonomy.csv`

2. **Importar módulos desde ubicaciones correctas**
   ```python
   # Antes
   from search_articles import search_articles_batch
   from download_pdfs import download_all_articles
   
   # Ahora
   from scripts.phase_2_search.search_articles import search_articles_batch
   from scripts.phase_3_download.download_pdfs import download_all_articles
   ```

3. **Ajustar rutas de proyecto**
   - El `PROJECT_ROOT` se calcula correctamente desde la nueva ubicación del script
   - Se añade la raíz del proyecto a `sys.path` para permitir importaciones

4. **Referenciar scripts ejecutables**
   - Cambio: `PROJECT_ROOT / "indexar.py"` → `PROJECT_ROOT / "scripts" / "phase_5_indexing" / "indexar.py"`
   - Cambio: `PROJECT_ROOT / "server.py"` → `PROJECT_ROOT / "scripts" / "utils" / "server.py"`

## Ejecución de scripts

### Desde la raíz del proyecto
```bash
# Fase 2: Búsqueda
python scripts/phase_2_search/run_new_species_pipeline.py

# Fase 3: Descarga
python scripts/phase_3_download/download_pdfs.py

# Fase 5: Indexación
python scripts/phase_5_indexing/indexar_paralelo.py --workers 8

# Fase 6: Consulta
python scripts/phase_6_query/buscar_rag.py

# Utilidades
python scripts/utils/check_setup.py
python scripts/utils/cli.py start
```

## Estructura de directorios __init__.py

Se han creado archivos `__init__.py` en todos los directorios de scripts para permitir:
- Importación de módulos desde cualquier parte del proyecto
- Correcta resolución de paths relativos

```
scripts/
├── __init__.py
├── phase_2_search/
│   └── __init__.py
├── phase_3_download/
│   └── __init__.py
├── phase_5_indexing/
│   └── __init__.py
├── phase_6_query/
│   └── __init__.py
├── utils/
│   └── __init__.py
└── ...
```

## Notas importantes

1. **Compatibilidad**: Los cambios mantienen la funcionalidad de todos los scripts
2. **Logs**: Los logs ahora se guardan en `outputs/logs/` en lugar de la raíz
3. **Datos de entrada**: Todos los scripts buscan archivos en `data/input/`
4. **Estado del pipeline**: Se mantiene en `outputs/state/` como antes

## Reversión (si es necesario)

Si necesitas revertir esta reorganización:
1. Mover archivos de vuelta a la raíz desde sus ubicaciones en `scripts/` y `data/`
2. Actualizar imports para remover prefijos `scripts.phase_X.`
3. Ajustar PROJECT_ROOT en cada script

Sin embargo, la nueva estructura es más mantenible y se recomienda mantenerla.
