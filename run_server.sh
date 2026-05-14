#!/bin/bash
#
# Script para controlar el servidor del pipeline
#
# Uso:
#   ./run_server.sh start [--host HOST] [--port PORT]   # Iniciar servidor
#   ./run_server.sh stop                                  # Detener servidor
#   ./run_server.sh status                                # Ver estado
#   ./run_server.sh logs                                  # Ver logs
#   ./run_server.sh restart                               # Reiniciar
#

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${PROJECT_DIR}/.server.pid"
LOG_FILE="${PROJECT_DIR}/server.log"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función de ayuda
usage() {
    cat << EOF
${BLUE}Uso: $0 {start|stop|status|logs|restart}${NC}

Comandos:
  ${GREEN}start${NC}     [--host HOST] [--port PORT]   Iniciar servidor
  ${GREEN}stop${NC}                                    Detener servidor
  ${GREEN}status${NC}                                  Ver estado del servidor
  ${GREEN}logs${NC}                                   Ver últimos logs
  ${GREEN}restart${NC}                                Reiniciar servidor

Ejemplos:
  $0 start
  $0 start --host 0.0.0.0 --port 8000
  $0 stop
  $0 status
  $0 logs

EOF
    exit 1
}

# Verificar si el servidor está corriendo
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# Función: iniciar servidor
start_server() {
    if is_running; then
        echo -e "${YELLOW}⚠ Servidor ya está corriendo (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi

    echo -e "${BLUE}Iniciando servidor...${NC}"

    # Extraer argumentos
    local host="127.0.0.1"
    local port="8000"
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host) host="$2"; shift 2 ;;
            --port) port="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    # Crear directorios necesarios
    mkdir -p "${PROJECT_DIR}/search_results"
    mkdir -p "${PROJECT_DIR}/pdfs"
    mkdir -p "${PROJECT_DIR}/rag_index"

    # Iniciar servidor en background
    cd "$PROJECT_DIR"
    nohup python server.py --host "$host" --port "$port" > "$LOG_FILE" 2>&1 &
    local pid=$!

    # Guardar PID
    echo "$pid" > "$PID_FILE"

    echo -e "${GREEN}✓ Servidor iniciado${NC}"
    echo -e "  PID: $pid"
    echo -e "  Host: $host"
    echo -e "  Puerto: $port"
    echo -e "  API: ${BLUE}http://$host:$port/docs${NC}"
    echo -e "  Log: ${BLUE}$LOG_FILE${NC}"

    # Esperar a que el servidor esté listo
    echo -e "${YELLOW}Esperando que el servidor esté listo...${NC}"
    sleep 2

    if is_running; then
        echo -e "${GREEN}✓ Servidor corriendo exitosamente${NC}"
    else
        echo -e "${RED}✗ Error: El servidor falló al iniciar${NC}"
        cat "$LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Función: detener servidor
stop_server() {
    if ! is_running; then
        echo -e "${YELLOW}⚠ Servidor no está corriendo${NC}"
        return 1
    fi

    local pid=$(cat "$PID_FILE")
    echo -e "${BLUE}Deteniendo servidor (PID: $pid)...${NC}"

    kill "$pid" 2>/dev/null || true
    sleep 1

    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}Forzando cierre...${NC}"
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo -e "${GREEN}✓ Servidor detenido${NC}"
}

# Función: estado
status_server() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        echo -e "${GREEN}✓ Servidor corriendo (PID: $pid)${NC}"

        # Intentar obtener estado via API
        if command -v curl &> /dev/null; then
            if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
                local status=$(curl -s http://127.0.0.1:8000/status 2>/dev/null)
                if [ ! -z "$status" ]; then
                    echo -e "${BLUE}Estado del pipeline:${NC}"
                    echo "$status" | python -m json.tool 2>/dev/null || echo "$status"
                fi
            fi
        fi
    else
        echo -e "${RED}✗ Servidor no está corriendo${NC}"
    fi
}

# Función: logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}Últimas líneas del log (${LOG_FILE}):${NC}"
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}No hay logs aún${NC}"
    fi
}

# Main
case "${1:-}" in
    start)
        shift
        start_server "$@"
        ;;
    stop)
        stop_server
        ;;
    status)
        status_server
        ;;
    logs)
        show_logs
        ;;
    restart)
        stop_server
        sleep 1
        start_server "${@:2}"
        ;;
    *)
        usage
        ;;
esac
