#!/usr/bin/env python3
"""
Monitor en tiempo real del progreso de indexación paralela.
Ejecutar en terminal separada mientras corre indexar_paralelo.py
"""

import os
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def get_batch_progress():
    """Obtiene progreso de cada batch."""
    batch_dirs = sorted(Path("outputs").glob("rag_index_batch_*"))

    progress = {}
    for batch_dir in batch_dirs:
        if (batch_dir / "index_config.json").exists():
            # Batch completado
            status = "✓ HECHO"
        elif (batch_dir / "faiss.index").exists():
            # Batch en progreso
            size = (batch_dir / "faiss.index").stat().st_size
            status = f"⏳ EN CURSO ({size/1024/1024:.0f}MB)"
        else:
            status = "⏱ ESPERANDO"

        batch_num = batch_dir.name.split("_")[-1]
        progress[batch_num] = status

    return progress

def get_active_processes():
    """Cuenta procesos Python activos de indexación."""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        count = len([l for l in result.stdout.split('\n')
                    if 'indexar.py' in l and 'paralelo' not in l])
        return count
    except:
        return 0

def main():
    """Monitor principal."""

    print("\n" + "="*70)
    print("MONITOR DE INDEXACIÓN PARALELA")
    print("="*70 + "\n")

    start_time = datetime.now()

    while True:
        os.system('clear')

        print("="*70)
        print(f"MONITOR INDEXACIÓN - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)

        # Tiempo transcurrido
        elapsed = datetime.now() - start_time
        hours = elapsed.total_seconds() / 3600
        print(f"\nTiempo transcurrido: {elapsed}")

        # Procesos activos
        active = get_active_processes()
        print(f"Procesos activos: {active}")

        # Batches
        print(f"\nEstado de batches:")
        batch_progress = get_batch_progress()

        if not batch_progress:
            print("  (Esperando inicio...)")
        else:
            completed = sum(1 for v in batch_progress.values() if "HECHO" in v)
            total = len(batch_progress)

            for batch_num in sorted(batch_progress.keys(), key=lambda x: int(x)):
                status = batch_progress[batch_num]
                print(f"  Batch {batch_num:2s}: {status}")

            print(f"\n  Progreso: {completed}/{total} batches completados ({completed*100//total}%)")

            # Estimación
            if completed > 0 and hours > 0:
                time_per_batch = hours / completed
                remaining_batches = total - completed
                eta_hours = time_per_batch * remaining_batches
                eta_time = datetime.now() + timedelta(hours=eta_hours)

                print(f"  ETA de finalización: {eta_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  (~{eta_hours:.1f} horas más)")

        # Log reciente
        print(f"\n{'─'*70}")
        print("Últimas líneas del log:")
        print('─'*70)

        try:
            result = subprocess.run(
                ['tail', '-8', 'indexar_paralelo.log'],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if line:
                    print(f"  {line[:68]}")
        except:
            print("  (Log no disponible)")

        print("\n" + "="*70)
        print("Presiona Ctrl+C para salir | Refresco cada 30 segundos")
        print("="*70 + "\n")

        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n✓ Monitor detenido\n")
            break

if __name__ == "__main__":
    main()
