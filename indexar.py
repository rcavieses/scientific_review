"""
Script CLI para indexar PDFs científicos en FAISS para RAG.

Uso:
    python indexar.py                          # indexa todos los PDFs en outputs/pdfs/
    python indexar.py --pdf-dir papers/        # directorio alternativo
    python indexar.py --pdf 2024_Smith.pdf     # uno o varios PDFs específicos
    python indexar.py --stats                  # estadísticas del índice existente
    python indexar.py --list                   # papers ya indexados
    python indexar.py --force                  # re-indexar aunque ya estén
    python indexar.py --chunk-size 1500        # chunks más pequeños
    python indexar.py --provider openai        # embeddings con OpenAI
"""

import argparse
import sys
from pathlib import Path

from pipeline.rag import RAGPipelineOrchestrator, VectorDBManager
from pipeline.rag.pdf_extractor import PdfPlumberExtractor
from pipeline.rag.text_chunker import TextChunker


def cmd_stats(index_dir: Path) -> None:
    """Muestra estadísticas del índice existente."""
    from pipeline.embeddings.embedding_generator import get_embedding_generator

    config_path = index_dir / "index_config.json"
    if not config_path.exists():
        print(f"No se encontró índice en {index_dir}")
        sys.exit(1)

    import json
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    dim = config.get("embedding_dimension", 384)
    db = VectorDBManager(index_dir, embedding_dim=dim)
    db.load()
    stats = db.get_stats()

    print(f"\n{'='*55}")
    print(f"  ESTADISTICAS DEL INDICE RAG")
    print(f"{'='*55}")
    print(f"  Directorio  : {stats.index_path}")
    print(f"  Modelo      : {stats.embedding_model}")
    print(f"  Dimension   : {stats.embedding_dimension}")
    print(f"  Papers      : {stats.total_papers}")
    print(f"  Chunks      : {stats.total_chunks}")
    print(f"  Tamano      : {stats.index_size_mb:.2f} MB")
    print(f"  Actualizado : {stats.last_updated.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")


def cmd_list(index_dir: Path) -> None:
    """Lista los papers ya indexados."""
    config_path = index_dir / "index_config.json"
    if not config_path.exists():
        print(f"No se encontró índice en {index_dir}")
        sys.exit(1)

    import json
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    dim = config.get("embedding_dimension", 384)
    db = VectorDBManager(index_dir, embedding_dim=dim)
    db.load()
    papers = db.get_papers_indexed()

    if not papers:
        print("El índice está vacío.")
        return

    print(f"\nPapers indexados ({len(papers)}):")
    for p in papers:
        print(f"  - {p}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexa PDFs científicos en FAISS para RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Modos de operación
    parser.add_argument(
        "--stats", action="store_true",
        help="Mostrar estadísticas del índice existente y salir",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Listar papers ya indexados y salir",
    )

    # Entrada
    parser.add_argument(
        "--pdf-dir", default="outputs/pdfs",
        help="Directorio con PDFs a indexar (default: outputs/pdfs/)",
    )
    parser.add_argument(
        "--pdf", nargs="+", default=None,
        help="Uno o varios PDFs específicos (rutas relativas o absolutas)",
    )

    # Índice
    parser.add_argument(
        "--index-dir", default="outputs/rag_index",
        help="Directorio del índice FAISS (default: outputs/rag_index/)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-indexar aunque el paper ya esté en el índice",
    )

    # Embedding
    parser.add_argument(
        "--provider", default="local", choices=["local", "openai"],
        help="Proveedor de embeddings (default: local)",
    )
    parser.add_argument(
        "--model", default=None,
        help="Modelo de embedding (default según proveedor)",
    )

    # Chunking
    parser.add_argument(
        "--chunk-size", type=int, default=2000,
        help="Tamaño de chunk en caracteres (default: 2000)",
    )
    parser.add_argument(
        "--overlap", type=int, default=200,
        help="Solapamiento entre chunks en caracteres (default: 200)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Mostrar progreso detallado",
    )

    args = parser.parse_args()

    index_dir = Path(args.index_dir)

    # Modos informativos
    if args.stats:
        cmd_stats(index_dir)
        return

    if args.list:
        cmd_list(index_dir)
        return

    # Resolver PDFs a indexar
    if args.pdf:
        pdf_paths = [Path(p) for p in args.pdf]
        missing = [p for p in pdf_paths if not p.exists()]
        if missing:
            for p in missing:
                print(f"Error: no se encontró {p}")
            sys.exit(1)
    else:
        pdf_dir = Path(args.pdf_dir)
        if not pdf_dir.exists():
            print(f"Error: directorio no encontrado: {pdf_dir}")
            sys.exit(1)
        pdf_paths = None  # el orquestador lee el directorio completo

    # Inicializar componentes
    from pipeline.embeddings.embedding_generator import get_embedding_generator
    generator = get_embedding_generator(
        provider=args.provider,
        model=args.model,
        verbose=args.verbose,
    )

    extractor = PdfPlumberExtractor(verbose=args.verbose)
    chunker = TextChunker(
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        verbose=args.verbose,
    )

    orchestrator = RAGPipelineOrchestrator(
        pdf_dir=Path(args.pdf_dir),
        index_dir=index_dir,
        extractor=extractor,
        chunker=chunker,
        embedding_generator=generator,
        skip_indexed=not args.force,
        verbose=args.verbose,
    )

    stats = orchestrator.run(pdf_paths=pdf_paths)

    if stats.get("failed"):
        print(f"\nPDFs con error:")
        for f in stats["failed"]:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
