#!/usr/bin/env python3
"""
Test script for GROBID-based PDF extraction.

Usage:
    python scripts/test_grobid_extractor.py <path_to_pdf>

This script tests the GROBID extractor with a sample PDF, verifying:
1. GROBID service is running
2. PDF processing works end-to-end
3. Text extraction quality

Example:
    python scripts/test_grobid_extractor.py ~/papers/sample.pdf
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.pdf_extractor import GrobidPDFExtractor, PDFExtractionError


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_grobid_extractor.py <path_to_pdf>")
        print()
        print("Example:")
        print("  python scripts/test_grobid_extractor.py ~/papers/sample.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    print("GROBID Extractor Test")
    print("=" * 70)
    print(f"PDF: {pdf_path}")
    print()

    try:
        extractor = GrobidPDFExtractor(verbose=True)

        print("Extracting text...")
        sections = extractor.extract_by_pages(pdf_path)

        print(f"\n✓ Extraction successful!")
        print(f"  Sections extracted: {len(sections)}")

        total_chars = sum(len(text) for _, text in sections)
        print(f"  Total characters: {total_chars:,}")

        print("\n" + "=" * 70)
        print("Section breakdown:")
        print("=" * 70)

        for section_num, text in sections:
            char_count = len(text)
            line_count = text.count("\n") + 1
            preview = text[:100].replace("\n", " ")
            if len(text) > 100:
                preview += "..."

            print(f"\nSection {section_num}:")
            print(f"  Chars: {char_count:,}")
            print(f"  Lines: {line_count}")
            print(f"  Preview: {preview}")

        print("\n" + "=" * 70)
        print("Full first section (first 500 chars):")
        print("=" * 70)

        if sections:
            _, first_text = sections[0]
            print(first_text[:500])
            if len(first_text) > 500:
                print("\n... [truncated]")

    except PDFExtractionError as e:
        print(f"\n✗ Extraction failed: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
