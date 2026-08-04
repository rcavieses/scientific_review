# Servidor del Pipeline de Procesamiento de Especies

Este documento describe cómo ejecutar y controlar el pipeline en segundo plano.

## 🚀 Inicio Rápido

### Opción 1: Usando Python (Recomendado)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Iniciar servidor
python cli.py start

# En otra terminal, monitorear estado
python cli.py status

# Iniciar el pipeline
python cli.py trigger-pipeline

# Ver logs
python cli.py logs

# Detener servidor
python cli.py stop
```

### Opción 2: Usando Bash (Linux/macOS)

```bash
# Hacer el script ejecutable
chmod +x run_server.sh

# Iniciar
./run_server.sh start

# Ver estado
./run_server.sh status

# Logs
./run_server.sh logs

# Detener
./run_server.sh stop
```

---

## 📊 API Endpoints

Una vez el servidor está corriendo, accede a:

- **Dashboard interactivo**: http://127.0.0.1:8000/docs
- **Health check**: `GET /health`
- **Estado del pipeline**: `GET /status`
- **Iniciar pipeline**: `POST /start`
- **Resultados**: `GET /results`
- **Logs**: `GET /log`
- **Descargar archivo**: `GET /download/{file_type}/{filename}`

### Ejemplos con curl

```bash
# Health check
curl http://localhost:8000/health

# Ver estado
curl http://localhost:8000/status

# Iniciar pipeline
curl -X POST http://localhost:8000/start

# Iniciar con force_restart
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{"force_restart": true}'

# Ver resultados
curl http://localhost:8000/results

# Ver logs
curl http://localhost:8000/log
```

---

## 🏗️ Arquitectura

### Componentes

```
┌─────────────────────────────────────────┐
│  CLI (cli.py / run_server.sh)           │
│  Interfaz de usuario en terminal        │
└─────────────┬───────────────────────────┘
              │ HTTP
┌─────────────▼───────────────────────────┐
│  FastAPI Server (server.py)             │
│  - Health checks                        │
│  - Status endpoint                      │
│  - Start/Stop triggers                  │
│  - Results management                   │
└─────────────┬───────────────────────────┘
              │ (thread pool)
┌─────────────▼───────────────────────────┐
│  PipelineManager (pipeline_manager.py)  │
│  - Orquestra pasos del pipeline         │
│  - Persiste estado a disco              │
│  - Ejecuta en background                │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┼─────────┬──────────┐
    │         │         │          │
┌───▼──┐ ┌──▼──┐ ┌────▼──┐ ┌────▼──┐
│Paso1 │ │Paso2│ │Paso3..│ │Paso6  │
│Class │ │Filter│ │Search │ │Report │
└──────┘ └─────┘ └───────┘ └───────┘
```

### Flujo de Ejecución

1. **CLI/usuario** ejecuta `python cli.py start`
2. **CLI** lanza el servidor FastAPI en background
3. **Usuario** llama `python cli.py trigger-pipeline`
4. **FastAPI** recibe solicitud en `/start`
5. **PipelineManager** inicia thread de trabajo
6. **Thread** ejecuta los 6 pasos en secuencia
7. **Cada paso** actualiza estado persistente
8. **Usuario** monitorea con `python cli.py status`
9. **Archivos** se guardan automáticamente durante ejecución

### Persistencia de Estado

El estado del pipeline se persiste en:
- `.pipeline_state.json` - Estado actual (etapa, progreso, errores)
- `server.log` - Logs del servidor
- `reporte.md` - Reporte final
- `analysis_species/` - Resultados de clasificación
- `search_results/` - Resultados de búsqueda
- `pdfs/` - PDFs descargados
- `rag_index/` - Índices FAISS

### Reanudación

Si el servidor se detiene:
1. El estado se persiste en `.pipeline_state.json`
2. Al reiniciar, carga el estado previo
3. El usuario puede reanudar desde donde se pausó (próxima implementación)

---

## 📋 Pasos del Pipeline

| Paso | Entrada | Salida | Estado |
|------|---------|--------|--------|
| 1 | species_unicas.csv | species_acuaticas.csv, species_terrestres.csv | ✅ Implementado |
| 2 | species_acuaticas.csv | lista MARINE en memoria | ✅ Implementado |
| 3 | lista MARINE | CSVs en search_results | ⏳ Stub |
| 4 | DOIs/URLs | PDFs en pdfs/ | ⏳ Stub |
| 5 | PDFs | índice FAISS | ⏳ Stub |
| 6 | estado | reporte.md | ✅ Implementado |

---

## 🔧 Configuración

### Variables de entorno

```bash
# En .env o como variables del sistema
PIPELINE_HOST=127.0.0.1
PIPELINE_PORT=8000
PIPELINE_PROJECT_ROOT=/ruta/al/proyecto
```

### Cambiar directorios de salida

En `cli.py` o `server.py`, modifica `create_default_manager()`:

```python
config = PipelineConfig(
    project_root=Path("/custom/path"),
    analysis_dir=Path("/custom/analysis"),
    search_results_dir=Path("/custom/search"),
    pdfs_dir=Path("/custom/pdfs"),
    rag_index_dir=Path("/custom/rag"),
)
```

---

## 🐛 Troubleshooting

### Puerto ya en uso

```bash
# Buscar qué está usando el puerto 8000
lsof -i :8000

# Usar otro puerto
python cli.py start --port 8001
```

### Servidor no responde

```bash
# Ver logs
python cli.py logs --lines 100

# Reiniciar
python cli.py stop
python cli.py start
```

### Pipeline atascado

```bash
# Detener servidor (mata el pipeline)
python cli.py stop

# Ver estado guardado
cat .pipeline_state.json

# Limpiar estado si es necesario
rm .pipeline_state.json
```

### Dependencias faltantes

```bash
pip install -r requirements.txt --upgrade
```

---

## 📈 Monitoreo

### Monitoreo en tiempo real

```bash
# Ver estado cada 5 segundos
while true; do
  clear
  python cli.py status
  sleep 5
done
```

### Esperar a que termine

```bash
# Esperar hasta que el pipeline esté completo
python cli.py trigger-pipeline
while true; do
  STATUS=$(curl -s http://localhost:8000/status | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    echo "Pipeline finalizado: $STATUS"
    break
  fi
  echo "Procesando... ($STATUS)"
  sleep 5
done
```

---

## 🚀 Próximas Mejoras

- [ ] Endpoint para pausar/reanudar pipeline
- [ ] Interfaz web (frontend)
- [ ] Notificaciones por email/Slack
- [ ] Métricas de performance
- [ ] Integración con bases de datos
- [ ] Implementar pasos 3-5 (búsqueda, descarga, indexación)

---

## 📞 Soporte

Para reportar problemas o sugerencias:
- Revisa logs: `python cli.py logs`
- Verifica estado: `python cli.py status`
- Consulta este documento

