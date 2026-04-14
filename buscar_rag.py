"""
Consulta semántica sobre el índice FAISS usando RAG + Claude API.

Uso:
    python buscar_rag.py "¿Qué métodos se usan para predecir capturas de Lutjanus?"
    python buscar_rag.py "species distribution" --top-k 8 --model claude-haiku-4-5-20251001
    python buscar_rag.py --interactive
    python buscar_rag.py --stats
"""
import argparse
import io
import sys
from pathlib import Path

# Forzar UTF-8 en la salida estándar (necesario en Windows con cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(
        description="RAG Query Engine: pregunta sobre tus papers indexados"
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Pregunta en lenguaje natural (omitir para modo --interactive)",
    )
    parser.add_argument(
        "--index-dir",
        default="outputs/rag_index",
        help="Directorio del índice FAISS (default: outputs/rag_index)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Número de chunks a recuperar de FAISS (default: 5)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.2,
        help="Similitud coseno mínima para incluir un chunk (default: 0.2)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Modelo de Claude a usar (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Límite de tokens en la respuesta (default: 1024)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Modo interactivo: escribe preguntas en bucle hasta 'salir'",
    )
    parser.add_argument(
        "--show-chunks",
        action="store_true",
        help="Mostrar los fragmentos recuperados de FAISS antes de la respuesta",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Mostrar estadísticas del índice y salir",
    )
    parser.add_argument("--verbose", action="store_true", help="Debug detallado")
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Enriquecer la búsqueda con el grafo de conocimiento (GraphRAG)",
    )
    parser.add_argument(
        "--graph-dir",
        default="outputs/graph_index",
        help="Directorio del grafo de conocimiento (default: outputs/graph_index)",
    )
    parser.add_argument(
        "--graph-hops",
        type=int,
        default=1,
        help="Profundidad de vecindad en el grafo (default: 1)",
    )

    args = parser.parse_args()

    index_dir = Path(args.index_dir)

    # Leer dimensión del config antes de instanciar (evita argumento requerido)
    config_path = index_dir / "index_config.json"
    if not config_path.exists():
        print(f"[error] No se encontró índice en '{index_dir}'. Indexa PDFs primero:")
        print("  python indexar.py --verbose")
        sys.exit(1)

    import json
    with open(config_path) as f:
        index_config = json.load(f)
    embedding_dim = index_config["embedding_dimension"]

    # Cargar índice
    from pipeline.rag import VectorDBManager
    db = VectorDBManager(index_dir=index_dir, embedding_dim=embedding_dim, verbose=args.verbose)
    loaded = db.load()
    if not loaded:
        print(f"[error] No se pudo cargar el índice en '{index_dir}'.")
        sys.exit(1)

    stats = db.get_stats()

    # Solo estadísticas
    if args.stats:
        print(f"\n=== ESTADO DEL ÍNDICE ===")
        print(f"  Chunks totales : {stats.total_chunks}")
        print(f"  Papers         : {stats.total_papers}")
        print(f"  Modelo         : {stats.embedding_model}")
        print(f"  Dimensión      : {stats.embedding_dimension}")
        print(f"  Tamaño         : {stats.index_size_mb:.2f} MB")
        print(f"  Directorio     : {stats.index_path}")
        papers = db.get_papers_indexed()
        if papers:
            print(f"\n  Papers indexados:")
            for p in papers:
                print(f"    • {p}")
        return

    # Inicializar Query Engine (RAG simple o GraphRAG)
    if args.graph:
        from pipeline.rag.graph import KnowledgeGraphStore, GraphQueryEngine
        graph_dir = Path(args.graph_dir)
        graph_store = KnowledgeGraphStore(graph_dir=graph_dir, verbose=args.verbose)
        graph_loaded = graph_store.load()
        if not graph_loaded:
            print(f"[error] No se encontró grafo en '{graph_dir}'. Construyelo primero:")
            print("  python construir_grafo.py")
            sys.exit(1)
        graph_stats = graph_store.get_stats()
        engine = GraphQueryEngine(
            graph_store=graph_store,
            vector_db=db,
            model=args.model,
            top_k=args.top_k,
            max_tokens=args.max_tokens,
            min_score=args.min_score,
            graph_hops=args.graph_hops,
            verbose=args.verbose,
        )
        print(f"Índice cargado: {stats.total_chunks} chunks de {stats.total_papers} papers")
        print(f"Grafo cargado: {graph_stats.total_entities} entidades, "
              f"{graph_stats.total_relations} relaciones")
        print(f"Modo: GraphRAG | Modelo: {args.model} | top_k={args.top_k}\n")
    else:
        from pipeline.rag.query_engine import RAGQueryEngine
        engine = RAGQueryEngine(
            vector_db=db,
            model=args.model,
            top_k=args.top_k,
            max_tokens=args.max_tokens,
            min_score=args.min_score,
            verbose=args.verbose,
        )
        print(f"Índice cargado: {stats.total_chunks} chunks de {stats.total_papers} papers")
        print(f"Modelo: {args.model} | top_k={args.top_k} | min_score={args.min_score}\n")

    # ── Modo interactivo ──────────────────────────────────────────────────────
    if args.interactive:
        print("Modo interactivo. Escribe 'salir' o 'exit' para terminar.\n")
        while True:
            try:
                question = input("Pregunta> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo.")
                break

            if question.lower() in ("salir", "exit", "quit", "q"):
                break
            if not question:
                continue

            _run_query(engine, question, args.show_chunks)

        return

    # ── Pregunta directa desde argumentos ────────────────────────────────────
    question = " ".join(args.question).strip() if args.question else ""
    if not question:
        parser.print_help()
        sys.exit(1)

    _run_query(engine, question, args.show_chunks)


def _run_query(engine, question: str, show_chunks: bool) -> None:
    """Ejecuta una consulta y muestra el resultado formateado en la terminal."""
    from pipeline.rag.graph.models import GraphQueryResult

    try:
        result = engine.query(question)
    except (ValueError, RuntimeError) as e:
        print(f"[error] {e}")
        return

    is_graph = isinstance(result, GraphQueryResult)

    # Entidades del grafo (solo en modo GraphRAG)
    if is_graph and result.graph_results:
        print(f"=== GRAFO DE CONOCIMIENTO ({result.graph_entities_used} entidades) ===")
        print(result.format_graph_context())
        print()

    # Chunks recuperados (opcional)
    if show_chunks and result.sources:
        print("=== FRAGMENTOS RECUPERADOS ===")
        for r in result.sources:
            print(r)
            print()

    # Respuesta principal
    print("=== RESPUESTA ===")
    print(result.answer)

    # Fuentes
    if result.sources:
        print(f"\n=== FUENTES ({result.chunks_used} fragmentos) ===")
        print(result.format_sources())

    print()


if __name__ == "__main__":
    main()
