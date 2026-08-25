#!/usr/bin/env python3
"""
BUSQUEDA 5 - Completar parámetros poblacionales usando RAG con Claude Sonnet 5.

Procesa un grupo funcional a la vez, consulta el RAG para cada especie
y completa el archivo Excel con la información encontrada.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill

# Agregar el directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager

# ── Configuración ────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent.parent / "outputs" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "rag_parameter_completion_BUSQUEDA5.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── LLM: BUSQUEDA 5 usa Claude Sonnet 5 (BUSQUEDA 4 usó Haiku 4.5) ──────────
LLM_MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096
# Sonnet 5 activa "adaptive thinking" por defecto; se desactiva para que el
# presupuesto de tokens vaya completo a la respuesta JSON (igual que Haiku).
# Para habilitar razonamiento extendido: THINKING = {"type": "adaptive"}
THINKING = {"type": "disabled"}

# RAG and data files
RAG_INDEX_DIR = Path(__file__).parent.parent / "outputs" / "rag_index_goc_full"
TAXONOMY_CSV = Path(__file__).parent.parent / "data" / "input" / "grupos_funcionals_Atlantis_GOC - full_taxonomy.csv"
PARAMETERS_XLSX = Path(__file__).parent.parent / "data" / "input" / "Atlantis_GOC_parametros_bioogicos.xlsx"
PARAMETERS_CSV = Path(__file__).parent.parent / "data" / "output" / "Atlantis_GOC_parametros_biologicos_BUSQUEDA_5.csv"
PROGRESS_JSON = Path(__file__).parent.parent / "outputs" / "rag_completion_progress_BUSQUEDA_5.json"

# Clases vertebradas
VERTEBRATE_CLASSES = [
    'Teleostei', 'Petromyzontida', 'Cephalochordata', 'Mammalia',
    'Aves', 'Reptilia', 'Amphibia', 'Actinopterygii', 'Chondrichthyes'
]

# Mapeo de parámetros a columnas del Excel (column_index, type)
PARAMETERS_MAPPING = {
    "biomass_mt": (6, "float", "Biomasa (toneladas métricas)"),
    "abundance_numbers": (7, "float", "Abundancia (número de individuos)"),
    "mean_body_size": (8, "float", "Tamaño corporal promedio"),
    "max_age": (10, "float", "Edad máxima (años)"),
    "natural_mortality": (11, "float", "Tasa de mortalidad natural"),
    "Lmax": (12, "float", "Longitud máxima (cm)"),
    "li_a": (13, "float", "Coeficiente a de la relación peso-talla W = a*L^b"),
    "li_b": (14, "float", "Exponente b de la relación peso-talla W = a*L^b"),
    # Columnas nuevas: el Excel no tenía dónde poner L∞ ni t₀, porque las 13 y 14
    # siempre fueron la relación alométrica peso-talla. Se añaden al final.
    "vb_Linf": (28, "float", "Talla asintótica L∞ de von Bertalanffy (cm)"),
    "vb_t0": (29, "float", "Edad teórica a talla cero t₀ de von Bertalanffy (años)"),
    "growth_rate": (15, "float", "Tasa máxima de crecimiento"),
    "age_first_maturity": (18, "float", "Edad de primera madurez (años)"),
    "larval_duration": (21, "float", "Duración larval (días)"),
    "StartSpawnDayOfYear": (22, "int", "Día inicio desove"),
    "EndSpawnDayOfYear": (23, "int", "Día fin desove"),
    "IsMigratory": (24, "string", "¿Es migratoria?"),
}

# ── Prompts Sistema Personalizados (EN INGLÉS) ────────────────────────────────

# STEP 1: Honest data extraction from scientific literature
SYSTEM_PROMPT_EXTRACT = """\
You are an assistant that extracts quantitative data from marine scientific literature.

