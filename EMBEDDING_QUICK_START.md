# 🚀 Quick Start Guide: Embedding System

## Installation

### Minimal (for Foundation only)
```bash
# No additional dependencies needed
# scientific_search and numpy are required
```

### With Local Embeddings
```bash
pip install sentence-transformers
# Optional: torch (for GPU support)
pip install torch  # For CUDA support
```

### With OpenAI Embeddings
```bash
pip install openai
export OPENAI_API_KEY="sk-your-key-here"
```

---

## 5-Minute Tutorial

### Step 1: Search for Articles
```python
from scientific_search import ScientificArticleSearcher

searcher = ScientificArticleSearcher()
results = searcher.search("fishing prediction", max_results=10)
```

### Step 2: Extract Information
```python
from pipeline.embeddings import InformationExtractor

extractor = InformationExtractor()
extracted_list, errors = extractor.extract_from_multiple(
    results.articles
)
```

### Step 3: Process Text
```python
from pipeline.embeddings import TextProcessor

processor = TextProcessor(strategy="title_abstract")
texts = processor.process_multiple(extracted_list)
```

### Step 4: Generate Embeddings
```python
from pipeline.embeddings.embedding_generator import get_embedding_generator

gen = get_embedding_generator(provider="local")
embeddings = gen.batch_generate(texts, batch_size=32)
```

### Done! 🎉
```python
print(f"Generated {len(embeddings)} embeddings")
print(f"Shape: {embeddings.shape}")  # (10, 384)
```

---

## Common Tasks

### Switch from Local to OpenAI
```python
# Option 1: Change provider only
gen = get_embedding_generator(
    provider="openai",
    api_key="sk-..."
)

# Option 2: Keep everything else
embeddings = gen.batch_generate(texts)  # Same API!
```

### Compare Models
```python
# Test different local models
models = [
    "all-MiniLM-L6-v2",      # Fast: 384 dims
    "all-mpnet-base-v2",      # Balanced: 768 dims
    "multilingual-e5-small"   # Multilingual: 384 dims
]

for model in models:
    gen = get_embedding_generator(
        provider="local",
        model=model
    )
    embeddings = gen.generate(["test text"])
    print(f"{model}: shape={embeddings.shape}")
```

### Calculate Similarity Between Texts
```python
text1 = "Deep learning for fishing"
text2 = "Machine learning in agriculture"

gen = get_embedding_generator(provider="local")
emb1 = gen.generate([text1])[0]
emb2 = gen.generate([text2])[0]

similarity = gen.cosine_similarity(emb1, emb2)
print(f"Similarity: {similarity:.4f}")
```

### Process Large Datasets
```python
# Automatic batching with progress
texts = [f"Article {i}" for i in range(100000)]

gen = get_embedding_generator(provider="local")
embeddings = gen.batch_generate(
    texts,
    batch_size=128,
    show_progress=True  # Shows progress
)

print(f"Generated {len(embeddings)} embeddings")
```

### Get Model Information
```python
gen = get_embedding_generator(provider="local")

print(gen.get_info())
# Output:
# {
#   'model': 'all-MiniLM-L6-v2',
#   'dimension': 384,
#   'type': 'LocalEmbeddingGenerator',
#   'device': 'cuda',  # or 'cpu'
#   'normalize_embeddings': True
# }
```

---

## Available Models

### Local (SentenceTransformers)
| Model | Dims | Speed | Quality |
|-------|------|-------|---------|
| all-MiniLM-L6-v2 | 384 | ⚡⚡⚡ | ⭐⭐⭐ |
| all-mpnet-base-v2 | 768 | ⚡⚡ | ⭐⭐⭐⭐ |
| multilingual-e5-small | 384 | ⚡⚡⚡ | ⭐⭐⭐ |
| paraphrase-MiniLM-L6-v2 | 384 | ⚡⚡⚡ | ⭐⭐⭐ |

### OpenAI
| Model | Dims | Cost | Quality |
|-------|------|------|---------|
| text-embedding-3-small | 512 | $ | ⭐⭐⭐⭐ |
| text-embedding-3-large | 3072 | $$ | ⭐⭐⭐⭐⭐ |

---

## Complete Example (End-to-End)

```python
#!/usr/bin/env python3
"""Complete embedding pipeline example."""

from scientific_search import ScientificArticleSearcher
from pipeline.embeddings import InformationExtractor, TextProcessor
from pipeline.embeddings.embedding_generator import get_embedding_generator
import numpy as np

def main():
    # 1. Search
    print("1. Searching for articles...")
    searcher = ScientificArticleSearcher()
    results = searcher.search(
        "deep learning fishing",
        max_results=50,
        year_start=2020
    )
    print(f"   Found {len(results.articles)} articles")

    # 2. Extract
    print("\n2. Extracting information...")
    extractor = InformationExtractor(verbose=False)
    extracted_list, errors = extractor.extract_from_multiple(
        results.articles,
        skip_errors=True
    )
    print(f"   Extracted {len(extracted_list)} articles, {len(errors)} errors")

    # 3. Process
    print("\n3. Processing text...")
    processor = TextProcessor(strategy="title_abstract")
    texts = processor.process_multiple(extracted_list)
    print(f"   Processed {len(texts)} texts")
    print(f"   Avg length: {np.mean([len(t) for t in texts]):.0f} chars")

    # 4. Generate embeddings
    print("\n4. Generating embeddings...")
    gen = get_embedding_generator(provider="local", verbose=True)
    embeddings = gen.batch_generate(texts, batch_size=32)
    print(f"   Generated embeddings shape: {embeddings.shape}")

    # 5. Calculate statistics
    print("\n5. Statistics:")
    print(f"   Model: {gen.get_model_name()}")
    print(f"   Dimensions: {gen.get_dimension()}")
    print(f"   Device: {gen.get_info()['device']}")

    # 6. Find similar articles
    print("\n6. Finding similar pairs...")
    if len(embeddings) >= 2:
        sim = gen.cosine_similarity(embeddings[0], embeddings[1])
        print(f"   Similarity between article 0 and 1: {sim:.4f}")

    print("\n✅ Done!")
    return embeddings

if __name__ == "__main__":
    embeddings = main()
```

