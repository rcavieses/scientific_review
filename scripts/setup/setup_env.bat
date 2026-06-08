@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: setup_env.bat — Configura el entorno de desarrollo en Windows
::
:: Uso:
::   setup_env.bat          instala dependencias core
::   setup_env.bat --dev    instala core + notebook + tools de dev
:: ─────────────────────────────────────────────────────────────────────────────
setlocal enabledelayedexpansion

set DEV=false
if "%1"=="--dev" set DEV=true

set VENV_DIR=.venv

echo ===================================================
echo   scientific_review - setup del entorno (Windows)
echo ===================================================

:: 1. Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instala Python 3.10+ desde https://python.org
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Python encontrado: %PYVER%

:: 2. Crear virtualenv
if not exist "%VENV_DIR%\" (
    echo.
    echo Creando virtualenv en %VENV_DIR%\ ...
    python -m venv %VENV_DIR%
) else (
    echo Virtualenv ya existe en %VENV_DIR%\
)

:: 3. Activar y actualizar pip
call %VENV_DIR%\Scripts\activate.bat
echo Actualizando pip...
pip install --upgrade pip --quiet

:: 4. Instalar dependencias
if "%DEV%"=="true" (
    echo.
    echo Instalando dependencias de desarrollo ^(requirements-dev.txt^)...
    pip install -r requirements-dev.txt
) else (
    echo.
    echo Instalando dependencias core ^(requirements.txt^)...
    pip install -r requirements.txt
)

:: 5. Crear directorio de secretos
if not exist "secrets\" mkdir secrets
echo.
echo Directorio secrets\ listo.
echo   Coloca tus API keys aqui (nunca se commitean):
echo     secrets\scopus_apikey.txt
echo     secrets\sciencedirect_apikey.txt
echo     secrets\anthropic-apikey

echo.
echo ===================================================
echo   Entorno listo.
echo.
echo   Activar entorno:
echo     %VENV_DIR%\Scripts\activate
echo.
echo   Buscar articulos:
echo     python buscar.py "Lutjanus peru Gulf of California" --download --index
echo.
if "%DEV%"=="true" (
    echo   Abrir notebook demo:
    echo     jupyter notebook pipeline_demo.ipynb
    echo.
)
echo   Correr tests:
echo     python -m unittest discover -s pipeline/embeddings/tests
echo     python -m unittest pipeline.rag.tests.test_rag_phase3
echo ===================================================
endlocal
