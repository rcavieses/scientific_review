# Tutorial: Ejecutar el Pipeline en Segundo Plano

Este tutorial guía paso a paso cómo usar el servidor y ejecutar el pipeline sin bloquear tu terminal.

## 📋 Requisitos

- Python 3.8+
- Dependencias instaladas: `pip install -r requirements.txt`
- `species_unicas.csv` en `analysis_species/` (generado por `extraer_species_unicas.py`)

---

## 🎯 Escenario: Procesar Especies de Forma Automática

### Paso 1: Verificar Configuración (1 minuto)

Primero, verifica que todo esté instalado:

```bash
cd /path/to/scientific_review
python3 check_setup.py
```

Deberías ver ✓ en todas las líneas.

### Paso 2: Iniciar el Servidor (30 segundos)

En una terminal, inicia el servidor:

```bash
python3 cli.py start
```

Verás:
```
🚀 Iniciando servidor en 127.0.0.1:8000...
✅ Servidor listo en http://127.0.0.1:8000
📊 Dashboard: http://127.0.0.1:8000/docs
```

**El servidor ahora está corriendo en background.**

### Paso 3: Verificar Estado (en otra terminal)

Abre otra terminal y verifica que el servidor está respondiendo:

```bash
python3 cli.py status
```

Deberías ver:
```
✓ Servidor corriendo (PID: 12345)
Estado del pipeline:
{
  "stage": "idle",
  "progress": {},
  "start_time": null,
  "end_time": null,
  "error": null
}
```

### Paso 4: Iniciar el Pipeline

Inicia la ejecución del pipeline:

```bash
python3 cli.py trigger-pipeline
```

Verás:
```
✅ Pipeline iniciado en segundo plano

💡 Monitorea el progreso con: python cli.py status
```

### Paso 5: Monitorear en Tiempo Real

En una tercera terminal, monitorea el progreso:

```bash
# Ver estado actual
python3 cli.py status

# O ver logs en vivo
python3 cli.py logs --lines 50
```

Para monitoreo continuo:

```bash
# Monitorear cada 5 segundos (en bash)
watch -n 5 'python3 cli.py status'

# O con un script manual
while true; do clear; python3 cli.py status; sleep 5; done
```

### Paso 6: Esperar Finalización

El pipeline se ejecutará en background. Mientras tanto, puedes:

- ✅ Cerrar la terminal del servidor
- ✅ Trabajar en otras cosas
- ✅ Verificar progreso cuando quieras
- ✅ Ver logs en cualquier momento

```bash
# El servidor sigue funcionando aunque cierres todo
# Para verificar:
python3 cli.py status
```

### Paso 7: Ver Resultados

Una vez complete, obtén los archivos:

```bash
python3 cli.py results
```

Verás:
```
📁 Resultados Disponibles
==================================================

analysis_files:
  - species_acuaticas.csv
  - species_terrestres.csv
  - species_pendientes.csv

report:
  ✓ reporte.md
```

### Paso 8: Descargar o Ver Resultados

```bash
# Ver el reporte
cat reporte.md

# Ver especies acuáticas
cat analysis_species/species_acuaticas.csv
```

---

## 🔄 Casos de Uso Avanzados

### Caso A: Reiniciar el Pipeline Si Falla

Si el pipeline falla y quieres reintentar:

```bash
python3 cli.py trigger-pipeline --force
```

El `--force` reinicia aunque el pipeline anterior no haya completado.

### Caso B: Ejecutar en Host Diferente

Para ejecutar en 0.0.0.0:8000 (accesible desde otras máquinas):

```bash
python3 cli.py start --host 0.0.0.0 --port 8000
```

Desde otra máquina:
```bash
# Reemplaza IP con la dirección real
curl http://192.168.1.100:8000/health
```

### Caso C: Acceso Web al Dashboard

Abre en tu navegador:
```
http://127.0.0.1:8000/docs
```

Verás un dashboard interactivo donde puedes:
- Ver estado del pipeline
- Iniciar el pipeline
- Descargar resultados
- Ver logs

### Caso D: Integración con Scripts/Cron

Puedes automatizar el pipeline con cron:

```bash
# Editar crontab
crontab -e

# Ejecutar cada día a las 2 AM
0 2 * * * cd /path/to/scientific_review && python3 cli.py trigger-pipeline
```

O en un script:

