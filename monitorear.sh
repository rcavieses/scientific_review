#!/bin/bash
#
# Script para monitorear el progreso del pipeline
# Uso: ./monitorear.sh
#

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colores
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Monitor del Pipeline de Procesamiento de Especies    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar que el servidor esté corriendo
if ! python3 cli.py status > /dev/null 2>&1; then
    echo -e "${RED}✗ El servidor no está corriendo${NC}"
    echo -e "${YELLOW}Inicia con:${NC} python3 cli.py start"
    exit 1
fi

echo -e "${GREEN}✓ Servidor activo${NC}"
echo ""

# Loop de monitoreo
iteration=0
while true; do
    iteration=$((iteration + 1))
    clear

    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Monitor del Pipeline - Iteración $iteration                    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Obtener estado
    status_json=$(curl -s http://127.0.0.1:8000/status 2>/dev/null || echo "{}")

    # Extraer información
    stage=$(echo "$status_json" | grep -o '"stage":"[^"]*"' | cut -d'"' -f4)
    start_time=$(echo "$status_json" | grep -o '"start_time":"[^"]*"' | cut -d'"' -f4)
    error=$(echo "$status_json" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)

    # Mostrar estado
    echo -e "${YELLOW}Estado Actual:${NC}"
    echo -e "  Etapa: ${GREEN}$stage${NC}"
    echo -e "  Inicio: $start_time"
    echo ""

    # Mostrar progreso según etapa
    case "$stage" in
        "idle")
            echo -e "${YELLOW}⏳ Pipeline en espera (idle)${NC}"
            ;;
        "classifying_habitats")
            echo -e "${YELLOW}🔄 PASO 1: Clasificando hábitats...${NC}"
            echo -e "   (Consultando WoRMS y GBIF APIs - puede tomar 10-30 min)"
            ;;
        "filtering_marine")
            echo -e "${YELLOW}🔄 PASO 2: Filtrando especies MARINE...${NC}"
            ;;
        "searching_articles")
            echo -e "${YELLOW}🔄 PASO 3: Buscando artículos científicos...${NC}"
            ;;
        "downloading_pdfs")
            echo -e "${YELLOW}🔄 PASO 4: Descargando PDFs...${NC}"
            ;;
        "indexing_rag")
            echo -e "${YELLOW}🔄 PASO 5: Indexando RAG...${NC}"
            ;;
        "generating_report")
            echo -e "${YELLOW}🔄 PASO 6: Generando reporte...${NC}"
            ;;
        "completed")
            echo -e "${GREEN}✓ ¡PIPELINE COMPLETADO!${NC}"
            echo ""
            echo -e "${BLUE}Resultados disponibles:${NC}"
            python3 cli.py results 2>/dev/null | tail -20
            echo ""
            echo -e "${GREEN}Para ver archivos:${NC}"
            echo "  cat analysis_species/species_acuaticas.csv"
            echo "  cat reporte.md"
            exit 0
            ;;
        "failed")
            echo -e "${RED}✗ PIPELINE FALLÓ${NC}"
            if [ ! -z "$error" ]; then
                echo -e "${RED}Error: $error${NC}"
            fi
            exit 1
            ;;
    esac

    # Mostrar logs recientes
    echo ""
    echo -e "${YELLOW}Últimos logs:${NC}"
    tail -5 server.log 2>/dev/null | sed 's/^/  /'

    echo ""
    echo -e "${BLUE}Comando para ver logs: ${NC}python3 cli.py logs"
    echo -e "${BLUE}Presiona Ctrl+C para salir${NC}"
    echo ""

    sleep 10
done