---

## Troubleshooting

### "SentenceTransformers not installed"
```bash
pip install sentence-transformers
```

### "OPENAI_API_KEY not defined"
```bash
export OPENAI_API_KEY="sk-your-key"
# or pass it directly:
gen = get_embedding_generator(
    provider="openai",
    api_key="sk-your-key"
)
```

### "CUDA out of memory"
```python
# Reduce batch size
embeddings = gen.batch_generate(
    texts,
    batch_size=8  # Instead of 32
)

# Or use CPU
gen = LocalEmbeddingGenerator(device="cpu")
```

### Slow performance on CPU
```python
# Use faster model
gen = get_embedding_generator(
    provider="local",
    model="all-MiniLM-L6-v2"  # Faster than mpnet
)
```

---

## Performance Tips

### 1. Use Batching
```python
# ❌ Slow: 1000 individual calls
for text in texts:
    gen.generate([text])

# ✅ Fast: 1 batched call
gen.batch_generate(texts, batch_size=32)
```

### 2. Choose Right Model
```python
# Development/Testing: Fast
gen = get_embedding_generator(
    provider="local",
    model="all-MiniLM-L6-v2"  # 384 dims, ~5000 texts/s
)

# Production/Quality: Slower but better
gen = get_embedding_generator(
    provider="local",
    model="all-mpnet-base-v2"  # 768 dims, ~2000 texts/s
)
```

### 3. Leverage GPU
```python
# Auto-detects CUDA if available
gen = LocalEmbeddingGenerator()
# Check:
print(gen.get_info()['device'])  # 'cuda' or 'cpu'
```

### 4. Reuse Generator
```python
# Create once
gen = get_embedding_generator(provider="local")

# Reuse for multiple batches
embeddings1 = gen.batch_generate(texts1)
embeddings2 = gen.batch_generate(texts2)
# Don't create new generator each time!
```

---

## API Cheat Sheet

### LocalEmbeddingGenerator
```python
from pipeline.embeddings.embedding_generator import LocalEmbeddingGenerator

# Create
gen = LocalEmbeddingGenerator(
    model_name="all-MiniLM-L6-v2",  # Default
    device="cpu",                    # Auto-detects GPU
    normalize_embeddings=True,       # For similarity
    verbose=False
)

# Use
embeddings = gen.generate(["text1", "text2"])              # (2, 384)
embeddings = gen.batch_generate(texts, batch_size=32)     # Large scale
dimension = gen.get_dimension()                            # 384
model_name = gen.get_model_name()                          # "all-MiniLM-L6-v2"
info = gen.get_info()                                      # Dict
```

### OpenAIEmbeddingGenerator
```python
from pipeline.embeddings.embedding_generator import OpenAIEmbeddingGenerator

# Create
gen = OpenAIEmbeddingGenerator(
    model_name="text-embedding-3-small",  # Default
    api_key="sk-...",                     # Or OPENAI_API_KEY env
    verbose=False
)

# Use (same API as LocalEmbeddingGenerator)
embeddings = gen.generate(["text1", "text2"])              # (2, 512)
embeddings = gen.batch_generate(texts, batch_size=2000)   # OpenAI limit
```

### Factory Function
```python
from pipeline.embeddings.embedding_generator import get_embedding_generator

# Local
gen = get_embedding_generator(provider="local")
gen = get_embedding_generator(provider="local", model="all-mpnet-base-v2")

# OpenAI
gen = get_embedding_generator(provider="openai", api_key="sk-...")
gen = get_embedding_generator(provider="openai", model="text-embedding-3-large")
```

### Static Methods
```python
# Cosine similarity
similarity = LocalEmbeddingGenerator.cosine_similarity(vec1, vec2)
# Range: -1 (opposite) to 1 (identical)
```

---

## Next Steps

✅ **Completed:**
- Article search & extraction
- Text processing
- Embedding generation

📋 **Coming Soon:**
- Vector database (FAISS)
- Metadata indexing
- Pipeline orchestration
- Knowledge graph export

---

**For more details:** See documentation files in repository
- EMBEDDING_SEMANA1_COMPLETADA.md (Text processing)
- EMBEDDING_SEMANA2_COMPLETADA.md (Embeddings)
- PROJECT_PROGRESS.md (Overall roadmap)
