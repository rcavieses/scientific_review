# Scientific Literature Analysis Toolkit

A comprehensive toolkit for searching, analyzing, and visualizing scientific literature across multiple academic databases with AI-powered classification.

## Overview

This project provides an end-to-end pipeline for:

1. Searching for scientific articles across multiple databases (Crossref, Semantic Scholar, Science Direct)
2. Integrating and deduplicating search results
3. Analyzing domain-specific terms and relevance
4. Classifying articles using AI (Claude 3.5 Haiku via Anthropic API)
5. Generating visualizations and statistics
6. Creating comprehensive Markdown/PDF reports

The toolkit is designed for bibliometric analysis and systematic literature reviews, with a focus on multi-domain searches (e.g., articles that mention both AI/ML methods and specific application domains like fisheries).

## Directory Structure

```
root/
├── scripts/
│   ├── crossref_search.py        # Search Crossref
│   ├── semantic_scholar_search.py # Search Semantic Scholar
│   ├── science_direct_search.py  # Search Science Direct (requires API key)
│   ├── integrated_search.py      # Combine and deduplicate results
│   ├── domain_analysis.py        # Analyze domain term frequency
│   ├── nlp_classifier_anthropic.py # Classify using Claude API
│   ├── analysis_generator.py     # Generate visualizations
│   ├── report_generator.py       # Create reports
│   ├── main_script.py            # Run search and classification pipeline
│   └── master_script.py          # Execute full workflow
├── data/
│   ├── Domain1.csv               # Terms for first domain
│   ├── Domain2.csv               # Terms for second domain
│   ├── Domain3.csv               # Terms for third domain (optional)
│   └── questions.json            # Classification questions for Claude
├── outputs/                      # Results and intermediate files
│   ├── crossref_results.json
│   ├── semantic_scholar_results.json
│   ├── science_direct_results.json
│   ├── integrated_results.json
│   ├── domain_analyzed_results.json
│   ├── classified_results.json
│   └── ...
├── figures/                      # Generated visualizations
│   ├── publications_by_year.png
│   ├── domain_distribution.png
│   ├── top_journals.png
│   └── ...
├── report.md                     # Generated report
└── report.pdf                    # PDF version of the report
```

## Prerequisites

### Python Dependencies

- Python 3.7+
- Required packages:
  - requests
  - pandas
  - numpy
  - matplotlib
  - seaborn
  - networkx
  - wordcloud
  - adjustText
  - elsapy (for Science Direct API)

Install dependencies:

```bash
pip install requests pandas numpy matplotlib seaborn networkx wordcloud adjustText elsapy
```

### API Keys

1. **Science Direct API Key** (optional): For accessing Science Direct/Scopus
   - Create file `sciencedirect_apikey.txt` with your API key
   
2. **Anthropic API Key**: For Claude classification
   - Create file `anthropic-apikey` with your API key
   - Create an account at [anthropic.com](https://anthropic.com/) if needed

## Configuration Files

### Domain Term Files (CSV)

Create CSV files with terms for each domain. Example for AI domain (Domain1.csv):
```
artificial intelligence
machine learning
deep learning
neural networks
random forest
support vector machine
```

### Classification Questions (JSON)

Create a JSON file with classification questions for Claude:
```json
[
    {
        "text": "Is it an application of AI/ML/DL to fisheries/aquaculture/marine resources?",
        "response_format": "1 or 0",
        "field_name": "is_ai_fishery_application",
        "answer_type": "int",
        "default_value": 0
    },
    {
        "text": "What specific model does the title mention?",
        "response_format": "the exact name of the mentioned model or \"Not mentioned\"",
        "field_name": "model_type",
        "answer_type": "string",
        "default_value": "Not mentioned"
    }
]
```

## Usage

### Quick Start

For a simple test run:

```bash
python setup_test.py  # Creates basic test files
python main_script.py --max-results 10  # Run with limited results
```

### Complete Workflow

```bash
python master_script.py --domain1 Domain1.csv --domain2 Domain2.csv --domain3 Domain3.csv --max-results 100 --year-start 2015 --generate-pdf
```

### Running Specific Phases

```bash
# Using new pipeline architecture (recommended)
python pipeline_executor_main.py --only-search
python pipeline_executor_main.py --only-analysis
python pipeline_executor_main.py --only-report --generate-pdf

# Legacy method (deprecated)
python master_script.py --only-search
python master_script.py --only-analysis
python master_script.py --only-report --generate-pdf
```

### Pipeline Architecture

The project has been migrated to a modular pipeline architecture:

1. Each phase is implemented as a separate class in `pipeline/phase_runner.py`
2. The pipeline execution is managed by `pipeline/pipeline_executor.py`
3. Configuration is handled by `config/config_manager.py`
4. Logging and error handling by `pipeline/logger.py`

This new architecture provides:
- Better modularity and testability
- Cleaner separation of concerns
- More flexible execution flow
- Direct execution of phases without subprocess calls

### Command-Line Options

#### Main Script Options

```
--domain1 FILE        CSV file with terms for domain 1 (default: Domain1.csv)
--domain2 FILE        CSV file with terms for domain 2 (default: Domain2.csv)
--domain3 FILE        CSV file with terms for domain 3 (default: Domain3.csv)
--max-results N       Maximum results per source (default: 100)
--year-start YEAR     Filter by start year (default: 2008)
--year-end YEAR       Filter by end year (default: None)
--email EMAIL         Email for Crossref API
--skip-searches       Skip search phase
--skip-integration    Skip integration phase
--skip-domain-analysis Skip domain analysis
--skip-classification Skip classification phase
```

#### Master Script Additional Options

```
--figures-dir DIR     Directory for figures (default: figures)
--report-file FILE    Output report file (default: report.md)
--generate-pdf        Generate PDF report (requires Pandoc)
--pandoc-path PATH    Path to Pandoc executable
--only-search         Run only search phase
--only-analysis       Run only analysis phase
--only-report         Run only report phase
```

## Individual Components

### Search Modules

- **crossref_search.py**: Search Crossref (no API key required)
- **semantic_scholar_search.py**: Search Semantic Scholar (no API key required)
- **science_direct_search.py**: Search Science Direct/Scopus (requires API key)

### Analysis Modules

- **integrated_search.py**: Combine and deduplicate results
- **domain_analysis.py**: Analyze and tag articles by domain
- **nlp_classifier_anthropic.py**: Classify using Claude AI

### Visualization and Reporting

- **analysis_generator.py**: Generate charts and visualizations
- **report_generator.py**: Create Markdown/PDF reports

## Example Output

The toolkit generates various visualizations:

- Publication trends over time
- Domain distribution
- Source distribution
- Top journals and authors
- Topic co-occurrence matrix
- Word clouds of key terms
- Collaboration networks
- Citations analysis

Reports are generated in Markdown format with optional PDF conversion using Pandoc.

## License

This project is provided for academic and research purposes.

## Acknowledgments

This toolkit was developed to facilitate comprehensive literature reviews and bibliometric analyses in interdisciplinary research fields.

## Troubleshooting

### Common Issues

- **API connection failures**: Check internet connection and API key validity
- **Missing dependencies**: Ensure all required packages are installed
- **PDF generation fails**: Verify Pandoc is installed and accessible
- **Claude classification fails**: Check API key and rate limits

For additional support or to report issues, please open an issue on the repository.