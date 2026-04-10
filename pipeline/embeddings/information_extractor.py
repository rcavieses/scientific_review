"""
Extrae información relevante de artículos para embeddings.
"""

import re
from typing import List, Optional, Tuple
from scientific_search import Article
from .models import ExtractedData


class InformationExtractor:
    """
    Extrae campos relevantes de artículos científicos.

    Proporciona métodos para:
    - Extraer campos de objetos Article
    - Validar datos extraídos
    - Limpiar campos individuales
    - Combinar campos según estrategia
    """

    def __init__(self, verbose: bool = False):
        """
        Inicializa el extractor.

        Args:
            verbose: Mostrar mensajes de debug.
        """
        self.verbose = verbose

    def extract_from_article(self, article: Article) -> ExtractedData:
        """
        Extrae información de un artículo.

        Args:
            article: Objeto Article de scientific_search.

        Returns:
            ExtractedData con campos extraídos.

        Raises:
            ValueError: Si no hay título válido.
        """
        # Extraer título (requerido)
        title = self._clean_text(article.title)
        if not title:
            raise ValueError(f"Artículo sin título: {article}")

        # Extraer otros campos (opcionales)
        abstract = self._clean_text(article.abstract) if article.abstract else None

        keywords = None
        if article.keywords:
            keywords = [self._clean_text(k) for k in article.keywords if k]
            keywords = [k for k in keywords if k]  # Filtrar vacíos

        authors = self._clean_author_list(article.authors) if article.authors else None

        journal = self._clean_text(article.journal) if article.journal else None

        doi = self._clean_doi(article.doi) if article.doi else None

        year = article.year if isinstance(article.year, int) else None

        # Crear objeto ExtractedData
        extracted = ExtractedData(
            title=title,
            abstract=abstract,
            keywords=keywords,
            authors=authors,
            journal=journal,
            year=year,
            doi=doi,
            source=article.source
        )

        if self.verbose:
            print(f"✓ Extraído: {title[:50]}...")

        return extracted

    def extract_from_multiple(
        self,
        articles: List[Article],
        skip_errors: bool = True
    ) -> Tuple[List[ExtractedData], List[str]]:
        """
        Extrae información de múltiples artículos.

        Args:
            articles: Lista de artículos.
            skip_errors: Si True, continúa con siguiente en caso de error.

        Returns:
            Tupla (lista de ExtractedData, lista de errores).
        """
        extracted_list = []
        errors = []

        for i, article in enumerate(articles):
            try:
                extracted = self.extract_from_article(article)
                extracted_list.append(extracted)
            except Exception as e:
                error_msg = f"Artículo {i}: {str(e)}"
                if skip_errors:
                    errors.append(error_msg)
                    if self.verbose:
                        print(f"✗ {error_msg}")
                else:
                    raise

        return extracted_list, errors

    def validate_extracted_data(self, data: ExtractedData) -> Tuple[bool, List[str]]:
        """
        Valida que los datos extraídos sean válidos.

        Args:
            data: ExtractedData a validar.

        Returns:
            Tupla (es_válido, lista_de_problemas).
        """
        problems = []

        # Validaciones obligatorias
        if not data.title:
            problems.append("Título vacío")

        # Validaciones recomendadas
        if not data.abstract:
            problems.append("Sin resumen (recomendado para mejor contexto)")

        if data.title and len(data.title) < 5:
            problems.append("Título muy corto")

        if data.abstract and len(data.abstract) < 20:
            problems.append("Resumen muy corto")

        if not data.authors or len(data.authors) == 0:
            problems.append("Sin autores")

        if not data.year:
            problems.append("Sin año de publicación")

        is_valid = len(problems) == 1 and "Sin resumen" in problems[0]
        # Consideramos válido si solo le falta el resumen (que es menos crítico)
        is_valid = len([p for p in problems if "vacío" not in p]) == 0 or \
                   (not data.title.strip() is False)

        # Realmente válido si tiene título
        is_valid = bool(data.title.strip())

        return is_valid, problems

    def get_statistics(self, extracted_list: List[ExtractedData]) -> dict:
        """
        Calcula estadísticas sobre datos extraídos.

        Args:
            extracted_list: Lista de ExtractedData.

        Returns:
            Diccionario con estadísticas.
        """
        stats = {
            "total": len(extracted_list),
            "con_titulo": sum(1 for e in extracted_list if e.title),
            "con_abstract": sum(1 for e in extracted_list if e.abstract),
            "con_keywords": sum(1 for e in extracted_list if e.keywords),
            "con_autores": sum(1 for e in extracted_list if e.authors),
            "con_ano": sum(1 for e in extracted_list if e.year),
            "con_doi": sum(1 for e in extracted_list if e.doi),
            "fuentes": self._count_by_source(extracted_list),
            "anos": self._count_by_year(extracted_list),
            "longitud_promedio_titulo": self._avg_length([e.title for e in extracted_list]),
            "longitud_promedio_abstract": self._avg_length([
                e.abstract for e in extracted_list if e.abstract
            ])
        }

        return stats

    # ==================== MÉTODOS PRIVADOS ====================

    @staticmethod
    def _clean_text(text: str) -> str:
        """Limpia un campo de texto."""
        if not text:
            return ""

        # Remover espacios extra
        text = " ".join(text.split())

        # Remover caracteres de control
        text = "".join(ch for ch in text if ord(ch) >= 32 or ch in '\n\t')

        # Trim
        text = text.strip()

        return text

    @staticmethod
    def _clean_author_list(authors: List[str]) -> List[str]:
        """Limpia lista de autores."""
        if not authors:
            return []

        cleaned = []
        for author in authors:
            clean_author = InformationExtractor._clean_text(author)
            if clean_author and len(clean_author) > 1:
                cleaned.append(clean_author)

        return cleaned

    @staticmethod
    def _clean_doi(doi: str) -> str:
        """Limpia y valida DOI."""
        if not doi:
            return ""

        doi = InformationExtractor._clean_text(doi)

        # DOI debe empezar con 10. o ser solo números después de 10.
        if doi and not doi.startswith("10."):
            doi = f"10.{doi}"

        return doi

    @staticmethod
    def _avg_length(items: List[Optional[str]]) -> float:
        """Calcula longitud promedio de strings."""
        valid_items = [item for item in items if item]
        if not valid_items:
            return 0.0

        return sum(len(item) for item in valid_items) / len(valid_items)

    @staticmethod
    def _count_by_source(extracted_list: List[ExtractedData]) -> dict:
        """Cuenta documentos por fuente."""
        counts = {}
        for item in extracted_list:
            counts[item.source] = counts.get(item.source, 0) + 1
        return counts

    @staticmethod
    def _count_by_year(extracted_list: List[ExtractedData]) -> dict:
        """Cuenta documentos por año."""
        counts = {}
        for item in extracted_list:
            if item.year:
                counts[item.year] = counts.get(item.year, 0) + 1
        return counts
