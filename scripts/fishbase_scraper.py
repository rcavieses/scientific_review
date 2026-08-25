#!/usr/bin/env python3
"""
FishBase Web Scraper for Population Parameters

Alternative scraper that uses web scraping to retrieve population biological
parameters when the API is unavailable or limited. More robust than API-only approach.

Usage:
    python3 fishbase_scraper.py [options]
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import logging
import argparse
from typing import Dict, List, Optional
from pathlib import Path
import time
from urllib.parse import quote, urljoin
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FishBaseScraper:
    """Web scraper for FishBase population parameters"""

    BASE_URL = "https://www.fishbase.org"
    TIMEOUT = 15

    # GOC endemic and common species
    GOC_SPECIES = {
        # Demersal species
        'Scorpaena guttata': 'California scorpionfish',
        'Sebastes caurinus': 'Copper rockfish',
        'Anoplopoma fimbria': 'Sablefish',
        'Ophiodon elongatus': 'Lingcod',
        'Paralabrax clathratus': 'Barred sand bass',
        'Hyperlophus exilis': 'Dwarf surfperch',

        # Pelagic species
        'Sardinops sagax': 'Pacific sardine',
        'Engraulis mordax': 'Northern anchovy',
        'Trachurus symmetricus': 'Jack mackerel',
        'Scomber japonicus': 'Pacific mackerel',
        'Thunnus obesus': 'Bigeye tuna',
        'Thunnus albacares': 'Yellowfin tuna',

        # Cephalopods
        'Dosidicus gigas': 'Jumbo squid',
        'Loligo opalescens': 'Market squid',

        # Crustaceans
        'Penaeus vannamei': 'White shrimp',
        'Callinectes sapidus': 'Blue crab',
        'Chionoecetes opilio': 'Snow crab',

        # Snappers and groupers
        'Lutjanus guttatus': 'Spotted rose snapper',
        'Lutjanus peru': 'Red snapper',
        'Epinephelus labriformis': 'Grouper',

        # Jacks and carangids
        'Caranx ignobilis': 'Giant trevally',
        'Caranx melampygus': 'Bluefin trevally',
        'Seriola lalandi': 'Yellowtail amberjack',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        })
        # Use requests session retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=3,
            status_forcelist=[403, 429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def search_species(self, species_name: str) -> Optional[str]:
        """
        Search for species on FishBase and return profile URL

        Args:
            species_name: Scientific name (e.g., "Sardinops sagax")

        Returns:
            Profile URL or None if not found
        """
        try:
            # Try direct URL approach first (more reliable)
            genus, *species = species_name.split()
            if species:
                # Convert to hyphenated format that FishBase uses
                # E.g., "Sardinops sagax" -> "Sardinops-sagax"
                direct_url = f"{self.BASE_URL}/summary/{genus}-{species[0]}.html"

                response = self.session.get(direct_url, timeout=self.TIMEOUT)
                if response.status_code == 200:
                    logger.debug(f"Found direct species URL: {direct_url}")
                    return direct_url
                else:
                    logger.debug(f"Direct URL not found (404), trying search: {direct_url}")

            # Fallback to search if direct URL fails
            search_url = f"{self.BASE_URL}/search.php"
            params = {
                'q': species_name,
                'fDocDB': 'FB',
                'match': 'contains',
            }

            response = self.session.get(search_url, params=params, timeout=self.TIMEOUT)

            # Check if we got blocked
            if response.status_code == 403:
                logger.warning(f"Access denied (403) for search of '{species_name}'")
                # Return a constructed URL as fallback
                if species:
                    fallback_url = f"{self.BASE_URL}/summary/{genus}-{species[0]}.html"
                    return fallback_url
                return None

            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for species link in results
            links = soup.find_all('a', href=re.compile(r'/species/|/summary/'))

            if links:
                # Return first match
                href = links[0].get('href')
                if href:
                    profile_url = urljoin(self.BASE_URL, href)
                    logger.debug(f"Found species URL: {profile_url}")
                    return profile_url

            logger.warning(f"Species not found in search results: {species_name}")
            return None

        except Exception as e:
            logger.warning(f"Search failed for '{species_name}': {e}")
            return None

    def scrape_species_profile(self, profile_url: str) -> Optional[Dict]:
        """
        Scrape population parameters from FishBase species profile

        Args:
            profile_url: Full URL to FishBase species profile

        Returns:
            Dictionary with extracted parameters
        """
        try:
            response = self.session.get(profile_url, timeout=self.TIMEOUT)

            if response.status_code == 404:
                logger.warning(f"Profile not found (404): {profile_url}")
                return None

            if response.status_code == 403:
                logger.warning(f"Access denied (403): {profile_url}")
                return None

            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            params = {
                'profile_url': profile_url,
            }

            # Extract basic info
            title = soup.find('h1')
            if title:
                params['scientific_name'] = title.get_text(strip=True)

            # Look for parameters in tables or text
            # FishBase uses various layouts, this is a general approach
            params.update(self._extract_from_tables(soup))
            params.update(self._extract_from_text(soup))

            return params

        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout for {profile_url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error for {profile_url}")
            return None
        except Exception as e:
            logger.warning(f"Failed to scrape profile {profile_url}: {e}")
            return None

    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict:
        """Extract parameters from HTML tables"""
        params = {}

        # Parameter mapping: (table cell text patterns, parameter name)
        param_patterns = [
            (r'max\s*length|maximum\s*length|l\s*max', 'lmax'),
            (r'age|tmax|maximum\s*age', 'tmax'),
            (r'linf|l∞|asymptotic', 'linf'),
            (r'growth.*coefficient|von.*bertalanffy.*k', 'k'),
            (r'natural\s*mortality|mortality\s*rate', 'm'),
            (r'maturity|length.*maturity|lmat', 'lmat'),
            (r'trophic.*level', 'trophic_level'),
            (r'fecundity', 'fecundity'),
        ]

        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    # Try to match parameter patterns
                    for pattern, param_name in param_patterns:
                        if re.search(pattern, key):
                            try:
                                # Try to parse numeric value
                                numeric_val = float(re.findall(r'[-+]?[0-9]*\.?[0-9]+', value)[0])
                                params[param_name] = numeric_val
                            except (ValueError, IndexError):
                                params[param_name] = value
                            break

        return params

    def _extract_from_text(self, soup: BeautifulSoup) -> Dict:
        """Extract parameters from main text content"""
        params = {}

        # Get main content
        content = soup.find('div', class_=re.compile(r'content|main|article'))
        if not content:
            content = soup.body

        if content:
            text = content.get_text().lower()

            # Look for specific patterns in text
            patterns = {
                'tmax': r'maximum age.*?(\d+)\s*(?:years?|yr)',
                'lmax': r'maximum length.*?(\d+\.?\d*)\s*(?:cm|mm)',
                'trophic_level': r'trophic level.*?(\d+\.?\d*)',
                'habitat': r'habitat.*?([^.;]+?)(?:\.|;)',
            }

            for param, pattern in patterns.items():
                match = re.search(pattern, text)
                if match:
                    try:
                        value = match.group(1)
                        if param.startswith('trophic') or 'level' in param:
                            params[param] = float(value)
                        else:
                            params[param] = value
                    except (ValueError, IndexError):
                        pass

        return params

    def fetch_all_species(self, delay: float = 1.0) -> List[Dict]:
        """
        Fetch parameters for all GOC species in the list

        Args:
            delay: Delay between requests in seconds

        Returns:
            List of parameter dictionaries
        """
        results = []
        species_list = list(self.GOC_SPECIES.keys())

        for i, species_name in enumerate(species_list, 1):
            logger.info(f"[{i}/{len(species_list)}] Processing: {species_name}")

            # Search for species
            profile_url = self.search_species(species_name)
            if not profile_url:
                results.append({
                    'scientific_name': species_name,
                    'common_name': self.GOC_SPECIES.get(species_name),
                    'found': False,
                    'error': 'Species not found on FishBase'
                })
                time.sleep(delay)
                continue

            # Scrape profile
            params = self.scrape_species_profile(profile_url)
            if params:
                params['found'] = True
                params['common_name'] = self.GOC_SPECIES.get(species_name)
                results.append(params)
            else:
                results.append({
                    'scientific_name': species_name,
                    'common_name': self.GOC_SPECIES.get(species_name),
                    'found': False,
                    'error': 'Failed to extract parameters'
                })

            time.sleep(delay)

        return results

    def save_results(self, results: List[Dict], filepath: str, format: str = 'csv'):
        """Save results to CSV or JSON"""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            if format.lower() == 'json':
                with open(filepath, 'w') as f:
                    json.dump(results, f, indent=2)
            else:
                df = pd.DataFrame(results)
                df.to_csv(filepath, index=False)

            logger.info(f"Results saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving results: {e}")
            raise

    def print_summary(self, results: List[Dict]):
        """Print summary of results"""
        found = [r for r in results if r.get('found', False)]
        not_found = [r for r in results if not r.get('found', False)]

        print("\n" + "="*70)
        print("FISHBASE SCRAPING SUMMARY - GULF OF CALIFORNIA SPECIES")
        print("="*70)
        print(f"Total species processed: {len(results)}")
        print(f"Successfully scraped: {len(found)}")
        print(f"Failed/Not found: {len(not_found)}")

        if found:
            print("\n" + "-"*70)
            print("SPECIES WITH EXTRACTED PARAMETERS:")
            print("-"*70)

            df = pd.DataFrame(found)
            key_cols = ['scientific_name', 'common_name', 'tmax', 'lmax', 'trophic_level']
            display_cols = [col for col in key_cols if col in df.columns]

            print(df[display_cols].fillna('N/A').to_string(index=False))

        if not_found:
            print("\n" + "-"*70)
            print("SPECIES NOT FOUND OR FAILED:")
            print("-"*70)
            for r in not_found:
                print(f"  • {r['scientific_name']}: {r.get('error')}")

        print("\n" + "="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Scrape population parameters from FishBase for GOC species'
    )
    parser.add_argument(
        '--output',
        default='outputs/fishbase_scrapped_parameters.csv',
        help='Output file path'
    )
    parser.add_argument(
        '--format',
        choices=['csv', 'json'],
        default='csv',
        help='Output format'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay between requests (seconds)'
    )

    args = parser.parse_args()

    scraper = FishBaseScraper()
    logger.info(f"Starting FishBase scraping for {len(scraper.GOC_SPECIES)} species")

    results = scraper.fetch_all_species(delay=args.delay)
    scraper.save_results(results, args.output, format=args.format)
    scraper.print_summary(results)


if __name__ == '__main__':
    main()
