#!/usr/bin/env python3
import json
import csv
import re
from pathlib import Path
from datetime import datetime

print("Analizando datos...")

# 1. Especies canónicas totales
total_species = 0
with open("data/input/final_taxonomy_occ.csv") as f:
    reader = csv.DictReader(f)
    total_species = len(list(reader))

# 2. Progreso de descargas
species_with_files = 0
species_with_articles_not_downloaded = 0
species_no_articles = 0

progress_data = {}
_progress_path = Path("outputs/state/download_progress.json")
if _progress_path.exists():
    with open(_progress_path) as f:
        progress_data = json.load(f)

total_processed = 0
total_downloaded = 0

for species, stats in progress_data.items():
    if not isinstance(stats, dict):
        continue

    processed = stats.get("processed", 0)
    downloaded = stats.get("downloaded", 0)

    total_processed += processed
    total_downloaded += downloaded

    if processed == 0:
        species_no_articles += 1
    elif downloaded > 0:
        species_with_files += 1
    elif processed > 0 and downloaded == 0:
        species_with_articles_not_downloaded += 1

# 3. Contar PDFs descargados
pdf_dir = Path("outputs/PDF")
total_pdfs = len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.exists() else 0
total_size_gb = sum(f.stat().st_size for f in pdf_dir.glob("*.pdf")) / (1024**3) if pdf_dir.exists() else 0.0

# 4. Progreso de indexación
indexing_progress = 0
if Path("indexar_paralelo.log").exists():
    with open("indexar_paralelo.log") as f:
        content = f.read()
        progress_lines = re.findall(r"Batch (\d+)/(\d+)", content)
        if progress_lines:
            last_match = progress_lines[-1]
            current = int(last_match[0])
            total = int(last_match[1])
            indexing_progress = (current / total) * 100 if total > 0 else 0

linea = "=" * 80

report = f"""{linea}
REPORTE INTEGRAL DE DESCARGA E INDEXACION
{linea}

Fecha de generacion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{linea}
1. ESTADISTICAS DE ESPECIES
{linea}

Total de especies en taxonomia canonica:        {total_species:>10,}
Especies con PDFs descargados:                  {species_with_files:>10,} ({species_with_files/max(1,total_species)*100:>6.2f}%)
Especies sin articulos disponibles:             {species_no_articles:>10,} ({species_no_articles/max(1,total_species)*100:>6.2f}%)
Especies con articulos pero no descargados:     {species_with_articles_not_downloaded:>10,} ({species_with_articles_not_downloaded/max(1,total_species)*100:>6.2f}%)

{linea}
2. ESTADISTICAS DE DESCARGAS
{linea}

Total de PDFs descargados:                      {total_pdfs:>10,}
Tamaño total descargado:                        {total_size_gb:>10.2f} GB

Resumen de descarga:
  - Total articulos encontrados:                {total_processed:>10,}
  - Articulos descargados:                      {total_downloaded:>10,}
  - Tasa de exito:                              {(total_downloaded/max(1,total_processed)*100):>10.2f}%

{linea}
3. ANALISIS DE ESPECIES POR ESTADO
{linea}

[OK] Especies con archivos descargados:         {species_with_files:>10,} ({species_with_files/max(1,total_species)*100:>6.2f}%)
     -> Listas para indexacion

[NO] Especies sin articulos encontrados:        {species_no_articles:>10,} ({species_no_articles/max(1,total_species)*100:>6.2f}%)
     -> No hay articulos disponibles en las fuentes

[BLOQ] Especies con articulos pero no descargados: {species_with_articles_not_downloaded:>10,} ({species_with_articles_not_downloaded/max(1,total_species)*100:>6.2f}%)
     -> Articulos encontrados pero bloqueados por:
        - Paywall / Acceso restringido
        - Errores en DOI o URL
        - Timeout en servidores

{linea}
4. PROGRESO DE INDEXACION
{linea}

Porcentaje completado:                         {indexing_progress:>10.2f}%
Estado:                                        En progreso (paralelo con 8 workers)
Estimacion tiempo restante:                    {(100-indexing_progress)/100*9:.1f} horas

{linea}
5. ARCHIVOS DE REFERENCIA
{linea}

- pdfs_indexed.txt                    Lista completa de PDFs descargados
- species_in_index.txt                Especies canonicas con PDFs
- download_progress.json              Progreso detallado por especie
- indexar_paralelo.log                Log de indexacion en tiempo real

{linea}
RECOMENDACIONES
{linea}

1. Monitorear indexar_paralelo.log para verificar progreso en vivo
2. Una vez completada la indexacion, usar RAG con los {species_with_files:,} especies indexadas
3. Para las {species_with_articles_not_downloaded:,} especies con paywall, considerar:
   - Usar VPN o acceso institucional
   - Contactar a autores para solicitar copias
   - Buscar preprints en arXiv o bioRxiv

{linea}
"""

print(report)

with open("REPORTE_DESCARGA_INDEXACION.txt", "w") as f:
    f.write(report)

print("\nReporte guardado en: REPORTE_DESCARGA_INDEXACION.txt")
