# FishBase Integration Guide

## Overview

Se ha creado un **sistema paralelo independiente** para consultar parámetros poblacionales de especies del Golfo de California (GOC) usando **FishBase** (la base de datos más completa de peces del mundo).

Este sistema **funciona independientemente del RAG**, permitiendo:
- Extracción rápida de parámetros desde FishBase
- Validación cruzada con resultados del RAG
- Comparación de datos para identificar discrepancias
- Integración de múltiples fuentes de información

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│  FishBase Population Parameters Extraction System            │
└─────────────────────────────────────────────────────────────┘
                              ▼
        ┌─────────────────────────────────┐
        │  goc_species_list_generator.py  │  (Paso 1)
        │  - Genera lista de 83 especies  │
        │  - Organizado por grupo        │
        └──────────────┬──────────────────┘
                       ▼
        ┌─────────────────────────────────┐
        │  fishbase_scraper.py            │  (Paso 2)
        │  - Web scraping de FishBase    │
        │  - Extrae parámetros           │
        └──────────────┬──────────────────┘
                       ▼
        ┌─────────────────────────────────┐
        │  outputs/fishbase_*.csv         │  (Resultados)
        │  - Parámetros poblacionales    │
        │  - URLs de perfiles            │
        └─────────────────────────────────┘
                       ▼
        ┌─────────────────────────────────┐
        │  Validación & Integración       │
        │  - Comparar con RAG            │
        │  - Consolidar resultados       │
        └─────────────────────────────────┘
```

## Archivos Creados

### 1. Scripts Principales

| Archivo | Función | Entrada | Salida |
|---------|---------|---------|--------|
| `goc_species_list_generator.py` | Genera lista GOC (83 especies) | Nada (hardcoded) | `goc_species_list.csv` |
| `fishbase_scraper.py` | Web scraper de FishBase | Lista de especies | `fishbase_*.csv` |
| `fishbase_population_fetcher.py` | Fetcher alternativo via API | Lista de especies | `fishbase_*.csv` |
| `run_fishbase_queries.sh` | Orquestador completo (pipeline) | Nada | CSV + reportes |
| `demo_fishbase_query.py` | Ejemplos de uso (demostrativo) | Nada | Outputs demo |

### 2. Documentación

| Archivo | Contenido |
|---------|----------|
| `FISHBASE_README.md` | Documentación técnica detallada (en scripts/) |
| `FISHBASE_INTEGRATION_GUIDE.md` | Esta guía (en raíz del proyecto) |

### 3. Configuración

- `requirements.txt` actualizado con `beautifulsoup4>=4.11.0`

## Instalación Rápida

### Opción 1: Setup Automático

```bash
cd /home/atlantis/scientific_review

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar pipeline completo
./scripts/run_fishbase_queries.sh
```

### Opción 2: Setup Manual

```bash
# 1. Generar lista de especies
python3 scripts/goc_species_list_generator.py

# 2. Ejecutar scraper
python3 scripts/fishbase_scraper.py \
    --output outputs/fishbase_parameters.csv \
    --format csv \
    --delay 1.0

# 3. Ver resultados
ls -lh outputs/fishbase_*.csv
```

### Opción 3: Demo

```bash
# Ver ejemplos de uso
python3 scripts/demo_fishbase_query.py
```

## Uso Detallado

### Generar Lista de Especies GOC

```bash
python3 scripts/goc_species_list_generator.py
```

**Salida esperada:**
- `data/input/goc_species_list.csv` (83 especies)
- Organizadas en 12 grupos ecológicos:
  - Rocky Bottom (9 especies)
  - Sandy Bottom (7 especies)
  - Small Pelagics (5 especies)
  - Medium Pelagics (7 especies)
  - Large Pelagics (7 especies)
  - Cephalopods (5 especies)
  - Snappers/Groupers (8 especies)
  - Carangidae (7 especies)
  - Crustaceans (7 especies)
  - Reef Fish (7 especies)
  - Deep Sea (5 especies)
  - Elasmobranchs (9 especies)

### Ejecutar Scraper de FishBase

**Modo simple (todas las especies):**
```bash
python3 scripts/fishbase_scraper.py
```

**Modo personalizado:**
```bash
python3 scripts/fishbase_scraper.py \
    --output results/mi_salida.csv \
    --format csv \
    --delay 2.0  # Más lento = más respeto al servidor
