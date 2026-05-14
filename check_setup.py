#!/usr/bin/env python
"""Verifica que el sistema esté listo para ejecutar el servidor."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Colores
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def check_python_version() -> bool:
    """Verifica versión de Python."""
    print(f"Python: {sys.version.split()[0]}", end=" ")
    if sys.version_info >= (3, 8):
        print(f"{GREEN}✓{RESET}")
        return True
    else:
        print(f"{RED}✗ (se requiere Python 3.8+){RESET}")
        return False


def check_package(package: str, import_name: str | None = None) -> bool:
    """Verifica si un paquete está instalado."""
    import_name = import_name or package.replace("-", "_")

    try:
        __import__(import_name)
        print(f"{package:<30} {GREEN}✓{RESET}")
        return True
    except ImportError:
        print(f"{package:<30} {RED}✗ (falta instalar){RESET}")
        return False


def check_file(file_path: str, description: str = "") -> bool:
    """Verifica si existe un archivo."""
    path = PROJECT_ROOT / file_path
    if path.exists():
        print(f"{file_path:<30} {GREEN}✓{RESET}")
        return True
    else:
        desc = f" ({description})" if description else ""
        print(f"{file_path:<30} {RED}✗ (no encontrado){desc}{RESET}")
        return False


def main():
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}Verificación de Configuración del Servidor{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}\n")

    # Python version
    print(f"{YELLOW}Verificando Python:{RESET}")
    python_ok = check_python_version()
    print()

    # Paquetes principales
    print(f"{YELLOW}Verificando paquetes requeridos:{RESET}")
    packages = [
        ("fastapi", None),
        ("uvicorn", None),
        ("pydantic", None),
        ("requests", None),
        ("pandas", None),
        ("numpy", None),
        ("sentence-transformers", "sentence_transformers"),
        ("faiss-cpu", "faiss"),
    ]

    packages_ok = all(check_package(pkg, imp) for pkg, imp in packages)
    print()

    # Archivos críticos
    print(f"{YELLOW}Verificando archivos:{RESET}")
    files = [
        ("server.py", "servidor principal"),
        ("pipeline_manager.py", "gestor del pipeline"),
        ("cli.py", "interfaz CLI"),
        ("requirements.txt", "dependencias"),
        ("analysis_species/clasificar_habitats.py", "paso 1"),
        ("analysis_species/extraer_species_unicas.py", "herramienta auxiliar"),
    ]

    files_ok = all(check_file(f, d) for f, d in files)
    print()

    # Directorios de salida
    print(f"{YELLOW}Directorios de salida:{RESET}")
    dirs_needed = [
        "analysis_species",
        "search_results",
        "pdfs",
        "rag_index",
    ]

    for dirname in dirs_needed:
        path = PROJECT_ROOT / dirname
        if path.exists() or path.mkdir(parents=True, exist_ok=True) or True:
            print(f"{dirname:<30} {GREEN}✓{RESET}")

    print()

    # Resumen
    if python_ok and packages_ok and files_ok:
        print(f"{GREEN}{'='*60}{RESET}")
        print(f"{GREEN}✓ Sistema listo para ejecutar el servidor{RESET}")
        print(f"{GREEN}{'='*60}{RESET}\n")

        print(f"{YELLOW}Próximos pasos:{RESET}")
        print(f"  1. python cli.py start        # Iniciar servidor")
        print(f"  2. python cli.py trigger-pipeline  # Iniciar pipeline")
        print(f"  3. python cli.py status       # Monitorear progreso")
        print(f"  4. python cli.py logs         # Ver logs")
        print()
        return 0
    else:
        print(f"{RED}{'='*60}{RESET}")
        print(f"{RED}✗ Faltan dependencias o configuración{RESET}")
        print(f"{RED}{'='*60}{RESET}\n")

        print(f"{YELLOW}Para instalar dependencias:{RESET}")
        print(f"  pip install -r requirements.txt\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
