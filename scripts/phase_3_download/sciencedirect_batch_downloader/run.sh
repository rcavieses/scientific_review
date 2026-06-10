#!/bin/bash
# Script auxiliar para ejecutar la descarga en Linux/Mac

set -e  # Salir si hay error

echo "======================================================================"
echo "ScienceDirect Batch Downloader - Golfo de California"
echo "======================================================================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 no encontrado"
    echo "  Instalar: sudo apt-get install python3"
    exit 1
fi

echo "✓ Python: $(python3 --version)"

# Verificar requests
echo ""
echo "Verificando dependencias..."
python3 -c "import requests" 2>/dev/null || {
    echo "✗ Módulo 'requests' no encontrado"
    echo "  Instalar: pip3 install requests"
    exit 1
}
echo "✓ Módulo requests presente"

# Verificar configuración
echo ""
if [ ! -f "config.json" ]; then
    echo "✗ Archivo config.json no encontrado"
    echo "  Crear desde config.example.json:"
    echo "  cp config.example.json config.json"
    exit 1
fi
echo "✓ config.json presente"

# Test API key
echo ""
echo "Validando configuración..."
python3 test_api.py
if [ $? -ne 0 ]; then
    echo ""
    echo "✗ Validación falló. Solucionar problemas en config.json"
    exit 1
fi

# Iniciar descarga
echo ""
echo "======================================================================"
read -p "¿Continuar con la descarga? (s/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo "Iniciando descarga..."
    echo ""
    python3 download_sciencedirect_api.py

    echo ""
    echo "✓ Descarga completada"
    echo ""
    echo "Resultados en: ./downloaded_pdfs/"
    ls -lh downloaded_pdfs/ | head -10
else
    echo "Descarga cancelada"
    exit 0
fi
