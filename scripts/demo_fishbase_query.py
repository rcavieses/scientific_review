#!/usr/bin/env python3
"""
Demo script showing how to use the FishBase query system

This demonstrates the main usage patterns for extracting population
parameters from FishBase.
"""

import pandas as pd
from pathlib import Path
from fishbase_scraper import FishBaseScraper
from goc_species_list_generator import generate_species_list

def demo_1_generate_species_list():
    """Demo 1: Generate GOC species list"""
    print("\n" + "="*70)
    print("DEMO 1: Generate GOC Species List")
    print("="*70)

    df = generate_species_list('data/input/goc_species_list.csv')

    print(f"\nGenerated list with {len(df)} species")
    print("\nGrouped by ecological type:")
    for group in sorted(df['ecological_group'].unique()):
        count = len(df[df['ecological_group'] == group])
        species = df[df['ecological_group'] == group]['scientific_name'].tolist()
        print(f"\n  {group} ({count} species):")
        for sp in species[:3]:
            print(f"    - {sp}")
        if count > 3:
            print(f"    ... and {count-3} more")

def demo_2_single_species():
    """Demo 2: Query single species"""
    print("\n" + "="*70)
    print("DEMO 2: Query Single Species")
    print("="*70)

    scraper = FishBaseScraper()

    species = "Sardinops sagax"
    print(f"\nSearching for: {species}")

    # Search
    url = scraper.search_species(species)
    print(f"  Search result: {'Found' if url else 'Not found'}")

    if url:
        print(f"  URL: {url}")

        # Scrape
        print(f"  Scraping profile...")
        params = scraper.scrape_species_profile(url)

        if params:
            print(f"  Extracted parameters:")
            for key, value in params.items():
                if value and key != 'profile_url':
                    print(f"    • {key}: {value}")

def demo_3_batch_query():
    """Demo 3: Batch query multiple species"""
    print("\n" + "="*70)
    print("DEMO 3: Batch Query Multiple Species")
    print("="*70)

    scraper = FishBaseScraper()

    # Get first 5 species from GOC list
    df = pd.read_csv('data/input/goc_species_list.csv')
    test_species = df['scientific_name'].head(5).tolist()

    print(f"\nQuerying {len(test_species)} species:")
    results = []

    for species in test_species:
        print(f"  • {species}...", end=' ', flush=True)

        url = scraper.search_species(species)
        if url:
            params = scraper.scrape_species_profile(url)
            if params:
                params['found'] = True
                params['scientific_name'] = species
                results.append(params)
                print("✓")
            else:
                print("✗ (parse failed)")
                results.append({
                    'scientific_name': species,
                    'found': False,
                    'error': 'Parse failed'
                })
        else:
            print("✗ (not found)")
            results.append({
                'scientific_name': species,
                'found': False,
                'error': 'Not found'
            })

    # Summary
    found = len([r for r in results if r.get('found')])
    print(f"\nResults: {found}/{len(test_species)} species found")

    # Save
    df_results = pd.DataFrame(results)
    output_file = 'outputs/demo_results.csv'
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(output_file, index=False)
    print(f"Saved to: {output_file}")

def demo_4_data_processing():
    """Demo 4: Process and analyze results"""
    print("\n" + "="*70)
    print("DEMO 4: Data Processing & Analysis")
    print("="*70)

    # Create sample data
    sample_data = {
        'scientific_name': ['Sardinops sagax', 'Engraulis mordax', 'Thunnus obesus'],
        'common_name': ['Pacific sardine', 'Northern anchovy', 'Bigeye tuna'],
        'tmax': [20, 18, 15],
        'lmax': [28.5, 20, 200],
        'trophic_level': [3.2, 3.5, 4.5],
        'ecological_group': ['Small_Pelagics', 'Small_Pelagics', 'Large_Pelagics'],
    }

    df = pd.DataFrame(sample_data)

    print("\nSample extracted data:")
    print(df.to_string(index=False))

    print("\n\nAnalysis by ecological group:")
    print(df.groupby('ecological_group')[['tmax', 'lmax', 'trophic_level']].mean().to_string())

    print("\n\nSpecies with highest trophic level:")
    top = df.nlargest(2, 'trophic_level')[['scientific_name', 'common_name', 'trophic_level']]
    print(top.to_string(index=False))

def main():
    """Run all demos"""
    print("\n" + "#"*70)
    print("# FishBase Query System - Usage Demonstrations")
    print("#"*70)

    try:
        demo_1_generate_species_list()
    except Exception as e:
        print(f"Demo 1 error: {e}")

    try:
        demo_2_single_species()
    except Exception as e:
        print(f"Demo 2 error: {e}")

    try:
        demo_3_batch_query()
    except Exception as e:
        print(f"Demo 3 error: {e}")

    try:
        demo_4_data_processing()
    except Exception as e:
        print(f"Demo 4 error: {e}")

    print("\n" + "#"*70)
    print("# Next steps:")
    print("#   1. Run: python3 fishbase_scraper.py")
    print("#   2. Run: ./run_fishbase_queries.sh")
    print("#   3. Check FISHBASE_README.md for full documentation")
    print("#"*70 + "\n")

if __name__ == '__main__':
    main()
