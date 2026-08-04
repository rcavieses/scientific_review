#!/usr/bin/env python3
"""
FastAPI Server + Web UI para RAG del Golfo de California.

Usa GROBID para extracción de PDFs + FAISS para búsqueda semántica + Claude LLM.

Uso:
    python scripts/server_rag.py --host 0.0.0.0 --port 8000

Acceso:
    - UI Web: http://localhost:8000
    - Docs: http://localhost:8000/docs
"""

import os
import sys
import time
import argparse
from pathlib import Path
from typing import Optional, List
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add project to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.rag.vector_db import VectorDBManager
from pipeline.embeddings.embedding_generator import get_embedding_generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Data Models ──────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    min_score: float = 0.2

class Source(BaseModel):
    paper_id: str
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    score: float
    page: Optional[int] = None
    text: Optional[str] = None

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[Source]
    chunks_used: int
    model: str
    execution_time_ms: float

class IndexStats(BaseModel):
    total_chunks: int
    total_papers: int
    embedding_model: str
    embedding_dimension: int
    index_size_mb: float
    last_updated: str

# ── Initialize FastAPI ──────────────────────────────────────────────────

app = FastAPI(
    title="Scientific Review RAG - Golfo de California",
    description="Semantic search + LLM for marine species research",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables (initialized once)
_query_engine = None
_vector_db = None

def get_query_engine():
    """Lazy load query engine."""
    global _query_engine, _vector_db

    if _query_engine is None:
        logger.info("Initializing query engine...")

        _vector_db = VectorDBManager(
            index_dir=Path("outputs/rag_index_goc"),
            embedding_dim=384
        )
        _vector_db.load()

        embedding_gen = get_embedding_generator(provider="local", verbose=False)

        _query_engine = RAGQueryEngine(
            vector_db=_vector_db,
            embedding_generator=embedding_gen,
            model="claude-haiku-4-5-20251001",
            top_k=5,
            verbose=False
        )

        logger.info("Query engine initialized ✓")

    return _query_engine

# ── HTML UI ──────────────────────────────────────────────────────────────

HTML_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scientific Review RAG - Golfo de California</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }

        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
            margin-bottom: 20px;
        }

        .query-section {
            margin-bottom: 30px;
        }

        .query-section label {
            display: block;
            font-weight: 600;
            margin-bottom: 10px;
            color: #333;
        }

        .input-group {
            display: flex;
            gap: 10px;
        }

        #questionInput {
            flex: 1;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }

        #questionInput:focus {
            outline: none;
            border-color: #667eea;
        }

        button {
            padding: 12px 30px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }

        button:hover {
            background: #5568d3;
        }

        button:active {
            transform: scale(0.98);
        }

        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        .results {
            display: none;
        }

        .results.show {
            display: block;
        }

        .answer-section {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }

        .answer-section h3 {
            margin-bottom: 10px;
            color: #333;
        }

        .answer-text {
            line-height: 1.6;
            color: #555;
        }

        .answer-text h1, .answer-text h2, .answer-text h3, .answer-text h4, .answer-text h5 {
            margin-top: 1em;
            margin-bottom: 0.5em;
            color: #333;
        }

        .answer-text ul, .answer-text ol {
            margin-left: 1.5em;
            margin-bottom: 1em;
        }

        .answer-text li {
            margin-bottom: 0.5em;
        }

        .answer-text strong {
            font-weight: 600;
            color: #333;
        }

        .answer-text code {
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }

        .answer-text pre {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            margin-bottom: 1em;
        }

        .answer-text pre code {
            background: none;
            padding: 0;
        }

        .answer-text blockquote {
            border-left: 4px solid #667eea;
            padding-left: 15px;
            margin-left: 0;
            color: #666;
        }

        .answer-text table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1em;
        }

        .answer-text th, .answer-text td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }

        .answer-text th {
            background: #f8f9fa;
            font-weight: 600;
        }

        .sources-section {
            margin-top: 20px;
        }

        .sources-section h3 {
            margin-bottom: 15px;
            color: #333;
        }

        .source-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }

        .source-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }

        .source-citation {
            font-weight: 600;
            color: #333;
            flex: 1;
        }

        .source-authors {
            color: #555;
        }

        .source-score {
            display: inline-block;
            background: #e0e7ff;
            color: #667eea;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
            white-space: nowrap;
            margin-left: 10px;
        }

        .source-text {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            font-size: 0.95em;
            line-height: 1.5;
            color: #555;
            margin-bottom: 10px;
            border-left: 2px solid #e0e7ff;
        }

        .source-meta {
            font-size: 0.85em;
            color: #999;
        }

        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }

        .loading.show {
            display: block;
        }

        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .stat-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }

        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }

        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }

        .error {
            background: #fee;
            border-left: 4px solid #e74c3c;
            padding: 15px;
            border-radius: 8px;
            color: #c0392b;
            display: none;
            margin-bottom: 20px;
        }

        .error.show {
            display: block;
        }

        .info-box {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            color: #1976d2;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌊 Scientific Review RAG</h1>
            <p>Semantic search on marine biodiversity papers from the Gulf of California</p>
        </div>

        <div class="card">
            <div class="info-box">
                📚 433 scientific papers indexed | 10,504 chunks | GROBID + FAISS + Claude
            </div>

            <div class="query-section">
                <label for="questionInput">Ask about marine species in the Gulf of California:</label>
                <div class="input-group">
                    <input
                        type="text"
                        id="questionInput"
                        placeholder="e.g., What is the size range of Huachinango? ¿Cuáles son las especies de arrecife?"
                        onkeypress="handleKeyPress(event)"
                    >
                    <button onclick="submitQuery()">Search</button>
                </div>
            </div>

            <div class="error" id="errorBox"></div>
            <div class="loading" id="loadingBox"><div class="spinner"></div><p>Searching...</p></div>

            <div class="results" id="resultsBox">
                <div class="answer-section">
                    <h3>Answer</h3>
                    <div class="answer-text" id="answerText"></div>
                </div>

                <div class="sources-section">
                    <h3>Sources (<span id="sourcesCount">0</span> chunks)</h3>
                    <div id="sourcesList"></div>
                </div>

                <div style="font-size: 0.85em; color: #999; margin-top: 15px;">
                    Execution time: <span id="executionTime">0</span>ms | Model: <span id="modelName">Claude Haiku</span>
                </div>
            </div>
        </div>

        <div class="card">
            <h2 style="margin-bottom: 20px;">Index Statistics</h2>
            <div class="stats" id="statsContainer">
                <div class="stat-item"><div class="stat-value">-</div><div class="stat-label">Papers</div></div>
                <div class="stat-item"><div class="stat-value">-</div><div class="stat-label">Chunks</div></div>
                <div class="stat-item"><div class="stat-value">-</div><div class="stat-label">Model</div></div>
            </div>
        </div>
    </div>

    <script>
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();

                const statsHtml = `
                    <div class="stat-item"><div class="stat-value">${data.total_papers}</div><div class="stat-label">Papers</div></div>
                    <div class="stat-item"><div class="stat-value">${data.total_chunks.toLocaleString()}</div><div class="stat-label">Chunks</div></div>
                    <div class="stat-item"><div class="stat-value">${data.embedding_dimension}</div><div class="stat-label">Dimensions</div></div>
                    <div class="stat-item"><div class="stat-value">${data.index_size_mb.toFixed(1)}MB</div><div class="stat-label">Index Size</div></div>
                `;

                document.getElementById('statsContainer').innerHTML = statsHtml;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        async function submitQuery() {
            const question = document.getElementById('questionInput').value.trim();

            if (!question) {
                showError('Please enter a question');
                return;
            }

            showLoading();
            hideError();
            hideResults();

            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: question,
                        top_k: 5,
                        min_score: 0.2
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Query failed');
                }

                const data = await response.json();
                displayResults(data);

            } catch (error) {
                showError(error.message);
            } finally {
                hideLoading();
            }
        }

        function extractYearFromPaperId(paperId) {
            // Try to extract year from paper_id (format: "2021SomeName..." or similar)
            const match = paperId.match(/^(\d{4})/);
            return match ? parseInt(match[1]) : null;
        }

        function displayResults(data) {
            document.getElementById('answerText').innerHTML = marked.parse(data.answer);
            document.getElementById('sourcesCount').textContent = data.chunks_used;
            document.getElementById('executionTime').textContent = data.execution_time_ms.toFixed(0);
            document.getElementById('modelName').textContent = data.model;

            const sourcesList = data.sources.map((source, i) => {
                const authors = source.authors && source.authors.length > 0
                    ? source.authors.slice(0, 3).join(', ') + (source.authors.length > 3 ? ' et al.' : '')
                    : 'Unknown Authors';

                // Extract year from paper_id if not available
                const year = source.year || extractYearFromPaperId(source.paper_id) || 'N/A';

                // Format paper_id more nicely (remove leading year)
                const displayId = source.paper_id.replace(/^\d{4}/, '').substring(0, 50);

                // Format text preview
                const textPreview = source.text ? source.text.substring(0, 300) + (source.text.length > 300 ? '...' : '') : 'No text available';

                return `
                    <div class="source-item">
                        <div class="source-header">
                            <div class="source-citation">
                                <div class="source-authors">${authors}, ${year}</div>
                                <div style="font-size: 0.85em; color: #999; margin-top: 3px;">${displayId}</div>
                            </div>
                            <span class="source-score">${(source.score * 100).toFixed(1)}%</span>
                        </div>
                        <div class="source-text">${textPreview}</div>
                        <div class="source-meta">
                            Page: ${source.page} | Chunk ${i + 1} of ${data.sources.length}
                        </div>
                    </div>
                `;
            }).join('');

            document.getElementById('sourcesList').innerHTML = sourcesList;
            showResults();
        }

        function showLoading() {
            document.getElementById('loadingBox').classList.add('show');
        }

        function hideLoading() {
            document.getElementById('loadingBox').classList.remove('show');
        }

        function showResults() {
            document.getElementById('resultsBox').classList.add('show');
        }

        function hideResults() {
            document.getElementById('resultsBox').classList.remove('show');
        }

        function showError(message) {
            const errorBox = document.getElementById('errorBox');
            errorBox.textContent = '❌ ' + message;
            errorBox.classList.add('show');
        }

        function hideError() {
            document.getElementById('errorBox').classList.remove('show');
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                submitQuery();
            }
        }

        // Load stats on page load
        loadStats();
    </script>
