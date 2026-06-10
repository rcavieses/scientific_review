@echo off
REM Script auxiliar para ejecutar la descarga en Windows

setlocal enabledelayedexpansion

echo.
echo ======================================================================
echo ScienceDirect Batch Downloader - Golfo de California
echo ======================================================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python no encontrado
    echo   Descargar desde: https://www.python.org/downloads/
    echo   Asegúrate de marcar "Add Python to PATH" durante la instalación
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo + %PYTHON_VERSION%

REM Verificar requests
echo.
echo Verificando dependencias...
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo X Módulo 'requests' no encontrado
    echo   Instalar con: pip install requests
    pause
    exit /b 1
)
echo + Módulo requests presente

REM Verificar configuración
echo.
if not exist "config.json" (
    echo X Archivo config.json no encontrado
    echo   Crear desde config.example.json:
    echo   - Copia config.example.json a config.json
    echo   - Edita config.json con Notepad
    pause
    exit /b 1
)
echo + config.json presente

REM Test API key
echo.
echo Validando configuración...
python test_api.py
if errorlevel 1 (
    echo.
    echo X Validación falló. Solucionar problemas en config.json
    pause
    exit /b 1
)

REM Iniciar descarga
echo.
echo ======================================================================
set /p CONTINUE="Continuar con la descarga? (s/n): "
if /i "%CONTINUE%"=="s" (
    echo.
    echo Iniciando descarga...
    echo.
    python download_sciencedirect_api.py

    echo.
    echo + Descarga completada
    echo.
    echo Resultados en: .\downloaded_pdfs\
    dir .\downloaded_pdfs\ /b
    pause
) else (
    echo Descarga cancelada
    pause
    exit /b 0
)
