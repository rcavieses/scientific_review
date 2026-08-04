"""
Clase principal para búsqueda de artículos científicos.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Callable

from .models import Article, SearchResult
from .adapters import AVAILABLE_ADAPTERS, BaseAdapter
from .registry import SearchRegistry
from .downloader import ArticleDownloader


class ScientificArticleSearcher:
    """
    Búsqueda integrada de artículos científicos en múltiples fuentes.

    Permite buscar en Crossref, PubMed y arXiv simultáneamente,
    guardar resultados en CSV y descargar archivos.
    """

    # Palabras genéricas que no identifican el dominio temático
    _GENERIC_WORDS = {
        "a", "an", "the", "in", "of", "on", "at", "to", "for", "by",
        "and", "or", "but", "with", "from", "into", "over", "under",
        "is", "are", "was", "were", "be", "been", "using", "based",
        "study", "review", "analysis", "model", "modeling", "modelling",
        "method", "approach", "system", "data", "result", "results",
        "performance", "evaluation", "assessment", "detection",
        "classification", "estimation", "prediction", "predicting",
        "forecast", "forecasting", "machine", "learning", "deep",
        "neural", "network", "algorithm", "framework", "technique",
        "novel", "new", "improved", "efficient", "robust", "accurate",
        "high", "low", "large", "small", "multiple", "various",
        "applied", "application", "applications", "toward", "towards",
    }

    def __init__(
        self,
        sources: Optional[List[str]] = None,
        output_directory: Optional[Path] = None,
        download_directory: Optional[Path] = None,
        local_pdf_directory: Optional[Path] = None,
        verbose: bool = False,
        adapter_config: Optional[Dict[str, Dict]] = None,
    ):
        """
        Inicializa el buscador de artículos.

        Args:
            sources: Fuentes a usar (por defecto todas: crossref, pubmed, arxiv, scopus).
                    Incluye "local_pdf" para buscar en carpeta local de PDFs.
            output_directory: Directorio para guardar resultados.
            download_directory: Directorio para descargas.
            local_pdf_directory: Directorio con PDFs locales (para fuente "local_pdf").
                                Si es None, usa outputs/pdfs/
            verbose: Mostrar mensajes detallados.
            adapter_config: Kwargs extra por adaptador, ej. {"scopus": {"apikey": "..."}}.
        """
        self.sources = sources or list(AVAILABLE_ADAPTERS.keys())
        self.output_directory = Path(output_directory or Path.cwd())
        self.download_directory = download_directory
        self.local_pdf_directory = local_pdf_directory
        self.verbose = verbose

        # Inicializar componentes
        self.registry = SearchRegistry(self.output_directory)
        self.downloader = ArticleDownloader(self.download_directory)
        self.adapters: Dict[str, BaseAdapter] = {}

        # Crear adaptadores (con kwargs específicos si se proporcionan)
        adapter_config = adapter_config or {}
        for source in self.sources:
            if source in AVAILABLE_ADAPTERS:
                kwargs = adapter_config.get(source, {})
                # Pasar local_pdf_directory a LocalPdfAdapter
                if source == "local_pdf" and local_pdf_directory:
                    kwargs["pdf_directory"] = local_pdf_directory
                self.adapters[source] = AVAILABLE_ADAPTERS[source](**kwargs)

        # Configurar logging
        self.logger = self._setup_logger()

    @staticmethod
    def _get_key_terms(query: str) -> List[str]:
        """Extrae términos de dominio de la query (elimina palabras genéricas)."""
        words = [w.lower().strip(".,;:()[]") for w in query.split()]
        key = [w for w in words if w not in ScientificArticleSearcher._GENERIC_WORDS and len(w) > 3]
        return key if key else words  # fallback si todo es genérico

    @staticmethod
    def _term_matches(query_term: str, text: str) -> bool:
        """
        Verifica si un término de la query aparece en el texto.

        Usa coincidencia por prefijo común de 5 caracteres para tolerar
        variaciones ortográficas e idiomáticas (plancton / plankton,
        fisheries / fishery, etc.).
        """
        # Coincidencia exacta de subcadena
        if query_term in text:
            return True
        # Coincidencia por prefijo: 4 chars comunes cubren variantes
        # entre idiomas: plancton/plankton → "plan", fisheries/fishery → "fish"
        prefix_len = min(4, len(query_term) - 1)
        if prefix_len < 4:
            return False
        prefix = query_term[:prefix_len]
        # Buscar el prefijo al inicio de cualquier palabra en el texto
        words_in_text = text.split()
        return any(w.startswith(prefix) for w in words_in_text)

    @staticmethod
    def _relevance_score(article, key_terms: List[str]) -> float:
        """Fracción de términos clave encontrados en título, abstract o keywords."""
        if not key_terms:
            return 1.0

        # Construir texto completo disponible del artículo
        parts = [article.title or ""]
        if article.abstract:
            parts.append(article.abstract)
        if article.keywords:
            parts.extend(article.keywords)
        full_text = " ".join(parts).lower()

        matches = sum(
            1 for term in key_terms
            if ScientificArticleSearcher._term_matches(term, full_text)
        )
        return matches / len(key_terms)

    def search(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        specific_sources: Optional[List[str]] = None,
        min_relevance: float = 0.3,
    ) -> SearchResult:
        """
        Realiza búsqueda en múltiples fuentes.

        Args:
            query: Término de búsqueda.
            max_results: Resultados máximos por fuente.
            year_start: Año inicial (opcional).
            year_end: Año final (opcional).
            specific_sources: Fuentes específicas a usar
                             (por defecto usa todas las configuradas).
            min_relevance: Fracción mínima de términos de dominio que deben
                           aparecer en el título (0.0 = sin filtro, 1.0 = todos).

        Returns:
            Objeto SearchResult con resultados y metadatos.
        """
        self.logger.info(f"Iniciando búsqueda: '{query}'")

        sources_to_query = (
            specific_sources or self.sources
        )

        # Validar fuentes
        sources_to_query = [
            s for s in sources_to_query
            if s in self.adapters
        ]

        all_articles = []
        errors = {}
        total_results = 0

        # Buscar en cada fuente
        for source in sources_to_query:
            try:
                self.logger.info(f"Buscando en {source}...")

                adapter = self.adapters[source]
                articles = adapter.search(
                    query,
                    max_results=max_results,
                    year_start=year_start,
                    year_end=year_end,
                )

                all_articles.extend(articles)
                total_results += len(articles)

                self.logger.info(
                    f"  → {len(articles)} artículos encontrados en {source}"
                )

            except Exception as e:
                error_msg = f"Error en {source}: {str(e)}"
                self.logger.error(error_msg)
                errors[source] = str(e)

        # Remover duplicados (por título)
        unique_articles = self._deduplicate_articles(all_articles)

        # Filtrar por relevancia temática
        if min_relevance > 0:
            key_terms = ScientificArticleSearcher._get_key_terms(query)
            self.logger.info(f"Términos de dominio: {key_terms}")
            before = len(unique_articles)
            unique_articles = [
                a for a in unique_articles
                if ScientificArticleSearcher._relevance_score(a, key_terms) >= min_relevance
            ]
            filtered = before - len(unique_articles)
            if filtered:
                self.logger.info(f"  → {filtered} artículos descartados por baja relevancia")

        self.logger.info(
            f"Búsqueda completada: {len(unique_articles)} "
            f"artículos únicos encontrados"
        )

        # Crear resultado
        result = SearchResult(
            query=query,
            articles=unique_articles,
            total_results=total_results,
            search_date=datetime.now(),
            sources_queried=sources_to_query,
            errors=errors if errors else None,
        )

        return result

    def search_and_save(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        output_filename: Optional[str] = None,
        min_relevance: float = 0.3,
    ) -> Dict[str, Path]:
        """
        Realiza búsqueda y guarda resultados automáticamente.

        Args:
            query: Término de búsqueda.
            max_results: Resultados máximos por fuente.
            year_start: Año inicial (opcional).
            year_end: Año final (opcional).
            output_filename: Nombre personalizado para CSV.

        Returns:
            Diccionario con rutas de archivos guardados.
        """
        # Realizar búsqueda
        result = self.search(
            query,
            max_results=max_results,
            year_start=year_start,
            year_end=year_end,
            min_relevance=min_relevance,
        )

        # Guardar resultados
        saved_files = self.registry.save_search_result(
            result,
            csv_filename=output_filename,
        )

        self.logger.info(f"Resultados guardados en: {saved_files['csv']}")

        return saved_files

    def search_and_download(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        download_limit: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict:
        """
        Realiza búsqueda, guarda resultados y descarga archivos.

        Args:
            query: Término de búsqueda.
            max_results: Resultados máximos por fuente.
            year_start: Año inicial (opcional).
            year_end: Año final (opcional).
            download_limit: Límite de descargas (None = todas).
            progress_callback: Función para reportar progreso.

        Returns:
            Diccionario con información de búsqueda y descargas.
        """
        # Realizar búsqueda y guardar
        saved_files = self.search_and_save(
            query,
            max_results=max_results,
            year_start=year_start,
            year_end=year_end,
        )

        # Obtener artículos a descargar
        result = self.registry.load_from_csv(saved_files["csv"].name)
        articles_to_download = (
            result[:download_limit]
            if download_limit
            else result
        )

        # Descargar
        if progress_callback:
            progress_callback(
                f"\nDescargando {len(articles_to_download)} artículos..."
            )

        downloaded_files = self.downloader.download_articles(
            articles_to_download,
            progress_callback=progress_callback,
        )

        # Estadísticas
        stats = self.downloader.get_download_stats()

        return {
            "query": query,
            "csv_file": str(saved_files["csv"]),
            "summary_file": str(saved_files["summary"]),
            "log_file": str(saved_files["log"]),
            "download_directory": str(self.downloader.get_temp_directory()),
            "downloaded_count": len(downloaded_files),
            "download_stats": stats,
        }

    def save_results(
        self,
        articles: List[Article],
        filename: str,
        query: Optional[str] = None,
    ) -> Path:
        """
        Guarda una lista de artículos en CSV.

        Args:
            articles: Artículos a guardar.
            filename: Nombre del archivo CSV.
            query: Término de búsqueda (para metadatos).

        Returns:
            Ruta del archivo guardado.
        """
        return self.registry.save_to_csv(
            articles,
            filename,
            search_query=query,
        )

    def load_results(self, csv_filename: str) -> List[Article]:
        """
        Carga resultados guardados de un CSV.

        Args:
            csv_filename: Nombre del archivo CSV a cargar.

        Returns:
            Lista de artículos cargados.
        """
        return self.registry.load_from_csv(csv_filename)

    def get_search_history(self) -> List[Dict]:
        """
        Obtiene el historial de búsquedas previas.

        Returns:
            Lista de búsquedas anteriores.
        """
        return self.registry.get_search_history()

    def get_output_directory(self) -> Path:
        """Obtiene el directorio de salida."""
        return self.output_directory

    def get_download_directory(self) -> Path:
        """Obtiene el directorio de descargas."""
        return self.downloader.get_temp_directory()

    def clear_downloads(self) -> int:
        """
        Limpia el directorio de descargas.

        Returns:
            Número de archivos eliminados.
        """
        count = self.downloader.clear_temp_directory()
        self.logger.info(f"Se eliminaron {count} archivos descargados")
        return count

    @staticmethod
    def _deduplicate_articles(articles: List[Article]) -> List[Article]:
        """
        Remove duplicate articles based on title.

        Args:
            articles: Lista de artículos.

        Returns:
            Lista sin duplicados.
        """
        seen_titles = set()
        unique = []

        for article in articles:
            # Normalizar título: minúsculas, espacios, y espacios múltiples
            title_normalized = " ".join(article.title.lower().split())
            if title_normalized not in seen_titles:
                seen_titles.add(title_normalized)
                unique.append(article)

        return unique

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger."""
        logger = logging.getLogger("scientific_search")

        if not logger.handlers:
            level = logging.DEBUG if self.verbose else logging.INFO
            logger.setLevel(level)

            handler = logging.StreamHandler()
            handler.setLevel(level)

            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)

            logger.addHandler(handler)

        return logger
