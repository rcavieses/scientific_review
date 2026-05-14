# Arquitectura del Sistema

## 📁 Estructura de Directorios

```
scientific_review/
├── server.py                          # Servidor FastAPI principal
├── pipeline_manager.py                # Orquestador del pipeline
├── cli.py                            # Interfaz CLI
├── run_server.sh                     # Script bash para controlar servidor
├── check_setup.py                    # Verificador de dependencias
│
├── SERVIDOR.md                       # Documentación del servidor
├── TUTORIAL.md                       # Tutorial paso a paso
├── ARQUITECTURA.md                   # Este archivo
│
├── requirements.txt                  # Dependencias Python
│
├── analysis_species/                 # Análisis y clasificación
│   ├── __init__.py
│   ├── clasificar_habitats.py       # PASO 1: Clasificar hábitats
│   ├── extraer_species_unicas.py    # Herramienta auxiliar
│   ├── species_unicas.csv           # (entrada) especies únicas
│   ├── species_acuaticas.csv        # (salida) especies MARINE/FRESHWATER
│   ├── species_terrestres.csv       # (salida) especies TERRESTRIAL
│   ├── species_pendientes.csv       # (salida) sin datos de hábitat
│   └── cache_habitats.json          # Cache de consultas API
│
├── search_results/                   # Resultados de búsqueda (PASO 3)
│   └── *.csv                        # CSV por especie con DOIs/URLs
│
├── pdfs/                            # PDFs descargados (PASO 4)
│   └── *.pdf                        # PDFs para indexación
│
├── rag_index/                       # Índice FAISS (PASO 5)
│   ├── index.faiss                  # Índice de embeddings
│   └── metadata.json                # Metadata de documentos
│
├── reporte.md                       # Reporte final (PASO 6)
│
├── server.log                       # Logs del servidor
├── .pipeline_state.json             # Estado persistente
├── .server.pid                      # PID del servidor
│
├── scripts/                         # Scripts auxiliares
│   ├── buscar_crossref.py
│   ├── buscar_sciencedirect.py
│   ├── buscar_pubmed.py
│   ├── buscar_arxiv.py
│   └── buscar_scopus.py
│
├── database_connectors/             # Conectores a bases de datos
│   ├── base.py
│   ├── models.py
│   └── fishbase_adapter.py
│
└── [otros archivos del proyecto...]
```

---

## 🔄 Flujo de Datos

### Entrada → Procesamiento → Salida

```
species_unicas.csv (entrada)
    ↓
[PASO 1: Clasificar Hábitats]
    ↓ (consulta WoRMS + GBIF)
    ├→ species_acuaticas.csv
    ├→ species_terrestres.csv
    └→ species_pendientes.csv
    ↓
[PASO 2: Filtrar MARINE]
    ↓ (memoria)
    └→ lista de especies MARINE
    ↓
[PASO 3: Buscar Artículos]
    ↓ (APIs científicas)
    └→ search_results/*.csv (DOIs/URLs)
    ↓
[PASO 4: Descargar PDFs]
    ↓
    └→ pdfs/*.pdf
    ↓
[PASO 5: Indexar RAG]
    ↓ (FAISS)
    └→ rag_index/
    ↓
[PASO 6: Generar Reporte]
    ↓
    └→ reporte.md
```

---

## 🏗️ Componentes Principales

### 1. **server.py** - Servidor FastAPI

**Responsabilidades:**
- Exponer API HTTP
- Manejar solicitudes de inicio/parada
- Servir estado y logs
- Permitir descargas de archivos

**Endpoints principales:**
```
GET  /health           → Health check
GET  /status           → Estado del pipeline
POST /start            → Iniciar pipeline
GET  /results          → Archivos disponibles
GET  /log              → Logs del servidor
GET  /docs             → Swagger UI
```

**Características:**
- CORS habilitado para acceso desde cualquier origen
- Logging a archivo y consola
- Interfaz Swagger automática
- Ejecución en background thread

### 2. **pipeline_manager.py** - Gestor de Pipeline

**Responsabilidades:**
- Orquestar ejecución de pasos
- Persistir estado a disco
- Ejecutar en threads separados
- Manejar errores y recuperación

**Estados (PipelineStage):**
```
idle → classifying_habitats → filtering_marine 
    → searching_articles → downloading_pdfs 
    → indexing_rag → generating_report 
    → completed | failed
```

**Persistencia:**
- `.pipeline_state.json` - Estado actual
- Permite reanudación si se interrumpe

### 3. **cli.py** - Interfaz de Línea de Comandos

**Responsabilidades:**
- Proporcionar interfaz amigable
- Comunicarse con servidor HTTP
- Formatear salida con colores
- Manejar argumentos de línea de comandos

**Comandos:**
```bash
start              # Iniciar servidor
stop               # Detener servidor
status             # Ver estado
logs               # Ver logs
trigger-pipeline   # Iniciar pipeline
results            # Ver archivos
```

### 4. **run_server.sh** - Script Bash

**Responsabilidades:**
- Controlar servidor desde bash
- Manejo de PID
- Start/stop/restart
- Logs en tiempo real

---

## 🔌 Integración de APIs (PASO 1)

El paso 1 utiliza dos APIs científicas:

