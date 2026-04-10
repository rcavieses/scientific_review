"""
Modelos de datos para representar artículos científicos.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Article:
    """Representa un artículo científico encontrado."""

    title: str
    """Título del artículo"""

    authors: List[str]
    """Lista de autores"""

    year: Optional[int] = None
    """Año de publicación"""

    doi: Optional[str] = None
    """Digital Object Identifier"""

    url: Optional[str] = None
    """URL del artículo"""

    abstract: Optional[str] = None
    """Resumen del artículo"""

    keywords: Optional[List[str]] = None
    """Palabras clave"""

    journal: Optional[str] = None
    """Nombre de la revista/journal"""

    source: str = "unknown"
    """Fuente de donde se obtuvo (crossref, pubmed, arxiv)"""

    full_data: Optional[Dict[str, Any]] = None
    """Datos completos del artículo para referencias futuras"""

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el artículo a diccionario."""
        authors_str = "; ".join(self.authors) if self.authors else ""
        keywords_str = "; ".join(self.keywords) if self.keywords else ""

        return {
            "title": self.title,
            "authors": authors_str,
            "year": self.year or "",
            "doi": self.doi or "",
            "url": self.url or "",
            "journal": self.journal or "",
            "source": self.source,
            "abstract": self.abstract or "",
            "keywords": keywords_str,
        }

    def __str__(self) -> str:
        """Representación en string del artículo."""
        authors_str = ", ".join(self.authors[:3]) if self.authors else "Unknown"
        if len(self.authors) > 3:
            authors_str += f" +{len(self.authors) - 3}"

        year_str = f" ({self.year})" if self.year else ""
        return f"{self.title}\n  {authors_str}{year_str}\n  [{self.source}]"


@dataclass
class SearchResult:
    """Resultado de una búsqueda."""

    query: str
    """Término de búsqueda utilizado"""

    articles: List[Article]
    """Lista de artículos encontrados"""

    total_results: int
    """Número total de resultados"""

    search_date: datetime
    """Fecha y hora de la búsqueda"""

    sources_queried: List[str]
    """Fuentes donde se realizó la búsqueda"""

    errors: Optional[Dict[str, str]] = None
    """Errores ocurridos durante la búsqueda"""

    def summary(self) -> str:
        """Genera un resumen de los resultados."""
        return (
            f"Búsqueda: '{self.query}'\n"
            f"Artículos encontrados: {len(self.articles)}\n"
            f"Total en bases de datos: {self.total_results}\n"
            f"Fuentes: {', '.join(self.sources_queried)}\n"
            f"Fecha: {self.search_date.strftime('%Y-%m-%d %H:%M:%S')}"
        )