Your task:
1. Read all provided paper fragments
2. Extract ALL numeric values and quantitative data found
3. Report EXACTLY what you found, don't invent
4. For EACH data point, include the source document/paper it came from
5. If information is not found, be honest about it

Return JSON with all extracted data including sources. Be flexible with structure.
Include everything: size ranges, weight ranges, age data, abundance, biomass, growth parameters,
spawning information, migratory status, aquaculture data, or any other quantitative values found.
Format: {"parameter_name": {"value": number, "source": "document title or authors"}}
"""

# STEP 2: Map and format data to Atlantis table schema
SYSTEM_PROMPT_FORMAT = """\
You are a specialist in marine species biological parameters.

You are given extracted information about a species from scientific literature.

Your task is to intelligently map that information to these 14 specific table fields:
- biomass_mt: biomass in metric tons
- abundance_numbers: abundance (number of individuals)
- mean_body_size: mean body size (cm)
- max_age: maximum age (years)
- natural_mortality: natural mortality rate (0-1)
- Lmax: maximum length (cm)
- li_a: coefficient a of the WEIGHT-LENGTH relationship W = a * L^b (typically 1e-6 to 1e-2). NOT a von Bertalanffy parameter.
- li_b: exponent b of the WEIGHT-LENGTH relationship W = a * L^b (typically 2.5 to 3.5, near 3). NOT a von Bertalanffy parameter.
- vb_Linf: von Bertalanffy asymptotic length L-infinity, in cm.
- vb_t0: von Bertalanffy theoretical age at zero length t0, in years (usually negative).
- growth_rate: von Bertalanffy growth coefficient K, in 1/year. This is the ONLY column for K; do not repeat it anywhere else.
- growth_rate: growth rate
- age_first_maturity: age at first maturity (years)
- larval_duration: larval duration (days)
- StartSpawnDayOfYear: spawning start day (1-365)
- EndSpawnDayOfYear: spawning end day (1-365)
- IsMigratory: is migratory? (Yes/No)

