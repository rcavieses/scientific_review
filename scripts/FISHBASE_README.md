# FishBase Population Parameters Query System

## Overview

This is a parallel data extraction system designed to complement the RAG-based parameter finding pipeline. It queries **FishBase** (the world's most comprehensive fish species database) to retrieve population biological parameters for species in the Gulf of California.

### Key Differences from RAG System

| Aspect | FishBase System | RAG System |
|--------|-----------------|-----------|
| **Data Source** | FishBase scientific database | Scientific literature (PDFs) |
| **Method** | API/Web scraping | Semantic retrieval + Claude |
| **Speed** | Fast, batch queries | Slower, requires context retrieval |
| **Coverage** | All catalogued fish species | Species mentioned in literature |
| **Reliability** | Curated data, but may be incomplete | Extracted from actual research |
| **Parameters** | Standardized fields | Context-dependent extraction |

## Installation

Install required dependencies:

```bash
pip install -r requirements.txt
```

The system requires:
- `pandas` - Data processing
- `requests` - HTTP requests to FishBase
- `beautifulsoup4` - Web scraping
- `numpy` - Numerical operations

## Scripts

### 1. `goc_species_list_generator.py`

Generates a comprehensive list of Gulf of California species organized by ecological group.

**Features:**
- 100+ GOC species pre-configured
- Organized by ecological group (Pelagics, Demersal, Cephalopods, etc.)
- Output: CSV file with scientific name, common name, and ecological group

**Usage:**
```bash
python3 goc_species_list_generator.py
```

**Output:** `data/input/goc_species_list.csv`

### 2. `fishbase_scraper.py`

Main web scraper that extracts population parameters from FishBase species profiles.

**Features:**
- Web scraping of FishBase profile pages
- Automatic parameter extraction
- Respectful rate limiting (default 1 second between requests)
- Handles search, retrieval, and parsing

**Population Parameters Extracted:**
- `tmax` - Maximum age (years)
- `lmax` - Maximum length (cm)
- `lmat` - Length at maturity
- `linf` - Asymptotic length (von Bertalanffy)
- `k` - Growth coefficient
- `m` - Natural mortality rate
- `trophic_level` - Position in food chain
- `fecundity` - Reproductive output
- `habitat` - Environmental preferences
- `profile_url` - Link to FishBase profile

**Usage:**
```bash
python3 fishbase_scraper.py \
    --output outputs/fishbase_results.csv \
    --format csv \
    --delay 1.0
```

**Options:**
- `--output FILE` - Output file path (default: `outputs/fishbase_scrapped_parameters.csv`)
- `--format {csv,json}` - Output format (default: csv)
- `--delay SECONDS` - Delay between requests (default: 1.0)

### 3. `fishbase_population_fetcher.py`

Alternative implementation using FishBase API (if available) instead of web scraping.

**Features:**
- API-based queries (more reliable if endpoint is available)
- Structured parameter extraction
- Can load custom species list from CSV file

**Usage:**
```bash
python3 fishbase_population_fetcher.py \
    --species data/input/custom_species_list.csv \
    --output outputs/api_results.csv \
    --format csv \
    --delay 0.5
```

**Options:**
- `--species FILE` - Input species list CSV (format: column "species" with names)
- `--output FILE` - Output file path
- `--format {csv,json}` - Output format
- `--delay SECONDS` - Delay between API requests
- `--use-defaults` - Use pre-configured GOC species

### 4. `run_fishbase_queries.sh`

Master orchestration script that runs the complete pipeline.

**Pipeline Steps:**
1. Generate GOC species list
2. Scrape FishBase for all species
3. Generate analysis report
4. Create consolidated output

**Usage:**
```bash
./run_fishbase_queries.sh
```

**Output Files:**
- `data/input/goc_species_list.csv` - Generated species list
- `outputs/fishbase_scrapped_parameters_TIMESTAMP.csv` - Raw scraping results
- `outputs/fishbase_parameters_consolidated_TIMESTAMP.csv` - Final consolidated output

## Workflow

### Quick Start (Default GOC Species)

```bash
# Method 1: Use orchestration script (recommended)
./run_fishbase_queries.sh

# Method 2: Run scraper directly
python3 fishbase_scraper.py

# Method 3: Run API-based fetcher
python3 fishbase_population_fetcher.py --use-defaults
```

### Custom Species

```bash
# 1. Create CSV with your species
cat > my_species.csv << EOF
scientific_name,common_name
Sardinops sagax,Pacific sardine
Engraulis mordax,Northern anchovy
EOF

# 2. Run queries
python3 fishbase_scraper.py --output results.csv
# or
python3 fishbase_population_fetcher.py \
    --species my_species.csv \
    --output results.csv
```

### Using with RAG System

```bash
# Run FishBase extraction
./run_fishbase_queries.sh

# Then compare with RAG-based extraction:
# Place FishBase CSV in outputs/
# Run RAG parameter completion
python3 complete_population_parameters_BUSQUEDA4.py

# Compare results for validation
python3 << 'EOF'
import pandas as pd

fb = pd.read_csv('outputs/fishbase_scrapped_parameters.csv')
rag = pd.read_csv('outputs/rag_parameters.csv')

print("FishBase species found:", len(fb[fb['found'] == True]))
print("RAG species found:", len(rag[rag['found'] == True]))

# Merge and compare
merged = fb.merge(rag, on='scientific_name', how='outer', suffixes=('_fb', '_rag'))
print(merged.head())
EOF
```

## Output Format

### CSV Columns

Default output includes:

| Column | Type | Example |
|--------|------|---------|
| `scientific_name` | str | "Sardinops sagax" |
| `common_name` | str | "Pacific sardine" |
| `found` | bool | true |
| `tmax` | float | 20.0 |
| `lmax` | float | 28.5 |
| `linf` | float | 30.2 |
| `k` | float | 0.35 |
| `m` | float | 0.45 |
| `trophic_level` | float | 3.5 |
| `fecundity` | int | 50000 |
| `habitat` | str | "Marine; depth range..." |
| `profile_url` | str | "https://www.fishbase.org/..." |

### JSON Format

```json
[
  {
    "scientific_name": "Sardinops sagax",
    "common_name": "Pacific sardine",
    "found": true,
    "tmax": 20.0,
    "lmax": 28.5,
    "linf": 30.2,
    "k": 0.35,
    "m": 0.45,
    "trophic_level": 3.5,
    "fecundity": 50000,
    "profile_url": "https://www.fishbase.org/summary/Sardinops-sagax.html"
  }
]
```

## Performance

### Speed Estimates

- **Scraper**: ~1-2 species/second (default 1s delay)
- **API Fetcher**: ~5-10 species/second (default 0.5s delay)
- **100 species**: ~2-5 minutes with default settings

### Optimization

```bash
# Faster scraping (less polite)
python3 fishbase_scraper.py --delay 0.5

# Batch processing with parallel requests
# Note: Not yet implemented, plan for future
```

## Troubleshooting

### Common Issues

**Issue: "Species not found on FishBase"**
- FishBase may have the species under a different name
- Check FishBase directly: https://www.fishbase.org
- Some species may be misspelled in the database

**Issue: "Failed to extract parameters"**
- FishBase page structure may have changed
- Check `profile_url` in output to manually verify
- Parameters may not exist for the species

**Issue: Rate limiting errors**
- Increase `--delay` parameter
- Default of 1 second is very conservative
- FishBase generally allows reasonable bot traffic for research

**Issue: Network timeout**
- Check internet connection
- FishBase server may be temporarily unavailable
- Try again later or use cached results

### Debug Mode

```bash
# Run with verbose logging
PYTHONUNBUFFERED=1 python3 fishbase_scraper.py \
    --output test.csv \
    --delay 2.0 2>&1 | tee debug.log
```

## Integration with Main Pipeline

### Step 1: Extract with FishBase
```bash
./run_fishbase_queries.sh
```

### Step 2: Run RAG-based extraction
```bash
cd /path/to/scientific_review
python3 scripts/complete_population_parameters_BUSQUEDA4.py
```

### Step 3: Merge and validate results
```bash
python3 << 'EOF'
import pandas as pd
import numpy as np

# Load both sources
fb = pd.read_csv('outputs/fishbase_scrapped_parameters_*.csv')
rag = pd.read_csv('outputs/rag_parameters.csv')

# Merge on scientific name
merged = fb.merge(
    rag,
    on='scientific_name',
    how='outer',
    suffixes=('_fishbase', '_rag')
)

# Find discrepancies
numeric_cols = ['tmax', 'lmax', 'linf', 'k', 'm']
for col in numeric_cols:
    if f'{col}_fishbase' in merged.columns and f'{col}_rag' in merged.columns:
        mask = merged[f'{col}_fishbase'].notna() & merged[f'{col}_rag'].notna()
        discrepancies = merged[mask][
            (merged[f'{col}_fishbase'] - merged[f'{col}_rag']).abs() > 
            merged[f'{col}_fishbase'] * 0.1  # 10% threshold
        ]
        if len(discrepancies) > 0:
            print(f"\nDiscrepancies in {col}:")
            print(discrepancies[['scientific_name', f'{col}_fishbase', f'{col}_rag']])

# Save merged results
merged.to_csv('outputs/merged_parameters.csv', index=False)
print("\nMerged results saved to outputs/merged_parameters.csv")
EOF
```

## Species Coverage by Ecological Group

Current database includes ~100 GOC species:

- **Rocky Bottom** (9 species): Scorpionfish, Rockfish, Lingcod
- **Sandy Bottom** (7 species): Halibut, Bass, Flounders
- **Small Pelagics** (5 species): Sardines, Anchovies, Herring
- **Medium Pelagics** (7 species): Mackerels, Jacks, Amberjack
- **Large Pelagics** (7 species): Tunas, Marlin, Swordfish
- **Cephalopods** (5 species): Squid, Octopus
- **Snappers/Groupers** (8 species): Various reef fish
- **Carangidae** (7 species): Jacks and trevally
- **Crustaceans** (7 species): Shrimp, Crabs
- **Reef Fish** (7 species): Wrasses, Damsels, Angelfish
- **Deep Sea** (5 species): Hatchetfish, Fangtooth
- **Elasmobranchs** (9 species): Sharks, Rays

Add more species by editing:
- `goc_species_list_generator.py` - Static list
- Input CSV file - Custom species

## Citation

When using data from FishBase, cite as:

> Froese, R. and D. Pauly. Editors. 2023. FishBase. World Wide Web electronic publication.
> www.fishbase.org, version (12/2023)

## Related Documents

- [GUIA_COMPLETACION_PARAMETROS.md](../GUIA_COMPLETACION_PARAMETROS.md) - RAG-based parameter extraction
- [README.md](../README.md) - Main project documentation
- [SCRIPT_RAG_PARAMETROS.md](../SCRIPT_RAG_PARAMETROS.md) - RAG system details

## Future Enhancements

- [ ] Parallel requests for faster extraction
- [ ] Cache mechanism to avoid re-querying
- [ ] Advanced parameter parsing with regex patterns
- [ ] Integration with other fish databases (SeaLifeBase, LovD)
- [ ] Automatic validation and error detection
- [ ] Web UI for parameter review and editing
- [ ] Automated comparison with RAG extraction

## Support

For issues or questions:
1. Check this README
2. Review script docstrings
3. Check FishBase directly: https://www.fishbase.org
4. Review logs and error messages
