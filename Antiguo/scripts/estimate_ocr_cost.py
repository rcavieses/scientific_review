#!/usr/bin/env python3
"""
Estimate Baidu OCR costs for your PDF corpus.

Analyzes PDF file sizes and estimates page counts to calculate processing costs.

Usage:
    python scripts/estimate_ocr_cost.py [--pdf-dir PATH] [--sample-size N]

Options:
    --pdf-dir PATH      Root directory containing PDFs (default: outputs/pdfs)
    --sample-size N     Number of PDFs to analyze (default: 100, or all if <100 found)
    --unit-cost COST    Cost per page in USD (default: 0.002)
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    print("Warning: PyPDF2 not available. Using file size heuristic instead.")


def estimate_pages_from_filesize(pdf_path: Path) -> int:
    """
    Estimate PDF page count from file size.

    Heuristic: Scientific papers average 5-7 KB per page (uncompressed).
    This is a rough estimate and varies by paper format/compression.
    """
    try:
        size_kb = pdf_path.stat().st_size / 1024
        # Conservative estimate: 6 KB/page
        pages = max(1, round(size_kb / 6))
        return pages
    except Exception:
        return 1


def get_page_count(pdf_path: Path) -> int:
    """Get actual page count from PDF, fallback to size heuristic."""
    if HAS_PYPDF2:
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                return len(reader.pages)
        except Exception:
            pass

    return estimate_pages_from_filesize(pdf_path)


def analyze_corpus(
    pdf_dir: Path,
    sample_size: int = 100,
    unit_cost: float = 0.002,
) -> dict:
    """
    Analyze PDF corpus and estimate OCR costs.

    Returns:
        dict with statistics: total_pdfs, analyzed_count, avg_pages, total_estimated_pages,
        estimated_cost, cost_range, processing_time_estimates
    """
    pdf_dir = Path(pdf_dir)

    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")

    # Find all PDFs
    all_pdfs = list(pdf_dir.rglob("*.pdf"))

    if not all_pdfs:
        raise ValueError(f"No PDFs found in {pdf_dir}")

    print(f"Found {len(all_pdfs)} total PDFs")

    # Sample
    if len(all_pdfs) <= sample_size:
        sample_pdfs = all_pdfs
        analyzed = len(all_pdfs)
    else:
        import random
        sample_pdfs = random.sample(all_pdfs, sample_size)
        analyzed = sample_size

    print(f"Analyzing {analyzed} PDFs (sample)...")

    page_counts = []
    file_sizes = []

    for i, pdf_path in enumerate(sample_pdfs, 1):
        try:
            pages = get_page_count(pdf_path)
            size_mb = pdf_path.stat().st_size / (1024 * 1024)
            page_counts.append(pages)
            file_sizes.append(size_mb)

            if i % 10 == 0:
                print(f"  [{i}/{analyzed}] {pdf_path.name}: {pages} pages, {size_mb:.2f} MB")
        except Exception as e:
            print(f"  Warning: Could not process {pdf_path.name}: {e}")

    if not page_counts:
        raise ValueError("Could not extract page counts from any PDF")

    # Statistics
    avg_pages = sum(page_counts) / len(page_counts)
    avg_size_mb = sum(file_sizes) / len(file_sizes)
    min_pages = min(page_counts)
    max_pages = max(page_counts)
    total_pages_sample = sum(page_counts)

    # Extrapolate to full corpus
    total_pdfs = len(all_pdfs)
    estimated_total_pages = int(avg_pages * total_pdfs)

    # Cost calculation
    cost_per_page = unit_cost
    base_cost = estimated_total_pages * cost_per_page

    # Uncertainty range (±20%)
    min_cost = base_cost * 0.8
    max_cost = base_cost * 1.2

    # Processing time estimates (Baidu API rate limits: 2 QPS submit, 5 QPS query)
    # ~2-5 seconds per PDF (poll + download)
    avg_time_per_pdf = 3  # seconds
    total_time_seconds = total_pdfs * avg_time_per_pdf
    total_time_hours = total_time_seconds / 3600

    return {
        "total_pdfs": total_pdfs,
        "analyzed_count": analyzed,
        "avg_pages_per_pdf": round(avg_pages, 1),
        "min_pages": min_pages,
        "max_pages": max_pages,
        "avg_size_mb": round(avg_size_mb, 2),
        "total_estimated_pages": estimated_total_pages,
        "unit_cost_usd": unit_cost,
        "estimated_cost_usd": round(base_cost, 2),
        "cost_range_usd": (round(min_cost, 2), round(max_cost, 2)),
        "total_time_seconds": total_time_seconds,
        "total_time_hours": round(total_time_hours, 1),
        "sample_stats": {
            "total_pages_in_sample": total_pages_sample,
            "sample_size": analyzed,
        },
    }


def print_report(stats: dict) -> None:
    """Pretty-print cost estimation report."""
    print("\n" + "=" * 70)
    print("BAIDU OCR COST ESTIMATION REPORT")
    print("=" * 70)

    print("\n📊 CORPUS STATISTICS")
    print(f"  Total PDFs in corpus:        {stats['total_pdfs']:,}")
    print(f"  PDFs analyzed (sample):      {stats['analyzed_count']:,}")
    print(f"  Average pages per PDF:       {stats['avg_pages_per_pdf']:.1f}")
    print(f"    (range: {stats['min_pages']} - {stats['max_pages']} pages)")
    print(f"  Average file size:           {stats['avg_size_mb']:.2f} MB")

    print("\n💰 COST ESTIMATION (Baidu Cloud)")
    print(f"  Total estimated pages:       {stats['total_estimated_pages']:,}")
    print(f"  Unit cost per page:          ${stats['unit_cost_usd']:.4f}")
    print(f"  TOTAL ESTIMATED COST:        ${stats['estimated_cost_usd']:,.2f}")
    print(f"  Cost range (±20%):           ${stats['cost_range_usd'][0]:,.2f} - ${stats['cost_range_usd'][1]:,.2f}")

    print("\n⏱️  PROCESSING TIME (Serial, Baidu API QPS limits)")
    print(f"  Estimated time per PDF:      ~3 seconds")
    print(f"  Total processing time:       {stats['total_time_hours']:.1f} hours (~{int(stats['total_time_seconds'] / 60)} minutes)")
    print(f"  (May be faster with optimizations/parallel requests)")

    print("\n📋 COMPARISON WITH FREE TIER")
    free_personal = 200
    free_enterprise = 1000
    free_cost_personal = f"Process {free_personal} pages"
    free_cost_enterprise = f"Process {free_enterprise} pages"

    pct_personal = (free_personal / stats['total_estimated_pages']) * 100
    pct_enterprise = (free_enterprise / stats['total_estimated_pages']) * 100

    print(f"  Free tier (personal):        {free_cost_personal} ({pct_personal:.1f}% of corpus)")
    print(f"  Free tier (enterprise):      {free_cost_enterprise} ({pct_enterprise:.1f}% of corpus)")
    print(f"  Remaining to pay for:        {stats['total_estimated_pages'] - free_enterprise:,} pages (enterprise)")
    remaining_cost = (stats['total_estimated_pages'] - free_enterprise) * stats['unit_cost_usd']
    print(f"  Estimated cost (after free): ${remaining_cost:,.2f}")

    print("\n💡 RECOMMENDATIONS")
    print("  1. Test with first 100 PDFs (~$0.30 est.) to validate quality")
    print("  2. Contact Baidu Cloud sales for academic discounts/credits")
    print("  3. Consider local mode if you have access to a GPU (one-time hardware cost)")
    print("  4. Batch processing in phases if budget is constrained")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Estimate Baidu OCR costs for your PDF corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick analysis (default directory)
  python scripts/estimate_ocr_cost.py

  # Custom PDF directory
  python scripts/estimate_ocr_cost.py --pdf-dir ~/my_papers

  # Analyze all PDFs (not just sample)
  python scripts/estimate_ocr_cost.py --sample-size 10000

  # Different unit cost (e.g., if Baidu offers discounts)
  python scripts/estimate_ocr_cost.py --unit-cost 0.001
        """,
    )
    parser.add_argument(
        "--pdf-dir",
        default="outputs/pdfs",
        help="Root directory containing PDFs (default: outputs/pdfs)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help="Number of PDFs to analyze (default: 100, or all if fewer)",
    )
    parser.add_argument(
        "--unit-cost",
        type=float,
        default=0.002,
        help="Cost per page in USD (default: 0.002, ~$0.20 per 100 pages)",
    )

    args = parser.parse_args()

    try:
        stats = analyze_corpus(
            pdf_dir=Path(args.pdf_dir),
            sample_size=args.sample_size,
            unit_cost=args.unit_cost,
        )
        print_report(stats)

        # Save report to file
        report_path = Path("outputs/ocr_cost_estimation.txt")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w") as f:
            f.write("BAIDU OCR COST ESTIMATION REPORT\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Total PDFs:                  {stats['total_pdfs']:,}\n")
            f.write(f"Analyzed:                    {stats['analyzed_count']:,}\n")
            f.write(f"Avg pages/PDF:               {stats['avg_pages_per_pdf']:.1f}\n")
            f.write(f"Total estimated pages:       {stats['total_estimated_pages']:,}\n")
            f.write(f"Estimated cost:              ${stats['estimated_cost_usd']:,.2f}\n")
            f.write(f"Cost range:                  ${stats['cost_range_usd'][0]:,.2f} - ${stats['cost_range_usd'][1]:,.2f}\n")
            f.write(f"Processing time:             {stats['total_time_hours']:.1f} hours\n")

        print(f"\n✓ Report saved to: {report_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
