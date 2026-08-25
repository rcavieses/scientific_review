#!/usr/bin/env python3
"""
Create a practical CSV table for population parameters.
Combines species list with parameter columns.
"""

import sys
from pathlib import Path
import pandas as pd

TAXONOMY_CSV = Path(__file__).parent.parent / "data" / "input" / "grupos_funcionals_Atlantis_GOC - full_taxonomy.csv"
OUTPUT_CSV = Path(__file__).parent.parent / "data" / "output" / "Atlantis_GOC_parametros_biologicos.csv"

# Vertebrate classes
VERTEBRATE_CLASSES = [
    'Teleostei', 'Petromyzontida', 'Cephalochordata', 'Mammalia',
    'Aves', 'Reptilia', 'Amphibia', 'Actinopterygii', 'Chondrichthyes'
]

# Parameter columns to include
PARAMETER_COLUMNS = [
    'biomass_mt',
    'abundance_numbers',
    'mean_body_size',
    'max_age',
    'natural_mortality',
    'Lmax',
    'li_a',
    'li_b',
    'vb_Linf',
    'vb_t0',
    'growth_rate',
    'age_first_maturity',
    'larval_duration',
    'StartSpawnDayOfYear',
    'EndSpawnDayOfYear',
    'IsMigratory',
    'citations',
    'notes'
]

def create_parameters_csv():
    """Create CSV with species and parameter columns."""

    print(f"Reading taxonomy file: {TAXONOMY_CSV}")

    if not TAXONOMY_CSV.exists():
        print(f"❌ Error: File not found: {TAXONOMY_CSV}")
        return 1

    try:
        # Read taxonomy
        df_taxonomy = pd.read_csv(TAXONOMY_CSV)

        # Filter vertebrates
        df_vertebrates = df_taxonomy[df_taxonomy['class'].isin(VERTEBRATE_CLASSES)].copy()

        print(f"✓ Found {len(df_vertebrates)} vertebrate records")

        # Get unique species per group
        df_species = df_vertebrates.drop_duplicates(
            subset=['atlantis_fg', 'species'],
            keep='first'
        ).reset_index(drop=True)

        print(f"✓ Unique species: {len(df_species)}")
        print(f"✓ Functional groups: {df_species['atlantis_fg'].nunique()}")

        # Select relevant columns
        result = df_species[[
            'atlantis_fg',
            'atlantis_code',
            'species',
            'genus',
            'family',
            'order',
            'class',
            'phylum'
        ]].copy()

        # Rename columns
        result.rename(columns={
            'atlantis_fg': 'Group',
            'atlantis_code': 'Code',
            'species': 'Species',
            'genus': 'Genus',
            'family': 'Family',
            'order': 'Order',
            'class': 'Class',
            'phylum': 'Phylum'
        }, inplace=True)

        # Add empty parameter columns
        for param in PARAMETER_COLUMNS:
            result[param] = None

        # Sort by group and species
        result = result.sort_values(['Group', 'Species']).reset_index(drop=True)

        # Create output directory if needed
        OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

        # Save to CSV
        result.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')

        print(f"\n✅ Successfully created CSV")
        print(f"Output file: {OUTPUT_CSV}")
        print(f"Rows: {len(result)}")
        print(f"Columns: {len(result.columns)}")
        print(f"File size: {OUTPUT_CSV.stat().st_size / 1024:.1f} KB")

        print(f"\nFirst 5 rows:")
        print(result.head())

        print(f"\nColumn list:")
        print(result.columns.tolist())

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(create_parameters_csv())
