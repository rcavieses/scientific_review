"""
Adaptadores para diferentes APIs de búsqueda de artículos científicos.
"""

import requests
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import Article
import xml.etree.ElementTree as ET

# Rutas donde buscar la API key de Elsevier (Scopus / ScienceDirect)
_ELSEVIER_APIKEY_PATHS = [
    Path(__file__).parent.parent / "secrets" / "scopus_apikey.txt",
    Path(__file__).parent.parent / "secrets" / "sciencedirect_apikey.txt",
]


class BaseAdapter(ABC):
    """Clase base para adaptadores de APIs científicas."""

    def __init__(self, timeout: int = 10, retry_delay: float = 1.0):
        """
        Inicializa el adaptador.

        Args:
            timeout: Tiempo máximo de espera para requests (segundos).
            retry_delay: Retraso entre reintentos (segundos).
        """
        self.timeout = timeout
        self.retry_delay = retry_delay

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> List[Article]:
        """
        Realiza una búsqueda en la API.

        Args:
            query: Término de búsqueda.
            max_results: Número máximo de resultados.
            year_start: Año inicial (opcional).
            year_end: Año final (opcional).

        Returns:
            Lista de artículos encontrados.
        """
        pass

    def _parse_author_list(self, author_data: Any) -> List[str]:
        """Parsea lista de autores de diferentes formatos."""
        if isinstance(author_data, list):
            authors = []
            for author in author_data:
                if isinstance(author, dict):
                    if "family" in author and "given" in author:
                        authors.append(f"{author['given']} {author['family']}")
                    elif "name" in author:
                        authors.append(author["name"])
                elif isinstance(author, str):
                    authors.append(author)
            return authors
        return []


class CrossrefAdapter(BaseAdapter):
    """Adaptador para la API de Crossref."""

    BASE_URL = "https://api.crossref.org/v1/works"

    def search(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> List[Article]:
        """Busca artículos en Crossref."""
        articles = []

        try:
            params = {
                "query": query,
                "rows": min(max_results, 100),
                "sort": "relevance",
                "order": "desc",
            }

            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "scientific-search/1.0"},
            )
            response.raise_for_status()

            data = response.json()

            for item in data.get("message", {}).get("items", []):
                article = self._parse_crossref_item(item, year_start, year_end)
                if article:
                    articles.append(article)

        except Exception as e:
            print(f"Error en Crossref: {str(e)}")

        return articles[:max_results]

    def _parse_crossref_item(
        self,
        item: Dict[str, Any],
        year_start: Optional[int],
        year_end: Optional[int],
    ) -> Optional[Article]:
        """Parsea un item de Crossref."""
        # Obtener año de publicación
        year = None
        if "published-online" in item:
            year = item["published-online"].get("date-parts", [[None]])[0][0]
        elif "published" in item:
            year = item["published"].get("date-parts", [[None]])[0][0]

        # Filtrar por rango de años
        if year:
            if year_start and year < year_start:
                return None
            if year_end and year > year_end:
                return None

        # Obtener autores
        authors = self._parse_author_list(item.get("author", []))

        # Obtener título
        title = ""
        if "title" in item:
            titles = item["title"]
            title = titles[0] if isinstance(titles, list) else titles

        if not title:
            return None

        # Obtener DOI
        doi = item.get("DOI", "")

        # Obtener URL
        url = item.get("URL", "")

        # Obtener journal
        journal = item.get("container-title", "")
        if isinstance(journal, list):
            journal = journal[0] if journal else ""

        return Article(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            url=url,
            journal=journal,
            source="crossref",
            full_data=item,
        )


