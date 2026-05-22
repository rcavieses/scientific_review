# 🚀 Pipeline Ejecutándose en Background

**PID:** 992351  
**Inicio:** 2026-05-22  
**Estado:** Procesando 8,916 especies nuevas

## 📊 Comandos de Monitoreo

### Ver estado actual
```bash
cat pipeline_new_species_state.json
```

### Ver log en tiempo real
```bash
tail -f pipeline_new_species.log
```

### Ver progreso (últimas 20 líneas)
```bash
tail -20 pipeline_new_species.log
```

### Contar archivos generados (búsqueda)
```bash
ls search_results/*.csv 2>/dev/null | wc -l
```

### Contar PDFs descargados
```bash
find pdfs -name "*.pdf" | wc -l
```

### Ver estado del RAG
```bash
cat outputs/rag_index/index_config.json 2>/dev/null
```

### Ver si el proceso sigue corriendo
```bash
ps aux | grep "run_new_species_pipeline.py" | grep -v grep
```

## 📈 Fases del Pipeline

1. **BÚSQUEDA** (2-4 horas)
   - 8,916 especies nuevas
   - APIs: PubMed, CrossRef, Scopus ✓, ScienceDirect, ArXiv
   - Output: CSV en search_results/

2. **DESCARGA** (2-6 horas)
   - Descarga de PDFs desde DOI, URLs directas, ArXiv
   - Output: PDFs en pdfs/

3. **INDEXACIÓN RAG** (2-4 horas)
   - Construcción de índice FAISS
   - Se indexarán TODOS los PDFs (nuevos + 4,742 previos)
   - Output: Índice en outputs/rag_index/

## ⏱️ Tiempo Estimado
- Total: 6-14 horas
- Puedes desconectar la terminal - el servidor sigue trabajando

## 🔧 Si necesitas pausar
```bash
kill 992351
```

## 🔄 Si necesitas reanudar desde una fase específica
```bash
# Editar pipeline_new_species_state.json y cambiar "phase"
# Luego ejecutar de nuevo:
python3 run_new_species_pipeline.py
```

