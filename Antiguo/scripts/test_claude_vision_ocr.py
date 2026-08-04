#!/usr/bin/env python3
"""
Prueba de Claude Vision OCR vs GROBID para un solo PDF.

Uso:
    python3 scripts/test_claude_vision_ocr.py [pdf_file]

Compara:
- Cantidad de texto extraído
- Calidad visual del resultado
- Tiempo de procesamiento
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ocr.claude_vision_provider import ClaudeVisionOCRProvider
from pipeline.ocr.grobid_provider import GrobidProvider
from pipeline.rag.pdf_extractor import PdfPlumberExtractor


def test_ocr_provider(provider, name, pdf_path):
    """Prueba un proveedor OCR y retorna estadísticas."""
    print(f"\n{'='*60}")
    print(f"Probando: {name}")
    print(f"{'='*60}")

    try:
        start = time.time()
        result = provider.extract_pdf(pdf_path)
        elapsed = time.time() - start

        total_chars = sum(len(text) for _, text in result)
        total_pages = len(result)

        print(f"✅ Éxito")
        print(f"   Tiempo: {elapsed:.2f}s")
        print(f"   Páginas: {total_pages}")
        print(f"   Caracteres totales: {total_chars:,}")
        print(f"   Promedio por página: {total_chars // max(total_pages, 1):,}")

        # Mostrar preview del primer párrafo
        if result:
            first_text = result[0][1]
            preview = first_text[:200].replace("\n", " ")
            print(f"\n   Preview (primeros 200 chars):")
            print(f"   {preview}...")

        return {
            "success": True,
            "name": name,
            "time": elapsed,
            "pages": total_pages,
            "chars": total_chars,
            "result": result,
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            "success": False,
            "name": name,
            "error": str(e),
        }


def main():
    # Seleccionar PDF para prueba
    pdf_file = sys.argv[1] if len(sys.argv) > 1 else None

    if not pdf_file:
        # Buscar un PDF de muestra
        pdf_dir = Path("outputs/PDF_GOC/PDF")
        pdfs = list(pdf_dir.glob("*.pdf"))

        if not pdfs:
            print("❌ No se encontraron PDFs en outputs/PDF_GOC/PDF/")
            return

        pdf_file = str(pdfs[0])  # Usar el primero

    pdf_path = Path(pdf_file)

    if not pdf_path.exists():
        print(f"❌ Archivo no encontrado: {pdf_file}")
        return

    print(f"📄 Prueba de OCR: {pdf_path.name}")
    print(f"   Tamaño: {pdf_path.stat().st_size / 1024 / 1024:.2f} MB")

    results = []

    # 1. Probar PdfPlumber (baseline rápido)
    try:
        pdfplumber = PdfPlumberExtractor(verbose=False)
        results.append(test_ocr_provider(pdfplumber, "PdfPlumber (baseline)", pdf_path))
    except Exception as e:
        print(f"\n❌ PdfPlumber no disponible: {e}")

    # 2. Probar GROBID
    grobid = GrobidProvider(grobid_url="http://localhost:8070")
    results.append(test_ocr_provider(grobid, "GROBID", pdf_path))

    # 3. Probar Claude Vision
    try:
        claude_vision = ClaudeVisionOCRProvider()
        results.append(test_ocr_provider(claude_vision, "Claude Vision OCR", pdf_path))
    except Exception as e:
        print(f"\n❌ Claude Vision no disponible: {e}")

    # Resumen comparativo
    print(f"\n\n{'='*60}")
    print("📊 RESUMEN COMPARATIVO")
    print(f"{'='*60}")

    successful = [r for r in results if r["success"]]

    if successful:
        # Tabla comparativa
        print(f"\n{'Provider':<20} {'Tiempo (s)':<12} {'Páginas':<10} {'Caracteres':<15} {'Chars/Página':<15}")
        print("-" * 72)

        for r in successful:
            chars_per_page = r["chars"] // max(r["pages"], 1)
            print(
                f"{r['name']:<20} {r['time']:<12.2f} {r['pages']:<10} {r['chars']:<15,} {chars_per_page:<15,}"
            )

        # Encontrar mejor resultado
        best = max(successful, key=lambda r: r["chars"])
        print(f"\n🏆 Mejor extracción: {best['name']} ({best['chars']:,} caracteres)")

    # Mostrar errores
    failed = [r for r in results if not r["success"]]
    if failed:
        print(f"\n⚠️  Providers que fallaron:")
        for r in failed:
            print(f"   - {r['name']}: {r['error']}")


if __name__ == "__main__":
    main()