class PubMedAdapter(BaseAdapter):
    """Adaptador para la API de PubMed."""

    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def search(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> List[Article]:
        """Busca artículos en PubMed."""
        articles = []

        try:
            # Construir query con rango de años
            search_query = query
            if year_start and year_end:
                search_query = (
                    f"({query}) AND ({year_start}[PDAT]:{year_end}[PDAT])"
                )
            elif year_start:
                search_query = f"({query}) AND ({year_start}[PDAT]:3000[PDAT])"

            # Fase 1: Buscar IDs
            search_params = {
                "db": "pubmed",
                "term": search_query,
                "retmax": min(max_results, 100),
                "retmode": "json",
            }

            search_response = requests.get(
                self.SEARCH_URL,
                params=search_params,
                timeout=self.timeout,
            )
            search_response.raise_for_status()

            search_data = search_response.json()
            pmids = search_data.get("esearchresult", {}).get("idlist", [])

            if not pmids:
                return articles

            # Esperar un poco antes de la próxima request
            time.sleep(self.retry_delay)

            # Fase 2: Obtener detalles
            pmids_str = ",".join(pmids[:max_results])
            fetch_params = {
                "db": "pubmed",
                "id": pmids_str,
                "rettype": "xml",
            }

            fetch_response = requests.get(
                self.FETCH_URL,
                params=fetch_params,
                timeout=self.timeout,
            )
            fetch_response.raise_for_status()

            articles = self._parse_pubmed_xml(fetch_response.text)

        except Exception as e:
            print(f"Error en PubMed: {str(e)}")

        return articles[:max_results]

    def _parse_pubmed_xml(self, xml_string: str) -> List[Article]:
        """Parsea XML de PubMed."""
        articles = []

        try:
            root = ET.fromstring(xml_string)

            for article_elem in root.findall(".//Article"):
                # Título
                title_elem = article_elem.find(".//ArticleTitle")
                title = title_elem.text if title_elem is not None else ""

                if not title:
                    continue

                # Autores
                authors = []
                for author_elem in article_elem.findall(".//Author"):
                    lastname = author_elem.find("LastName")
                    forename = author_elem.find("ForeName")
                    if lastname is not None:
                        author_name = lastname.text or ""
                        if forename is not None and forename.text:
                            author_name = f"{forename.text} {author_name}"
                        if author_name:
                            authors.append(author_name)

                # Año
                year = None
                pub_date = article_elem.find(".//PubDate")
                if pub_date is not None:
                    year_elem = pub_date.find("Year")
                    if year_elem is not None and year_elem.text:
                        year = int(year_elem.text)

                # PMID como identificador
                pmid = ""
                pmid_elem = article_elem.find(".//PMID")
                if pmid_elem is not None:
                    pmid = pmid_elem.text or ""

                # URL basada en PMID
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

                # Journal
                journal_elem = article_elem.find(".//Journal/Title")
                journal = journal_elem.text if journal_elem is not None else ""

                # Abstract
                abstract_parts = [
                    elem.text for elem in article_elem.findall(".//AbstractText")
                    if elem.text
                ]
                abstract = " ".join(abstract_parts) if abstract_parts else None

                # Keywords (MeSH headings)
                keywords = [
                    kw.text for kw in article_elem.findall(".//DescriptorName")
                    if kw.text
                ]

                article = Article(
                    title=title,
                    authors=authors,
                    year=year,
                    doi="",
                    url=url,
                    abstract=abstract,
                    keywords=keywords if keywords else None,
                    journal=journal,
                    source="pubmed",
                    full_data={"pmid": pmid},
                )
                articles.append(article)

        except Exception as e:
            print(f"Error parseando XML de PubMed: {str(e)}")

        return articles


class ArxivAdapter(BaseAdapter):
    """Adaptador para la API de arXiv."""

    BASE_URL = "http://export.arxiv.org/api/query"

    def search(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> List[Article]:
        """Busca artículos en arXiv."""
        articles = []

        try:
            # Construir query de arXiv (términos separados, sin comillas estrictas)
            arxiv_query = "all:" + "+".join(query.split())

            params = {
                "search_query": arxiv_query,
                "start": 0,
                "max_results": min(max_results, 100),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }

            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)
            namespace = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", namespace):
                article = self._parse_arxiv_entry(
                    entry,
                    namespace,
                    year_start,
                    year_end,
                )
                if article:
                    articles.append(article)

        except Exception as e:
            print(f"Error en arXiv: {str(e)}")

        return articles[:max_results]

    def _parse_arxiv_entry(
        self,
        entry: ET.Element,
        namespace: Dict[str, str],
        year_start: Optional[int],
        year_end: Optional[int],
    ) -> Optional[Article]:
        """Parsea un entry de arXiv."""
        # Título
        title_elem = entry.find("atom:title", namespace)
        title = (
            title_elem.text.strip() if title_elem is not None else ""
        )

        if not title:
            return None

        # Autores
        authors = []
        for author_elem in entry.findall("atom:author", namespace):
            name_elem = author_elem.find("atom:name", namespace)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text)

        # Año (de la fecha publicada)
        year = None
        published_elem = entry.find("atom:published", namespace)
        if published_elem is not None and published_elem.text:
            try:
                year = int(published_elem.text[:4])
                if year_start and year < year_start:
                    return None
                if year_end and year > year_end:
                    return None
            except (ValueError, IndexError):
                pass

        # URL (arxiv link)
        url = ""
        for link_elem in entry.findall("atom:link", namespace):
            if link_elem.get("title") == "pdf":
                url = link_elem.get("href", "")
                break
        if not url:
            for link_elem in entry.findall("atom:link", namespace):
                url = link_elem.get("href", "")
                if "arxiv.org" in url:
                    break

        # Resumen
        summary_elem = entry.find("atom:summary", namespace)
        abstract = (
            summary_elem.text.strip() if summary_elem is not None else ""
        )

        return Article(
            title=title,
            authors=authors,
            year=year,
            doi="",
            url=url,
            abstract=abstract,
            source="arxiv",
            full_data=None,
        )


