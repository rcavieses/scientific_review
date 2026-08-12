# 📋 Guía: Completación Automática de Parámetros Poblacionales

## 🎯 Objetivo

Usar el sistema RAG para buscar parámetros poblacionales de especies vertebradas en la literatura científica del Golfo de California y completar automáticamente la tabla Excel.

## 📊 Datos de Entrada

- **Grupos funcionales**: `data/input/grupos_funcionals_Atlantis_GOC - full_taxonomy.csv`
  - 6,508 especies totales
  - 1,122 vertebrados en 52 grupos funcionales
  
- **Tabla a completar**: `data/input/Atlantis_GOC_parametros_bioogicos.xlsx`
  - Sheet: `parameters`
  - Columnas: biomass, abundance, body size, max age, mortality rate, Lmax, Von Bertalanffy params, growth rate, maturity age, larval duration, spawning dates, migratory status, etc.

- **Índice RAG**: `outputs/rag_index_goc/`
  - 433 PDFs del Golfo de California
  - 10,504 chunks semánticos
  - Embeddings: all-MiniLM-L6-v2 (384-dim)

## 🚀 Inicio Rápido

### 1. Prueba el Sistema (opcional pero recomendado)

```bash
cd /home/atlantis/scientific_review
python scripts/test_parameter_extraction.py
```

Esto verifica que:
- ✓ Índice RAG está disponible
- ✓ RAG Query Engine funciona correctamente
- ✓ Las respuestas se parsean como JSON
- ✓ Parámetros se extraen correctamente

### 2. Procesa el Primer Grupo Funcional

```bash
python scripts/complete_population_parameters.py
```

**Comportamiento:**
- Lee todas las especies de un grupo funcional
- Para cada especie, consulta el RAG con un prompt estructurado
- Extrae parámetros en formato JSON
- Los inserta en el Excel con formato visual (texto verde)
- Guarda el progreso en `outputs/rag_completion_progress.json`
- Si no hay información para una especie, simplemente continúa a la siguiente

**Tiempo estimado:** 5-15 minutos por grupo (depende del número de especies)

### 3. Continuar con Siguientes Grupos

Ejecuta nuevamente el mismo script:

```bash
python scripts/complete_population_parameters.py
```

Automáticamente continuará desde donde se detuvo (gracias al archivo `rag_completion_progress.json`).

## 📋 Parámetros Extraídos

El sistema extrae los siguientes parámetros:

| Parámetro | Columna Excel | Tipo | Descripción |
|-----------|--------------|------|-------------|
| `biomass_mt` | F | float | Biomasa en toneladas métricas |
| `abundance_numbers` | G | float | Abundancia en número de individuos |
| `mean_body_size` | H | float | Tamaño corporal promedio (cm) |
| `max_age` | J | float | Edad máxima (años) |
| `natural_mortality` | K | float | Tasa de mortalidad natural (0-1) |
| `Lmax` | L | float | Longitud máxima (cm) |
| `Von_bertalanffy_a` | M | float | Coeficiente 'a' |
| `Von_bertalanffy_b` | N | float | Coeficiente 'b' |
| `growth_rate` | O | float | Tasa de crecimiento |
| `age_first_maturity` | R | float | Edad de primera madurez (años) |
| `larval_duration` | U | float | Duración larval (días) |
| `StartSpawnDayOfYear` | V | int | Día de inicio de desove (1-365) |
| `EndSpawnDayOfYear` | W | int | Día de fin de desove (1-365) |
| `IsMigratory` | X | string | ¿Es migratoria? ("Yes"/"No") |

## 💡 Cómo Funciona

### Flujo de Procesamiento

```
1. Carga índice FAISS (RAG)
   ↓
2. Para cada grupo funcional:
   ↓
3.   Para cada especie única en el grupo:
   ↓
4.     Consulta RAG con prompt estructurado
        → Sistema pide respuesta en JSON
   ↓
5.     Extrae parámetros de la respuesta
   ↓
6.     Encuentra especie en Excel
   ↓
7.     Inserta valores en columnas apropiadas
   ↓
8.     Marca celdas con color verde (completadas)
   ↓
9.     Guarda Excel y progreso
```

### Prompt Estratégico

El script usa un prompt del sistema personalizado que le pide a Claude:

> "Eres un asistente especializado en extraer parámetros poblacionales de literatura científica marina.
> Tu tarea es extraer información SOLO del contexto proporcionado y devolver un JSON estructurado.
> Si no encuentras un parámetro, establécelo como null.
> Retorna ÚNICAMENTE un JSON válido sin explicaciones adicionales."