IMPORTANT:
- If data can be reasonably mapped to a field, do it (e.g., subadult weight ranges → mean_body_size)
- Include both wild population data AND aquaculture data if available
- If a field cannot be mapped or data doesn't exist, use null
- Return ONLY a JSON with exactly these 14 fields, nothing else
- All numeric values should be numbers (no units), strings for Yes/No only
"""

# ── Funciones auxiliares ─────────────────────────────────────────────────────

def load_rag_engines():
    """Load two RAG query engines with custom prompts."""
    logger.info("Loading RAG index...")

    vector_db = VectorDBManager(
        index_dir=str(RAG_INDEX_DIR),
        embedding_dim=384
    )
    vector_db.load()

    # Motor 1: Para extracción honesta de datos
    query_engine_extract = RAGQueryEngine(
        vector_db=vector_db,
        model=LLM_MODEL,
        top_k=10,
        min_score=0.15,
        max_tokens=MAX_TOKENS,
        verbose=False,
        system_prompt=SYSTEM_PROMPT_EXTRACT,
        thinking=THINKING,
    )

    # Motor 2: Para formateo en la tabla
    query_engine_format = RAGQueryEngine(
        vector_db=vector_db,
        model=LLM_MODEL,
        top_k=1,  # No necesita buscar en RAG, solo formatea
        min_score=0.0,
        max_tokens=MAX_TOKENS,
        verbose=False,
        system_prompt=SYSTEM_PROMPT_FORMAT,
        thinking=THINKING,
    )

    logger.info(f"RAG loaded. Total chunks: {vector_db.get_stats().total_chunks}")
    return query_engine_extract, query_engine_format


def load_vertebrate_species() -> pd.DataFrame:
    """Carga solo las especies vertebradas del CSV."""
    logger.info("Cargando especies vertebradas...")

    df = pd.read_csv(TAXONOMY_CSV)
    vertebrates = df[df['class'].isin(VERTEBRATE_CLASSES)].copy()

    logger.info(f"Total vertebrados cargados: {len(vertebrates)}")
    return vertebrates


def load_progress() -> Dict:
    """Carga el archivo de progreso si existe."""
    if PROGRESS_JSON.exists():
        with open(PROGRESS_JSON, 'r') as f:
            return json.load(f)
    return {
        "last_processed_group": None,
        "processed_groups": {},
        "species_not_found": [],
        "errors": []
    }


def save_progress(progress: Dict):
    """Guarda el progreso en JSON."""
    with open(PROGRESS_JSON, 'w') as f:
        json.dump(progress, f, indent=2)


def query_rag_for_species(
    query_engine_extract,
    query_engine_format,
    species_name: str,
    group_name: str
) -> Tuple[Dict[str, Optional[str]], str]:
    """
    Consulta RAG en dos pasos:
    1. Extracción honesta de datos + citas
    2. Formateo para la tabla

    Retorna tupla: (diccionario con parámetros, citas como string)
    """
    try:
        logger.info(f"  [{species_name}] Extracting data...")

        # STEP 1: Extract from RAG
        extract_query = (
            f"What quantitative information (numbers, measurements, biological parameters) "
            f"do you have about {species_name} in the Gulf of California? "
            f"\n\nReport ALL numeric values found (sizes, ages, weights, abundances, growth rates, "
            f"spawning info, migration status, aquaculture data, or any other numbers). "
            f"For EACH value, include the source document/paper. "
            f"If information is not found, be honest. Return JSON format."
        )

        extract_result = query_engine_extract.query(extract_query)
        extracted_info = extract_result.answer

        if not extracted_info or len(extracted_info) < 20:
            logger.info(f"    ✗ No information found")
            return {}, ""

        logger.debug(f"    Extracted info: {extracted_info[:100]}...")

        # STEP 1.5: Extract citations from the information
        citations = extract_citations_from_info(extracted_info)

        # STEP 2: Format for table
        logger.info(f"  [{species_name}] Mapping to table schema...")

        format_query = (
            f"Extracted information about {species_name}:\n\n"
            f"{extracted_info}\n\n"
            f"Map this information intelligently to these 14 table fields: "
            f"biomass_mt, abundance_numbers, mean_body_size, max_age, natural_mortality, "
            f"Lmax, li_a, li_b, vb_Linf, vb_t0, growth_rate, "
            f"age_first_maturity, larval_duration, StartSpawnDayOfYear, EndSpawnDayOfYear, IsMigratory. "
            f"\n\nReturn ONLY JSON with exactly these 14 fields."
        )

        format_result = query_engine_format.query(format_query)
        formatted_response = format_result.answer

        # Parsear JSON de la respuesta formateada
        response_text = formatted_response.strip()

        if response_text.startswith("```"):
            parts = response_text.split("```")
            response_text = parts[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        params = json.loads(response_text)

        found_count = len([v for v in params.values() if v is not None and v != "null"])
        logger.info(f"    ✓ {found_count} parameters mapped")
        return params, citations

    except json.JSONDecodeError as e:
        logger.warning(f"    ⚠ JSON parse error: {str(e)[:50]}")
        return {}, ""
    except Exception as e:
        logger.error(f"    Error: {str(e)}")
        return {}, ""


def extract_citations_from_info(info_text: str) -> str:
    """Extrae referencias/citas del texto extraído."""
    try:
        # Si la información es JSON, extraer campos de 'source'
        data = json.loads(info_text)
        sources = set()

        def extract_sources(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.lower() in ['source', 'citation', 'reference', 'from', 'paper']:
                        if value:
                            sources.add(str(value))
                    else:
                        extract_sources(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_sources(item)

        extract_sources(data)
        return "; ".join(sorted(sources)) if sources else ""
    except:
        # Si no es JSON válido, buscar patrones de citación
        lines = info_text.split('\n')
        citations = [line.strip() for line in lines if 'source' in line.lower() or 'from' in line.lower()]
        return "; ".join(citations) if citations else ""


def find_species_in_xlsx(wb, species_name: str, group_name: str) -> Optional[int]:
    """
    Encuentra la fila de una especie en el Excel.
    Retorna el número de fila o None si no existe.
    """
    ws = wb['parameters']

    for row in ws.iter_rows(min_row=2, max_col=4):
        group_cell = row[1]
        species_cell = row[3]

        if (group_cell.value == group_name and
            species_cell.value and species_name.lower() in str(species_cell.value).lower()):
            return row[0].row

    return None


def update_csv_row(species_name: str, group_name: str, params: Dict[str, Optional[str]], citations: str = ""):
    """Update a row in the CSV file with parameters and citations."""
    try:
        # Read CSV
        df = pd.read_csv(PARAMETERS_CSV)

        # Asegurar que exista la columna 'citations'
        if 'citations' not in df.columns:
            df['citations'] = ""

        # Find the row(s) for this species
        mask = (df['Species'] == species_name) & (df['Group'] == group_name)
        indices = df[mask].index

        if len(indices) == 0:
            logger.warning(f"Species not found in CSV: {species_name} ({group_name})")
            return

        # Update parameters for all matching rows
        for idx in indices:
            for param_name, value in params.items():
                if param_name in df.columns and value is not None and value != "null":
                    df.at[idx, param_name] = value

            # Update citations if available
            if citations:
                df.at[idx, 'citations'] = citations

        # Save CSV
        df.to_csv(PARAMETERS_CSV, index=False, encoding='utf-8')
        logger.debug(f"Updated CSV for {species_name}")

    except Exception as e:
        logger.warning(f"Error updating CSV: {e}")


def insert_parameter_to_xlsx(wb, row_num: int, param_name: str, value: Optional[str]):
    """
    Inserta un parámetro en el Excel en la fila y columna correctas.
    """
    ws = wb['parameters']

    if param_name not in PARAMETERS_MAPPING:
        return

    col_idx, param_type, _ = PARAMETERS_MAPPING[param_name]
    if col_idx is None:
        logger.warning(f"'{param_name}' no tiene columna asignada en el Excel; se omite")
        return False

    # Convertir índice de columna a letra (A, B, C, ... AA, AB, ...)
    col_letter = openpyxl.utils.get_column_letter(col_idx)
    cell_address = f'{col_letter}{row_num}'

    try:
        cell = ws[cell_address]

        if value is None or value == "null":
            cell.value = None
        elif param_type == "float":
            cell.value = float(value) if value else None
        elif param_type == "int":
            cell.value = int(value) if value else None
        else:  # string
            cell.value = str(value)

        # Aplicar formato visual
        cell.font = Font(color="00B050")  # Verde para celdas completadas

    except (ValueError, TypeError) as e:
        logger.warning(f"    No se pudo insertar {param_name} = {value} en {cell_address}: {e}")


def process_functional_group(
    query_engine_extract,
    query_engine_format,
    vertebrates_df: pd.DataFrame,
    group_name: str,
    wb: openpyxl.Workbook,
    progress: Dict
) -> Tuple[int, int, int]:
    """
    Procesa todas las especies de un grupo funcional.

    Retorna: (processed, found, not_found)
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Procesando grupo: {group_name}")
    logger.info(f"{'='*70}")

    group_data = vertebrates_df[vertebrates_df['atlantis_fg'] == group_name]
    species_list = group_data.drop_duplicates(subset=['species']).to_dict('records')

    logger.info(f"Especies en este grupo: {len(species_list)}")

    processed = 0
    found = 0
    not_found = 0

    for idx, species_record in enumerate(species_list, 1):
        species_name = species_record['species']

        logger.info(f"[{idx}/{len(species_list)}] {species_name}")

        # Consultar RAG con dos pasos (ahora retorna tupla: params, citations)
        rag_result, citations = query_rag_for_species(
            query_engine_extract, query_engine_format, species_name, group_name
        )

        processed += 1

        if rag_result and any(v is not None for v in rag_result.values()):
            found += 1

            # Update CSV (incluyendo citas)
            update_csv_row(species_name, group_name, rag_result, citations)

            # Update Excel
            row_num = find_species_in_xlsx(wb, species_name, group_name)
            if row_num:
                for param_name, value in rag_result.items():
                    if value is not None and value != "null":
                        insert_parameter_to_xlsx(wb, row_num, param_name, value)

            param_count = len([v for v in rag_result.values() if v])
            logger.info(f"  ✓ {param_count} parameters saved (CSV + Excel)")
        else:
            not_found += 1
            progress['species_not_found'].append(species_name)

    # Save progress
    progress['last_processed_group'] = group_name
    progress['processed_groups'][group_name] = {
        'processed': processed,
        'found': found,
        'not_found': not_found
    }
    save_progress(progress)

    # Save Excel
    wb.save(PARAMETERS_XLSX)
    logger.info(f"Excel saved.")

    return processed, found, not_found