```bash
#!/bin/bash
cd /path/to/scientific_review

# Iniciar servidor si no está corriendo
python3 cli.py start &

# Esperar a que esté listo
sleep 3

# Iniciar pipeline
python3 cli.py trigger-pipeline

# Esperar a que complete
while true; do
  STATUS=$(python3 cli.py status 2>/dev/null | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    echo "Pipeline finalizado: $STATUS"
    break
  fi
  echo "Procesando... ($STATUS)"
  sleep 10
done

# Hacer algo con los resultados
echo "Enviando resultados por email..."
# tu comando aquí
```

---

## 🛠️ Solución de Problemas

### Problema: "Servidor no está corriendo"

**Solución:**
```bash
# Iniciar el servidor
python3 cli.py start

# O verificar si ya hay uno corriendo
lsof -i :8000
```

### Problema: "Pipeline atascado"

**Solución:**
```bash
# Ver estado actual
python3 cli.py status

# Ver logs detallados
python3 cli.py logs --lines 100

# Si está realmente atascado
python3 cli.py stop
python3 cli.py start
python3 cli.py trigger-pipeline --force
```

### Problema: Puerto 8000 ya en uso

**Solución:**
```bash
# Usar diferente puerto
python3 cli.py start --port 8001

# O matar el proceso anterior
pkill -f "python3 server.py"
```

### Problema: Dependencias incompletas

**Solución:**
```bash
# Reinstalar todo
pip install --upgrade -r requirements.txt

# O solo lo que falta
pip install fastapi uvicorn pydantic
```

---

## 📊 Arquitectura del Sistema

```
┌─────────────────────────────────────┐
│ Tu terminal/script                  │
│  python3 cli.py start               │
└──────────────┬──────────────────────┘
               │ (lanza en background)
               ▼
┌─────────────────────────────────────┐
│ Servidor FastAPI (puerto 8000)      │
│ - Corriendo en background            │
│ - Recibe solicitudes HTTP            │
│ - No bloquea tu terminal             │
└──────────────┬──────────────────────┘
               │ (ejecuta en thread)
               ▼
┌─────────────────────────────────────┐
│ Pipeline Manager                    │
│ - Paso 1: Clasificar hábitats        │
│ - Paso 2: Filtrar MARINE             │
│ - Paso 3: Buscar artículos           │
│ - Paso 4: Descargar PDFs             │
│ - Paso 5: Indexar RAG                │
│ - Paso 6: Generar reporte            │
└─────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Archivos de salida                  │
│ - species_*.csv                     │
│ - search_results/*.csv              │
│ - pdfs/*.pdf                        │
│ - rag_index/index.faiss             │
│ - reporte.md                        │
└─────────────────────────────────────┘
```

---

## ⏱️ Tiempos Estimados

| Paso | Tiempo | Status |
|------|--------|--------|
| 1. Clasificar hábitats | 10-30 min | ✅ Implementado |
| 2. Filtrar MARINE | < 1 seg | ✅ Implementado |
| 3. Buscar artículos | 2-5 min (si implementado) | ⏳ Pending |
| 4. Descargar PDFs | 5-15 min (si implementado) | ⏳ Pending |
| 5. Indexar RAG | 5-10 min (si implementado) | ⏳ Pending |
| 6. Generar reporte | < 1 seg | ✅ Implementado |
| **TOTAL** | **~30-60 min** | **Variable** |

---

## 🎓 Ejemplo Completo (Copy & Paste)

```bash
#!/bin/bash
# Script completo para ejecutar todo

PROJECT_DIR="/path/to/scientific_review"
cd "$PROJECT_DIR"

# 1. Verificar
echo "Verificando instalación..."
python3 check_setup.py || exit 1

# 2. Iniciar servidor
echo -e "\nIniciando servidor..."
python3 cli.py start

# 3. Esperar a que esté listo
sleep 3

# 4. Iniciar pipeline
echo -e "\nIniciando pipeline..."
python3 cli.py trigger-pipeline

# 5. Monitorear
echo -e "\nMonitoreando progreso..."
for i in {1..60}; do
  echo "Check $i/60:"
  python3 cli.py status | grep -E '"stage"|"error"'
  sleep 10
done

# 6. Mostrar resultados
echo -e "\nResultados finales:"
python3 cli.py results

echo -e "\n✅ Done! Ver reporte.md"
```

Ejecuta con:
```bash
bash run_everything.sh
```

---

## 📚 Más Información

- [SERVIDOR.md](SERVIDOR.md) - Documentación completa
- [server.py](server.py) - API endpoints
- [pipeline_manager.py](pipeline_manager.py) - Lógica del pipeline
- [cli.py](cli.py) - Interfaz de línea de comandos