Esto asegura que:
- ✓ Las respuestas sean JSON estructurado
- ✓ Solo valores verificados en documentos
- ✓ Formato consistente para parsing automático
- ✓ Sin alucinaciones o inventos

## 📊 Monitorear Progreso

### Log en Tiempo Real

```bash
tail -f outputs/logs/rag_parameter_completion.log
```

### Archivo de Progreso

```bash
cat outputs/rag_completion_progress.json | jq
```

Muestra:
- Último grupo procesado
- Grupos completados con estadísticas
- Especies sin información encontrada
- Errores (si hubo)

## 🎓 Ejemplos de Salida

### Consulta Exitosa

```json
{
  "biomass_mt": 150000,
  "abundance_numbers": 5000000,
  "mean_body_size": 45.5,
  "max_age": 12,
  "natural_mortality": 0.25,
  "Lmax": 150,
  "Von_bertalanffy_a": 0.05,
  "Von_bertalanffy_b": 3.15,
  "growth_rate": 0.30,
  "age_first_maturity": 3,
  "larval_duration": 25,
  "StartSpawnDayOfYear": 90,
  "EndSpawnDayOfYear": 180,
  "IsMigratory": "Yes"
}
```

### Sin Información

```json
{
  "biomass_mt": null,
  "abundance_numbers": null,
  "max_age": null,
  "natural_mortality": null,
  "IsMigratory": null,
  ...
}
```

(La especie se salta sin hacer nada)

## ⚙️ Configuración

Puedes modificar en `scripts/complete_population_parameters.py`:

```python
# Número de chunks a recuperar
top_k=5  # Aumentar para más contexto (más lento)

# Score mínimo de similitud
min_score=0.2  # Bajar para ser más permisivo

# Modelo LLM
model="claude-haiku-4-5-20251001"  # O cambiar a claude-opus-5 si necesitas más precisión

# Máximo tokens en respuesta
max_tokens=1024  # Aumentar si respuestas se truncan
```

## 📈 Estadísticas Esperadas

Basado en los 1,122 vertebrados en 52 grupos:

- **Mejor escenario**: 40-50% de especies con algún parámetro encontrado
- **Caso típico**: 20-35% con información
- **Por grupo**: 2-50 especies según tamaño del grupo

**Estimación de tiempo total** (todos los grupos):
- Con Haiku: ~6-12 horas (parallelizable si separas grupos)
- Con Opus: ~12-24 horas (más preciso, más lento)

## 🔄 Reanudar Después de Interrupción

El script guarda progreso automáticamente. Simplemente ejecuta:

```bash
python scripts/complete_population_parameters.py
```

Continuará desde el siguiente grupo después del último procesado.

## 🐛 Troubleshooting

### Error: "Índice RAG no encontrado"

```bash
# Reconstruir índice
python scripts/run_exhaustive_rebuild.py
```

### Error: "ANTHROPIC_API_KEY not found"

```bash
# Verificar variable de entorno
echo $ANTHROPIC_API_KEY

# O crear .env
cp .env.example .env
# Editar .env con tu API key
```

### Respuestas truncadas o incompletas

Aumentar `max_tokens`:

```python
# En scripts/complete_population_parameters.py
query_engine = RAGQueryEngine(
    ...
    max_tokens=2048  # Era 1024
)
```

### Bajo porcentaje de éxito

1. Verificar que los PDFs están bien indexados
2. Probar con una especie manualmente en `test_parameter_extraction.py`
3. Considerar usar modelo más potente (Opus en lugar de Haiku)

## 📚 Recursos Relacionados

- `RAG_EXHAUSTIVE_REBUILD.md` — Cómo reconstruir el índice
- `GUIA_RAPIDA_RAG.md` — Referencia del sistema RAG
- `pipeline/rag/query_engine.py` — Código del Query Engine
- `pipeline/rag/vector_db.py` — Código del Vector DB

## ✅ Checklist

Antes de ejecutar a escala:

- [ ] Prueba `test_parameter_extraction.py` pasa correctamente
- [ ] Primer grupo procesa exitosamente
- [ ] Excel se actualiza correctamente
- [ ] Archivo de progreso se crea en `outputs/rag_completion_progress.json`
- [ ] Logs en `outputs/logs/rag_parameter_completion.log` son limpios

## 🎯 Próximos Pasos

1. **Procesamiento completo**: Ejecutar para todos los 52 grupos
2. **Análisis de cobertura**: Ver qué parámetros se llenaron más
3. **Manual QA**: Verificar muestras aleatorias de datos extraídos
4. **Enriquecimiento**: Complementar con otras fuentes si es necesario
5. **Exportación**: Convertir Excel a CSV/JSON para análisis

---

**Creado:** Agosto 2026  
**Última actualización:** 2026-08-11
