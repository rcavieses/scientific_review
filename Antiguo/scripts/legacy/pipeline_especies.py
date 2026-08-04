"""
Script para ejecutar búsquedas de artículos científicos para múltiples especies del Golfo de California.

Uso:
    python pipeline_especies.py
    python pipeline_especies.py --download
    python pipeline_especies.py --download --index
"""
import argparse
import subprocess
import json
from pathlib import Path
from datetime import datetime


# 12 especies importantes del Golfo de California
ESPECIES_GOLFO_CALIFORNIA = [
    {
        "nombre": "Sardina Pacific",
        "nombre_cientifico": "Sardinops sagax",
        "query": "Sardinops sagax fisheries population dynamics",
        "descripcion": "Pacific Sardine - Especie clave para pesca comercial"
    },
    {
        "nombre": "Calamar Gigante",
        "nombre_cientifico": "Dosidicus gigas",
        "query": "Dosidicus gigas jumbo squid fisheries",
        "descripcion": "Jumbo Squid - Recurso emergente importante"
    },
    {
        "nombre": "Atún Aleta Amarilla",
        "nombre_cientifico": "Thunnus albacares",
        "query": "Thunnus albacares yellowfin tuna population",
        "descripcion": "Yellowfin Tuna - Pesca internacional importante"
    },
    {
        "nombre": "Atún Ojo Grande",
        "nombre_cientifico": "Thunnus obesus",
        "query": "Thunnus obesus bigeye tuna stock assessment",
        "descripcion": "Bigeye Tuna - Especie migradora"
    },
    {
        "nombre": "Bonito Pacífico",
        "nombre_cientifico": "Sarda chiliensis",
        "query": "Sarda chiliensis bonito fisheries dynamics",
        "descripcion": "Pacific Bonito - Pesca comercial significativa"
    },
    {
        "nombre": "Pargo Colorado",
        "nombre_cientifico": "Lutjanus peru",
        "query": "Lutjanus peru red snapper population dynamics",
        "descripcion": "Red Snapper - Especie demersal importante"
    },
    {
        "nombre": "Mero",
        "nombre_cientifico": "Mycteroperca spp.",
        "query": "Mycteroperca grouper fisheries management",
        "descripcion": "Grouper - Pesca selectiva tradicional"
    },
    {
        "nombre": "Camarón Blanco",
        "nombre_cientifico": "Litopenaeus vannamei",
        "query": "Litopenaeus vannamei white shrimp aquaculture",
        "descripcion": "White Shrimp - Pesca y acuacultura"
    },
    {
        "nombre": "Caballa Pacífica",
        "nombre_cientifico": "Scomber japonicus",
        "query": "Scomber japonicus mackerel stock assessment",
        "descripcion": "Pacific Mackerel - Pesca comercial"
    },
    {
        "nombre": "Dorado",
        "nombre_cientifico": "Coryphaena hippurus",
        "query": "Coryphaena hippurus dorado mahi-mahi migration",
        "descripcion": "Dorado/Mahi-mahi - Pesca deportiva y comercial"
    },
    {
        "nombre": "Jurel del Pacífico",
        "nombre_cientifico": "Trachurus murphyi",
        "query": "Trachurus murphyi jack mackerel stock",
        "descripcion": "Jack Mackerel - Recurso transfronterizo"
    },
    {
        "nombre": "Pez León",
        "nombre_cientifico": "Pterois spp.",
        "query": "Pterois lionfish invasive species control",
        "descripcion": "Lionfish - Especie invasora"
    }
]


def ejecutar_busqueda_especie(especie, max_results=15, year_start=2015, download=False, index=False):
    """Ejecuta búsqueda para una especie específica."""
    print(f"\n{'='*80}")
    print(f"Especie: {especie['nombre']} ({especie['nombre_cientifico']})")
    print(f"Descripción: {especie['descripcion']}")
    print(f"{'='*80}")

    cmd = [
        "python", "buscar.py",
        especie['query'],
        "--lugar", "Gulf of California",
        "--max-results", str(max_results),
        "--year-start", str(year_start)
    ]

    if download:
        cmd.append("--download")

    if index and download:
        cmd.append("--index")

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        # Mostrar solo información relevante
        for linea in resultado.stdout.split('\n'):
            if 'encontrados' in linea or 'guardados' in linea or 'Buscando' in linea:
                print(linea)
        return True
    except Exception as e:
        print(f"Error al ejecutar búsqueda: {e}")
        return False


def generar_reporte(resultados):
    """Genera un reporte de las búsquedas ejecutadas."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reporte_path = Path(f"outputs/pipeline_report_{timestamp}.json")

    with open(reporte_path, 'w') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)

    print(f"\nReporte guardado en: {reporte_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Ejecutar búsquedas de artículos científicos para 12 especies del Golfo de California"
    )
    parser.add_argument("--max-results", type=int, default=15, help="Resultados por fuente (default: 15)")
    parser.add_argument("--year-start", type=int, default=2015, help="Año inicial (default: 2015)")
    parser.add_argument("--download", action="store_true", help="Descargar PDFs en acceso abierto")
    parser.add_argument("--index", action="store_true", help="Indexar PDFs descargados para RAG")
    parser.add_argument("--especie", type=int, help="Ejecutar solo una especie (índice 1-12)")

    args = parser.parse_args()

    print("\n" + "="*80)
    print("PIPELINE DE BÚSQUEDA: 12 ESPECIES DEL GOLFO DE CALIFORNIA")
    print("="*80)

    especies_a_ejecutar = ESPECIES_GOLFO_CALIFORNIA

    if args.especie:
        if 1 <= args.especie <= len(ESPECIES_GOLFO_CALIFORNIA):
            especies_a_ejecutar = [ESPECIES_GOLFO_CALIFORNIA[args.especie - 1]]
        else:
            print(f"Error: índice debe estar entre 1 y {len(ESPECIES_GOLFO_CALIFORNIA)}")
            return

    resultados = {
        "timestamp": datetime.now().isoformat(),
        "total_especies": len(especies_a_ejecutar),
        "parametros": {
            "max_results": args.max_results,
            "year_start": args.year_start,
            "download": args.download,
            "index": args.index
        },
        "especies": []
    }

    for idx, especie in enumerate(especies_a_ejecutar, 1):
        print(f"\n[{idx}/{len(especies_a_ejecutar)}] Procesando: {especie['nombre']}")
        exito = ejecutar_busqueda_especie(
            especie,
            max_results=args.max_results,
            year_start=args.year_start,
            download=args.download,
            index=args.index
        )

        resultados["especies"].append({
            "nombre": especie['nombre'],
            "nombre_cientifico": especie['nombre_cientifico'],
            "exito": exito
        })

    # Generar reporte
    generar_reporte(resultados)

    print("\n" + "="*80)
    print(f"Pipeline completado: {len(especies_a_ejecutar)} especie(s) procesada(s)")
    print("="*80)

    # Mostrar resumen de archivos generados
    buscar_results = Path("outputs/search_results")
    if buscar_results.exists():
        resultados_recientes = sorted(buscar_results.glob("*.csv"))[-len(especies_a_ejecutar):]
        print("\nArchivos de resultados generados:")
        for archivo in resultados_recientes:
            print(f"  + {archivo.name}")


if __name__ == "__main__":
    main()
