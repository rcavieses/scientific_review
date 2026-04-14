"""
Construye el grafo de conocimiento extrayendo entidades y relaciones de los chunks indexados.

Usa Claude Haiku para procesar cada chunk eficientemente (una llamada por chunk).
La extracción es incremental: omite chunks ya procesados en ejecuciones previas.

Uso:
    python construir_grafo.py                          # todos los chunks del índice
    python construir_grafo.py --stats                  # estadísticas del grafo existente
    python construir_grafo.py --model claude-haiku-4-5-20251001
    python construir_grafo.py --graph-dir outputs/graph_index
    python construir_grafo.py --force                  # re-procesar todos los chunks
    python construir_grafo.py --verbose
"""

import io
import json
import sys
from pathlib import Path

# Forzar UTF-8 en la salida
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Construye el grafo de conocimiento desde el índice FAISS"
    )
    parser.add_argument(
        "--index-dir", default="outputs/rag_index",
        help="Directorio del índice FAISS (default: outputs/rag_index)",
    )
    parser.add_argument(
        "--graph-dir", default="outputs/graph_index",
        help="Directorio donde guardar el grafo (default: outputs/graph_index)",
    )
    parser.add_argument(
        "--model", default="claude-haiku-4-5-20251001",
        help="Modelo de Claude para extracción (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-procesar todos los chunks aunque ya estén en el grafo",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Mostrar estadísticas del grafo existente y salir",
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    graph_dir = Path(args.graph_dir)
    index_dir = Path(args.index_dir)

    from pipeline.rag.graph import KnowledgeGraphStore, GraphExtractor

    store = KnowledgeGraphStore(graph_dir=graph_dir, verbose=args.verbose)

    # ── Solo estadísticas ──────────────────────────────────────────────────
    if args.stats:
        loaded = store.load()
        if not loaded:
            print(f"No se encontró grafo en '{graph_dir}'.")
            sys.exit(1)
        stats = store.get_stats()
        print(f"\n{'='*55}")
        print(f"  ESTADÍSTICAS DEL GRAFO DE CONOCIMIENTO")
        print(f"{'='*55}")
        print(f"  Directorio      : {stats.graph_path}")
        print(f"  Entidades       : {stats.total_entities}")
        print(f"  Relaciones      : {stats.total_relations}")
        print(f"  Papers cubiertos: {stats.total_papers_covered}")
        print(f"  Chunks procesados: {stats.total_chunks_processed}")
        print(f"  Actualizado     : {stats.last_updated.strftime('%Y-%m-%d %H:%M')}")
        if stats.entity_type_counts:
            print(f"\n  Entidades por tipo:")
            for etype, count in sorted(stats.entity_type_counts.items()):
                print(f"    {etype:<15}: {count}")
        if stats.relation_type_counts:
            print(f"\n  Relaciones por tipo:")
            for rtype, count in sorted(stats.relation_type_counts.items()):
                print(f"    {rtype:<20}: {count}")
        print(f"{'='*55}\n")
        return

    # ── Cargar chunks desde metadata_store.json ────────────────────────────
    metadata_file = index_dir / "metadata_store.json"
    if not metadata_file.exists():
        print(f"[error] No se encontró índice en '{index_dir}'. Indexa PDFs primero.")
        sys.exit(1)

    with open(metadata_file, encoding="utf-8") as f:
        metadata_store = json.load(f)

    # Reconstruir ChunkData desde el metadata_store
    from pipeline.rag.models import ChunkData

    chunks = []
    for fid, chunk_dict in metadata_store.items():
        try:
            chunk = ChunkData.from_dict(chunk_dict)
            chunks.append(chunk)
        except Exception as e:
            if args.verbose:
                print(f"  [warn] Error al deserializar chunk {fid}: {e}")

    print(f"Chunks disponibles en el índice: {len(chunks)}")

    # ── Cargar grafo existente (extracción incremental) ────────────────────
    store.load()
    stats_before = store.get_stats()

    skip_ids = set() if args.force else store._processed_chunk_ids
    to_process = [c for c in chunks if c.chunk_id not in skip_ids]
    print(f"Chunks a procesar: {len(to_process)} ({len(chunks) - len(to_process)} ya procesados)")

    if not to_process:
        print("Todos los chunks ya están procesados. Usa --force para re-procesar.")
        store.get_stats()
        return

    # ── Extraer entidades y relaciones ─────────────────────────────────────
    extractor = GraphExtractor(
        model=args.model,
        verbose=args.verbose,
    )

    print(f"\nModelo: {args.model}")
    print(f"Grafo destino: {graph_dir}/\n")

    results = extractor.extract_from_chunks(
        to_process,
        show_progress=True,
        skip_chunk_ids=skip_ids,
    )

    # ── Ingestar al grafo ──────────────────────────────────────────────────
    total_new_entities = 0
    total_new_relations = 0

    for extraction in results:
        chunk_id = extraction.pop("chunk_id", "")
        paper_id = extraction.pop("paper_id", "")
        new_ent, new_rel = store.ingest_extraction(extraction, chunk_id, paper_id)
        total_new_entities += new_ent
        total_new_relations += new_rel

    store.save()

    stats_after = store.get_stats()
    print(f"\n{'='*55}")
    print(f"  RESULTADO")
    print(f"{'='*55}")
    print(f"  Entidades nuevas   : {total_new_entities}")
    print(f"  Relaciones nuevas  : {total_new_relations}")
    print(f"  Total entidades    : {stats_after.total_entities}")
    print(f"  Total relaciones   : {stats_after.total_relations}")
    print(f"  Chunks procesados  : {stats_after.total_chunks_processed}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