```

**Opciones:**
- `--output FILE` - Archivo de salida (default: `outputs/fishbase_scrapped_parameters.csv`)
- `--format {csv,json}` - Formato (default: csv)
- `--delay SECONDS` - Espera entre requests (default: 1.0)

**Salida esperada:**

| Column | Ejemplo |
|--------|---------|
| `scientific_name` | Sardinops sagax |
| `common_name` | Pacific sardine |
| `found` | True/False |
| `tmax` | 20.0 |
| `lmax` | 28.5 |
| `linf` | 30.2 |
| `k` | 0.35 |
| `m` | 0.45 |
| `trophic_level` | 3.5 |
| `profile_url` | https://www.fishbase.org/summary/... |

### Usar API Fetcher (Alternativa)

```bash
# Con especies por defecto
python3 scripts/fishbase_population_fetcher.py --use-defaults

# Con archivo personalizado
python3 scripts/fishbase_population_fetcher.py \
    --species mi_lista.csv \
    --output resultados.json \
    --format json
```

## Parámetros Poblacionales Extraídos

El sistema extrae los siguientes parámetros biológicos:

### Crecimiento
- **linf** (L∞): Longitud asintótica (von Bertalanffy)
- **k**: Coeficiente de crecimiento
- **tmax**: Edad máxima (años)
- **lmax**: Longitud máxima observada (cm)

### Reproducción
- **lmat**: Longitud de madurez
- **fecundity**: Fecundidad (huevos por adulto)

### Mortalidad
- **m**: Tasa de mortalidad natural

### Ecología
- **trophic_level**: Nivel trófico
- **habitat**: Hábitat preferido
- **salinity**: Salinidad
- **depth_range**: Rango de profundidad

## Validación y Comparación

### Comparar con RAG

```python
import pandas as pd

# Cargar resultados
fishbase = pd.read_csv('outputs/fishbase_scrapped_parameters.csv')
rag = pd.read_csv('outputs/rag_parameters.csv')

# Merge
merged = fishbase.merge(rag, on='scientific_name', how='outer', suffixes=('_fb', '_rag'))

# Ver discrepancias en tmax (edad máxima)
discrepancias = merged[
    (merged['tmax_fb'].notna()) & 
    (merged['tmax_rag'].notna()) &
    ((merged['tmax_fb'] - merged['tmax_rag']).abs() > 2)  # Diferencia > 2 años
]

print(discrepancias[['scientific_name', 'tmax_fb', 'tmax_rag']])
```

### Generar Reporte Consolidado

```python
import pandas as pd
import numpy as np

# Cargar
fb = pd.read_csv('outputs/fishbase_scrapped_parameters.csv')
rag = pd.read_csv('outputs/rag_parameters.csv')

# Consolidar (prioridad a FishBase como referencia)
consolidated = pd.concat([fb, rag]).drop_duplicates(subset='scientific_name', keep='first')

# Estadísticas
print("Parámetros por grupo ecológico:")
print(fb.groupby('ecological_group').agg({
    'tmax': ['mean', 'std'],
    'lmax': ['mean', 'std'],
    'trophic_level': ['mean', 'std']
}))

# Guardar
consolidated.to_csv('outputs/consolidated_parameters.csv', index=False)
```

## Integración con Pipeline RAG

### Flujo Completo

```bash
# Paso 1: Extraer con FishBase
./scripts/run_fishbase_queries.sh

# Paso 2: Extraer con RAG
python3 scripts/complete_population_parameters_BUSQUEDA4.py

# Paso 3: Consolidar y validar
python3 << 'EOF'
import pandas as pd

