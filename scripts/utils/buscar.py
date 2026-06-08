"""
Script para buscar artículos científicos y descargar PDFs en acceso abierto.

Uso:
    python buscar.py "tu consulta"
    python buscar.py "tu consulta" --max-results 30 --year-start 2018
    python buscar.py "tu consulta" --min-relevance 0   # sin filtro de relevancia
    python buscar.py "tu consulta" --sources crossref pubmed scopus
    python buscar.py "sardina" --lugar "Gulf of California" --sources scopus
    python buscar.py "tu consulta" --download
    python buscar.py "tu consulta" --download --download-dir papers/
"""
import argparse
from pathlib import Path
from scientific_search import ScientificArticleSearcher
from scientific_search.downloader import ArticleDownloader


def main():
    parser = argparse.ArgumentParser(description="Búsqueda de artículos científicos")
    parser.add_argument("query", nargs="*", help="Consulta de búsqueda")
    parser.add_argument("--max-results", type=int, default=20, help="Resultados por fuente (default: 20)")
    parser.add_argument("--year-start", type=int, default=2020, help="Año inicial (default: 2020)")
    parser.add_argument("--year-end", type=int, default=None, help="Año final (default: sin límite)")
    parser.add_argument(
        "--min-relevance", type=float, default=0.3,
        help="Fracción mínima de términos de dominio en el título (0=sin filtro, 1=todos; default: 0.3)",
    )
    parser.add_argument(
        "--sources", nargs="+", default=None,
        help="Fuentes: crossref pubmed arxiv scopus (default: todas excepto scopus si no hay apikey)",
    )
    parser.add_argument(
        "--apikey", default=None,
        help="API key de Elsevier para Scopus (alternativa a secrets/scopus_apikey.txt)",
    )
    parser.add_argument(
        "--lugar", default=None,
        help="Filtro geográfico que se añade a la búsqueda (ej: 'Gulf of California')",
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Descargar PDFs en acceso abierto tras la búsqueda",
    )
    parser.add_argument(
        "--download-dir", default=None,
        help="Directorio donde guardar PDFs (default: outputs/pdfs/)",
    )
    parser.add_argument(
        "--email", default="research@scientific-search.org",
        help="Email para Unpaywall API (solo para rate-limit)",
    )
    parser.add_argument(
        "--index", action="store_true",
        help="Indexar PDFs en FAISS para RAG después de descargar",
    )
    parser.add_argument(
        "--index-dir", default=None,
        help="Directorio del índice RAG (default: outputs/rag_index/)",
    )

    args = parser.parse_args()

    query = " ".join(args.query) if args.query else "fisheries forecast in the Gulf of California using machine learning"

    # Si se especifica --lugar, añadirlo al query
    if args.lugar:
        query = f"{query} {args.lugar}"

    print(f"Buscando: '{query}'")
    print(f"Parámetros: max_results={args.max_results}, year_start={args.year_start}, min_relevance={args.min_relevance}\n")

    # Configuración de adaptadores con credenciales específicas
    adapter_config = {}
    if args.apikey:
        adapter_config["scopus"] = {"apikey": args.apikey}

    # Si no se especifican fuentes, usar todas excepto scopus (requiere apikey)
    sources = args.sources
    if sources is None:
        secrets_dir = Path("secrets")
        has_scopus_key = (
            args.apikey is not None
            or (secrets_dir / "scopus_apikey.txt").exists()
            or (secrets_dir / "sciencedirect_apikey.txt").exists()
        )
        sources = ["crossref", "pubmed", "arxiv"]
        if has_scopus_key:
            sources.append("scopus")

    searcher = ScientificArticleSearcher(
        sources=sources,
        output_directory=Path("outputs/"),
        verbose=True,
        adapter_config=adapter_config,
    )

    search_result = searcher.search(
        query=query,
        max_results=args.max_results,
        year_start=args.year_start,
        year_end=args.year_end,
        min_relevance=args.min_relevance,
    )

    saved = searcher.registry.save_search_result(search_result)

    print("\n=== ARCHIVOS GUARDADOS ===")
    for tipo, ruta in saved.items():
        print(f"  {tipo}: {ruta}")

    # Descarga de PDFs en acceso abierto
    if args.download and search_result.articles:
        download_dir = Path(args.download_dir) if args.download_dir else Path("outputs/pdfs")
        downloader = ArticleDownloader(
            download_directory=download_dir,
            email=args.email,
        )

        print(f"\n=== DESCARGANDO PDFs (acceso abierto) ===")
        print(f"  Directorio: {download_dir}\n")

        results = downloader.download_articles(
            search_result.articles,
            progress_callback=lambda msg, **kw: print(f"  {msg}"),
        )

        downloader.print_results(results)

        # Indexar PDFs descargados en FAISS
        if args.index:
            ok_pdfs = [r.filepath for r in results if r.status == "ok" and r.filepath]
            if not ok_pdfs:
                print("\n[--index] No hay PDFs descargados para indexar.")
            else:
                from pipeline.rag import RAGPipelineOrchestrator
                index_dir = Path(args.index_dir) if args.index_dir else Path("outputs/rag_index")
                print(f"\n=== INDEXANDO {len(ok_pdfs)} PDFs para RAG ===")
                orchestrator = RAGPipelineOrchestrator(
                    index_dir=index_dir,
                    verbose=True,
                )
                run_stats = orchestrator.run(pdf_paths=ok_pdfs)
                print(f"  Chunks nuevos: {run_stats['total_chunks']}")


if __name__ == "__main__":
    main()
