#!/usr/bin/env python3
"""Test simple de extracción de PDFs - diagnóstico"""

import sys
from pathlib import Path

# Agregar project al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.pdf_extractor import PdfPlumberExtractor

PDF_DIR = Path(__file__).parent.parent / "outputs" / "PDF_GOC" / "PDF"

def test_extraction():
    """Test de extracción en primeros 5 PDFs"""
    pdfs = sorted(PDF_DIR.glob("*.pdf"))[:1]

    print(f"📋 Testing extracción en {len(pdfs)} PDFs")
    print(f"Directorio: {PDF_DIR}\n")

    # Test pdfplumber fallback
    print("=" * 80)
    print("Intentando pdfplumber...")
    print("=" * 80)
    try:
        pdfplumber_extractor = PdfPlumberExtractor(verbose=True)
        for pdf_path in pdfs:
            print(f"\n📄 {pdf_path.name}")
            try:
                result = pdfplumber_extractor.extract_by_pages(pdf_path)
                print(f"   Type: {type(result)}")
                print(f"   Length: {len(result)}")
                if result:
                    print(f"   Type[0]: {type(result[0])}")
                    print(f"   Content[0]: {result[0]}")

                    # Intenta acceder como tupla o dict
                    try:
                        text = result[0]['text']
                        print(f"   ✓ Acceso como dict funcionó")
                    except TypeError:
                        try:
                            text, page_num = result[0]
                            print(f"   ✓ Acceso como tupla funcionó: page {page_num}")
                        except:
                            print(f"   ✗ Ni dict ni tupla")
            except Exception as e:
                print(f"   ✗ Error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
    except Exception as e:
        print(f"❌ pdfplumber falló: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction()
