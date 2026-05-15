# 🚀 Ejecución de Pasos 3, 4 y 6 en Background

## ✅ Estado Actual

**El proceso está corriendo en background** 🎉

```
PID: 1137870
Log: pipeline_steps.log
```

---

## 🔄 Flujo de Ejecución

El sistema ejecutará automáticamente:

```
PASO 3: Buscar Artículos Científicos (1-2 horas)
    ↓
    Consulta: PubMed, CrossRef, Scopus*, ScienceDirect*, ArXiv
    Genera: search_results/*.csv
    
PASO 4: Descargar PDFs (~30-60 minutos)
    ↓
    Descargar desde: DOIs, ArXiv, URLs directas
    Almacena: pdfs/{especie}/*.pdf
    
PASO 6: Generar Reporte Automático
    ↓
    Genera: REPORTE_PASOS_3_4.md
    Incluye: Estadísticas, especies con/sin información
```

---

## 📊 Monitorear Progreso

### Opción 1: Ver estado rápido
```bash
./run_steps_3_4.sh status
```

### Opción 2: Ver logs en vivo
```bash
./run_steps_3_4.sh logs
```
o
```bash
tail -f pipeline_steps.log
```

### Opción 3: Verificar archivos generados
```bash
# Contar especies procesadas
ls search_results/*.csv 2>/dev/null | wc -l

# Ver último artículo encontrado
tail -5 search_progress.json | head -20

# Contar PDFs descargados
find pdfs -name "*.pdf" 2>/dev/null | wc -l
```

### Opción 4: Ver logs del servidor
```bash
python3 cli.py status
python3 cli.py logs --lines 50
```

---

## 🛑 Controlar el Proceso

### Pausar/Detener
```bash
./run_steps_3_4.sh stop
```

### Reanudar desde último punto
```bash
python3 execute_pipeline_steps.py --start-from 3
# o
python3 execute_pipeline_steps.py --start-from 4
# o
python3 execute_pipeline_steps.py --start-from 6
```

---

## 📈 Tiempos Estimados

| Fase | Tiempo | Actividad |
|------|--------|-----------|
| **PASO 3** | 1-2 horas | Buscando en APIs científicas |
| **PASO 4** | 30-60 min | Descargando PDFs |
| **PASO 6** | < 1 min | Generando reporte |
| **TOTAL** | **2-3 horas** | Procesamiento completo |

---

## 📁 Archivos Que Se Generarán

### Resultados de Búsqueda
```
search_results/
├── species_1.csv
├── species_2.csv
├── ...
└── species_n.csv
```

**Contenido de cada CSV:**
```csv
source,title,authors,year,journal,doi,url,pubmed_id,arxiv_id
PubMed,"Título del artículo","Autor1, Autor2",2023,"Nature","10.1234/...","https://..","12345678",""
CrossRef,"Otro artículo","Smith J.",2022,"Science","10.5678/...","https://..","","
ArXiv,"Preprint","Lee B.",2024,"ArXiv","","https://..","","2401.12345"
```

### PDFs Descargados
```
pdfs/
├── species_name_1/
│   ├── PubMed_article1.pdf
│   ├── CrossRef_article2.pdf
│   └── ArXiv_article3.pdf
├── species_name_2/
│   └── ...
└── species_name_n/
```

### Reporte Final
```
REPORTE_PASOS_3_4.md
```

Incluye:
- Resumen ejecutivo
- Estadísticas por paso
- Top 20 especies con más artículos
- Especies sin información
- Próximos pasos

---

## 🎯 Verificar Resultados Finales

Una vez complete (2-3 horas):

```bash
# Ver reporte completo
cat REPORTE_PASOS_3_4.md

# Ver primeras líneas del reporte
head -100 REPORTE_PASOS_3_4.md

# Contar totales
echo "=== RESUMEN ==="
echo "Especies procesadas: $(ls search_results/*.csv 2>/dev/null | wc -l)"
echo "Artículos encontrados: $(tail -1 search_progress.json | grep -o '"[0-9]*"' | tail -1)"
echo "PDFs descargados: $(find pdfs -name '*.pdf' 2>/dev/null | wc -l)"
```

---

## 🔍 Qué Está Pasando Ahora Mismo

### PASO 3: Búsqueda de Artículos

