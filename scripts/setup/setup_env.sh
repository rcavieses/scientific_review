#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_env.sh — Configura el entorno de desarrollo en macOS / Linux
#
# Uso:
#   bash setup_env.sh          # instala dependencias core
#   bash setup_env.sh --dev    # instala core + notebook + tools de dev
# ─────────────────────────────────────────────────────────────────────────────
set -e

DEV=false
for arg in "$@"; do
    [[ "$arg" == "--dev" ]] && DEV=true
done

PYTHON=${PYTHON:-python3}
VENV_DIR=".venv"

echo "═══════════════════════════════════════════════════"
echo "  scientific_review — setup del entorno"
echo "═══════════════════════════════════════════════════"

# 1. Verificar Python >= 3.10
PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYMAJ=$($PYTHON -c "import sys; print(sys.version_info.major)")
PYMIN=$($PYTHON -c "import sys; print(sys.version_info.minor)")
echo "Python encontrado: $PYVER"
if [[ $PYMAJ -lt 3 || ($PYMAJ -eq 3 && $PYMIN -lt 10) ]]; then
    echo "ERROR: Se requiere Python 3.10 o superior."
    exit 1
fi

# 2. Crear virtualenv
if [[ ! -d "$VENV_DIR" ]]; then
    echo ""
    echo "Creando virtualenv en $VENV_DIR/ ..."
    $PYTHON -m venv "$VENV_DIR"
else
    echo "Virtualenv ya existe en $VENV_DIR/"
fi

# 3. Activar y actualizar pip
source "$VENV_DIR/bin/activate"
echo "Actualizando pip..."
pip install --upgrade pip --quiet

# 4. Instalar dependencias
if [[ "$DEV" == true ]]; then
    echo ""
    echo "Instalando dependencias de desarrollo (requirements-dev.txt)..."
    pip install -r requirements-dev.txt
else
    echo ""
    echo "Instalando dependencias core (requirements.txt)..."
    pip install -r requirements.txt
fi

# 5. Crear directorio de secretos (ignorado por git)
mkdir -p secrets
echo ""
echo "Directorio secrets/ listo."
echo "  Coloca tus API keys aquí (nunca se commitean):"
echo "    secrets/scopus_apikey.txt"
echo "    secrets/sciencedirect_apikey.txt"
echo "    secrets/anthropic-apikey"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Entorno listo."
echo ""
echo "  Activar entorno:"
echo "    source $VENV_DIR/bin/activate"
echo ""
echo "  Buscar artículos:"
echo "    python buscar.py \"Lutjanus peru Gulf of California\" --download --index"
echo ""
if [[ "$DEV" == true ]]; then
    echo "  Abrir notebook demo:"
    echo "    jupyter notebook pipeline_demo.ipynb"
    echo ""
fi
echo "  Correr tests:"
echo "    python -m unittest discover -s pipeline/embeddings/tests"
echo "    python -m unittest pipeline.rag.tests.test_rag_phase3"
echo "═══════════════════════════════════════════════════"
