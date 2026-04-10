"""
Búsqueda en Crossref (https://www.crossref.org).

Crossref es un índice de metadatos de publicaciones académicas con DOI.
Cubre revistas científicas, libros, conferencias y preprints.

Uso:
    python scripts/buscar_crossref.py "tu consulta"
    python scripts/buscar_crossref.py "fisheries gulf california" --max-results 50
    python scripts/buscar_crossref.py "plankton" --year-start 2018 --year-end 2023
    python scripts/buscar_crossref.py "marine ecology" --min-relevance 0.5 --tipo journal-article
    python scripts/buscar_crossref.py plankton --lugar "Gulf of California"  # frase exacta
    python scripts/buscar_crossref.py "plankton" --min-relevance 0  # sin filtro de relevancia

Parámetros exclusivos de Crossref:
    --lugar      Ubicación geográfica (se añade al query, ej: 'Gulf of California')
    --tipo       Tipo de publicación: journal-article, book-chapter, proceedings-article, preprint
    --email      Email para acceso polite pool (mayor límite de requests)
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scientific_search.adapters import CrossrefAdapter
from scientific_search.models import SearchResult
from scientific_search.registry import SearchRegistry
from scientific_search.searcher import ScientificArticleSearcher

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def main():
    parser = argparse.ArgumentParser(
        description="Búsqueda en Crossref",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", nargs="*", help="Consulta de búsqueda")
    parser.add_argument("--max-results", type=int, default=20,
                        help="Número máximo de resultados (default: 20, max: 100)")
    parser.add_argument("--year-start", type=int, default=None,
                        help="Año de publicación mínimo")
    parser.add_argument("--year-end", type=int, default=None,
                        help="Año de publicación máximo")
    parser.add_argument("--min-relevance", type=float, default=0.3,
                        help="Umbral de relevancia 0.0-1.0 (default: 0.3, 0=sin filtro)")
    parser.add_argument("--tipo", default=None,
                        choices=["journal-article", "book-chapter", "proceedings-article", "preprint"],
                        help="Filtrar por tipo de publicación")
    parser.add_argument("--lugar", default=None,
                        help="Ubicación geográfica (se añade al query, ej: 'Gulf of California')")
    parser.add_argument("--email", default=None,
                        help="Email para Crossref polite pool (mayor rate limit)")
    parser.add_argument("--output", default=None,
                        help="Nombre base del archivo de salida (sin extensión)")

    args = parser.parse_args()
    query = " ".join(args.query) if args.query else None

    if not query:
        parser.print_help()
        sys.exit(1)

    # El query que se envía al API incluye la ubicación (Crossref no tiene tags de campo)
    api_query = f"{query} {args.lugar}" if args.lugar else query

    print(f"\n{'='*60}")
    print(f"  CROSSREF SEARCH")
    print(f"{'='*60}")
    print(f"  Consulta    : {query}")
    if args.lugar:
        print(f"  Lugar       : {args.lugar}")
        print(f"  Query API   : {api_query}")
    print(f"  Max results : {args.max_results}")
    print(f"  Años        : {args.year_start or 'sin límite'} → {args.year_end or 'presente'}")
    print(f"  Relevancia  : {args.min_relevance}")
    if args.tipo:
        print(f"  Tipo        : {args.tipo}")
    print(f"{'='*60}\n")

    adapter = CrossrefAdapter()
    if args.email:
        adapter.headers = {"User-Agent": f"scientific-search/1.0 (mailto:{args.email})"}

    articles = adapter.search(
        query=api_query,
        max_results=args.max_results * 3,
        year_start=args.year_start,
        year_end=args.year_end,
    )

    # Filtrar por tipo
    if args.tipo:
        before = len(articles)
        articles = [a for a in articles if (a.full_data or {}).get("type") == args.tipo]
        print(f"Filtro por tipo '{args.tipo}': {before} → {len(articles)}")

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
    print(f"  {len(articles)} resultados encontrados")
    print(f"{'─'*60}")
    for i, a in enumerate(articles, 1):
        tipo_pub = (a.full_data or {}).get("type", "N/A")
        print(f"\n{i:3}. {a.title}")
        print(f"     Autores : {', '.join(a.authors[:3]) + (' et al.' if len(a.authors) > 3 else '') if a.authors else 'N/A'}")
        print(f"     Año     : {a.year or 'N/A'}  |  Tipo: {tipo_pub}")
        print(f"     Journal : {a.journal or 'N/A'}")
        print(f"     DOI     : {a.doi or 'N/A'}")

    # Guardar usando SearchRegistry (igual que ScientificArticleSearcher)
    result = SearchResult(
        query=query,
        articles=articles,
        total_results=len(articles),
        search_date=datetime.now(),
        sources_queried=["crossref"],
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
