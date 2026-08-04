#!/usr/bin/env python3
"""
Consulta RAG mejorada con integración de FishBase.

Combina búsqueda en papers científicos (FAISS) + parámetros de FishBase
para respuestas más completas sobre especies marinas.

Uso:
    python buscar_rag_con_fishbase.py "¿Cuál es la talla máxima del Huachinango?"
    python buscar_rag_con_fishbase.py "Parámetros biológicos del Lutjanus peru" --top-k 8
    python buscar_rag_con_fishbase.py --interactive
"""
import argparse
import io
import sys
import re
from pathlib import Path
from typing import Optional, Dict, Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def extract_species_names(text: str) -> list[str]:
    """Extrae posibles nombres científicos del texto."""
    # Patrón: Capitalizado seguido de palabra en minúscula (Género especie)
    pattern = r'\b([A-Z][a-z]+)\s+([a-z]+)\b'
    matches = re.findall(pattern, text)
    return [f"{genus} {species}" for genus, species in matches]


def get_fishbase_context(question: str, verbose: bool = False) -> Optional[str]:
    """Obtiene parámetros de FishBase para la especie mencionada."""
    import urllib3

    # Desactivar advertencias de SSL
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        from database_connectors import FishBaseAdapter
    except ImportError:
        if verbose:
            print("[FishBase] Adaptador no disponible")
        return None

    species_names = extract_species_names(question)
    if not species_names:
        return None

    # Usar timeout más largo y retry_delay más corto
    adapter = FishBaseAdapter(timeout=15, retry_delay=0.2)
    context_parts = []

    for species_name in species_names[:2]:  # Máximo 2 especies
        if verbose:
            print(f"[FishBase] Buscando: {species_name}")

        try:
            # Validar especie
            info = adapter.validate_species(species_name)
            if not info:
                if verbose:
                    print(f"[FishBase] No encontrada: {species_name}")
                continue

            # Obtener parámetros
            params = adapter.get_all_params(species_name, ecosystem="Gulf of California")
            if params and params.parameters:
                summary = params.to_summary_dict()
                context_parts.append(
                    f"### Datos de FishBase: {species_name}\n"
                    f"{summary}\n"
                )

                if verbose:
                    print(f"[FishBase] ✓ {len(params.parameters)} parámetros recuperados")
        except Exception as e:
            if verbose:
                print(f"[FishBase] Advertencia: {str(e)[:100]}")
            continue

    return "\n".join(context_parts) if context_parts else None


