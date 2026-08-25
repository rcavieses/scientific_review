#!/bin/bash
# Script para ejecutar BUSQUEDA_4 completa hasta procesar todos los grupos

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROGRESS_FILE="$PROJECT_ROOT/outputs/rag_completion_progress_BUSQUEDA_4.json"
OUTPUT_CSV="$PROJECT_ROOT/data/output/Atlantis_GOC_parametros_biologicos_BUSQUEDA_4.csv"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         BUSQUEDA_4 - Búsqueda Completa de Parámetros      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Configuración:"
echo "   Proyecto: $PROJECT_ROOT"
echo "   Archivo de salida: $OUTPUT_CSV"
echo ""

# Contador de iteraciones
iteration=0
max_iterations=100  # Prevención contra loops infinitos

while [ $iteration -lt $max_iterations ]; do
    iteration=$((iteration + 1))

    echo "▶ Iteración $iteration - Ejecutando script..."
    python3 "$PROJECT_ROOT/scripts/complete_population_parameters_BUSQUEDA4.py" 2>&1 | tail -20

    # Verificar si hay progreso
    if [ ! -f "$PROGRESS_FILE" ]; then
        echo "❌ Error: Archivo de progreso no encontrado"
        exit 1
    fi

    # Extraer el último grupo procesado
    LAST_GROUP=$(grep -o '"last_processed_group": "[^"]*"' "$PROGRESS_FILE" | cut -d'"' -f4)

    if [ "$LAST_GROUP" == "null" ]; then
        echo "⏳ Esperando inicio del procesamiento..."
        sleep 5
        continue
    fi

    echo "   ✓ Grupo completado: $LAST_GROUP"

    # Contar grupos procesados
    GROUPS_PROCESSED=$(grep -o '"processed_groups"' "$PROGRESS_FILE" | wc -l)
    echo "   📈 Grupos procesados hasta ahora: $GROUPS_PROCESSED"

    # Pequeña pausa entre iteraciones
    sleep 2
done

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                   BUSQUEDA_4 COMPLETADA                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Resultado final guardado en:"
echo "   $OUTPUT_CSV"
echo ""
