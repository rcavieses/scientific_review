"""
Búsqueda en PubMed / NCBI (https://pubmed.ncbi.nlm.nih.gov).

PubMed es la base de datos biomédica del NCBI. Contiene más de 35 millones
de citas de literatura biomédica, incluyendo biología marina, ecología,
bioquímica, medicina y ciencias de la vida en general.

Uso:
    python scripts/buscar_pubmed.py "tu consulta"
    python scripts/buscar_pubmed.py "plankton Gulf California" --max-results 50
    python scripts/buscar_pubmed.py "coral reef" --year-start 2018 --year-end 2023
    python scripts/buscar_pubmed.py "zooplankton" --campo "titulo"
    python scripts/buscar_pubmed.py "sardine" --tipo "review"
    python scripts/buscar_pubmed.py "plankton" --min-relevance 0  # sin filtro

Parámetros exclusivos de PubMed:
    --campo      Campo de búsqueda: todo (default), titulo, abstract, autor, journal, mesh
    --tipo       Tipo de artículo: review, clinical_trial, meta_analysis, journal_article
    --especie    Filtrar por organismo (ej: "Sardinops sagax")
    --email      Email para mayor rate limit de NCBI (recomendado)
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scientific_search.adapters import PubMedAdapter
from scientific_search.models import SearchResult
from scientific_search.registry import SearchRegistry
from scientific_search.searcher import ScientificArticleSearcher

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"

# Mapeo de campos de búsqueda PubMed
CAMPOS_PUBMED = {
    "todo": "",
    "titulo": "[Title]",
    "abstract": "[Abstract]",
    "autor": "[Author]",
    "journal": "[Journal]",
    "mesh": "[MeSH Terms]",
}

# Mapeo de tipos de publicación
TIPOS_PUBMED = {
    "review": "Review[pt]",
    "clinical_trial": "Clinical Trial[pt]",
    "meta_analysis": "Meta-Analysis[pt]",
    "journal_article": "Journal Article[pt]",
}


def build_pubmed_query(query: str, campo: str, tipo: str, year_start, year_end, especie: str, lugar: str = None) -> str:
    """Construye la query PubMed con filtros avanzados."""
    parts = []

    campo_tag = CAMPOS_PUBMED.get(campo, "")
    if campo_tag:
        parts.append(f'("{query}"){campo_tag}')
    else:
        parts.append(query)

    if year_start or year_end:
        y_start = year_start or 1900
        y_end = year_end or 3000
        parts.append(f"({y_start}[PDAT]:{y_end}[PDAT])")

    if tipo and tipo in TIPOS_PUBMED:
        parts.append(TIPOS_PUBMED[tipo])

    if especie:
        parts.append(f'"{especie}"[Organism]')

    if lugar:
        parts.append(f'"{lugar}"[All Fields]')

    return " AND ".join(parts) if len(parts) > 1 else parts[0]


def fetch_pubmed_articles(pubmed_query: str, max_results: int, email: str = None):
    """Llama a la API de NCBI y devuelve artículos parseados."""
    base_params = {"db": "pubmed", "retmode": "json"}
    if email:
        base_params["email"] = email

    # Fase 1 — obtener IDs
    search_params = {
        **base_params,
        "term": pubmed_query,
        "retmax": min(max_results, 200),
        "usehistory": "y",
    }
    resp = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params=search_params,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    result_info = data.get("esearchresult", {})
    pmids = result_info.get("idlist", [])
    total_available = int(result_info.get("count", 0))

    if not pmids:
        return [], total_available

    time.sleep(0.4)  # respetar rate limit NCBI

    # Fase 2 — obtener detalles en XML
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids[:max_results]),
        "rettype": "xml",
    }
    if email:
        fetch_params["email"] = email

    fetch_resp = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        params=fetch_params,
        timeout=15,
    )
    fetch_resp.raise_for_status()

    adapter = PubMedAdapter()
    articles = adapter._parse_pubmed_xml(fetch_resp.text)
    return articles, total_available


def main():
    parser = argparse.ArgumentParser(
        description="Búsqueda en PubMed (NCBI)",
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
                        choices=list(CAMPOS_PUBMED.keys()),
                        help="Campo de búsqueda (default: todo)")
    parser.add_argument("--tipo", default=None,
                        choices=list(TIPOS_PUBMED.keys()),
                        help="Tipo de artículo")
    parser.add_argument("--especie", default=None,
                        help="Filtrar por organismo (ej: 'Sardinops sagax')")
    parser.add_argument("--lugar", default=None,
                        help="Ubicación geográfica exact (ej: 'Gulf of California')")
    parser.add_argument("--email", default=None,
                        help="Email para NCBI polite access (recomendado)")
    parser.add_argument("--output", default=None,
                        help="Nombre base del archivo de salida")

    args = parser.parse_args()
    query = " ".join(args.query) if args.query else None

    if not query:
        parser.print_help()
        sys.exit(1)

    pubmed_query = build_pubmed_query(
        query, args.campo, args.tipo, args.year_start, args.year_end, args.especie,
        lugar=getattr(args, 'lugar', None)
    )

    print(f"\n{'='*60}")
    print(f"  PUBMED SEARCH")
    print(f"{'='*60}")
    print(f"  Consulta    : {query}")
    print(f"  Query NCBI  : {pubmed_query}")
    print(f"  Max results : {args.max_results}")
    print(f"  Campo       : {args.campo}")
    if args.tipo:
        print(f"  Tipo        : {args.tipo}")
    if args.especie:
        print(f"  Especie     : {args.especie}")
    if getattr(args, 'lugar', None):
        print(f"  Lugar       : {args.lugar}")
    print(f"  Relevancia  : {args.min_relevance}")
    print(f"{'='*60}\n")

    print("Consultando PubMed/NCBI...")
    try:
        articles, total_available = fetch_pubmed_articles(
            pubmed_query, args.max_results * 2, args.email
        )
    except Exception as e:
        print(f"Error al consultar PubMed: {e}")
        sys.exit(1)

    print(f"Total disponible en PubMed: {total_available}")
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
        mesh_terms = ", ".join(a.keywords[:4]) if a.keywords else "N/A"
        print(f"\n{i:3}. {a.title}")
        print(f"     Autores : {', '.join(a.authors[:3]) + (' et al.' if len(a.authors) > 3 else '') if a.authors else 'N/A'}")
        print(f"     Año     : {a.year or 'N/A'}  |  URL: {a.url}")
        print(f"     MeSH    : {mesh_terms}")
        print(f"     Abstract: {abstract_preview}")

    # Guardar usando SearchRegistry (igual que ScientificArticleSearcher)
    result = SearchResult(
        query=query,
        articles=articles,
        total_results=total_available,
        search_date=datetime.now(),
        sources_queried=["pubmed"],
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
