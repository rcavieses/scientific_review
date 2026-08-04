#!/bin/bash
# Script para iniciar el sistema RAG - Golfo de California v2.0
# Nuevo pipeline exhaustivo de 4 fases

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   🐟 Sistema RAG - Golfo de California v2.0           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: archivo .env no encontrado${NC}"
    echo "Ejecuta este script desde /home/atlantis/scientific_review"
    exit 1
fi

# Verificar ANTHROPIC_API_KEY
if ! grep -q "ANTHROPIC_API_KEY" .env; then
    echo -e "${YELLOW}⚠️  ANTHROPIC_API_KEY no configurada${NC}"
    echo "Será necesaria para queries con Claude. Añade a .env:"
    echo "  echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env"
    echo ""
fi

# Paso 1: Verificar ambiente
echo -e "${YELLOW}📋 Paso 1: Verificando ambiente...${NC}"
if ! python3 scripts/verify_environment.py; then
    echo -e "${RED}❌ Verificación falló${NC}"
    exit 1
fi
echo ""

# Paso 2: Verificar índice
INDEX_DIR="outputs/rag_index_goc_full"
echo -e "${YELLOW}📋 Paso 2: Verificando índice RAG...${NC}"

if [ ! -d "$INDEX_DIR" ] || [ -z "$(ls -A "$INDEX_DIR" 2>/dev/null)" ]; then
    echo -e "${YELLOW}⚠️  Índice no encontrado en $INDEX_DIR${NC}"
    echo ""
    echo -e "${BLUE}Opciones:${NC}"
    echo "  1. Reconstruir completo (nueva opción)"
    echo "  2. Ejecutar solo fase (actualización rápida)"
    echo "  3. Salir"
    echo ""
    read -p "¿Selecciona opción (1-3)? " option

    case $option in
        1)
            echo -e "${YELLOW}🔨 Reconstruyendo índice (esto tomará ~35-40 minutos)...${NC}"
            echo ""
            python3 scripts/run_exhaustive_rebuild.py
            echo ""
            ;;
        2)
            echo -e "${BLUE}Fases disponibles:${NC}"
            echo "  0 - Limpieza y validación (2-3 min)"
            echo "  1 - Reconstrucción de índice (20-25 min)"
            echo "  2 - Enriquecimiento de metadatos (5-10 min)"
            echo "  3 - Optimización de retrieval (3-5 min)"
            echo ""
            read -p "¿Selecciona fase (0-3)? " phase
            python3 scripts/run_exhaustive_rebuild.py --phase "$phase"
            echo ""
            ;;
        *)
            echo -e "${RED}Saliendo${NC}"
            exit 1
            ;;
    esac
fi

# Paso 3: Verificar que el índice está listo
if [ ! -f "$INDEX_DIR/index.faiss" ]; then
    echo -e "${RED}❌ Índice incompleto${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Índice verificado${NC}"
echo ""

# Paso 4: Mostrar opciones de uso
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Sistema RAG Listo - Opciones de Uso                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}📖 Documentación:${NC}"
echo "  • INDEX.md                  - Navegación del proyecto"
echo "  • GUIA_RAPIDA_RAG.md        - Ejemplos de código"
echo "  • RAG_EXHAUSTIVE_REBUILD.md - Documentación técnica completa"
echo ""

echo -e "${YELLOW}💡 Opción 1: Queries en Python (Interactivo)${NC}"
echo ""
echo "  from pipeline.rag.query_engine import RAGQueryEngine"
echo "  from pipeline.rag.vector_db import VectorDBManager"
echo ""
echo "  vector_db = VectorDBManager('$INDEX_DIR', embedding_dim=384)"
echo "  vector_db.load()"
echo ""
echo "  engine = RAGQueryEngine(vector_db=vector_db)"
echo "  result = engine.query('¿Parámetros poblacionales del pargo rojo?')"
echo "  print(result.answer)"
echo ""

echo -e "${YELLOW}💡 Opción 2: Jupyter Notebook${NC}"
echo "  jupyter notebook pipeline_demo.ipynb"
echo ""

echo -e "${YELLOW}💡 Opción 3: CLI interactivo (próximamente)${NC}"
echo "  python3 scripts/query_cli.py"
echo ""

echo -e "${BLUE}📊 Estadísticas del índice:${NC}"
python3 << 'EOF'
import json
from pathlib import Path

idx_dir = Path("outputs/rag_index_goc_full")
cfg = json.load(open(idx_dir / "index_config.json"))
metadata = json.load(open(idx_dir / "metadata_store.json"))

print(f"  • Chunks totales: {cfg['total_chunks']:,}")
print(f"  • Modelo: {cfg['embedding_model']}")
print(f"  • Dimensión: {cfg['embedding_dimension']}")
print(f"  • Tamaño index.faiss: {(idx_dir / 'index.faiss').stat().st_size / 1024**2:.1f} MB")
print(f"  • Tamaño metadata: {(idx_dir / 'metadata_store.json').stat().st_size / 1024**2:.1f} MB")
EOF

echo ""
echo -e "${GREEN}✅ Sistema RAG listo para usar${NC}"
echo ""
echo -e "${BLUE}💬 ¿Preguntas?${NC}"
echo "  Consulta la documentación en INDEX.md"
echo ""
