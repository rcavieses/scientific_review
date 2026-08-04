#!/usr/bin/env python3
"""
Demo: Claude Vision OCR para extracción de PDF.

Muestra cómo usar Claude Vision para extraer texto de artículos científicos.

Requisitos:
    export ANTHROPIC_API_KEY="sk-ant-..."

Uso:
    python3 scripts/demo_claude_vision_ocr.py [pdf_file]
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def demo_claude_vision_single_page():
    """Demo: Extrae texto de UNA página de un PDF usando Claude Vision."""
    import os
    import base64

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY no configurada")
        print("\n   Configura con:")
        print("   export ANTHROPIC_API_KEY='sk-ant-...'")
        return

    import anthropic

    # Buscar un PDF de prueba
    pdf_dir = Path("outputs/PDF_GOC/PDF")
    pdfs = list(pdf_dir.glob("*.pdf"))

    if not pdfs:
        print("❌ No se encontraron PDFs en outputs/PDF_GOC/PDF/")
        return

    pdf_path = pdfs[0]
    print(f"📄 Extrayendo texto de: {pdf_path.name}")

    try:
        import fitz  # pymupdf
    except ImportError:
        print("❌ pymupdf requerido: pip install pymupdf")
        return

    # 1. Convertir primera página a imagen
    print("   1️⃣  Convirtiendo primera página a imagen...")
    doc = fitz.open(pdf_path)
    page = doc[0]

    mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI
    pix = page.get_pixmap(matrix=mat)

    image_path = "/tmp/page_sample.png"
    pix.save(image_path)
    doc.close()

    print(f"      ✓ Imagen guardada en {image_path}")

    # 2. Enviar a Claude Vision
    print("   2️⃣  Enviando a Claude Vision...")

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic()

    start = time.time()

    message = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extrae TODO el texto de esta página científica. "
                            "Mantén la estructura (párrafos, títulos, listas). "
                            "Retorna SOLO el texto, sin comentarios."
                        ),
                    },
                ],
            }
        ],
    )

    elapsed = time.time() - start
    extracted_text = message.content[0].text

    # 3. Mostrar resultados
    print(f"      ✓ Extracción completada en {elapsed:.2f}s")

    print(f"\n{'='*70}")
    print("📋 TEXTO EXTRAÍDO (primeros 800 caracteres):")
    print(f"{'='*70}\n")

    preview = extracted_text[:800]
    print(preview)
    if len(extracted_text) > 800:
        print(f"\n... ({len(extracted_text) - 800} caracteres más)")

    print(f"\n{'='*70}")
    print(f"📊 ESTADÍSTICAS:")
    print(f"{'='*70}")
    print(f"   Total caracteres extraídos: {len(extracted_text):,}")
    print(f"   Líneas: {len(extracted_text.splitlines())}")
    print(f"   Tiempo total: {elapsed:.2f}s")
    print(f"   Velocidad: {len(extracted_text) / elapsed:.0f} chars/seg")

    # Limpiar
    import os
    os.unlink(image_path)

    print(f"\n✅ Demo completado exitosamente")
    print(f"\n💡 Ventajas de Claude Vision para OCR:")
    print(f"   ✓ Excelente con layouts científicos complejos")
    print(f"   ✓ Reconoce ecuaciones y símbolos matemáticos")
    print(f"   ✓ Mantiene estructura de tablas")
    print(f"   ✓ Detecta headers/footers correctamente")


if __name__ == "__main__":
    demo_claude_vision_single_page()
