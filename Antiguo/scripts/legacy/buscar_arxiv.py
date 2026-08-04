"""
Búsqueda en arXiv (https://arxiv.org).

arXiv es un repositorio de preprints de acceso libre. Es especialmente
relevante para física, matemáticas, ciencias de la computación, biología
cuantitativa, estadística, economía y finanzas. Contiene trabajos antes
de la revisión por pares, por lo que se puede acceder a resultados recientes.

Uso:
    python scripts/buscar_arxiv.py "tu consulta"
    python scripts/buscar_arxiv.py "deep learning ocean" --max-results 30
    python scripts/buscar_arxiv.py "climate forecast" --year-start 2022
    python scripts/buscar_arxiv.py "neural network ecology" --categoria cs.LG
    python scripts/buscar_arxiv.py "satellite oceanography" --campo titulo
    python scripts/buscar_arxiv.py plankton --lugar "Gulf of California"  # frase exacta
    python scripts/buscar_arxiv.py "plankton" --min-relevance 0  # sin filtro

Parámetros exclusivos de arXiv:
    --campo       Campo: todo (default), titulo, abstract, autor, categoria
    --categoria   Categoría arXiv: cs.LG, q-bio.PE, physics.ao-ph, stat.ML, etc.
    --lugar       Ubicación geográfica (se añade como frase exacta al query)
    --orden       Ordenar por: relevance (default), lastUpdatedDate, submittedDate

Categorías útiles:
    q-bio.PE   — Poblaciones y Evolución (biología cuantitativa)
    q-bio.QM   — Métodos cuantitativos en biología
    cs.LG      — Machine Learning
    stat.ML    — Machine Learning (estadística)
    physics.ao-ph — Física de la atmósfera y océanos
    eess.SP    — Procesamiento de señales
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scientific_search.models import Article, SearchResult
from scientific_search.registry import SearchRegistry
from scientific_search.searcher import ScientificArticleSearcher

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"

ARXIV_BASE_URL = "http://export.arxiv.org/api/query"

# Mapeo de campos de búsqueda arXiv
CAMPOS_ARXIV = {
    "todo": "all",
    "titulo": "ti",
    "abstract": "abs",
    "autor": "au",
    "categoria": "cat",
}


def build_arxiv_query(query: str, campo: str, categoria: str, lugar: str = None) -> str:
    """Construye la query arXiv con filtros de campo, categoría y ubicación."""
    campo_prefix = CAMPOS_ARXIV.get(campo, "all")
    terms = " ".join(query.split())
    q = f"{campo_prefix}:{terms}"

    if lugar:
        # Frase exacta — sintaxis Lucene con AND y comillas
        q = f'{q} AND all:"{lugar}"'

    if categoria:
        q = f"{q} AND cat:{categoria}"

    return q


def fetch_arxiv_articles(arxiv_query: str, max_results: int, sort_by: str,
                         year_start: int = None, year_end: int = None):
    """Llama a la API de arXiv y devuelve artículos parseados."""
    params = {
        "search_query": arxiv_query,
        "start": 0,
        "max_results": min(max_results, 200),
        "sortBy": sort_by,
        "sortOrder": "descending",
    }

    response = requests.get(ARXIV_BASE_URL, params=params, timeout=15)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom",
          "opensearch": "http://a9.com/-/spec/opensearch/1.1/"}

    # Total de resultados disponibles en arXiv
    total_elem = root.find("opensearch:totalResults", ns)
    total_available = int(total_elem.text) if total_elem is not None else 0

    articles = []
    for entry in root.findall("atom:entry", ns):
        title_elem = entry.find("atom:title", ns)
        title = title_elem.text.strip() if title_elem is not None else ""
        if not title:
            continue

        # Autores
        authors = [
            name.text
            for author in entry.findall("atom:author", ns)
            for name in [author.find("atom:name", ns)]
            if name is not None and name.text
        ]

        # Fecha de publicación
        year = None
        published_elem = entry.find("atom:published", ns)
        if published_elem is not None and published_elem.text:
            try:
                year = int(published_elem.text[:4])
                if year_start and year < year_start:
                    continue
                if year_end and year > year_end:
                    continue
            except (ValueError, IndexError):
                pass

        # Fecha de última actualización
        updated_elem = entry.find("atom:updated", ns)
        updated = updated_elem.text[:10] if updated_elem is not None else None

        # URLs
        pdf_url = ""
        abs_url = ""
        for link in entry.findall("atom:link", ns):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
            elif link.get("type") == "text/html":
                abs_url = link.get("href", "")

        # Abstract
        summary_elem = entry.find("atom:summary", ns)
        abstract = summary_elem.text.strip() if summary_elem is not None else ""

        # Categorías como keywords
        categories = [
            tag.get("term", "")
            for tag in entry.findall("atom:category", ns)
            if tag.get("term")
        ]

        # arXiv ID
        id_elem = entry.find("atom:id", ns)
        arxiv_id = id_elem.text.split("/abs/")[-1] if id_elem is not None else ""

        article = Article(
            title=title,
            authors=authors,
            year=year,
            doi=f"10.48550/arXiv.{arxiv_id}" if arxiv_id else "",
            url=abs_url or pdf_url,
            abstract=abstract,
            keywords=categories,
            journal="arXiv preprint",
            source="arxiv",
            full_data={"arxiv_id": arxiv_id, "updated": updated, "pdf_url": pdf_url},
        )
        articles.append(article)

    return articles, total_available


def main():
    parser = argparse.ArgumentParser(
        description="Búsqueda en arXiv",
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
                        choices=list(CAMPOS_ARXIV.keys()),
                        help="Campo de búsqueda (default: todo)")
    parser.add_argument("--categoria", default=None,
                        help="Categoría arXiv (ej: cs.LG, q-bio.PE, physics.ao-ph)")
    parser.add_argument("--lugar", default=None,
                        help="Ubicación geográfica (se añade al query, ej: 'Gulf of California')")
    parser.add_argument("--orden", default="relevance",
                        choices=["relevance", "lastUpdatedDate", "submittedDate"],
                        help="Criterio de ordenamiento (default: relevance)")
    parser.add_argument("--output", default=None,
                        help="Nombre base del archivo de salida")

    args = parser.parse_args()
    query = " ".join(args.query) if args.query else None

    if not query:
        parser.print_help()
        sys.exit(1)

    arxiv_query = build_arxiv_query(query, args.campo, args.categoria, lugar=args.lugar)

    print(f"\n{'='*60}")
    print(f"  ARXIV SEARCH")
    print(f"{'='*60}")
    print(f"  Consulta    : {query}")
    print(f"  Query arXiv : {arxiv_query}")
    print(f"  Max results : {args.max_results}")
    print(f"  Campo       : {args.campo}")
    if args.categoria:
        print(f"  Categoría   : {args.categoria}")
    if args.lugar:
        print(f"  Lugar       : {args.lugar}")
    print(f"  Ordenar por : {args.orden}")
    print(f"  Años        : {args.year_start or 'sin límite'} → {args.year_end or 'presente'}")
    print(f"  Relevancia  : {args.min_relevance}")
    print(f"{'='*60}\n")

    print("Consultando arXiv...")
    try:
        articles, total_available = fetch_arxiv_articles(
            arxiv_query,
            max_results=args.max_results * 3,
            sort_by=args.orden,
            year_start=args.year_start,
            year_end=args.year_end,
        )
    except Exception as e:
        print(f"Error al consultar arXiv: {e}")
        sys.exit(1)

    print(f"Total disponible en arXiv: {total_available}")
    print(f"Recuperados para filtrar  : {len(articles)}")

    # Filtrar por relevancia
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

    # Mostrar resultados
    print(f"{'─'*60}")
    print(f"  {len(articles)} resultados finales")
    print(f"{'─'*60}")
    for i, a in enumerate(articles, 1):
        abstract_preview = (a.abstract[:100] + "...") if a.abstract else "Sin abstract"
        cats = ", ".join(a.keywords[:4]) if a.keywords else "N/A"
        pdf_url = a.full_data.get("pdf_url", "") if a.full_data else ""
        print(f"\n{i:3}. {a.title}")
        print(f"     Autores    : {', '.join(a.authors[:3]) + (' et al.' if len(a.authors) > 3 else '') if a.authors else 'N/A'}")
        print(f"     Año        : {a.year or 'N/A'}  |  arXiv ID: {a.full_data.get('arxiv_id', 'N/A') if a.full_data else 'N/A'}")
        print(f"     Categorías : {cats}")
        print(f"     PDF        : {pdf_url or 'N/A'}")
        print(f"     Abstract   : {abstract_preview}")

    # Guardar usando SearchRegistry (igual que ScientificArticleSearcher)
    result = SearchResult(
        query=query,
        articles=articles,
        total_results=total_available,
        search_date=datetime.now(),
        sources_queried=["arxiv"],
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
