#!/usr/bin/env python3
"""
Test script for OCR provider.

Usage:
    python scripts/test_ocr_provider.py <path_to_pdf>

This script loads your Baidu Cloud credentials from .env and attempts to
extract text from the provided PDF using the OCR API, then prints results.

Useful for validating:
1. API credentials are correct
2. PDF processing works end-to-end
3. Text quality from OCR
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path so we can import pipeline modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.ocr import BaiduCloudOCRProvider, get_ocr_provider


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_ocr_provider.py <path_to_pdf>")
        print()
        print("Example:")
        print("  python scripts/test_ocr_provider.py ~/papers/sample.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    load_dotenv()

    provider_name = os.getenv("OCR_PROVIDER", "baidu_api")
    print(f"Using OCR provider: {provider_name}")
    print(f"PDF: {pdf_path}")
    print("-" * 70)

    try:
        provider = get_ocr_provider(provider_name)

        pages = provider.extract_pdf(pdf_path)

        print(f"\n✓ Extraction successful!")
        print(f"  Total pages extracted: {len(pages)}")
        print(f"  Total characters: {sum(len(text) for _, text in pages)}")

        print("\n" + "=" * 70)
        print("Sample output (first 500 chars from first page):")
        print("=" * 70 + "\n")

        if pages:
            _, text = pages[0]
            sample = text[:500]
            print(sample)
            if len(text) > 500:
                print("\n... [truncated]")

        print("\n" + "=" * 70)
        print("Full page breakdown:")
        print("=" * 70)
        for page_num, text in pages:
            char_count = len(text)
            line_count = text.count("\n") + 1
            print(f"  Page {page_num:3d}: {char_count:6d} chars, {line_count:4d} lines")

    except Exception as e:
        print(f"\n✗ Extraction failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