def main():
    parser = argparse.ArgumentParser(
        description="RAG Query Engine con integración FishBase"
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Pregunta en lenguaje natural (omitir para modo --interactive)",
    )
    parser.add_argument(
        "--index-dir",
        default="outputs/rag_index_goc",
        help="Directorio del índice FAISS (default: outputs/rag_index_goc)",
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
        help="Similitud coseno mínima (default: 0.2)",
    )
    parser.add_argument(
        "--provider",
        default="claude",
        choices=["claude", "ollama"],
        help="Proveedor de LLM (default: claude). Opciones: claude, ollama",
    )
    parser.add_argument(
        "--model",
        dest="llm_model",
        default="claude-haiku-4-5-20251001",
        help="Modelo LLM a usar (default: claude-haiku-4-5-20251001 para claude, qwen3:14b para ollama)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1500,
        help="Límite de tokens en la respuesta (default: 1500)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Modo interactivo",
    )
    parser.add_argument(
        "--show-chunks",
        action="store_true",
        help="Mostrar fragmentos recuperados",
    )
    parser.add_argument(
        "--show-fishbase",
        action="store_true",
        help="Mostrar datos de FishBase en la salida",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Mostrar estadísticas del índice y salir",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Debug detallado",
    )

    args = parser.parse_args()

    # Cargar índice FAISS
    from pipeline.rag import VectorDBManager
    import json

    index_dir = Path(args.index_dir)
    if not index_dir.exists():
        print(f"[error] Índice no encontrado en {index_dir}")
        sys.exit(1)

    config_file = index_dir / "index_config.json"
    with open(config_file) as f:
        config = json.load(f)

    db = VectorDBManager(
        index_dir=index_dir,
        embedding_dim=config["embedding_dimension"],
        verbose=args.verbose,
    )
    db.load()
    stats = db.get_stats()

    # Mostrar stats si se solicita
    if args.stats:
        print(f"\n{'='*55}")
        print(f"  ESTADÍSTICAS DEL ÍNDICE RAG")
        print(f"{'='*55}")
        print(f"  Directorio  : {stats.index_path}")
        print(f"  Chunks      : {stats.total_chunks}")
        print(f"  Papers      : {stats.total_papers}")
        print(f"  Modelo      : {stats.embedding_model}")
        print(f"{'='*55}\n")
        return

    # Crear proveedor LLM
    from pipeline.llm import get_llm_provider

    # Usar modelo default según provider si no se especificó
    model_to_use = args.llm_model
    if args.provider == "ollama" and args.llm_model == "claude-haiku-4-5-20251001":
        model_to_use = "qwen3:14b"

    llm_provider = get_llm_provider(
        provider=args.provider,
        model=model_to_use,
        verbose=args.verbose,
    )

    # Crear query engine RAG
    from pipeline.rag.query_engine import RAGQueryEngine
    from pipeline.embeddings.embedding_generator import get_embedding_generator

    embedding_generator = get_embedding_generator(
        provider="local",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=args.verbose,
    )

    engine = RAGQueryEngine(
        vector_db=db,
        model=args.llm_model,
        top_k=args.top_k,
        max_tokens=args.max_tokens,
        min_score=args.min_score,
        llm_provider=llm_provider,
        embedding_generator=embedding_generator,
        verbose=args.verbose,
    )

    print(f"Índice cargado: {stats.total_chunks} chunks de {stats.total_papers} papers")
    print(f"Modelo: {args.llm_model} | top_k={args.top_k}\n")

    # Modo interactivo
    if args.interactive:
        print("Modo interactivo (escribe 'salir' para terminar)\n")
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

            _run_query_with_fishbase(
                engine, question, args.show_chunks, args.show_fishbase, args.verbose
            )

        return

    # Pregunta directa
    question = " ".join(args.question).strip() if args.question else ""
    if not question:
        parser.print_help()
        sys.exit(1)

    _run_query_with_fishbase(
        engine, question, args.show_chunks, args.show_fishbase, args.verbose
    )


def _run_query_with_fishbase(
    engine, question: str, show_chunks: bool, show_fishbase: bool, verbose: bool
) -> None:
    """Ejecuta consulta combinando RAG + FishBase."""

    # 1. Obtener datos de FishBase
    if verbose:
        print("[query] Consultando FishBase...")
    fishbase_context = get_fishbase_context(question, verbose=verbose)

    # 2. Ejecutar consulta RAG
    if verbose:
        print("[query] Consultando índice RAG...")
    result = engine.query(question)

    # 3. Mostrar datos de FishBase
    if fishbase_context and show_fishbase:
        print("=== DATOS DE FISHBASE ===")
        print(fishbase_context)
        print()

    # 4. Mostrar chunks recuperados
    if show_chunks and result.sources:
        print("=== FRAGMENTOS RECUPERADOS ===")
        for r in result.sources:
            print(f"[{r.score:.3f}] {r.paper_id}")
            print(f"  {r.text[:200]}...")
            print()

    # 5. Respuesta principal
    print("=== RESPUESTA ===")
    print(result.answer)

    # 6. Fuentes
    if result.sources:
        print(f"\n=== FUENTES ({result.chunks_used} fragmentos) ===")
        for r in result.sources:
            authors = ", ".join(r.authors[:2]) if r.authors else "N/A"
            year = r.year or "N/A"
            print(f"  • {authors} ({year}): {r.paper_id}")

    if fishbase_context:
        print(f"  • FishBase (https://www.fishbase.se/)")

    print()


if __name__ == "__main__":
    main()