fb = pd.read_csv('outputs/fishbase_scrapped_parameters_*.csv', low_memory=False)
rag = pd.read_csv('outputs/rag_parameters.csv')

# Consolidar con metadata
consolidated = fb.merge(
    rag[['scientific_name', 'source_document', 'confidence']],
    on='scientific_name',
    how='left'
)

consolidated.to_csv('outputs/FINAL_parameters.csv', index=False)
print("✓ Consolidated to FINAL_parameters.csv")
EOF
```

## Solución de Problemas

### Problema: "403 Forbidden" desde FishBase

**Causa:** FishBase está bloqueando web scraping directo

**Soluciones:**
1. Aumentar `--delay` a 2-5 segundos
2. Ejecutar en horas fuera de pico
3. Usar `fishbase_population_fetcher.py` (API alternativa)

```bash
# Versión más lenta y respetuosa
python3 scripts/fishbase_scraper.py --delay 3.0
```

### Problema: "Species not found"

**Causa:** Nombre incorrecto o especie no en FishBase

**Soluciones:**
1. Verificar nombre en https://www.fishbase.org
2. Actualizar `goc_species_list.csv`
3. Revisar URL directa construida

```bash
# Verificar manualmente
curl "https://www.fishbase.org/summary/Sardinops-sagax.html" | head -50
```

### Problema: Timeout o conexión rechazada

**Causa:** Red lenta o FishBase no responde

**Soluciones:**
```bash
# Aumentar timeout
export FISHBASE_TIMEOUT=30
python3 scripts/fishbase_scraper.py --delay 2.0

# O usar modo local sin API
python3 scripts/demo_fishbase_query.py
```

## Casos de Uso

### 1. Validar Parámetros RAG

```bash
# Ejecutar ambos sistemas
./scripts/run_fishbase_queries.sh
python3 scripts/complete_population_parameters_BUSQUEDA4.py

# Comparar resultados
python3 scripts/compare_extraction_results.py
```

### 2. Rellenar Huecos en RAG

```python
# Identificar parámetros faltantes en RAG
import pandas as pd

fb = pd.read_csv('outputs/fishbase_scrapped_parameters.csv')
rag = pd.read_csv('outputs/rag_parameters.csv')

# Especies en FishBase pero no en RAG
missing_in_rag = fb[~fb['scientific_name'].isin(rag['scientific_name'])]

# Usar FishBase para llenar
rag = pd.concat([rag, missing_in_rag[['scientific_name', 'tmax', 'lmax', 'k']]])
rag.to_csv('outputs/rag_parameters_updated.csv', index=False)
```

### 3. Análisis Comparativo

```bash
# Generar estadísticas por grupo
python3 << 'EOF'
import pandas as pd

df = pd.read_csv('outputs/fishbase_scrapped_parameters.csv')

print("Análisis de parámetros por grupo ecológico:")
stats = df.groupby('ecological_group').agg({
    'tmax': ['count', 'mean', 'std', 'min', 'max'],
    'lmax': ['mean', 'std'],
    'trophic_level': ['mean', 'std']
}).round(2)

print(stats)
EOF
```

## Próximas Mejoras

- [ ] Caché local para evitar re-queries
- [ ] Paralelización de requests
- [ ] Integración con otras bases de datos (SeaLifeBase, LovD)
- [ ] Validación automática de parámetros
- [ ] UI web para revisión de datos
- [ ] Sincronización automática con RAG

## Referencias

- **FishBase:** https://www.fishbase.org
- **SeaLifeBase:** https://www.sealifebase.org
- **Documentación del Sistema RAG:** [GUIA_COMPLETACION_PARAMETROS.md](GUIA_COMPLETACION_PARAMETROS.md)
- **README Principal:** [README.md](README.md)

## Contacto / Soporte

Para dudas sobre el sistema FishBase:
1. Revisar [FISHBASE_README.md](scripts/FISHBASE_README.md)
2. Consultar docstrings en scripts
3. Ejecutar demos: `python3 scripts/demo_fishbase_query.py`
