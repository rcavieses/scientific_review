# GROBID Setup Guide

## Overview

**GROBID** (GeneRation Of BIbliographic Data) is a machine-learning tool specifically designed for extracting and parsing structure from scientific papers. It's now the default extractor in this pipeline because it:

- ✅ Extracts document **structure** (title, abstract, sections, references)
- ✅ Handles complex scientific paper layouts
- ✅ Returns semantic metadata (authors, keywords, publication date)
- ✅ Free and open-source
- ✅ No GPU required
- ✅ ~2-5 pages/second processing speed

This guide covers installation, configuration, and usage.

---

## Quick Start (5 minutes)

### 1. Install Docker

GROBID runs in a Docker container. If you don't have Docker:
- **macOS**: https://docs.docker.com/desktop/install/mac-install/
- **Windows**: https://docs.docker.com/desktop/install/windows-install/
- **Linux**: https://docs.docker.com/engine/install/

### 2. Start GROBID

**Option A: Automatic setup (recommended)**
```bash
chmod +x scripts/setup_grobid.sh
./scripts/setup_grobid.sh
```

This script:
- Pulls the GROBID Docker image
- Starts the service
- Waits for it to be ready

**Option B: Manual Docker command**
```bash
docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:latest
```

**Option C: Using docker-compose**
Create `docker-compose.yml`:
```yaml
version: '3'
services:
  grobid:
    image: lfoppiano/grobid:latest
    ports:
      - "8070:8070"
```

Then run:
```bash
docker-compose up -d
```

### 3. Verify GROBID is running

```bash
curl http://localhost:8070/api/isalive
# Should return: [200] true
```

### 4. Test with a PDF

```bash
python scripts/test_grobid_extractor.py path/to/sample.pdf
```

Expected output:
```
Extraction successful!
  Sections extracted: 5
  Total characters: 12,345
```

---

## Configuration

### Environment Variables

`.env` (or `.env.local`):
```bash
# GROBID service URL (default: http://localhost:8070)
GROBID_URL=http://localhost:8070

# PDF Extractor to use (default: grobid)
PDF_EXTRACTOR=grobid
```

### Override Defaults in Code

```python
from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pipeline.rag.pdf_extractor import GrobidPDFExtractor
from pathlib import Path

# Use GROBID explicitly
grobid_extractor = GrobidPDFExtractor(
    grobid_url="http://localhost:8070",
    verbose=True
)

orchestrator = RAGPipelineOrchestrator(
    pdf_dir=Path("outputs/pdfs"),
    extractor=grobid_extractor
)

result = orchestrator.run()
```

---

## How It Works

### Processing Pipeline

1. **Submit PDF to GROBID** → Sends file to `/api/processFulltextDocument`
2. **GROBID processes** → Extracts structure, metadata, text (~2-5 sec per PDF)
3. **Return TEI XML** → GROBID returns XML with full document structure
4. **Parse XML** → Extract text by logical sections (abstract, introduction, methods, results, references)
5. **Clean & chunk** → Standard text cleaning + chunking for RAG

### What GROBID Extracts

The XML response includes:

- **Header (teiHeader)**
  - Title
  - Authors with affiliations
  - Abstract
  - Keywords
  - Publication date

- **Body (text/body)**
  - Sections organized hierarchically
  - Subsections and paragraphs
  - References to figures and tables

- **Back (back)**
  - Bibliography (references)
  - Appendices

- **Metadata**
  - Language
  - Document type
  - Publishing information

---

## Usage Examples

### Basic Extraction

```python
from pipeline.rag.pdf_extractor import GrobidPDFExtractor
from pathlib import Path

extractor = GrobidPDFExtractor()
sections = extractor.extract_by_pages(Path("paper.pdf"))

for section_num, text in sections:
    print(f"Section {section_num}:")
    print(text[:200])
    print()
```

### Extract Metadata

```python
from pipeline.ocr import GrobidProvider

provider = GrobidProvider()
metadata = provider.get_metadata(Path("paper.pdf"))

print(f"Title: {metadata['title']}")
print(f"Authors: {', '.join(metadata['authors'])}")
print(f"Abstract: {metadata['abstract'][:200]}...")
print(f"Keywords: {', '.join(metadata['keywords'])}")
```

### Use with RAG Pipeline

```python
from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pathlib import Path

# GROBID is now the default
orchestrator = RAGPipelineOrchestrator(verbose=True)

result = orchestrator.run(
    pdf_paths=[Path("outputs/pdfs/paper1.pdf"), Path("outputs/pdfs/paper2.pdf")]
)

print(f"Processed: {result['processed']}")
print(f"Failed: {len(result['failed'])}")
print(f"Chunks indexed: {result['total_chunks']}")
```

### Fallback to pdfplumber

If GROBID is not available, the pipeline automatically falls back to pdfplumber:

```bash
# Disable GROBID, use pdfplumber instead
PDF_EXTRACTOR=pdfplumber python my_script.py
```

---

## Troubleshooting

