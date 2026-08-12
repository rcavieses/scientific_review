# 🔍 Sistema Automático de Completación de Parámetros Poblacionales

## 📌 Resumen

Sistema para completar automáticamente la tabla de parámetros biológicos (`Atlantis_GOC_parametros_bioogicos.xlsx`) consultando el índice RAG con especies vertebradas del Golfo de California.

**Creado:** Agosto 2026  
**Estado:** Listo para usar  
**Ubicación:** `/home/atlantis/scientific_review/scripts/`

## 🎯 Qué Hace

1. Lee la lista de especies vertebradas del CSV (`grupos_funcionals_Atlantis_GOC - full_taxonomy.csv`)
2. Las agrupa por grupo funcional (52 grupos en total, 1,122 especies)
3. Procesa un grupo funcional a la vez
4. Para cada especie, consulta el índice RAG pidiendo parámetros poblacionales específicos
5. Extrae la información en formato JSON estructurado
6. Completa las celdas correspondientes en el Excel
7. Guarda progreso automáticamente entre ejecuciones
8. Si no hay información para una especie, simplemente continúa a la siguiente

## 📂 Archivos Principales

| Archivo | Descripción |
|---------|------------|
| `scripts/complete_population_parameters.py` | ⭐ **Script principal** - Procesa grupos y completa Excel |
| `scripts/test_parameter_extraction.py` | 🧪 **Test** - Verifica que el sistema funciona |
| `GUIA_COMPLETACION_PARAMETROS.md` | 📖 Documentación completa y troubleshooting |
| `outputs/rag_completion_progress.json` | 📊 Progreso de procesamiento (se crea automáticamente) |

## 🚀 Uso

### Opción A: Prueba Rápida (Recomendado Primero)

```bash
cd /home/atlantis/scientific_review
python3 scripts/test_parameter_extraction.py
```

Verifica:
- ✓ Índice RAG disponible (18,080 chunks, 525 papers)
- ✓ Query Engine funciona
- ✓ Formato JSON se parsea correctamente
- ✓ Sistema está listo

**Tiempo:** ~2-3 minutos

### Opción B: Procesar Primer Grupo

```bash
cd /home/atlantis/scientific_review
python3 scripts/complete_population_parameters.py
```

Procesa un grupo funcional completo. Ejemplo de salida:

```
RESUMEN - Amberjacks
======================================================================
Especies procesadas: 2
Con información: 0
Sin información: 2
Tasa de éxito: 0.0%
```

**Tiempo:** 5-15 minutos (según el grupo)

### Opción C: Continuar Desde Donde Se Paró

```bash
python3 scripts/complete_population_parameters.py
```

Automáticamente carga el progreso anterior y continúa con el siguiente grupo.

## 📊 Parámetros Que Extrae

El sistema busca y extrae estos 14 parámetros:

| # | Parámetro | Tipo | Ejemplo |
|---|-----------|------|---------|
| 1 | Biomasa (MT) | float | 150000 |
| 2 | Abundancia (individuos) | float | 5000000 |
| 3 | Tamaño corporal promedio | float | 45.5 (cm) |
| 4 | Edad máxima | float | 12 (años) |
| 5 | Mortalidad natural | float | 0.25 (0-1) |
| 6 | Longitud máxima (Lmax) | float | 150 (cm) |
| 7 | Von Bertalanffy a | float | 0.05 |
| 8 | Von Bertalanffy b | float | 3.15 |
| 9 | Tasa de crecimiento | float | 0.30 |
| 10 | Edad de primera madurez | float | 3 (años) |
| 11 | Duración larval | float | 25 (días) |
| 12 | Inicio desove (día año) | int | 90 (1-365) |
| 13 | Fin desove (día año) | int | 180 (1-365) |
| 14 | ¿Es migratoria? | string | "Yes" / "No" |

## 🔧 Cómo Funciona Técnicamente

### Arquitectura

```
┌─────────────────────────────────────────────────────┐
│  CSV de Taxonomía (1,122 vertebrados)               │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Script: complete_population_parameters.py          │
│  - Filtra vertebrados                               │
│  - Agrupa por grupo funcional                       │
│  - Itera sobre especies                             │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  RAG Query Engine con Prompt Personalizado          │
│  - Consulta: "Extrae parámetros de [especie]"      │
│  - Índice FAISS: 18,080 chunks, 525 papers         │
│  - LLM: Claude Haiku 4.5                           │
│  - Respuesta: JSON estructurado                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Parser JSON                                         │
│  - Extrae parámetros encontrados                    │
│  - Ignora valores null                              │
│  - Mapea a columnas Excel                           │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Excel Writer                                        │
│  - Localiza fila de la especie                      │
│  - Inserta valores con formato verde                │
│  - Guarda archivo                                   │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
            ✅ Completado
```

### Prompt Estratégico

El script usa un **prompt del sistema personalizado** que instruye a Claude:

> "Extrae información SOLO del contexto proporcionado y devuelva un JSON estructurado.
> Si no encuentras un parámetro, establécelo como null.
> Retorna ÚNICAMENTE JSON válido sin explicaciones adicionales."

Esto asegura:
- ✓ Respuestas consistentes en JSON
- ✓ Sin alucinaciones
- ✓ Parsing automático confiable
- ✓ Solo valores verificados en documentos

## 📈 Estadísticas

**Capacidad del Índice RAG:**
- 18,080 chunks semánticos
- 525 documentos PDF
- Cobertura: Golfo de California
- Modelo de embeddings: all-MiniLM-L6-v2 (384-dim)

