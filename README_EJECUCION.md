# Pipeline en Ejecución

## 🚀 Estado Actual

✅ **Servidor iniciado** en `http://127.0.0.1:8000`
✅ **Pipeline en ejecución** (iniciado: 2026-05-14 18:26:06)
✅ **Etapa actual**: Clasificando hábitats (PASO 1)

---

## 📋 Lo que está pasando ahora

El sistema está ejecutando la **secuencia lógica completa**:

```
PASO 1: Clasificar hábitats
├─ Consultando WoRMS (especies marinas)
├─ Consultando GBIF (hábitats)
└─ Clasificando: MARINE, FRESHWATER, TERRESTRIAL
   ⏳ Tiempo estimado: 10-30 minutos

PASO 2: Filtrar MARINE (< 1 segundo)
PASO 3: Buscar artículos (implementación pendiente)
PASO 4: Descargar PDFs (implementación pendiente)
PASO 5: Indexar RAG (implementación pendiente)
PASO 6: Generar reporte (< 1 segundo)
```

---

## 🔍 Cómo Monitorear Cuando Regreses

### Opción 1: Monitoreo Automático (Recomendado)

```bash
./monitorear.sh
```

Muestra:
- Etapa actual del pipeline
- Logs en tiempo real
- Avance de ejecución
- Se actualiza cada 10 segundos

### Opción 2: Comandos Manuales

```bash
# Ver estado actual
python3 cli.py status

# Ver logs del servidor
python3 cli.py logs --lines 50

# Ver logs en vivo
tail -f server.log

# Ver archivos generados
python3 cli.py results

# Ver especies acuáticas procesadas
head -20 analysis_species/species_acuaticas.csv
```

### Opción 3: Dashboard Web

Abre en tu navegador:
```
http://127.0.0.1:8000/docs
```

Verás:
- Estado del pipeline
- Endpoint interactivo `/status`
- Endpoint para iniciar pipeline
- API completa documentada

---

## 📁 Archivos de Salida

El pipeline genera archivos en estas ubicaciones:

```
analysis_species/
├── species_acuaticas.csv        ← Especies MARINE/FRESHWATER
├── species_terrestres.csv       ← Especies terrestres
├── species_pendientes.csv       ← Sin datos
└── cache_habitats.json          ← Cache de consultas

search_results/
└── *.csv                        ← Resultados de búsqueda (cuando impl.)

pdfs/
└── *.pdf                        ← PDFs descargados (cuando impl.)

rag_index/
└── index.faiss                  ← Índice vectorial (cuando impl.)

reporte.md                       ← Reporte final
```

---

## ⏱️ Tiempos Estimados

| Componente | Tiempo | Estado |
|------------|--------|--------|
| Paso 1 (WoRMS/GBIF) | 10-30 min | ⏳ Ejecutando |
| Paso 2 (Filtrado) | < 1 seg | ⏳ Pendiente |
| Paso 3 (Búsqueda) | Variable | ⏳ Pendiente |
| Paso 4 (Descargas) | Variable | ⏳ Pendiente |
| Paso 5 (Indexación) | 5-10 min | ⏳ Pendiente |
| Paso 6 (Reporte) | < 1 seg | ⏳ Pendiente |
| **TOTAL** | **~30-60 min** | ⏳ En progreso |

---

## 🛑 Si Necesitas Detener

```bash
# Detener el servidor (pausa el pipeline)
python3 cli.py stop

# El estado se persiste en .pipeline_state.json
# Puedes reiniciar después con: python3 cli.py start
```

---

## 🔄 Si Quieres Reiniciar

```bash
# Detener
python3 cli.py stop

# Limpiar estado (opcional)
rm .pipeline_state.json

# Reiniciar
python3 cli.py start
python3 cli.py trigger-pipeline --force
```

---

## 📊 Verificación Rápida

Para ver si todo sigue ejecutándose:

```bash
# ¿Está el servidor activo?
curl http://127.0.0.1:8000/health

# ¿Cuál es la etapa actual?
curl http://127.0.0.1:8000/status | python3 -m json.tool

# ¿Hay errores?
python3 cli.py logs | grep -i error
```

---

## 💾 Persistencia

El sistema **persiste el estado** en:

- `.pipeline_state.json` → Estado actual (etapa, progreso, errores)
- `server.log` → Logs del servidor
- Archivos de salida → Se guardan automáticamente

**Si el proceso se interrumpe**, puedes reanudar desde donde se pausó.

---

## 🎯 Próximo Pasos Cuando Termine

1. **Ver clasificación**:
   ```bash
   wc -l analysis_species/species_*.csv
   head -20 analysis_species/species_acuaticas.csv
   ```

2. **Ver reporte**:
   ```bash
   cat reporte.md
   ```

3. **Implementar pasos 3-5** (búsqueda, descarga, indexación)

4. **Procesar los resultados** con tu código

---

## 🆘 Troubleshooting

### "El servidor no responde"

```bash
python3 cli.py status
# Si da error, reinicia:
python3 cli.py stop
python3 cli.py start
```

### "El pipeline está lento"

Es normal. El PASO 1 consulta APIs externas:
- WoRMS: 50 nombres por petición
- GBIF: 0.15 segundos entre peticiones
- Respeta rate limits

### "¿Cuánto falta?"

```bash
python3 cli.py logs | tail -20
# Busca líneas como:
# [classifying_habitats] WoRMS 100/2000
```

---

## 📞 Información Técnica

**Servidor**: FastAPI corriendo en puerto 8000
**Process ID**: Ver con `ps aux | grep server.py`
**Log file**: `server.log`
**State file**: `.pipeline_state.json`

---

## ✨ Resumen

✅ El pipeline está **ejecutándose en segundo plano**
✅ **No bloquea la terminal** - puedes desconectar
✅ **Persiste el estado** - puedes reanudar
✅ **Genera archivos automáticamente** - en las carpetas especificadas
✅ **API disponible** - para monitoreo y control

### 🎉 ¡Vuelve cuando quieras a verificar el progreso!

```bash
./monitorear.sh          # Monitoreo automático
python3 cli.py status   # Verificación rápida
```
