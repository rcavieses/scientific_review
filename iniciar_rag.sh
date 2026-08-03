#!/bin/bash
# Script para iniciar el servidor RAG fácilmente

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐟 Scientific Review RAG Server${NC}"
echo "======================================"

# Verificar que estamos en el directorio correcto
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env no encontrado${NC}"
    echo "Por favor, ejecuta este script desde /home/atlantis/scientific_review"
    exit 1
fi

# Verificar ANTHROPIC_API_KEY
if ! grep -q "ANTHROPIC_API_KEY" .env; then
    echo -e "${RED}❌ Error: ANTHROPIC_API_KEY no está en .env${NC}"
    echo "Agrega tu API key a .env:"
    echo "  echo 'ANTHROPIC_API_KEY=tu-api-key' >> .env"
    exit 1
fi

# Verificar índice
if [ ! -d "outputs/rag_index_goc" ]; then
    echo -e "${RED}❌ Error: Índice RAG no encontrado${NC}"
    echo "Ejecuta primero: python3 scripts/phase_5_indexing/indexar.py"
    exit 1
fi

echo -e "${GREEN}✓ Configuración OK${NC}"
echo ""

# Parsear argumentos
PORT=${1:-8000}
HOST=${2:-0.0.0.0}

echo -e "${YELLOW}Iniciando servidor...${NC}"
echo "Dirección: http://localhost:${PORT}"
echo ""
echo "Para acceder desde otra máquina:"
echo "  http://$(hostname -I | awk '{print $1}'):${PORT}"
echo ""

# Cargar variables de entorno y ejecutar
set -a
source .env
set +a

python3 scripts/phase_6_query/server_rag_api.py --host "$HOST" --port "$PORT"
