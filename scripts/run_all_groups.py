#!/usr/bin/env python3
"""
Ejecuta el script de completación de parámetros para todos los grupos funcionales.
"""

import subprocess
import sys
import time
import json
from pathlib import Path

PROGRESS_FILE = Path(__file__).parent.parent / "outputs" / "rag_completion_progress.json"
SCRIPT = Path(__file__).parent / "complete_population_parameters.py"

def get_pending_groups():
    """Obtiene cantidad de grupos pendientes."""
    if not PROGRESS_FILE.exists():
        return None

    with open(PROGRESS_FILE, 'r') as f:
        progress = json.load(f)

    # Contar grupos procesados vs totales
    processed_count = len(progress.get('processed_groups', {}))
    return processed_count

def main():
    """Ejecuta el script repetidamente hasta completar."""

    print("🚀 Iniciando procesamiento de todos los grupos funcionales")
    print("=" * 70)

    iteration = 0
    max_iterations = 60  # Máximo 60 iteraciones (por si acaso)

    while iteration < max_iterations:
        iteration += 1
        pending = get_pending_groups()

        if pending is not None and pending > 0:
            print(f"\n📍 Iteración {iteration}: {pending} grupos procesados hasta ahora")

        print(f"\n▶️  Ejecutando script (iteración {iteration})...")

        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=SCRIPT.parent.parent
        )

        if result.returncode != 0:
            print(f"❌ Error en iteración {iteration}")
            return 1

        # Verificar progreso
        pending = get_pending_groups()
        print(f"✅ Completado. Grupos procesados: {pending}")

        # Si no hay cambio en el contador, probablemente ya terminó
        if pending is not None:
            with open(PROGRESS_FILE, 'r') as f:
                progress = json.load(f)

            if not progress.get('processed_groups'):
                break

            # Si fue el último grupo, salir
            # (check by looking if any group is still pending)
            from pandas import read_csv
            taxonomy_file = SCRIPT.parent.parent / "data" / "input" / "grupos_funcionals_Atlantis_GOC - full_taxonomy.csv"
            if taxonomy_file.exists():
                df = read_csv(taxonomy_file)
                vertebrate_classes = ['Teleostei', 'Petromyzontida', 'Cephalochordata', 'Mammalia',
                                     'Aves', 'Reptilia', 'Amphibia', 'Actinopterygii', 'Chondrichthyes']
                df_vert = df[df['class'].isin(vertebrate_classes)]
                total_groups = len(df_vert['atlantis_fg'].unique())

                if pending >= total_groups:
                    print(f"\n✅ TODOS LOS GRUPOS PROCESADOS ({pending}/{total_groups})")
                    break

        time.sleep(1)  # Pequeña pausa entre iteraciones

    print("\n" + "=" * 70)
    print("🏁 PROCESO COMPLETADO")
    return 0

if __name__ == "__main__":
    sys.exit(main())