</body>
</html>
"""

# ── API Endpoints ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("Server starting up...")
    try:
        get_query_engine()
        logger.info("✓ RAG system initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize RAG system: {e}")

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serve the web UI."""
    return HTML_UI

@app.get("/api/stats", response_model=IndexStats)
async def get_stats():
    """Get index statistics."""
    try:
        engine = get_query_engine()
        stats = engine.vector_db.get_stats()
        return IndexStats(
            total_chunks=stats.total_chunks,
            total_papers=stats.total_papers,
            embedding_model=stats.embedding_model,
            embedding_dimension=stats.embedding_dimension,
            index_size_mb=stats.index_size_mb,
            last_updated=stats.last_updated.isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Execute a semantic search query."""
    try:
        start_time = time.time()
        engine = get_query_engine()

        result = engine.query(request.question)

        execution_time_ms = (time.time() - start_time) * 1000

        sources = [
            Source(
                paper_id=source.paper_id,
                authors=source.authors,
                year=source.year,
                score=source.score,
                page=source.page_number,
                text=source.text[:200] if source.text else None
            )
            for source in result.sources
        ]

        return QueryResponse(
            question=request.question,
            answer=result.answer,
            sources=sources,
            chunks_used=result.chunks_used,
            model=result.model,
            execution_time_ms=execution_time_ms
        )

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "Scientific Review RAG"}

# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RAG Web Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    logger.info(f"Starting server at http://{args.host}:{args.port}")
    logger.info(f"UI: http://{args.host}:{args.port}")
    logger.info(f"API Docs: http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "scripts.server_rag:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