El sistema está:

1. **Leyendo** `species_acuaticas.csv` con 3,814 especies
2. **Consultando** múltiples bases de datos:
   - **PubMed** (NCBI) - Base de datos biomédica gratuita
   - **CrossRef** - DOIs y referencias gratuitas
   - **Scopus** - Si tiene API key configurada*
   - **ScienceDirect** - Si tiene API key configurada*
   - **ArXiv** - Preprints gratuitos

3. **Guardando** resultados en `search_results/{especie}.csv`
4. **Rastreando** progreso en `search_progress.json`
5. **Removiendo** duplicados por título

### Velocidad

- ~1-2 segundos por especie
- 3,814 especies × 1.5 seg = ~1.5 horas aprox
- Pero se salta especies que ya procesó (reanudable)

### Configurar Scopus/ScienceDirect (Opcional)

Si tienes credenciales de Elsevier:

```bash
# Editar .env
export SCOPUS_API_KEY="tu_key_aqui"
export SCIENCEDIRECT_API_KEY="tu_key_aqui"

# O crear archivo .env:
echo "SCOPUS_API_KEY=tu_key" >> .env
echo "SCIENCEDIRECT_API_KEY=tu_key" >> .env

# Reiniciar el proceso
./run_steps_3_4.sh stop
sleep 2
./run_steps_3_4.sh start
```

---

## 💡 Tips y Trucos

### Monitor automático (cada 10 segundos)
```bash
while true; do clear; ./run_steps_3_4.sh status; sleep 10; done
```

### Esperar hasta que termine
```bash
# En bash
while [ -f ".pipeline_steps.pid" ] && kill -0 $(cat .pipeline_steps.pid) 2>/dev/null; do
  echo "Ejecutándose... $(date)"
  sleep 60
done
echo "¡Completado!"
```

### Ver crecimiento en tiempo real
```bash
watch -n 5 'echo "Especies: $(ls search_results/*.csv 2>/dev/null | wc -l)"; echo "PDFs: $(find pdfs -name "*.pdf" 2>/dev/null | wc -l)"'
```

---

## ⚠️ Si Algo Sale Mal

### El proceso se detiene
```bash
# Verificar error
tail -50 pipeline_steps.log | grep -i error

# Reintentar desde donde se pausó
./run_steps_3_4.sh start
```

### API rate limit
```bash
# Es normal si muchas APIs
# El script tiene delays integrados
# Espera y continúa automáticamente
```

### Espacio en disco
```bash
# Verificar espacio
df -h

# Los PDFs pueden ocupar mucho espacio
# ~10-50 GB es posible con 3,814 especies
```

---

## 📞 Comandos de Referencia

```bash
# Inicio
./run_steps_3_4.sh start          # Inicia en background

# Monitoreo
./run_steps_3_4.sh status         # Ver estado actual
./run_steps_3_4.sh logs           # Ver logs en vivo
tail -f pipeline_steps.log        # Logs directos

# Control
./run_steps_3_4.sh stop           # Detener (pausable)

# Reanudar
python3 execute_pipeline_steps.py --start-from 3  # Continuar paso 3
python3 execute_pipeline_steps.py --start-from 4  # Continuar paso 4
python3 execute_pipeline_steps.py --start-from 6  # Solo generar reporte

# Verificar resultados
cat REPORTE_PASOS_3_4.md          # Ver reporte final
```

---

## 🎉 Cuando Termine

Tendrás:

✅ **3,814 búsquedas completadas** en PubMed, CrossRef, ArXiv, etc.
✅ **Miles de artículos encontrados** (promedio 30%+ por especie)
✅ **Cientos/miles de PDFs descargados** desde DOIs y ArXiv
✅ **Reporte automático** con estadísticas completas
✅ **Archivo CSV por especie** con metadatos de artículos
✅ **Datos listos para**: Indexación RAG, análisis, búsqueda

---

## 📝 Resumen

**Estado**: ✅ En ejecución  
**Tiempo estimado**: 2-3 horas  
**Puedes**: Cerrar la terminal ahora  
**Monitorea**: Con `./run_steps_3_4.sh status` cuando quieras  
**Resultados**: REPORTE_PASOS_3_4.md + search_results/ + pdfs/  

**¡Todo corre automáticamente en background! 🚀**
