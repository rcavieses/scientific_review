#!/usr/bin/env python3
"""
Script de indexación paralela optimizado para 42K PDFs.

Estrategia mixta:
1. Procesa por carpetas de especies (batches)
2. Ejecuta múltiples indexadores en paralelo
3. Usa provider local (2-3x más rápido que Ollama)
4. Chunk size mayor (1024 chars) = menos embeddings
"""

import subprocess
import os
import csv
from pathlib import Path
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Configuración
PDF_BASE_DIR = Path("outputs/pdfs/pdfs2")
INDEX_DIR = Path("outputs/rag_index")
CANONICAL_CSV = Path("data/input/final_taxonomy_occ.csv")  # fuente canónica
MAX_WORKERS = 8  # 8 CPUs lógicos (4 cores × 2 HT) — 1 thread por worker via OMP_NUM_THREADS
PROVIDER = "local"
MODEL = "all-mpnet-base-v2"  # 768 dims, balance calidad/velocidad
CHUNK_SIZE = 1500  # ~375 tokens (73% del límite 512 del modelo) — 3x menos chunks que 500
OVERLAP = 150
BATCH_SIZE = 50  # Especies por batch

def load_canonical_species() -> set:
    """Carga nombres de especies canónicas desde final_taxonomy_occ.csv (case-insensitive)."""
    species = set()
    with open(CANONICAL_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sp = row.get("species", "").strip()
            if sp:
                species.add(sp.lower())
    return species


def get_species_folders():
    """Obtiene lista de carpetas de especies canónicas con PDFs."""
    canonical = load_canonical_species()
    all_dirs = sorted([d for d in PDF_BASE_DIR.iterdir() if d.is_dir()])
    filtered = [d for d in all_dirs if d.name.lower() in canonical]
    skipped = len(all_dirs) - len(filtered)
    print(f"Carpetas totales en pdfs2: {len(all_dirs):,}")
    print(f"  → Canónicas con PDF:     {len(filtered):,}")
    print(f"  → No canónicas (omitidas): {skipped:,}")
    return filtered


def batch_is_done(batch_num: int) -> bool:
    """True si el batch ya fue indexado exitosamente (tiene index.faiss)."""
    return (Path(f"outputs/rag_index_batch_{batch_num:03d}") / "index.faiss").exists()


def count_pdfs_in_species(species_dir):
    """Cuenta PDFs en una carpeta de especie."""
    pdfs = list(species_dir.rglob("*.pdf"))
    return species_dir.name, len(pdfs)

def index_batch(species_folders, batch_num, total_batches):
    """
    Indexa un lote de especies con índice temporal.

    Usa un índice temporal por batch que luego se fusiona.

    Args:
        species_folders: Lista de carpetas de especies
        batch_num: Número del batch
        total_batches: Total de batches

    Returns:
        Dict con estadísticas
    """
    batch_index_dir = Path(f"outputs/rag_index_batch_{batch_num:03d}")

    print(f"\n{'='*70}")
    print(f"BATCH {batch_num}/{total_batches} - {len(species_folders)} especies")
    print(f"Índice temporal: {batch_index_dir}")
    print(f"{'='*70}")

    total_processed = 0
    total_failed = 0

    for i, species_dir in enumerate(species_folders, 1):
        species_name = species_dir.name
        pdf_count = len(list(species_dir.rglob("*.pdf")))

        print(f"\n  [{i}/{len(species_folders)}] {species_name:<40} ({pdf_count:4d} PDFs)")

        # Ejecutar indexador para esta especie (usa índice temporal del batch)
        cmd = [
            "./venv/bin/python", "indexar.py",
            "--provider", PROVIDER,
            "--model", MODEL,
            "--chunk-size", str(CHUNK_SIZE),
            "--overlap", str(OVERLAP),
            "--pdf-dir", str(species_dir),
            "--index-dir", str(batch_index_dir),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 min por especie
                env={**os.environ, "OMP_NUM_THREADS": "1", "TOKENIZERS_PARALLELISM": "false"},
            )

            if result.returncode == 0:
                total_processed += pdf_count
                # Mostrar si hay errores en la salida
                if "error" in result.stdout.lower():
                    for line in result.stdout.split('\n'):
                        if "error" in line.lower():
                            print(f"    ⚠ {line.strip()[:60]}")
            else:
                print(f"    ❌ Error (código {result.returncode})")
                total_failed += pdf_count

        except subprocess.TimeoutExpired:
            print(f"    ⏱ Timeout (30 min)")
            total_failed += pdf_count
        except Exception as e:
            print(f"    ❌ Exception: {str(e)[:50]}")
            total_failed += pdf_count

    result = {
        "batch": batch_num,
        "processed": total_processed,
        "failed": total_failed,
        "species_count": len(species_folders),
        "index_dir": str(batch_index_dir),
    }

    print(f"\n  ✓ Batch {batch_num}: {total_processed} PDFs OK, {total_failed} errores")
    return result

def main():
    """Orquesta la indexación paralela."""

    print("\n" + "="*70)
    print("INDEXACIÓN PARALELA — solo especies canónicas (final_taxonomy_occ)")
    print("="*70)
    print(f"Estrategia:")
    print(f"  • Provider: {PROVIDER} (local, 2-3x más rápido)")
    print(f"  • Modelo: {MODEL} (768 dims)")
    print(f"  • Chunk size: {CHUNK_SIZE} caracteres")
    print(f"  • Procesos paralelos: {MAX_WORKERS}")
    print(f"  • Batch size: {BATCH_SIZE} especies/batch")

    # Obtener carpetas de especies canónicas
    species_folders = get_species_folders()
    print(f"\nEspecies con PDF a indexar: {len(species_folders):,}")

    if not species_folders:
        print("❌ No se encontraron carpetas de especies")
        sys.exit(1)

    # Agrupar en batches
    batches = []
    for i in range(0, len(species_folders), BATCH_SIZE):
        batches.append(species_folders[i:i+BATCH_SIZE])

    # Detectar batches ya completados (resume)
    pending_batches = [(i+1, batch) for i, batch in enumerate(batches) if not batch_is_done(i+1)]
    done_count = len(batches) - len(pending_batches)
    total_pdfs_est = sum(len(list(d.glob("*.pdf"))) for d in species_folders)

    print(f"Batches totales: {len(batches)} | Ya completados: {done_count} | Pendientes: {len(pending_batches)}")
    print(f"PDFs a indexar: {total_pdfs_est:,}")
    print(f"Estimación: ~{len(pending_batches) * BATCH_SIZE / MAX_WORKERS / 60:.1f} horas")
    print()

    # Procesamiento paralelo (solo batches pendientes)
    results = []
    start_time = time.time()

    if not pending_batches:
        print("✅ Todos los batches ya están indexados.")
        return

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(index_batch, batch, batch_num, len(batches)): batch_num
            for batch_num, batch in pending_batches
        }

        for future in as_completed(futures):
            batch_num = futures[future]
            try:
                result = future.result()
                results.append(result)

                # Mostrar progreso global
                elapsed = time.time() - start_time
                completed = len(results)
                percent = (completed / len(batches)) * 100
                eta_seconds = (elapsed / completed) * (len(batches) - completed)

                print(f"\n📊 PROGRESO: {completed}/{len(batches)} batches ({percent:.0f}%)")
                print(f"   ETA: {eta_seconds/3600:.1f} horas")

            except Exception as e:
                print(f"❌ Error en batch {batch_num}: {e}")

    # Resumen final
    total_elapsed = time.time() - start_time
    total_processed = sum(r["processed"] for r in results)
    total_failed = sum(r["failed"] for r in results)

    print(f"\n{'='*70}")
    print(f"RESUMEN FINAL")
    print(f"{'='*70}")
    print(f"Tiempo total: {total_elapsed/3600:.1f} horas ({total_elapsed/86400:.1f} días)")
    print(f"PDFs procesados: {total_processed}")
    print(f"PDFs con error: {total_failed}")
    print(f"Batches completados: {len(results)}/{len(batches)}")
    print(f"Índice guardado en: {INDEX_DIR}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
