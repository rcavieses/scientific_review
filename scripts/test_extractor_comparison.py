#!/usr/bin/env python3
"""Comparación de extractores GROBID vs pdfplumber"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.pdf_extractor import GrobidPDFExtractor, PdfPlumberExtractor

PDF_DIR = Path(__file__).parent.parent / "outputs" / "PDF_GOC" / "PDF"

def compare_extractors():
    """Compara extracción de GROBID vs pdfplumber"""
    pdfs = sorted(PDF_DIR.glob("*.pdf"))[:3]

    for pdf_path in pdfs:
        print(f"\n{'='*80}")
        print(f"PDF: {pdf_path.name}")
        print(f"Tamaño: {pdf_path.stat().st_size / 1024**2:.1f} MB")
        print('='*80)

        # GROBID
        print("\n🔹 GROBID:")
        try:
            grobid = GrobidPDFExtractor(verbose=True)
            grobid_pages = grobid.extract_by_pages(pdf_path)
            grobid_total = sum(len(text) for _, text in grobid_pages)
            print(f"  ✓ {len(grobid_pages)} secciones, {grobid_total:,} caracteres")
            for i, (section_num, text) in enumerate(grobid_pages[:2]):
                print(f"    [{i+1}] Sección {section_num}: {len(text):,} chars")
                print(f"        Preview: {text[:80]}...")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {e}")
            grobid_total = 0

        # pdfplumber
        print("\n🔹 pdfplumber:")
        try:
            pdfplumber_ext = PdfPlumberExtractor(verbose=True)
            pdf_pages = pdfplumber_ext.extract_by_pages(pdf_path)
            pdf_total = sum(len(text) for _, text in pdf_pages)
            print(f"  ✓ {len(pdf_pages)} páginas, {pdf_total:,} caracteres")
            for i, (page_num, text) in enumerate(pdf_pages[:2]):
                print(f"    [{i+1}] Página {page_num}: {len(text):,} chars")
                print(f"        Preview: {text[:80]}...")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {e}")
            pdf_total = 0

        # Comparación
        print(f"\n📊 Comparación:")
        print(f"  GROBID:    {grobid_total:>8,} chars")
        print(f"  pdfplumber:{pdf_total:>8,} chars")
        if grobid_total > 0 and pdf_total > 0:
            ratio = grobid_total / pdf_total * 100
            print(f"  Ratio: GROBID es {ratio:.1f}% del pdfplumber")
            if ratio < 20:
                print(f"  ⚠️  GROBID está extrayendo muy poco!")

if __name__ == "__main__":
    compare_extractors()
