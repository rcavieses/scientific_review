#!/usr/bin/env python3
"""
API REST para el modelo RAG - acceso remoto para colegas.

Uso:
    python server_rag_api.py --host 0.0.0.0 --port 8000

Luego accede a:
    - API: http://localhost:8000/docs
    - Web UI: http://localhost:8000/
"""
import os
import sys
from pathlib import Path
from typing import Optional, List
import json
import logging
import re

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Modelos de datos ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    min_score: float = 0.2
    include_fishbase: bool = True
    include_chunks: bool = False

class Source(BaseModel):
    paper_id: str
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    score: float
    page: Optional[int] = None
    text: Optional[str] = None
    doi: Optional[str] = None
    doi_url: Optional[str] = None

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[Source]
    chunks_used: int
    model: str
    execution_time_ms: float
    fishbase_data: Optional[str] = None

class IndexStats(BaseModel):
    total_chunks: int
    total_papers: int
    embedding_model: str
    embedding_dimension: int
    last_updated: str

# ── Funciones auxiliares ────────────────────────────────────────────────

def extract_doi_from_text(text: Optional[str]) -> Optional[str]:
    """Extrae DOI del texto si existe."""
    if not text:
        return None

    # Buscar patrones comunes de DOI
    patterns = [
        r'https?://doi\.org/(10\.\S+?)(?:\s|$|["\'])',  # URL format
        r'doi\.org/(10\.\S+?)(?:\s|$|["\'])',  # Without protocol
        r'doi:\s*(10\.\S+?)(?:\s|$|["\'])',  # doi: prefix
        r'DOI:\s*(10\.\S+?)(?:\s|$|["\'])',  # DOI: uppercase
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    return None

# ── Inicialización ──────────────────────────────────────────────────────

app = FastAPI(
    title="ATLANTIS RAG Parameter Finder API",
    description="API para consultar parámetros de especies marinas del Golfo de California con RAG + FishBase",
    version="1.0.0"
)

# Variables globales (se cargan una vez)
_db = None
_engine = None
_index_stats = None
_fishbase_adapter = None

def init_rag_engine(index_dir: str = "outputs/rag_index_goc_full"):
    """Inicializa el motor RAG."""
    global _db, _engine, _index_stats, _fishbase_adapter

    try:
        from pipeline.rag import VectorDBManager
        from pipeline.rag.bm25_index import BM25IndexManager
        from pipeline.rag.hybrid_query_engine import HybridRAGQueryEngine
        from pipeline.llm import get_llm_provider

        index_path = Path(index_dir)
        config_file = index_path / "index_config.json"

        if not config_file.exists():
            raise FileNotFoundError(f"Índice no encontrado en {index_dir}")

        with open(config_file) as f:
            config = json.load(f)

        with open(index_path / "metadata_store.json", encoding="utf-8") as f:
            metadata_store = json.load(f)

        # Cargar base de datos vectorial (FAISS, semántico)
        _db = VectorDBManager(
            index_dir=index_path,
            embedding_dim=config["embedding_dimension"],
            verbose=False,
        )
        _db.load()
        _index_stats = _db.get_stats()

        # Cargar índice BM25 (léxico) — ver scripts/build_bm25_index.py
        bm25_index = BM25IndexManager(index_dir=index_path)
        if not bm25_index.load():
            raise FileNotFoundError(
                f"Índice BM25 no encontrado en {index_path}. "
                "Ejecuta: python3 scripts/build_bm25_index.py"
            )

        # Cargar sub-índice de tablas (opcional) — ver scripts/build_table_index.py
        table_index_path = index_path / "table_index"
        table_vector_db = None
        table_bm25_index = None
        if table_index_path.exists():
            table_vector_db = VectorDBManager(
                index_dir=table_index_path, embedding_dim=config["embedding_dimension"], verbose=False,
            )
            table_vector_db.load()
            table_bm25_index = BM25IndexManager(index_dir=table_index_path)
            table_bm25_index.load()
            logger.info(f"Canal de tablas cargado: {table_vector_db.get_stats().total_chunks} chunks")
        else:
            logger.warning(
                f"Sub-índice de tablas no encontrado en {table_index_path}. "
                "Ejecuta: python3 scripts/build_table_index.py (opcional, mejora respuestas con datos tabulares)"
            )

        # Crear motor RAG híbrido (fusión semántico + BM25 + tablas vía RRF)
        llm_provider = get_llm_provider(
            provider="claude",
            model="claude-haiku-4-5-20251001",
            verbose=False,
        )

        _engine = HybridRAGQueryEngine(
            vector_db=_db,
            bm25_index=bm25_index,
            metadata_store=metadata_store,
            model="claude-haiku-4-5-20251001",
            top_k=8,
            candidate_k=30,
            max_tokens=1500,
            min_score=0.0,
            llm_provider=llm_provider,
            verbose=False,
            table_vector_db=table_vector_db,
            table_bm25_index=table_bm25_index,
        )

        # Intentar cargar FishBase
        try:
            from database_connectors import FishBaseAdapter
            _fishbase_adapter = FishBaseAdapter(timeout=10, retry_delay=0.2)
            logger.info("FishBase adapter cargado ✓")
        except Exception as e:
            logger.warning(f"FishBase no disponible: {e}")

        logger.info(f"RAG Engine inicializado: {_index_stats.total_chunks} chunks")
        return True

    except Exception as e:
        logger.error(f"Error al inicializar RAG: {e}")
        return False

# ── Rutas de API ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Inicializar al arrancar."""
    if not init_rag_engine():
        logger.error("No se pudo inicializar el motor RAG")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Interfaz web principal."""
    return HTML_INTERFACE

@app.get("/api/stats", response_model=IndexStats)
async def get_stats():
    """Obtener estadísticas del índice."""
    if not _index_stats:
        raise HTTPException(status_code=503, detail="RAG no inicializado")

    return IndexStats(
        total_chunks=_index_stats.total_chunks,
        total_papers=_index_stats.total_papers,
        embedding_model=_index_stats.embedding_model,
        embedding_dimension=_index_stats.embedding_dimension,
        last_updated=_index_stats.last_updated.isoformat(),
    )

@app.post("/api/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """Ejecutar consulta RAG."""
    if not _engine:
        raise HTTPException(status_code=503, detail="RAG no inicializado")

    import time
    start = time.time()

    try:
        # Consulta RAG
        result = _engine.query(request.question)

        # FishBase: Consultar automáticamente si RAG tiene pocos resultados relevantes
        fishbase_data = None
        fishbase_species = None
        should_query_fishbase = False

        # Determinar si se debe consultar FishBase
        # 1. Si el usuario lo solicita explícitamente
        # 2. Si RAG retornó pocos resultados o con baja relevancia
        if _fishbase_adapter:
            low_quality_results = (
                request.include_fishbase or  # Usuario solicita explícitamente
                len(result.sources) < 3 or  # Muy pocos resultados
                (result.sources and result.sources[0].score < 0.5)  # Baja relevancia
            )

            if low_quality_results:
                should_query_fishbase = True

        if should_query_fishbase:
            try:
                import re

                # Extraer nombres de especies de la pregunta
                species_names = re.findall(r'\b([A-Z][a-z]+)\s+([a-z]+)\b', request.question)

                if species_names:
                    for genus, species_name in species_names[:2]:  # Máximo 2 especies
                        species = f"{genus} {species_name}"

                        try:
                            # Intentar validar y obtener parámetros
                            info = _fishbase_adapter.validate_species(species)
                            if info:
                                params = _fishbase_adapter.get_all_params(species, ecosystem="Gulf of California")
                                if params and params.parameters:
                                    fishbase_data = str(params.to_summary_dict())
                                    fishbase_species = species
                                    logger.info(f"✓ FishBase consultado para {species}: {len(params.parameters)} parámetros obtenidos")
                                    break  # Encontró datos, salir del loop
                        except Exception as e:
                            logger.debug(f"FishBase: no pudo obtener {species}: {str(e)[:50]}")
                            continue

            except Exception as e:
                logger.warning(f"Error en búsqueda FishBase fallback: {e}")

        # Formatear respuesta
        sources = []
        for s in result.sources:
            # Intentar obtener DOI: primero de metadatos, luego extraer del texto
            doi = s.doi or extract_doi_from_text(s.text)
            doi_url = f"https://doi.org/{doi}" if doi else None

            sources.append(Source(
                paper_id=s.paper_id,
                authors=s.authors,
                year=s.year,
                score=s.score,
                page=s.page_number,
                text=s.text[:300] if request.include_chunks and s.text else None,
                doi=doi,
                doi_url=doi_url,
            ))

        # Si tenemos datos de FishBase, enriquecer la respuesta con ellos
        final_answer = result.answer
        if fishbase_data:
            try:
                # Crear un prompt que enriquezca la respuesta con datos de FishBase
                enrichment_prompt = f"""La respuesta anterior no contenía información suficiente.
Aquí hay datos adicionales de FishBase para la especie {fishbase_species}:

{fishbase_data}

Por favor, enriquece tu respuesta anterior integrando estos datos de FishBase.
Combina información de ambas fuentes (papers científicos + FishBase) en una respuesta coherente.
Cita FishBase cuando uses sus datos."""

                enrichment_message = f"""Pregunta original: {request.question}

Datos de FishBase para {fishbase_species}:
{fishbase_data}

Respuesta anterior (basada en papers científicos):
{result.answer}

---

Por favor, crea una respuesta MEJORADA que integre TANTO los datos de los papers científicos COMO los datos de FishBase.
Destaca claramente qué información viene de cada fuente.
Usa el formato: [Fuente: FishBase] para datos de FishBase y [Autor et al., Año] para papers."""

                enriched_response = _llm_provider.generate(
                    system_prompt="Eres un asistente científico experto. Tu tarea es integrar información de múltiples fuentes (papers científicos y FishBase) para dar respuestas completas y precisas sobre especies marinas.",
                    user_message=enrichment_message,
                    max_tokens=1500,
                )

                if enriched_response and enriched_response.strip():
                    final_answer = enriched_response
                    logger.info(f"✓ Respuesta enriquecida con datos de FishBase ({fishbase_species})")
            except Exception as e:
                logger.warning(f"Error enriqueciendo respuesta con FishBase: {e}")
                # Usar la respuesta original si hay error

        elapsed = (time.time() - start) * 1000

        return QueryResponse(
            question=request.question,
            answer=final_answer,
            sources=sources,
            chunks_used=result.chunks_used,
            model=result.model,
            execution_time_ms=elapsed,
            fishbase_data=fishbase_data,
        )

    except Exception as e:
        logger.error(f"Error en consulta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    """Health check."""
    return {
        "status": "ok" if _engine else "error",
        "rag_initialized": _engine is not None,
        "fishbase_available": _fishbase_adapter is not None,
    }

# ── Interfaz HTML ────────────────────────────────────────────────────────

HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATLANTIS RAG Parameter Finder</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #0b2545 0%, #14487a 100%);
            min-height: 100vh;
            padding: 20px;
            color: #1a2733;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #0b2545 0%, #14487a 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 0.95em; }
        .content {
            padding: 40px 30px;
        }
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .search-box input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #cddbe8;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }
        .search-box input:focus {
            outline: none;
            border-color: #14487a;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .search-box button {
            padding: 12px 30px;
            background: #14487a;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.3s;
        }
        .search-box button:hover {
            background: #0d3660;
        }
        .search-box button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .options {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        .option { display: flex; align-items: center; gap: 5px; }
        .option input[type="checkbox"] { cursor: pointer; }
        .option label { cursor: pointer; }
        .results {
            display: none;
            animation: slideIn 0.3s ease;
        }
        .results.show { display: block; }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .answer-box {
            background: #eef4fa;
            border-left: 4px solid #14487a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            line-height: 1.6;
        }
        .answer-box h2 {
            font-size: 1.4em;
            margin: 15px 0 10px 0;
            color: #333;
            border-bottom: 2px solid #14487a;
            padding-bottom: 8px;
        }
        .answer-box h3 {
            font-size: 1.1em;
            margin: 12px 0 8px 0;
            color: #444;
        }
        .answer-box h4 {
            font-size: 1em;
            margin: 10px 0 6px 0;
            color: #555;
        }
        .answer-box ul, .answer-box ol {
            margin: 10px 0 10px 20px;
        }
        .answer-box li {
            margin: 5px 0;
        }
        .answer-box strong {
            color: #333;
        }
        .answer-box code {
            background: #dce9f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .answer-box blockquote {
            border-left: 4px solid #0b2545;
            padding-left: 15px;
            margin: 10px 0;
            color: #666;
            font-style: italic;
        }
        .answer-box p {
            margin: 8px 0;
        }
        .sources-box {
            background: #eef4fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .sources-box h3 {
            margin-bottom: 15px;
            color: #333;
        }
        .source {
            padding: 12px;
            background: white;
            border-left: 3px solid #0b2545;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .source-title {
            font-weight: 600;
            color: #14487a;
        }
        .source-meta {
            font-size: 0.85em;
            color: #666;
            margin-top: 5px;
        }
        .source-score {
            display: inline-block;
            background: #14487a;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            margin-left: 10px;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 30px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #14487a;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .error {
            background: #fee;
            border: 1px solid #fcc;
            color: #c33;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .success-badge {
            display: inline-block;
            background: #4caf50;
            color: white;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.85em;
            margin-left: 10px;
        }
        .time-badge {
            display: inline-block;
            background: #2c6ca8;
            color: white;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.85em;
            margin-left: 10px;
        }
        .fishbase-box {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        .fishbase-box h4 {
            color: #2e7d32;
            margin-bottom: 10px;
        }
        .stats {
            background: #eef4fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            font-size: 0.9em;
            color: #666;
            margin-bottom: 20px;
        }
        .stats span {
            font-weight: 600;
            color: #14487a;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌊 ATLANTIS RAG Parameter Finder</h1>
            <p>Búsqueda de parámetros ecológicos de especies marinas del Golfo de California</p>
        </div>

        <div class="content">
            <div class="search-box">
                <input
                    type="text"
                    id="question"
                    placeholder="Ej: ¿Cuál es la talla máxima del Huachinango?"
                    onkeypress="if(event.key==='Enter') query()"
                >
                <button onclick="query()" id="searchBtn">Buscar</button>
            </div>

            <div class="options">
                <div class="option">
                    <input type="checkbox" id="fishbase" checked>
                    <label for="fishbase">Incluir FishBase</label>
                </div>
                <div class="option">
                    <input type="checkbox" id="chunks">
                    <label for="chunks">Mostrar fragmentos</label>
                </div>
            </div>

            <div class="stats" id="stats"></div>

            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Buscando en papers científicos...</p>
            </div>

            <div id="error"></div>

            <div class="results" id="results">
                <div id="answer"></div>
                <div id="fishbase"></div>
                <div id="sources"></div>
            </div>
        </div>
    </div>

    <script>
        let stats = null;

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                stats = await res.json();
                document.getElementById('stats').innerHTML =
                    `Índice: <span>${stats.total_chunks}</span> chunks de <span>${stats.total_papers}</span> papers`;
            } catch (e) {
                console.error('Error cargando stats:', e);
            }
        }

        async function query() {
            const question = document.getElementById('question').value.trim();
            if (!question) return;

            const includeFishbase = document.getElementById('fishbase').checked;
            const includeChunks = document.getElementById('chunks').checked;

            document.getElementById('loading').style.display = 'block';
            document.getElementById('error').innerHTML = '';
            document.getElementById('results').classList.remove('show');

            try {
                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question,
                        include_fishbase: includeFishbase,
                        include_chunks: includeChunks,
                        top_k: 5,
                    }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Error en la consulta');
                }

                const data = await res.json();
                displayResults(data);
            } catch (e) {
                document.getElementById('error').innerHTML =
                    `<div class="error">❌ Error: ${e.message}</div>`;
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }

        function displayResults(data) {
            // Respuesta - parse markdown
            const parsedAnswer = marked.parse(data.answer);
            const answerHtml = `
                <div class="answer-box">
                    <strong>Respuesta:</strong> <span class="time-badge">${data.execution_time_ms.toFixed(0)}ms</span>
                    <div style="margin-top: 15px;">${parsedAnswer}</div>
                </div>
            `;
            document.getElementById('answer').innerHTML = answerHtml;

            // FishBase
            if (data.fishbase_data) {
                const fishbaseHtml = `
                    <div class="fishbase-box">
                        <h4>🐟 Datos de FishBase</h4>
                        <pre style="font-size: 0.9em; overflow-x: auto;">${data.fishbase_data}</pre>
                    </div>
                `;
                document.getElementById('fishbase').innerHTML = fishbaseHtml;
            }

            // Fuentes
            if (data.sources.length > 0) {
                let sourcesHtml = `<div class="sources-box"><h3>📚 Fuentes (${data.sources.length} fragmentos)</h3>`;
                data.sources.forEach(s => {
                    const authors = s.authors ? s.authors.slice(0, 2).join(', ') : 'Autor desconocido';
                    const year = s.year ? ` (${s.year})` : '';
                    sourcesHtml += `
                        <div class="source">
                            <div class="source-title">${s.paper_id}${year}</div>
                            <div class="source-meta">
                                ${authors}
                                <span class="source-score">${(s.score * 100).toFixed(0)}%</span>
                            </div>
                            ${s.text ? `<div style="margin-top: 8px; font-size: 0.85em; color: #555;">${s.text}...</div>` : ''}
                        </div>
                    `;
                });
                sourcesHtml += '</div>';
                document.getElementById('sources').innerHTML = sourcesHtml;
            }

            document.getElementById('results').classList.add('show');
        }

        // Cargar estadísticas al iniciar
        loadStats();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="Host del servidor")
    parser.add_argument("--port", type=int, default=8000, help="Puerto del servidor")
    parser.add_argument("--index-dir", default="outputs/rag_index_goc_full", help="Directorio del índice")
    parser.add_argument("--reload", action="store_true", help="Recargar código cambios")
    args = parser.parse_args()

    uvicorn.run(
        "server_rag_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