### "Cannot connect to GROBID at http://localhost:8070"

**Problem**: GROBID service is not running.

**Solution**:
```bash
# Check if container is running
docker ps | grep grobid

# If not running, start it
docker start grobid
# OR
./scripts/setup_grobid.sh
```

### "GROBID service is not responding"

**Problem**: Service started but not ready yet.

**Solution**: Wait 10-30 seconds for the service to fully initialize, then retry.

```bash
# Monitor logs
docker logs -f grobid

# Test after a moment
sleep 15 && curl http://localhost:8070/api/isalive
```

### "No text extracted from PDF"

**Problem**: PDF is corrupted, encrypted, or not a standard PDF.

**Solution**:
1. Verify PDF is readable: `file document.pdf`
2. Try opening in a PDF reader
3. Check GROBID logs: `docker logs grobid`
4. Fall back to pdfplumber: `PDF_EXTRACTOR=pdfplumber python script.py`

### High memory usage

**Problem**: Docker container using too much RAM.

**Solution**: Limit container memory:
```bash
docker run -d \
    --name grobid \
    -p 8070:8070 \
    -m 4g \
    lfoppiano/grobid:latest
```

### Slow processing

**Problem**: GROBID processing is slow (>10 sec/page).

**Causes**:
- GROBID container is under-resourced
- Large PDFs (>50 pages)
- High load on system

**Solutions**:
```bash
# Allocate more CPU cores
docker run -d \
    --name grobid \
    -p 8070:8070 \
    --cpus 4 \
    lfoppiano/grobid:latest

# Or reduce batch size in pipeline
orchestrator = RAGPipelineOrchestrator(batch_size=32)
```

---

## Performance Expectations

### Speed

| Scenario | Time per PDF |
|----------|--------------|
| Simple paper (5-10 pages) | 5-15 seconds |
| Standard paper (10-30 pages) | 15-45 seconds |
| Long paper (30-100 pages) | 45-120 seconds |
| Full corpus (450 PDFs avg 26 págs) | ~2-4 minutes (serial) |

### Quality

GROBID is **specifically trained** on scientific papers from:
- arXiv
- PubMed
- ACL anthology
- IEEE Xplore

Expected accuracy:
- Title extraction: >99%
- Author extraction: >95%
- Abstract extraction: >90%
- Section structure: >85%
- Reference parsing: >80%

---

## Limitations

1. **Page-by-page structure not preserved**: GROBID returns logical sections (abstract, introduction, etc.), not physical PDF pages. This is actually an advantage for RAG since it respects semantic boundaries.

2. **Scanned PDFs**: GROBID is trained on digital PDFs. Scanned papers (images) won't work without OCR preprocessing.

3. **Non-English papers**: Works with multiple languages but trained primarily on English papers.

4. **Complex layouts**: Some exotic formatting (columns, sidebars, complex tables) may not be perfectly preserved.

---

## Stopping and Restarting

### Stop GROBID

```bash
docker stop grobid
```

### Start again later

```bash
docker start grobid
# Or restart automatically:
docker restart grobid
```

### Remove container (if needed)

```bash
docker stop grobid
docker rm grobid
# Then run setup script again to recreate
```

---

## Advanced Configuration

### Custom GROBID Instance

If running GROBID elsewhere (e.g., remote server):

```bash
# .env
GROBID_URL=http://remote-server.com:8070
```

### Docker resource limits

For large-scale processing, configure Docker resource limits:

```bash
docker run -d \
    --name grobid \
    -p 8070:8070 \
    --cpus 8 \
    -m 8g \
    --restart unless-stopped \
    lfoppiano/grobid:latest
```

### Batch processing with monitoring

```python
from pipeline.rag.rag_pipeline import RAGPipelineOrchestrator
from pathlib import Path
import time

orchestrator = RAGPipelineOrchestrator(verbose=True)

# Process in batches to monitor progress
all_pdfs = sorted(Path("outputs/pdfs").rglob("*.pdf"))
batch_size = 50

for i in range(0, len(all_pdfs), batch_size):
    batch = all_pdfs[i:i+batch_size]
    print(f"\n>>> Processing batch {i//batch_size + 1} ({len(batch)} PDFs)")

    result = orchestrator.run(pdf_paths=batch)

    print(f"  Processed: {result['processed']}")
    print(f"  Failed: {len(result['failed'])}")

    # Monitor system
    time.sleep(5)
```

---

## References

- **GROBID GitHub**: https://github.com/kermitt2/grobid
- **GROBID Documentation**: https://grobid.readthedocs.io/
- **GROBID Docker**: https://hub.docker.com/r/lfoppiano/grobid
- **TEI XML Standard**: https://tei-c.org/

---

## Support

If you encounter issues:

1. Check Docker logs: `docker logs grobid`
2. Run test script: `python scripts/test_grobid_extractor.py sample.pdf`
3. Verify GROBID is alive: `curl http://localhost:8070/api/isalive`
4. Check GROBID GitHub issues: https://github.com/kermitt2/grobid/issues
