# Unlimited-OCR Integration Setup

## Overview

The RAG pipeline now supports **Unlimited-OCR** from Baidu for document text extraction, replacing the previous `pdfplumber`-only approach. This enables processing of:

- **Scanned PDFs** (true OCR capability)
- **Complex layouts** (tables, multi-column, dense scientific papers)
- **Digital PDFs** with improved text extraction quality

## Architecture

### Providers

Two OCR providers are implemented:

1. **`baidu_api`** (default, recommended for this environment)
   - Uses Baidu Cloud's hosted Unlimited-OCR API
   - Async task-based: submit PDF → poll for results → download markdown
   - No GPU required; works from any machine with internet
   - Rate limits: QPS=2 (submit) / QPS=5 (query)
   - **Free quota**: 200 pages (personal) / 1000 (enterprise)
   - Location: `pipeline/ocr/baidu_api_provider.py`

2. **`local`** (for GPU-equipped machines)
   - Uses the Unlimited-OCR model locally via transformers
   - Requires: CUDA 12.1+, ~20GB GPU memory
   - Not executed in this environment (no GPU)
   - Prepared for future use on GPU hardware
   - Location: `pipeline/ocr/local_transformers_provider.py`

### Component Integration

- **New module**: `pipeline/ocr/` with `base.py`, provider implementations, and `factory.py`
- **Extractor**: New `OCRPDFExtractor` class in `pipeline/rag/pdf_extractor.py` implements the `PDFExtractor` interface
- **Pipeline**: `RAGPipelineOrchestrator` now defaults to `OCRPDFExtractor` (configurable via env var)
- **Text cleaning**: Shared functions (`_clean_extracted_text`, `_strip_repeated_headers`) used by all extractors

## Setup

### 1. Obtain Baidu Cloud Credentials