class ScopusAdapter(BaseAdapter):
    """Adaptador para la API de Scopus (Elsevier)."""

    BASE_URL = "https://api.elsevier.com/content/search/scopus"

    def __init__(self, apikey: Optional[str] = None, timeout: int = 10, retry_delay: float = 1.0):
        """
        Inicializa el adaptador de Scopus.

        Args:
            apikey: API key de Elsevier. Si no se provee, busca en secrets/.
            timeout: Tiempo máximo de espera para requests (segundos).
            retry_delay: Retraso entre reintentos (segundos).
        """
        super().__init__(timeout=timeout, retry_delay=retry_delay)
        self.apikey = apikey or self._load_apikey()

    def _load_apikey(self) -> Optional[str]:
        """Carga la API key desde los archivos de secretos."""
        for path in _ELSEVIER_APIKEY_PATHS:
            if path.exists():
                key = path.read_text(encoding="utf-8").strip()
                if key:
                    return key
        return None

    def search(
        self,
        query: str,
        max_results: int = 10,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> List[Article]:
        """Busca artículos en Scopus."""
        if not self.apikey:
            print(
                "Scopus: API key no encontrada. "
                "Crea el archivo 'secrets/scopus_apikey.txt' o usa --apikey."
            )
            return []

        try:
            scopus_query = f"TITLE-ABS-KEY({query})"
            if year_start and year_end:
                scopus_query += f" AND PUBYEAR > {year_start - 1} AND PUBYEAR < {year_end + 1}"
            elif year_start:
                scopus_query += f" AND PUBYEAR > {year_start - 1}"
            elif year_end:
                scopus_query += f" AND PUBYEAR < {year_end + 1}"

            headers = {
                "X-ELS-APIKey": self.apikey,
                "Accept": "application/json",
            }
            params = {
                "query": scopus_query,
                "count": min(max_results, 25),
                "start": 0,
                "sort": "relevancy",
                "field": (
                    "dc:title,prism:publicationName,prism:coverDate,prism:doi,"
                    "prism:url,dc:creator,author,authkeywords,citedby-count,dc:description"
                ),
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params, timeout=self.timeout)

            if response.status_code == 401:
                print("Scopus: API key inválida o sin permisos. Verifica en https://dev.elsevier.com")
                return []

            response.raise_for_status()

            data = response.json().get("search-results", {})
            entries = data.get("entry", [])
            articles = []

            for entry in entries:
                article = self._parse_entry(entry)
                if article:
                    articles.append(article)

            return articles[:max_results]

        except Exception as e:
            print(f"Error en Scopus: {str(e)}")
            return []

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[Article]:
        """Parsea un resultado de Scopus."""
        title = entry.get("dc:title", "").strip()
        if not title or title.lower() == "no results found":
            return None

        # Año
        year = None
        cover = entry.get("prism:coverDate", "")
        if cover:
            try:
                year = int(cover[:4])
            except ValueError:
                pass

        # Autores
        authors = []
        raw_authors = entry.get("author", [])
        if isinstance(raw_authors, list):
            for a in raw_authors:
                name = a.get("authname", "").strip()
                if name:
                    authors.append(name)
        if not authors:
            creator = entry.get("dc:creator", "")
            if creator:
                authors.append(creator)

        doi = entry.get("prism:doi", "")
        url = entry.get("prism:url", "") or (f"https://doi.org/{doi}" if doi else "")

        raw_keywords = entry.get("authkeywords", "")
        keywords = (
            [k.strip() for k in raw_keywords.replace("|", ",").split(",") if k.strip()]
            if raw_keywords else []
        )

        citations = 0
        try:
            citations = int(entry.get("citedby-count", 0))
        except (ValueError, TypeError):
            pass

        return Article(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            url=url,
            abstract=entry.get("dc:description") or None,
            keywords=keywords or None,
            journal=entry.get("prism:publicationName", ""),
            source="scopus",
            full_data={"citations": citations, "eid": entry.get("eid", "")},
        )


# Registro de adaptadores disponibles
AVAILABLE_ADAPTERS = {
    "crossref": CrossrefAdapter,
    "pubmed": PubMedAdapter,
    "arxiv": ArxivAdapter,
    "scopus": ScopusAdapter,
}
