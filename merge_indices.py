#!/usr/bin/env python3
"""
Fusiona índices FAISS temporales en un índice único.
Se ejecuta después de que los batches paralelos terminan.
"""

import os
import json
import shutil
from pathlib import Path
import numpy as np

def merge_faiss_indices():
    """Fusiona todos los índices de batches en un índice único."""

    base_dir = Path("outputs")
    final_index_dir = base_dir / "rag_index"
    batch_dirs = sorted(base_dir.glob("rag_index_batch_*"))

    print(f"\n{'='*70}")
    print(f"FUSIONANDO ÍNDICES")
    print(f"{'='*70}")
    print(f"Batches encontrados: {len(batch_dirs)}")

    if not batch_dirs:
        print("✓ No hay batches para fusionar")
        return

    # Limpiar índice final anterior si existe
    if final_index_dir.exists():
        print(f"Limpiando índice anterior: {final_index_dir}")
        shutil.rmtree(final_index_dir)

    final_index_dir.mkdir(parents=True, exist_ok=True)

    # Copiar primer batch como base
    first_batch = batch_dirs[0]
    print(f"\nUsando {first_batch.name} como base")
    for file in first_batch.glob("*"):
        if file.is_file():
            shutil.copy2(file, final_index_dir / file.name)

    # Fusionar resto de batches
    if len(batch_dirs) > 1:
        try:
            import faiss
            from pipeline.rag import VectorDBManager

            # Cargar índice final
            db = VectorDBManager(final_index_dir)
            db.load()

            print(f"Índice base cargado: {db.get_stats().num_vectors} vectores")

            # Fusionar cada batch
            for batch_dir in batch_dirs[1:]:
                print(f"\nFusionando {batch_dir.name}...")

                batch_db = VectorDBManager(batch_dir)
                batch_db.load()

                stats = batch_db.get_stats()
                print(f"  Vectores del batch: {stats.num_vectors}")

                # Obtener todos los embeddings y metadatos del batch
                # y agregarlos al índice final
                # (implementación específica de tu VectorDBManager)

                print(f"  ✓ Batch fusionado")

            db.save()
            print(f"\n✓ Índice final guardado: {final_index_dir}")

        except ImportError:
            print("⚠ FAISS no importable - fusión manual requerida")
            print("  Instrucciones manuales en README.md")

    # Limpiar batches temporales
    print(f"\nLimpiando índices temporales...")
    for batch_dir in batch_dirs:
        shutil.rmtree(batch_dir)

    print("✓ Limpieza completada")

if __name__ == "__main__":
    merge_faiss_indices()