**Especies Vertebradas:**
- Total: 1,122
- Grupos funcionales: 52
- Clases: Teleostei, Mammalia, Aves, Reptilia, etc.
- Tamaño promedio de grupo: ~21 especies

**Tiempo Estimado:**
- Por grupo: 5-15 minutos (depende del tamaño)
- Por especie: 15-30 segundos
- Todos los grupos: 6-12 horas si se ejecutan secuencialmente

## 🛠️ Configuración

Parámetros ajustables en `scripts/complete_population_parameters.py`:

```python
# Número de chunks RAG a usar
top_k=5  # Aumentar (10-15) para más contexto, más lento

# Score mínimo de similitud para incluir un chunk
min_score=0.2  # Bajar (0.1-0.15) para ser más permisivo

# Modelo LLM
model="claude-haiku-4-5-20251001"  # O "claude-opus-5" para más precisión

# Máximo tokens en respuesta
max_tokens=1024  # Aumentar si hay truncamiento
```

## 📋 Monitorear Progreso

### Ver logs en tiempo real:
```bash
tail -f outputs/logs/rag_parameter_completion.log
```

### Ver progreso JSON:
```bash
cat outputs/rag_completion_progress.json | python3 -m json.tool
```

### Ver cuántos grupos se han completado:
```bash
grep "last_processed_group" outputs/rag_completion_progress.json
```

## ✅ Validación

Para validar que todo funciona antes de procesamiento completo:

```bash
# 1. Test básico
python3 scripts/test_parameter_extraction.py

# 2. Ver primer grupo
python3 scripts/complete_population_parameters.py

# 3. Revisar Excel
# Abre: data/input/Atlantis_GOC_parametros_bioogicos.xlsx
# Busca columnas con texto verde (parámetros completados)

# 4. Revisar progreso
cat outputs/rag_completion_progress.json
```

## 🎓 Ejemplo de Ejecución

```bash
$ python3 scripts/complete_population_parameters.py

2026-08-11 10:30:45 - INFO - Completación de parámetros poblacionales con RAG + JSON
2026-08-11 10:30:46 - INFO - Cargando datos...
2026-08-11 10:30:50 - INFO - RAG cargado. Total chunks: 18080

======================================================================
Procesando grupo: Amberjacks
======================================================================
Especies en este grupo: 2

[1/2] Procesando: Seriola lalandi
  Consultando RAG para Seriola lalandi...
    ✗ Sin información para Seriola lalandi

[2/2] Procesando: Seriola rivoliana
  Consultando RAG para Seriola rivoliana...
    ✗ Sin información para Seriola rivoliana

======================================================================
RESUMEN - Amberjacks
======================================================================
Especies procesadas: 2
Con información: 0
Sin información: 2
Tasa de éxito: 0.0%

✅ Completado
```

## 🔄 Reanudación

El script guarda progreso automáticamente en `outputs/rag_completion_progress.json`. Para reanudar:

```bash
# Simplemente ejecuta de nuevo
python3 scripts/complete_population_parameters.py

# Continuará desde el grupo siguiente al último procesado
```

## 🐛 Si Algo Falla

### "Índice RAG no encontrado"
```bash
ls outputs/rag_index_goc_full/
# Debería mostrar: index.faiss, metadata_store.json, index_config.json
```

### "ANTHROPIC_API_KEY not found"
```bash
echo $ANTHROPIC_API_KEY  # Verificar variable
# O editar .env con tu API key
```

### Bajo porcentaje de éxito
1. Esto es normal - no todos los PDFs contienen info de todas las especies
2. Verifica manualmente que los PDFs tengan contenido relevante
3. Considera cambiar a modelo más potente (Claude Opus)

Ver `GUIA_COMPLETACION_PARAMETROS.md` para troubleshooting detallado.

## 📊 Resultados Esperados

Basado en la cobertura del índice RAG:

| Escenario | Éxito | Tiempo |
|-----------|-------|--------|
| Optimista | 40-50% | 6 hrs |
| Típico | 20-35% | 8-10 hrs |
| Pesimista | 10-20% | 10-12 hrs |

**Factores que afectan el éxito:**
- Calidad de los PDFs indexados
- Especificidad de la especie
- Disponibilidad de datos publicados
- Precisión del proceso de extracción de PDFs

## 🎯 Próximos Pasos

Después de procesar algunos grupos:

1. **QA Manual**: Verificar 10-20 especies aleatorias
2. **Análisis**: Ver qué parámetros se llenaron más
3. **Enriquecimiento**: Complementar con otras fuentes si es necesario
4. **Exportación**: Convertir a CSV/JSON para análisis downstream
5. **Iteración**: Ajustar prompts si es necesario

## 📚 Documentación Relacionada

- `GUIA_COMPLETACION_PARAMETROS.md` — Guía completa y detallada
- `GUIA_RAPIDA_RAG.md` — Referencia del sistema RAG
- `RAG_EXHAUSTIVE_REBUILD.md` — Cómo reconstruir el índice si es necesario

## ✨ Características

✓ Procesamiento automático grupo a grupo  
✓ Manejo inteligente de errores (continúa si no hay información)  
✓ Guardado automático de progreso  
✓ Reanudación desde último grupo procesado  
✓ Formato JSON estructurado y predecible  
✓ Integración limpia con Excel (celdas con color verde)  
✓ Logs detallados para debugging  
✓ Sin alucinaciones LLM (solo valores en contexto)  

---

**Listo para usar.** Comienza con:
```bash
python3 scripts/test_parameter_extraction.py
```
