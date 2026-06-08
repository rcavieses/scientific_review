#!/usr/bin/env python3
"""Test de los nuevos adapters (bioRxiv y PLOS)."""

import logging

from scientific_search import ScientificArticleSearcher

logging.basicConfig(level=logging.WARNING)

# Test species
test_species = ["Dosidicus gigas", "Prionace glauca"]

print("=" * 70)
print("TEST DE ADAPTERS: BIORXIV Y PLOS")
print("=" * 70)

searcher = ScientificArticleSearcher(verbose=False)

for species in test_species:
    print(f"\n🔍 {species}")

    for source in ["biorxiv", "plos"]:
        try:
            result = searcher.search(
                query=species,
                max_results=5,
                specific_sources=[source],
                min_relevance=0.0,
            )

            articles = result.articles if hasattr(result, 'articles') else result
            count = len(articles) if isinstance(articles, list) else 0

            print(f"   {source.upper():10} ✓ {count} resultados")

            if count > 0 and isinstance(articles, list):
                print(f"      → {articles[0].title[:50]}...")

        except Exception as e:
            print(f"   {source.upper():10} ✗ Error: {str(e)[:40]}")

print("\n" + "=" * 70)
print("Test completado")
print("=" * 70)
