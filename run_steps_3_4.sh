#!/bin/bash
#
# Ejecuta pasos 3, 4 y 6 en background
# Permite desconectar la terminal y volver después
#
# Uso:
#   ./run_steps_3_4.sh [start|stop|status|logs]
#

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PID_FILE=".pipeline_steps.pid"
LOG_FILE="pipeline_steps.log"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

is_running() {
    [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null
}

start() {
    if is_running; then
        echo -e "${YELLOW}⚠️  Proceso ya está ejecutándose (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi

    echo -e "${BLUE}🚀 Iniciando ejecución de pasos 3, 4 y 6...${NC}"
    echo -e "${BLUE}📍 PASO 3: Buscar artículos${NC}"
    echo -e "${BLUE}📍 PASO 4: Descargar PDFs${NC}"
    echo -e "${BLUE}📍 PASO 6: Generar reporte${NC}"
    echo ""

    # Ejecutar en background
    nohup python3 execute_pipeline_steps.py > "$LOG_FILE" 2>&1 &
    local pid=$!

    echo $pid > "$PID_FILE"
    echo -e "${GREEN}✅ Proceso iniciado${NC}"
    echo -e "   PID: $pid"
    echo -e "   Log: ${BLUE}$LOG_FILE${NC}"
    echo ""
    echo -e "${YELLOW}Monitorea con:${NC}"
    echo "   ./run_steps_3_4.sh status"
    echo "   ./run_steps_3_4.sh logs"
    echo "   tail -f $LOG_FILE"
}

stop() {
    if ! is_running; then
        echo -e "${YELLOW}⚠️  No hay proceso ejecutándose${NC}"
        return 1
    fi

    local pid=$(cat "$PID_FILE")
    echo -e "${YELLOW}Deteniendo proceso (PID: $pid)...${NC}"
    kill $pid 2>/dev/null || true
    sleep 1
    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ Proceso detenido${NC}"
}

status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo -e "${GREEN}✅ Proceso activo (PID: $pid)${NC}"
        echo ""
        echo -e "${BLUE}Últimas líneas del log:${NC}"
        tail -10 "$LOG_FILE" | sed 's/^/  /'
    else
        echo -e "${RED}✗ No hay proceso ejecutándose${NC}"
        
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo -e "${BLUE}Última ejecución:${NC}"
            tail -5 "$LOG_FILE" | sed 's/^/  /'
        fi
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}No hay logs aún${NC}"
    fi
}

usage() {
    cat << USAGE
${BLUE}Uso: $0 {start|stop|status|logs}${NC}

Comandos:
  ${GREEN}start${NC}    - Iniciar ejecución en background
  ${GREEN}stop${NC}     - Detener el proceso
  ${GREEN}status${NC}   - Ver estado actual
  ${GREEN}logs${NC}     - Ver logs en tiempo real

Ejemplo:
  $0 start           # Inicia y puedes cerrar la terminal
  sleep 5 && $0 status  # Ver progreso después
  $0 logs            # Ver logs en vivo

USAGE
}

case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        usage
        ;;
esac
