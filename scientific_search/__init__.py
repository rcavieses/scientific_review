"""
scientific_search: Librería para búsqueda de artículos científicos.

Esta librería permite buscar artículos en múltiples fuentes científicas,
descargar archivos y registrar resultados en CSV.

Uso básico:
    >>> from scientific_search import ScientificArticleSearcher
    >>> searcher = ScientificArticleSearcher()
    >>> results = searcher.search("machine learning", max_results=10)
    >>> searcher.save_to_csv(results, "results.csv")
"""

from .searcher import ScientificArticleSearcher
from .models import Article, SearchResult

__version__ = "1.0.0"
__author__ = "Scientific Search Library"

__all__ = [
    "ScientificArticleSearcher",
    "Article",
    "SearchResult",
]
