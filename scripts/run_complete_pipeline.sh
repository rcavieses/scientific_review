#!/bin/bash
# Pipeline completo: Descarga → RAG Indexación
# Se ejecuta en background

LOG_FILE="pipeline_complete.log"
DOWNLOAD_PROGRESS="download_progress.json"
STATE_FILE="pipeline_new_species_state.json"

{
echo "$(date) - Esperando a que termine la descarga..."

# Esperar a que exista el archivo de estado de descarga
while true; do
    if [ -f "$DOWNLOAD_PROGRESS" ]; then
        echo "$(date) - Descarga completada, iniciando RAG..."
        break
    fi
    echo "$(date) - Descarga en progreso..."
    sleep 30
done

# Ejecutar indexación RAG
echo "$(date) - Iniciando indexación RAG..."
python3 run_rag_indexing.py

if [ $? -eq 0 ]; then
    echo "$(date) - ✅ PIPELINE COMPLETO"
else
    echo "$(date) - ❌ Error en pipeline"
    exit 1
fi

} >> "$LOG_FILE" 2>&1