1. Go to [Baidu Cloud Console](https://console.bce.baidu.com)
2. Navigate to **Products → 文字识别 (Text Recognition / OCR)**
3. Create or select an application
4. Copy your **API Key** (client_id) and **Secret Key** (client_secret)

### 2. Configure Environment

Edit `.env` and add:

```bash
# OCR Configuration
OCR_PROVIDER=baidu_api
BAIDU_OCR_API_KEY=<your_api_key>
BAIDU_OCR_SECRET_KEY=<your_secret_key>
```

Or for local mode (requires GPU):

```bash
OCR_PROVIDER=local
```

### 3. Install Dependencies

Base requirement (already in `requirements.txt`):
```bash
pip install pymupdf>=1.24.0
```

For local mode (optional, only if you have a GPU):
```bash
pip install -r requirements-ocr-local.txt
```

## Usage

### Option A: Use with RAG Pipeline (automatic)

Once `.env` is configured, the RAG pipeline automatically uses OCR:

```bash
python -c "
from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pathlib import Path

orch = RAGPipelineOrchestrator(
    pdf_dir=Path('outputs/pdfs'),
    index_dir=Path('outputs/rag_index'),
    verbose=True
)
result = orch.run()
print(f'Indexed: {result[\"processed\"]}, Failed: {len(result[\"failed\"])}')
"
```

### Option B: Test Single PDF

```bash
python scripts/test_ocr_provider.py path/to/your/document.pdf
```

This script:
- Validates your Baidu credentials
- Processes the PDF with OCR
- Prints extracted text and statistics
- Useful for troubleshooting before running the full pipeline

### Option C: Direct API Usage

```python
from pipeline.ocr import BaiduCloudOCRProvider
from pathlib import Path

provider = BaiduCloudOCRProvider()
pages = provider.extract_pdf(Path("document.pdf"))

for page_num, text in pages:
    print(f"Page {page_num}: {len(text)} chars")
    print(text[:200])
```

## Important Notes

### Free Quota Limits

- **Personal**: 200 pages/month
- **Enterprise**: 1,000 pages/month
- Current corpus: ~14,500 PDFs

**Action required**: Before running the pipeline on the full corpus, either:
1. Request a quota upgrade from Baidu Cloud (paid plan)
2. Process a smaller subset for testing/validation
3. Check the quota display in Baidu Cloud console

### API Rate Limits

- Submit: 2 QPS (can process ~200 PDFs/minute serially)
- Query: 5 QPS

The provider respects these limits and will backoff gracefully if throttled.

### Response Format

The Baidu API returns markdown-formatted text. The provider attempts to parse page boundaries from markdown markers (e.g., `---` or `# Page X`). If markers are absent, the entire document is treated as page 1.

## Fallback Behavior

If Baidu OCR credentials are missing or invalid:
1. The pipeline **warns** but does **not crash**
2. Falls back to `PdfPlumberExtractor` (previous behavior)
3. Logged in verbose mode

To force a provider:
```python
from pipeline.rag.pdf_extractor import PdfPlumberExtractor

orchestrator = RAGPipelineOrchestrator(
    extractor=PdfPlumberExtractor(),  # Explicit, no OCR
)
```

## Local Mode (Future, GPU Required)

To prepare for local mode on a GPU-equipped machine:

1. Install GPU dependencies:
   ```bash
   pip install -r requirements-ocr-local.txt
   ```

2. Set in `.env`:
   ```bash
   OCR_PROVIDER=local
   ```

3. The provider will:
   - Lazy-load the model on first PDF
   - Convert PDF pages to PNG (300 DPI)
   - Run inference via `model.infer_multi()`
   - Return text by page

**GPU Requirements**: CUDA 12.1+, ~20GB VRAM for the Unlimited-OCR model.

## Troubleshooting

### "Credentials not found"
```
OCRExtractionError: Baidu OCR credentials not found.
```
- Check `.env` file has `BAIDU_OCR_API_KEY` and `BAIDU_OCR_SECRET_KEY` set
- Verify no trailing spaces or quotes in values
- Reload shell after editing `.env` if using `source .env`

### "Quota exceeded"
```
OCRExtractionError: Baidu OCR quota exceeded...
```
- You've hit the free tier limit
- Visit Baidu Cloud console to check remaining quota or upgrade plan

### "Rate limit (QPS=2)"
```
OCRExtractionError: Rate limit (QPS=2) hit on submit.
```
- Too many PDFs submitted simultaneously
- Reduce batch size or add delays between submissions
- The provider auto-retries with backoff; may take longer

### "Task timeout after 600s"
```
OCRExtractionError: Task ... timed out
```
- PDF processing took too long (very large files)
- May be API overload; retry later
- Increase `max_wait_seconds` in provider constructor if needed

### "No text extracted (local mode)"
```
OCRExtractionError: CUDA not available and allow_cpu=False
```
- Local mode needs a GPU and CUDA
- Either: (a) use GPU machine, (b) switch to `baidu_api`, or (c) set `allow_cpu=True` (very slow)

## Performance Expectations

### Baidu API Mode
- ~1–5 seconds per PDF (depending on size and API load)
- Bottleneck: API processing + polling
- Full corpus (~14.5k PDFs) would take ~4–20 hours (with respect to QPS limits)

### Local Mode (GPU)
- ~5–30 seconds per page (depending on GPU)
- Faster for large batches due to no network I/O
- Requires powerful GPU; CPU is impractical

## Files Modified / Added

### New Files
- `pipeline/ocr/__init__.py` — Module exports
- `pipeline/ocr/base.py` — Abstract `OCRProvider` interface
- `pipeline/ocr/baidu_api_provider.py` — Baidu Cloud API implementation
- `pipeline/ocr/local_transformers_provider.py` — Local transformers implementation
- `pipeline/ocr/factory.py` — Provider factory function
- `scripts/test_ocr_provider.py` — Single-PDF testing script
- `requirements-ocr-local.txt` — Optional GPU dependencies
- `docs/UNLIMITED_OCR_SETUP.md` — This file

### Modified Files
- `pipeline/rag/pdf_extractor.py` — Added `OCRPDFExtractor`, extracted shared cleaning functions
- `pipeline/rag/rag_pipeline.py` — Defaults to `OCRPDFExtractor` instead of `PdfPlumberExtractor`
- `.env.example` — Added OCR configuration template
- `requirements.txt` — Added `pymupdf>=1.24.0`

## Next Steps

1. **Validate credentials**: `python scripts/test_ocr_provider.py <sample.pdf>`
2. **Test on small subset**: Run pipeline on 5–10 PDFs with `OCR_PROVIDER=baidu_api`
3. **Check quota**: Verify remaining pages in Baidu Cloud console before full run
4. **Tune if needed**: Adjust `poll_interval`, `max_wait_seconds` in `BaiduCloudOCRProvider` if needed
5. **Monitor quality**: Manually review 2–3 extracted texts to confirm quality before mass processing

## References

- **Baidu Unlimited-OCR GitHub**: https://github.com/baidu/Unlimited-OCR
- **Baidu Cloud API Docs**: https://cloud.baidu.com/doc/OCR/s/fmr1p39gb (Chinese)
- **Baidu Console**: https://console.bce.baidu.com
- **Paper**: https://arxiv.org/abs/2606.23050
