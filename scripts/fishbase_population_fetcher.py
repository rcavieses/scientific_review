#!/usr/bin/env python3
"""
FishBase Population Parameters Fetcher

Queries FishBase API to retrieve population biological parameters for species
in the Gulf of California (Golfo de California). This is an independent program
that complements the RAG-based parameter extraction system.

Usage:
    python3 fishbase_population_fetcher.py [options]

Options:
    --species FILE       CSV file with species list (common or scientific names)
    --output FILE        Output file for results (CSV or JSON)
    --region GOC         Region (default: GOC - Gulf of California)
    --format FORMAT      Output format: csv or json (default: csv)
"""

import requests
import pandas as pd
import json
import logging
import argparse
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import time
from urllib.parse import quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FishBaseClient:
    """Client for querying FishBase API"""

    BASE_URL = "https://www.fishbase.org"
    API_TIMEOUT = 10

    # Common GOC species (example list)
    GOC_SPECIES = [
        # Demersal species
        "Scorpaena guttata",  # California scorpionfish
        "Sebastes caurinus",  # Copper rockfish
        "Anoplopoma fimbria",  # Sablefish
        "Opsanus tau",  # Oyster toadfish
        "Paralabrax clathratus",  # Barred sand bass

        # Pelagic species
        "Sardinops sagax",  # Pacific sardine
        "Engraulis mordax",  # Northern anchovy
        "Trachurus symmetricus",  # Jack mackerel
        "Scomber japonicus",  # Pacific mackerel
        "Thunnus obesus",  # Bigeye tuna

        # Commercial species
        "Dosidicus gigas",  # Jumbo squid
        "Penaeus vannamei",  # White shrimp
        "Callinectes sapidus",  # Blue crab
        "Lutjanus guttatus",  # Spotted rose snapper
        "Caranx ignobilis",  # Giant trevally
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ATLANTIS-GOC-Research/1.0'
        })
        self.results = []

    def search_species(self, species_name: str) -> Optional[Dict]:
        """
        Search for species on FishBase

        Args:
            species_name: Scientific or common name

        Returns:
            Species data dict or None if not found
        """
        try:
            # Try scientific name search
            url = f"{self.BASE_URL}/api/v1/species/search"
            params = {"q": species_name}

            response = self.session.get(url, params=params, timeout=self.API_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]

            return None

        except requests.RequestException as e:
            logger.warning(f"API request failed for '{species_name}': {e}")
            return None

    def get_species_by_id(self, species_id: int) -> Optional[Dict]:
        """Get full species details by ID"""
        try:
            url = f"{self.BASE_URL}/api/v1/species/{species_id}"
            response = self.session.get(url, timeout=self.API_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to get species ID {species_id}: {e}")
            return None

    def extract_population_params(self, species_data: Dict) -> Dict:
        """
        Extract population biological parameters from species data

        Args:
            species_data: Full species data from FishBase

        Returns:
            Dictionary with extracted parameters
        """
        params = {
            'species_id': species_data.get('id'),
            'scientific_name': species_data.get('Sci_name'),
            'common_name': species_data.get('FBname'),
            'family': species_data.get('Family'),

            # Growth parameters
            'linf': species_data.get('Linf'),  # Asymptotic length
            'k': species_data.get('K'),  # von Bertalanffy growth coefficient
            'tmax': species_data.get('tmax'),  # Maximum age

            # Size parameters
            'lmat': species_data.get('Lmat'),  # Length at maturity
            'lmax': species_data.get('LongevityWild'),  # Maximum observed length

            # Reproductive parameters
            'fecundity': species_data.get('Fecundity'),
            'maturation_age': species_data.get('tm'),  # Age at maturity

            # Mortality
            'm': species_data.get('M'),  # Natural mortality

            # Feeding
            'trophic_level': species_data.get('TrophicLevel'),

            # Environment
            'habitat': species_data.get('Habitat'),
            'salinity': species_data.get('Salinity'),
            'depth_range': species_data.get('DepthRangeShallow'),
        }

        return params

    def fetch_species_parameters(
        self,
        species_list: List[str],
        delay: float = 0.5
    ) -> List[Dict]:
        """
        Fetch population parameters for a list of species

        Args:
            species_list: List of species names
            delay: Delay between requests (seconds) to avoid rate limiting

        Returns:
            List of parameter dictionaries
        """
        results = []

        for i, species in enumerate(species_list, 1):
            logger.info(f"[{i}/{len(species_list)}] Fetching: {species}")

            # Search species
            species_info = self.search_species(species)
            if not species_info:
                logger.warning(f"Species not found: {species}")
                results.append({
                    'query': species,
                    'found': False,
                    'error': 'Not found on FishBase'
                })
                time.sleep(delay)
                continue

            # Get full details if we have an ID
            species_id = species_info.get('id')
            if species_id:
                full_data = self.get_species_by_id(species_id)
                if full_data:
                    params = self.extract_population_params(full_data)
                    params['found'] = True
                    params['query'] = species
                    results.append(params)
                else:
                    results.append({
                        'query': species,
                        'found': False,
                        'error': 'Could not retrieve full details'
                    })
            else:
                results.append({
                    'query': species,
                    'found': False,
                    'error': 'No species ID returned'
                })

            time.sleep(delay)

        return results

    def load_species_from_file(self, filepath: str) -> List[str]:
        """
        Load species list from CSV file

        Expected format:
        - Column header: 'species' or 'scientific_name' or 'common_name'
        - One species per row
        """
        try:
            df = pd.read_csv(filepath)

            # Try to find species column
            species_col = None
            for col in ['species', 'scientific_name', 'common_name', 'Species']:
                if col in df.columns:
                    species_col = col
                    break

            if species_col is None:
                # Use first column if no known column found
                species_col = df.columns[0]

            species_list = df[species_col].dropna().tolist()
            logger.info(f"Loaded {len(species_list)} species from {filepath}")
            return species_list

        except Exception as e:
            logger.error(f"Error loading species file: {e}")
            raise

    def save_results(self, results: List[Dict], filepath: str, format: str = 'csv'):
        """
        Save results to file

        Args:
            results: List of parameter dictionaries
            filepath: Output file path
            format: 'csv' or 'json'
        """
        try:
            output_path = Path(filepath)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format.lower() == 'json':
                with open(filepath, 'w') as f:
                    json.dump(results, f, indent=2)
                logger.info(f"Results saved to {filepath}")

            else:  # CSV
                df = pd.DataFrame(results)
                df.to_csv(filepath, index=False)
                logger.info(f"Results saved to {filepath}")

                # Print summary
                found = sum(1 for r in results if r.get('found', False))
                total = len(results)
                logger.info(f"Summary: {found}/{total} species found")

        except Exception as e:
            logger.error(f"Error saving results: {e}")
            raise

    def print_summary(self, results: List[Dict]):
        """Print summary of results"""
        found = [r for r in results if r.get('found', False)]
        not_found = [r for r in results if not r.get('found', False)]

        print("\n" + "="*70)
        print("FISHBASE POPULATION PARAMETERS EXTRACTION SUMMARY")
        print("="*70)
        print(f"Total species queried: {len(results)}")
        print(f"Found: {len(found)}")
        print(f"Not found: {len(not_found)}")

        if found:
            print("\n" + "-"*70)
            print("SPECIES FOUND WITH PARAMETERS:")
            print("-"*70)

            df_found = pd.DataFrame(found)
            # Select key columns for display
            key_cols = ['scientific_name', 'common_name', 'tmax', 'linf', 'k', 'trophic_level']
            display_cols = [col for col in key_cols if col in df_found.columns]

            print(df_found[display_cols].to_string(index=False))

        if not_found:
            print("\n" + "-"*70)
            print("SPECIES NOT FOUND:")
            print("-"*70)
            for r in not_found:
                print(f"  • {r.get('query')}: {r.get('error')}")

        print("\n" + "="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Fetch population parameters from FishBase for GOC species'
    )
    parser.add_argument(
        '--species',
        help='CSV file with species list'
    )
    parser.add_argument(
        '--output',
        default='outputs/fishbase_parameters.csv',
        help='Output file path (default: outputs/fishbase_parameters.csv)'
    )
    parser.add_argument(
        '--format',
        choices=['csv', 'json'],
        default='csv',
        help='Output format (default: csv)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between API requests in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--use-defaults',
        action='store_true',
        help='Use default GOC species list if no species file provided'
    )

    args = parser.parse_args()

    # Initialize client
    client = FishBaseClient()

    # Get species list
    if args.species:
        species_list = client.load_species_from_file(args.species)
    elif args.use_defaults:
        species_list = client.GOC_SPECIES
        logger.info(f"Using default GOC species list ({len(species_list)} species)")
    else:
        print("Please provide --species file or use --use-defaults")
        parser.print_help()
        return

    # Fetch parameters
    logger.info(f"Starting FishBase query for {len(species_list)} species")
    results = client.fetch_species_parameters(species_list, delay=args.delay)

    # Save results
    client.save_results(results, args.output, format=args.format)

    # Print summary
    client.print_summary(results)


if __name__ == '__main__':
    main()
