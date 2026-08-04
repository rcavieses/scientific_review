#!/usr/bin/env python3
"""
Verificación rápida del entorno antes de reconstrucción exhaustiva.

Valida:
  - Ubicación correcta de PDFs
  - Acceso a GROBID
  - Dependencias de Python
  - Espacio en disco
  - Configuración de ANTHROPIC_API_KEY
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def check_pdf_directory():
    """Verifica que el directorio de PDFs existe y tiene archivos."""
    pdf_dir = PROJECT_ROOT / "outputs" / "PDF_GOC" / "PDF"

    print(f"✓ Verificando directorio de PDFs...")
    print(f"  Ruta: {pdf_dir}")

    if not pdf_dir.exists():
        print(f"  ❌ Directorio NO encontrado")
        return False

    pdfs = list(pdf_dir.glob("*.pdf"))
    print(f"  PDFs encontrados: {len(pdfs)}")

    if len(pdfs) == 0:
        print(f"  ❌ No hay archivos PDF")
        return False

    total_size = sum(p.stat().st_size for p in pdfs) / 1024**2
    print(f"  Tamaño total: {total_size:.1f} MB")
    print(f"  ✅ Directorio validado")

    return True

def check_grobid():
    """Verifica que GROBID está disponible."""
    print(f"\n✓ Verificando GROBID...")

    try:
        import requests
        response = requests.get("http://localhost:8070/api/isalive", timeout=2)

        if response.status_code == 200:
            print(f"  ✅ GROBID disponible en http://localhost:8070")
            return True
        else:
            print(f"  ⚠️  GROBID no responde (status: {response.status_code})")
            print(f"      Se usará pdfplumber como fallback automático")
            return True  # No es fatal

    except Exception as e:
        print(f"  ⚠️  GROBID no disponible: {e}")
        print(f"      Se usará pdfplumber como fallback automático")
        return True  # No es fatal

def check_dependencies():
    """Verifica que las dependencias Python están instaladas."""
    print(f"\n✓ Verificando dependencias Python...")

    required = [
        "faiss",
        "sentence_transformers",
        "numpy",
        "requests",
        "pdfplumber",
    ]

    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing.append(package)

    if missing:
        print(f"\n  ❌ Faltan paquetes: {', '.join(missing)}")
        print(f"     Ejecuta: pip install -r requirements.txt")
        return False

    print(f"  ✅ Todas las dependencias instaladas")
    return True

def check_disk_space():
    """Verifica que hay suficiente espacio en disco."""
    print(f"\n✓ Verificando espacio en disco...")

    import shutil

    stat = shutil.disk_usage(PROJECT_ROOT)
    free_gb = stat.free / 1024**3

    print(f"  Espacio libre: {free_gb:.1f} GB")

    # Necesitamos al menos 2GB para índice + temporales
    if free_gb < 2:
        print(f"  ⚠️  Advertencia: poco espacio disponible (<2GB)")
        return False

    print(f"  ✅ Espacio suficiente")
    return True

def check_anthropic_key():
    """Verifica que ANTHROPIC_API_KEY está configurada."""
    print(f"\n✓ Verificando ANTHROPIC_API_KEY...")

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print(f"  ⚠️  ANTHROPIC_API_KEY no configurada")
        print(f"     Será necesaria para la síntesis de queries con Claude")
        return True  # No es fatal para indexación

    if api_key.startswith("sk-"):
        print(f"  ✅ ANTHROPIC_API_KEY configurada")
        return True
    else:
        print(f"  ⚠️  ANTHROPIC_API_KEY parece inválida")
        return True

def main():
    print("\n" + "=" * 70)
    print("🔍 VERIFICACIÓN DEL ENTORNO - RECONSTRUCCIÓN EXHAUSTIVA RAG")
    print("=" * 70)

    checks = [
        ("PDFs", check_pdf_directory),
        ("GROBID", check_grobid),
        ("Dependencias", check_dependencies),
        ("Espacio en disco", check_disk_space),
        ("ANTHROPIC_API_KEY", check_anthropic_key),
    ]

    results = {}
    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[name] = False

    # Resumen
    print(f"\n" + "=" * 70)
    print("📊 RESUMEN")
    print("=" * 70)

    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")

    all_pass = all(results.values())

    if all_pass:
        print(f"\n✅ ¡Entorno listo para reconstrucción exhaustiva!")
        print(f"\nEjecuta:")
        print(f"  python3 scripts/run_exhaustive_rebuild.py")
        sys.exit(0)
    else:
        print(f"\n⚠️  Algunos checks fallaron. Revisa los problemas arriba.")
        sys.exit(1)

if __name__ == "__main__":
    main()
