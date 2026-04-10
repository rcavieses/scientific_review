"""
Búsqueda en Scopus (https://www.scopus.com) — API de Elsevier.

Scopus es la base de datos de citas y abstracts más grande del mundo,
indexando más de 25,000 revistas de todos los editores. A diferencia
de ScienceDirect (solo Elsevier), Scopus cubre Springer, Wiley, Taylor &
Francis, Nature, Science, y muchos más. Incluye conteo de citas.

Requiere una API key de Elsevier Developer Portal (https://dev.elsevier.com).
La misma clave sirve para ScienceDirect y Scopus.

Uso:
    python scripts/buscar_scopus.py "tu consulta"
    python scripts/buscar_scopus.py plankton --lugar "Gulf of California"
    python scripts/buscar_scopus.py "zooplankton" --year-start 2018 --year-end 2023
    python scripts/buscar_scopus.py "marine ecology" --campo titulo
    python scripts/buscar_scopus.py "sardine" --sort citas  # ordenar por citas
    python scripts/buscar_scopus.py "plankton" --min-relevance 0  # sin filtro

Parámetros exclusivos de Scopus:
    --campo      Campo Scopus: todo (default), titulo, abstract, palabras_clave,
                 autor, journal
    --lugar      Frase geográfica exacta a añadir al query
    --sort       Ordenar por: relevance (default), date, citas
    --apikey     API key de Elsevier (alternativa al archivo de credenciales)
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scientific_search.models import Article, SearchResult
from scientific_search.registry import SearchRegistry
from scientific_search.searcher import ScientificArticleSearcher

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
APIKEY_PATHS = [
    Path(__file__).parent.parent / "secrets" / "scopus_apikey.txt",
    Path(__file__).parent.parent / "secrets" / "sciencedirect_apikey.txt",
]

BASE_URL = "https://api.elsevier.com/content/search/scopus"

# Campos de búsqueda Scopus y sus tags de query
CAMPOS_SCOPUS = {
    "todo": "TITLE-ABS-KEY",
    "titulo": "TITLE",
    "abstract": "ABS",
    "palabras_clave": "KEY",
    "autor": "AUTH",
    "journal": "SRCTITLE",
}

SORT_MAP = {
    "relevance": "relevancy",
    "date": "-pub-date",
    "citas": "-citedby-count",
}


def load_apikey(explicit_key: str = None) -> str:
    if explicit_key:
        return explicit_key.strip()
    for path in APIKEY_PATHS:
        if path.exists():
            key = path.read_text(encoding="utf-8").strip()
            if key:
                return key
    raise FileNotFoundError(
        "No se encontró la API key de Elsevier.\n"
        "Crea el archivo 'secrets/scopus_apikey.txt' o usa --apikey."
    )


def build_scopus_query(query: str, campo: str, lugar: str = None,
                        year_start: int = None, year_end: int = None) -> str:
    """Construye el query Scopus con sintaxis de campo y filtros de año."""
    campo_tag = CAMPOS_SCOPUS.get(campo, "TITLE-ABS-KEY")
    q = f'{campo_tag}({query})'

    if lugar:
        q = f'{q} AND TITLE-ABS-KEY({lugar})'

    if year_start and year_end:
        q = f'{q} AND PUBYEAR > {year_start - 1} AND PUBYEAR < {year_end + 1}'
    elif year_start:
        q = f'{q} AND PUBYEAR > {year_start - 1}'
    elif year_end:
        q = f'{q} AND PUBYEAR < {year_end + 1}'

    return q


def fetch_scopus(scopus_query: str, apikey: str, max_results: int,
                 sort: str = "relevancy") -> tuple:
    """Llama a la API de Scopus y devuelve artículos + total."""
    headers = {
        "X-ELS-APIKey": apikey,
        "Accept": "application/json",
    }

    params = {
        "query": scopus_query,
        "count": min(max_results, 25),
        "start": 0,
        "sort": sort,
        "field": (
            "dc:title,prism:publicationName,prism:coverDate,prism:doi,"
            "prism:url,dc:creator,author,authkeywords,citedby-count,dc:description"
        ),
    }

    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=20)

    if resp.status_code == 401:
        raise PermissionError(
            "API key inválida o sin permisos para Scopus.\n"
            "Verifica tu clave en https://dev.elsevier.com"
        )
    resp.raise_for_status()

    data = resp.json().get("search-results", {})
    total = int(data.get("opensearch:totalResults", 0))
    entries = data.get("entry", [])

    articles = []
    for entry in entries:
        title = entry.get("dc:title", "").strip()
        if not title or title.lower() == "no results found":
            continue

        # Año desde coverDate
        year = None
        cover = entry.get("prism:coverDate", "")
        if cover:
            try:
                year = int(cover[:4])
            except ValueError:
                pass

        # Autores: author es lista o dc:creator es el primero
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
        url = entry.get("prism:url", "")
        if doi and not url:
            url = f"https://doi.org/{doi}"

        abstract = entry.get("dc:description", None)

        raw_keywords = entry.get("authkeywords", "")
        keywords = [k.strip() for k in raw_keywords.replace("|", ",").split(",") if k.strip()] if raw_keywords else []

        # Citas
        citations = entry.get("citedby-count", "0")
        try:
            citations = int(citations)
        except (ValueError, TypeError):
            citations = 0

        articles.append(Article(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            url=url,
            abstract=abstract,
            keywords=keywords,
            journal=entry.get("prism:publicationName", ""),
            source="scopus",
            full_data={"citations": citations, "eid": entry.get("eid", "")},
        ))

    return articles, total


def main():
    parser = argparse.ArgumentParser(
        description="Búsqueda en Scopus (Elsevier)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", nargs="*", help="Consulta de búsqueda")
    parser.add_argument("--max-results", type=int, default=20,
                        help="Número máximo de resultados (default: 20, max: 200)")
    parser.add_argument("--year-start", type=int, default=None,
                        help="Año de publicación mínimo")
    parser.add_argument("--year-end", type=int, default=None,
                        help="Año de publicación máximo")
    parser.add_argument("--min-relevance", type=float, default=0.3,
                        help="Umbral de relevancia 0.0-1.0 (default: 0.3, 0=sin filtro)")
    parser.add_argument("--campo", default="todo",
                        choices=list(CAMPOS_SCOPUS.keys()),
                        help="Campo de búsqueda (default: todo = TITLE-ABS-KEY)")
    parser.add_argument("--lugar", default=None,
                        help="Ubicación geográfica exacta (ej: 'Gulf of California')")
    parser.add_argument("--sort", default="relevance",
                        choices=list(SORT_MAP.keys()),
                        help="Ordenar por: relevance, date, citas (default: relevance)")
    parser.add_argument("--apikey", default=None,
                        help="API key de Elsevier (alternativa al archivo de credenciales)")
    parser.add_argument("--output", default=None,
                        help="Nombre base del archivo de salida (sin extensión)")

    args = parser.parse_args()
    query = " ".join(args.query) if args.query else None

    if not query:
        parser.print_help()
        sys.exit(1)

    try:
        apikey = load_apikey(args.apikey)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    scopus_query = build_scopus_query(
        query, args.campo, args.lugar, args.year_start, args.year_end
    )

    print(f"\n{'='*60}")
    print(f"  SCOPUS SEARCH (Elsevier)")
    print(f"{'='*60}")
    print(f"  Consulta    : {query}")
    print(f"  Query Scopus: {scopus_query}")
    print(f"  Max results : {args.max_results}")
    print(f"  Campo       : {args.campo}")
    if args.lugar:
        print(f"  Lugar       : {args.lugar}")
    print(f"  Años        : {args.year_start or 'sin límite'} → {args.year_end or 'presente'}")
    print(f"  Orden       : {args.sort}")
    print(f"  Relevancia  : {args.min_relevance}")
    print(f"{'='*60}\n")

    print("Consultando Scopus...")
    try:
        articles, total_available = fetch_scopus(
            scopus_query, apikey,
            max_results=args.max_results * 2,
            sort=SORT_MAP[args.sort],
        )
    except PermissionError as e:
        print(f"Error de autenticación: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error al consultar Scopus: {e}")
        sys.exit(1)

    print(f"Total disponible en Scopus: {total_available}")
    print(f"Recuperados para filtrar  : {len(articles)}")

    if args.min_relevance > 0:
        key_terms = ScientificArticleSearcher._get_key_terms(query)
        print(f"Términos de dominio: {key_terms}")
        before = len(articles)
        articles = [
            a for a in articles
            if ScientificArticleSearcher._relevance_score(a, key_terms) >= args.min_relevance
        ]
        print(f"Filtro de relevancia: {before} → {len(articles)} artículos\n")

    articles = articles[:args.max_results]

    print(f"{'─'*60}")
    print(f"  {len(articles)} resultados finales")
    print(f"{'─'*60}")
    for i, a in enumerate(articles, 1):
        citations = (a.full_data or {}).get("citations", 0)
        abstract_preview = (a.abstract[:100] + "...") if a.abstract else "Sin abstract"
        keywords_preview = ", ".join(a.keywords[:4]) if a.keywords else "N/A"
        print(f"\n{i:3}. {a.title}")
        print(f"     Autores : {', '.join(a.authors[:3]) + (' et al.' if len(a.authors) > 3 else '') if a.authors else 'N/A'}")
        print(f"     Año     : {a.year or 'N/A'}  |  Citas: {citations}  |  Journal: {a.journal or 'N/A'}")
        print(f"     DOI     : {a.doi or 'N/A'}")
        print(f"     Keywords: {keywords_preview}")
        print(f"     Abstract: {abstract_preview}")

    # Guardar usando SearchRegistry
    result = SearchResult(
        query=query,
        articles=articles,
        total_results=total_available,
        search_date=datetime.now(),
        sources_queried=["scopus"],
    )
    registry = SearchRegistry(OUTPUT_DIR)
    filename = (args.output + ".csv") if args.output else None
    saved = registry.save_search_result(result, csv_filename=filename)

    print(f"\n{'='*60}")
    print(f"  ARCHIVOS GUARDADOS")
    print(f"{'='*60}")
    for tipo, ruta in saved.items():
        print(f"  {tipo:8}: {ruta}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
