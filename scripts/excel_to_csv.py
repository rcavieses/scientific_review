#!/usr/bin/env python3
"""
Convert Atlantis biological parameters Excel to CSV format.
"""

import sys
from pathlib import Path
import pandas as pd

EXCEL_FILE = Path(__file__).parent.parent / "data" / "input" / "Atlantis_GOC_parametros_bioogicos.xlsx"
CSV_OUTPUT = Path(__file__).parent.parent / "data" / "input" / "Atlantis_GOC_parametros_biologicos.csv"

def excel_to_csv():
    """Convert Excel to CSV."""
    print(f"Reading Excel file: {EXCEL_FILE}")

    if not EXCEL_FILE.exists():
        print(f"❌ Error: File not found: {EXCEL_FILE}")
        return 1

    try:
        # Read Excel file (sheet name: 'parameters')
        # Headers are in row 2 (index 1), skip row 1
        df = pd.read_excel(EXCEL_FILE, sheet_name='parameters', header=1)

        # Remove completely empty rows
        df = df.dropna(how='all')

        print(f"✓ Loaded {len(df)} rows, {len(df.columns)} columns")
        print(f"\nFirst few rows:")
        print(df.head(10))

        print(f"\nColumn names:")
        print(df.columns.tolist())

        # Save to CSV
        df.to_csv(CSV_OUTPUT, index=False, encoding='utf-8')

        print(f"\n✅ Successfully converted to CSV")
        print(f"Output file: {CSV_OUTPUT}")
        print(f"File size: {CSV_OUTPUT.stat().st_size / 1024:.1f} KB")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(excel_to_csv())