### WoRMS (World Register of Marine Species)
```
Consulta: GET /rest/AphiaRecordsByNames
Parámetros: scientificnames[]
Respuesta: JSON con registros encontrados
```

### GBIF (Global Biodiversity Information Facility)
```
Consulta 1: GET /species/match?name=...
Respuesta: usageKey
Consulta 2: GET /species/{key}
Respuesta: { marine, freshwater, terrestrial }
```

---

## 💾 Persistencia de Estado

### .pipeline_state.json

```json
{
  "stage": "classifying_habitats",
  "progress": {
    "status": "completado",
    "total_acuaticas": 523,
    "marine_count": 342,
    "sample": ["Genus species 1", "Genus species 2"]
  },
  "start_time": "2024-01-15T14:30:00.000000",
  "end_time": null,
  "error": null
}
```

**Propósito:**
- Permitir reanudación
- Auditoría de ejecución
- Debugging de errores

---

## 🚀 Ciclo de Vida de Ejecución

```
1. Usuario ejecuta: python3 cli.py start
   └→ Lanza server.py en subprocess/background
   └→ FastAPI inicia en puerto 8000

2. Usuario ejecuta: python3 cli.py trigger-pipeline
   └→ POST /start
   └→ PipelineManager.run_pipeline()
   └→ Thread inicia ejecución
   └→ Retorna inmediatamente

3. Pipeline ejecuta en background:
   └→ Paso 1: 10-30 minutos
   └→ Paso 2: < 1 segundo
   └→ Paso 3-5: depende de implementación
   └→ Paso 6: < 1 segundo

4. Usuario monitorea: python3 cli.py status
   └→ GET /status
   └→ Devuelve estado actual
   └→ Puede hacer esto en cualquier momento

5. Usuario descarga: python3 cli.py results
   └→ GET /results
   └→ Lista archivos disponibles

6. Usuario detiene: python3 cli.py stop
   └→ Mata el servidor (pipeline se interruptiría)
   └→ Estado se persiste
```

---

## 🔐 Seguridad

### Consideraciones

1. **Acceso Local por Defecto**
   - Host: 127.0.0.1 (solo local)
   - Puerto: 8000
   - Para remoto: usa `--host 0.0.0.0`

2. **Sin Autenticación**
   - Asume entorno local seguro
   - Para producción: agregar JWT/OAuth

3. **Validación de Rutas**
   - Previene directory traversal
   - Valida límites de directorios

---

## 📊 Rendimiento

### Estimaciones

| Componente | Tiempo | Escalabilidad |
|------------|--------|---------------|
| Paso 1 | 10-30 min | O(n) con APIs |
| Paso 2 | < 1 seg | O(n) en memoria |
| Paso 3 | Variable | O(n) con APIs |
| Paso 4 | Variable | O(n·tamaño PDF) |
| Paso 5 | 5-10 min | O(n·dim) indexación |
| Paso 6 | < 1 seg | O(1) |

### Optimizaciones Posibles

1. **Paralelización**: Procesar especies en paralelo
2. **Caching**: Guardar resultados de APIs
3. **Batching**: Agrupar solicitudes HTTP
4. **Índices**: Usar índices en búsquedas

---

## 🧪 Testing

### Estructura propuesta

```
tests/
├── test_pipeline_manager.py    # Tests del manager
├── test_server.py              # Tests de API
├── test_cli.py                 # Tests de CLI
└── test_integration.py         # Tests end-to-end
```

### Ejecutar tests

```bash
pytest tests/ -v
pytest tests/ --cov=.           # Con cobertura
```

---

## 📈 Monitoreo y Observabilidad

### Métricas Disponibles

1. **Estado del Pipeline**
   - Etapa actual
   - Tiempo inicio/fin
   - Errores

2. **Logs**
   - `server.log` - Logs del servidor
   - `.pipeline_state.json` - Estado persistente

3. **Archivos de Salida**
   - Tamaño de CSVs
   - Cantidad de PDFs
   - Tamaño del índice FAISS

### Próximos: Métricas Avanzadas

- Endpoint `/metrics` con Prometheus
- Dashboard Grafana
- Notificaciones Slack/email

---

## 🔮 Mejoras Futuras

### Corto Plazo (v1.1)
- [ ] Pausa/reanudación del pipeline
- [ ] Validación de datos de entrada
- [ ] Manejo de errores transitorios

### Mediano Plazo (v1.2)
- [ ] Implementar pasos 3-5
- [ ] Base de datos (PostgreSQL)
- [ ] Autenticación y autorización

### Largo Plazo (v2.0)
- [ ] Interfaz web (React/Vue)
- [ ] Cluster distribuido
- [ ] ML model training
- [ ] API GraphQL

---

## 📝 Notas de Desarrollo

### Para Agregar Nuevo Paso

1. Crear método en `PipelineManager._step_XXX()`
2. Agregar stage en `PipelineStage` enum
3. Llamar desde `_run_pipeline_internal()`
4. Actualizar documentación

### Para Agregar Nuevo Endpoint

1. Crear función con decorador `@app.get()` en `server.py`
2. Usar tipos Pydantic para inputs/outputs
3. Manejar excepciones con HTTPException
4. Documentar en este archivo

---

## 📞 Contacto y Soporte

Para preguntas o mejoras:
- Ver logs: `python3 cli.py logs`
- Verificar estado: `python3 cli.py status`
- Revisar este documento