def main():
    """Función principal."""
    logger.info("="*70)
    logger.info("Completación de parámetros poblacionales con RAG + JSON")
    logger.info("="*70)

    # Verificar archivos
    if not RAG_INDEX_DIR.exists():
        logger.error(f"Índice RAG no encontrado: {RAG_INDEX_DIR}")
        logger.error("Ejecuta primero: python scripts/run_exhaustive_rebuild.py")
        return 1

    if not TAXONOMY_CSV.exists():
        logger.error(f"CSV no encontrado: {TAXONOMY_CSV}")
        return 1

    if not PARAMETERS_XLSX.exists():
        logger.error(f"Excel no encontrado: {PARAMETERS_XLSX}")
        return 1

    # Cargar datos
    logger.info("Cargando datos...")
    query_engine_extract, query_engine_format = load_rag_engines()
    vertebrates_df = load_vertebrate_species()
    progress = load_progress()
    wb = openpyxl.load_workbook(PARAMETERS_XLSX)

    # Obtener grupos únicos
    groups = sorted(vertebrates_df['atlantis_fg'].unique().tolist())

    # Continuar desde donde se paró
    if progress['last_processed_group']:
        try:
            last_idx = groups.index(progress['last_processed_group'])
            groups = groups[last_idx + 1:]
            logger.info(f"Continuando desde: {progress['last_processed_group']}")
        except ValueError:
            pass

    # Procesar TODOS los grupos en loop
    total_groups = len(groups)
    processed_count = len(progress['processed_groups'])

    if groups:
        logger.info(f"Procesando {total_groups} grupos (ya procesados: {processed_count})")

        for idx, group in enumerate(groups, start=processed_count + 1):
            try:
                logger.info(f"\n[{idx}/{total_groups + processed_count}] Procesando: {group}")
                processed, found, not_found = process_functional_group(
                    query_engine_extract, query_engine_format, vertebrates_df, group, wb, progress
                )

                logger.info(f"\n{'='*70}")
                logger.info(f"RESUMEN - {group}")
                logger.info(f"{'='*70}")
                logger.info(f"Especies procesadas: {processed}")
                logger.info(f"Con información: {found}")
                logger.info(f"Sin información: {not_found}")
                logger.info(f"Tasa de éxito: {100*found/processed if processed > 0 else 0:.1f}%")

                # Guardar progreso después de cada grupo
                save_progress(progress)

            except KeyboardInterrupt:
                logger.info("\nInterrumpido por usuario.")
                wb.save(PARAMETERS_XLSX)
                save_progress(progress)
                return 0
            except Exception as e:
                logger.error(f"Error en grupo {group}: {e}", exc_info=True)
                progress['errors'].append(f"{group}: {str(e)}")
                save_progress(progress)
                # Continuar con siguiente grupo en lugar de salir
                continue
    else:
        logger.info("Todos los grupos han sido procesados.")

    logger.info("\n✅ Completado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
