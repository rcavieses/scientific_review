#!/bin/bash

# FishBase Population Parameters Query Script
# Runs complete GOC species parameter extraction pipeline

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
DATA_DIR="$PROJECT_DIR/data/input"
OUTPUT_DIR="$PROJECT_DIR/outputs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   FishBase Population Parameters Query Pipeline                 ║"
echo "║   Gulf of California Biological Parameter Extraction            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Generate GOC species list
echo -e "${YELLOW}[1/3] Generating GOC species list...${NC}"
python3 "$SCRIPTS_DIR/goc_species_list_generator.py"
SPECIES_LIST="$DATA_DIR/goc_species_list.csv"

if [ ! -f "$SPECIES_LIST" ]; then
    echo -e "${RED}Error: Species list not generated${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Species list generated: $SPECIES_LIST${NC}"

# Step 2: Scrape FishBase (main method)
echo -e "${YELLOW}[2/3] Scraping FishBase for population parameters...${NC}"
SCRAPER_OUTPUT="$OUTPUT_DIR/fishbase_scrapped_parameters_${TIMESTAMP}.csv"

python3 "$SCRIPTS_DIR/fishbase_scraper.py" \
    --output "$SCRAPER_OUTPUT" \
    --format csv \
    --delay 1.0

if [ ! -f "$SCRAPER_OUTPUT" ]; then
    echo -e "${RED}Error: Scraper output not generated${NC}"
    exit 1
fi

echo -e "${GREEN}✓ FishBase scraping complete: $SCRAPER_OUTPUT${NC}"

# Step 3: Generate comparison report
echo -e "${YELLOW}[3/3] Generating analysis report...${NC}"

python3 << 'PYTHON_EOF'
import pandas as pd
import sys

try:
    # Load scraped parameters
    df_fb = pd.read_csv(sys.argv[1])

    # Generate statistics
    print("\n" + "="*70)
    print("FISHBASE PARAMETER EXTRACTION ANALYSIS")
    print("="*70)

    found = df_fb[df_fb['found'] == True] if 'found' in df_fb.columns else df_fb

    print(f"\nTotal species processed: {len(df_fb)}")
    print(f"Successfully extracted: {len(found)}")

    if len(found) > 0:
        print("\nAvailable parameters:")
        params = [col for col in found.columns if found[col].notna().sum() > 0]
        for param in sorted(params):
            count = found[param].notna().sum()
            print(f"  • {param}: {count} records")

    print("\n" + "="*70)

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF

"$SCRAPER_OUTPUT"

# Step 4: Create final consolidated output
echo -e "${YELLOW}Creating consolidated output file...${NC}"

CONSOLIDATED="$OUTPUT_DIR/fishbase_parameters_consolidated_${TIMESTAMP}.csv"
cp "$SCRAPER_OUTPUT" "$CONSOLIDATED"

echo -e "${GREEN}✓ Consolidated output: $CONSOLIDATED${NC}"

# Summary
echo -e "\n${GREEN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   PIPELINE EXECUTION COMPLETE                                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Output files:"
echo "  • Species list: $SPECIES_LIST"
echo "  • FishBase scrape: $SCRAPER_OUTPUT"
echo "  • Consolidated: $CONSOLIDATED"
echo ""
echo "Next steps:"
echo "  1. Review the output files in $OUTPUT_DIR"
echo "  2. Compare with RAG-based extraction results"
echo "  3. Integrate validated parameters into main database"
echo -e "${NC}"
