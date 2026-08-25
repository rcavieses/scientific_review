#!/usr/bin/env python3
"""Tablero de revisión manual de parámetros con asistencia RAG.

Servidor independiente: NO modifica ni importa scripts/phase_6_query/server_rag_api.py.
La inicialización del motor RAG está copiada de ahí para poder evolucionar por
separado.

Uso:
    python3 scripts/phase_7_review/review_server.py            # http://127.0.0.1:8600
    python3 scripts/phase_7_review/review_server.py --port 8700 --host 0.0.0.0

    # Protegido con contraseña (obligatorio si se expone con ngrok o similar):
    REVIEW_PASSWORD='…' python3 scripts/phase_7_review/review_server.py

Requiere haber construido antes la cola:
    python3 scripts/phase_7_review/build_review_queue.py
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import secrets
import sys
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(HERE))          # para importar build_review_queue

STATIC_DIR = HERE / "static"
REVIEW_DIR = PROJECT_ROOT / "outputs" / "review"
QUEUE_FILE = REVIEW_DIR / "review_queue.json"
DECISIONS_FILE = REVIEW_DIR / "decisions.json"
RAG_CACHE_FILE = REVIEW_DIR / "rag_evidence.json"
FB_FILE = REVIEW_DIR / "fishbase_suggestions.json"
EXPORT_CSV = REVIEW_DIR / "Atlantis_GOC_parametros_consolidado.csv"
EXPORT_PROV = REVIEW_DIR / "Atlantis_GOC_procedencia.csv"
INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("review")

_engines: dict[str, object] = {}      # "semantic" | "hybrid"
_store: dict | None = None            # metadata_store.json, indexado por chunk y por paper
_by_chunk: dict[str, dict] = {}
_by_paper: dict[str, list[dict]] = {}
_store_lock = threading.Lock()
PDF_ROOTS = [PROJECT_ROOT / "outputs" / "PDF_GOC"]
_index_stats = None
_engine_lock = threading.Lock()
_write_lock = threading.Lock()
DEFAULT_ENGINE = "semantic"


# ── modelos ─────────────────────────────────────────────────────────────

class RagRequest(BaseModel):
    item_id: Optional[str] = None
    question: Optional[str] = None
    engine: str = "semantic"          # semantic | hybrid
    top_k: int = 8
    include_chunks: bool = True


class Decision(BaseModel):
    item_id: str
    status: str              # accepted | rejected | pending | needs_more_evidence
    value: Optional[str] = None
    source: Optional[str] = None   # B1..B6 | RAG | externo | IA | manual | ninguna
    # Referencia cuando el respaldo NO está en el corpus (FishBase, Birds of the
    # World, IUCN, un paper no indexado…). Hay parámetros que el corpus no puede
    # respaldar por su alcance —la migración de un ave playera, por ejemplo— y sin
    # este campo esa evidencia no tendría dónde quedar registrada.
    reference: str = ""
    reviewer: str = ""
    comment: str = ""


# ── motor RAG (copiado de scripts/phase_6_query/server_rag_api.py) ──────

REVIEW_SYSTEM_PROMPT = """You are a scientific data auditor for the Atlantis Gulf of \
California ecosystem model. Several automated extraction runs disagree on a parameter \
value and a human reviewer must adjudicate.

Rules:
1. Answer ONLY from the provided document fragments. Never fill gaps with general \
   knowledge about the taxon — that is exactly the failure mode under audit.
2. If the fragments contain no value for the species and parameter asked, reply with \
   "NO EVIDENCE IN CORPUS" and nothing else beyond a one-line explanation.
3. When you report a value, quote the sentence or table cell it comes from and cite the \
   paper (author/year or paper id) and page.
4. State the units explicitly and flag any unit mismatch, life-stage difference, sex, or \
   study area that could explain the disagreement between candidate values.
5. If the fragments describe a different species than the one asked, say so plainly \
   instead of transferring the value.
6. Be concise: verdict first, then evidence."""

# Modelo de la asistencia de revisión (el mismo con el que corrió la búsqueda 5).
REVIEW_MODEL = "claude-sonnet-5"


def init_rag_engine(kind: str = DEFAULT_ENGINE, index_dir: Path = INDEX_DIR):
    """Inicializa (perezosamente) el motor RAG pedido.

    "semantic" — FAISS puro, el mismo que corrió B1–B5.
    "hybrid"   — FAISS + BM25 fusionados por RRF; requiere bm25_index.pkl.

    Ambos se cachean por separado para poder comparar la misma celda con los dos.
    """
    global _index_stats
    if kind in _engines:
        return _engines[kind]

    with _engine_lock:
        if kind in _engines:
            return _engines[kind]

        from pipeline.rag import VectorDBManager
        from pipeline.llm import get_llm_provider
        from scripts.section_aware_engine import SectionAwareRAGQueryEngine, load_sections

        config_file = index_dir / "index_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Índice no encontrado en {index_dir}")
        config = json.loads(config_file.read_text())

        db = _engines.get("_db")
        if db is None:
            logger.info("Cargando índice semántico…")
            db = VectorDBManager(index_dir=str(index_dir),
                                 embedding_dim=config["embedding_dimension"], verbose=False)
            db.load()
            _index_stats = db.get_stats()
            _engines["_db"] = db

        # thinking desactivado: el presupuesto de tokens va completo a la respuesta,
        # igual que en las búsquedas B4/B5.
        provider = get_llm_provider(provider="claude", model=REVIEW_MODEL,
                                    verbose=False, thinking={"type": "disabled"})

        if kind == "hybrid":
            from pipeline.rag.bm25_index import BM25IndexManager
            from pipeline.rag.hybrid_query_engine import HybridRAGQueryEngine

            bm25 = BM25IndexManager(index_dir=index_dir)
            if not bm25.load():
                raise FileNotFoundError(
                    "Índice BM25 no encontrado. Ejecuta: python3 scripts/build_bm25_index.py")
            metadata_store = json.loads(
                (index_dir / "metadata_store.json").read_text(encoding="utf-8"))

            table_vector_db = table_bm25 = None
            table_path = index_dir / "table_index"
            if table_path.exists():
                table_vector_db = VectorDBManager(
                    index_dir=table_path,
                    embedding_dim=config["embedding_dimension"], verbose=False)
                table_vector_db.load()
                table_bm25 = BM25IndexManager(index_dir=table_path)
                table_bm25.load()
                logger.info("Canal de tablas cargado ✓")

            engine = HybridRAGQueryEngine(
                vector_db=db, bm25_index=bm25, metadata_store=metadata_store,
                model=REVIEW_MODEL, top_k=10, candidate_k=30, max_tokens=2000,
                min_score=0.0, llm_provider=provider, verbose=False,
                table_vector_db=table_vector_db, table_bm25_index=table_bm25,
            )
            # El híbrido no expone system_prompt en su constructor, pero lo hereda
            # de RAGQueryEngine: se fija aquí para que ambos motores auditen igual.
            engine.system_prompt = REVIEW_SYSTEM_PROMPT
            engine.thinking = {"type": "disabled"}
            logger.info("Motor híbrido (semántico + BM25) listo")
        else:
            # Mismo motor semántico de B1–B5, más el relegado de bibliografía:
            # sin él, el 68 % de las consultas por especie arrastra referencias.
            engine = SectionAwareRAGQueryEngine(
                vector_db=db, model=REVIEW_MODEL, top_k=10, min_score=0.15,
                max_tokens=2000, verbose=False, llm_provider=provider,
                system_prompt=REVIEW_SYSTEM_PROMPT, thinking={"type": "disabled"},
                sections=load_sections(index_dir),
            )
            logger.info("Motor semántico + relegado de bibliografía listo")

        _engines[kind] = engine
        logger.info("Motor RAG listo: %s chunks", getattr(_index_stats, "total_chunks", "?"))
        return engine


# ── persistencia ────────────────────────────────────────────────────────

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("JSON corrupto en %s, se ignora", path)
    return default


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def get_queue() -> dict:
    if not QUEUE_FILE.exists():
        raise HTTPException(503, "Falta review_queue.json. Ejecuta build_review_queue.py")
    return load_json(QUEUE_FILE, {})


def item_by_id(item_id: str) -> dict:
    for item in get_queue()["items"]:
        if item["id"] == item_id:
            return item
    raise HTTPException(404, f"Celda no encontrada: {item_id}")


# ── metadatos de los chunks y sus PDF ───────────────────────────────────
# El índice NO contiene bibliografía real: `title` y `doi` están vacíos en los
# 18 080 chunks, y `authors`/`year` se derivaron del nombre del archivo. Lo que sí
# hay es el texto de la portada (chunk 0 de cada paper), donde suelen estar el
# título, la revista y el DOI, y el PDF original en disco.

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;)\]]+)")


def load_store() -> dict:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        path = INDEX_DIR / "metadata_store.json"
        if not path.exists():
            raise HTTPException(503, f"No existe {path}")
        logger.info("Cargando metadata_store (38 MB)…")
        store = json.loads(path.read_text(encoding="utf-8"))
        for record in store.values():
            _by_chunk[record["chunk_id"]] = record
            _by_paper.setdefault(record["paper_id"], []).append(record)
        for chunks in _by_paper.values():
            chunks.sort(key=lambda r: r.get("chunk_index", 0))
        _store = store
        logger.info("Metadatos listos: %s chunks · %s papers", len(_by_chunk), len(_by_paper))
        return _store


def find_doi(*texts: str) -> Optional[str]:
    for text in texts:
        if not text:
            continue
        match = DOI_RE.search(text)
        if match:
            return match.group(1).rstrip(".,;")
    return None


def paper_pdf_path(paper_id: str) -> Optional[Path]:
    """Ruta del PDF, sólo si cae dentro de los directorios permitidos."""
    load_store()
    chunks = _by_paper.get(paper_id)
    if not chunks:
        return None
    raw = chunks[0].get("source_pdf")
    if not raw:
        return None
    path = Path(raw).resolve()
    if not any(str(path).startswith(str(root.resolve())) for root in PDF_ROOTS):
        logger.warning("PDF fuera de los directorios permitidos: %s", path)
        return None
    return path if path.exists() else None


# ── pregunta RAG por celda ──────────────────────────────────────────────

def build_question(item: dict) -> str:
    """Pregunta dirigida: qué valor sostiene la literatura para esta celda."""
    species = item["species"]
    label, unit = item["param_label"], item["unit"]
    candidates = ", ".join(f"{k}={v}" for k, v in item["values"].items())
    unit_txt = f" (unidades: {unit})" if unit else ""

    if item["kind"] == "cat":
        return (
            f"For the species {species} ({item.get('family') or 'n/a'}) in the Gulf of California: "
            f"is it a migratory species? Answer strictly from the indexed literature. "
            f"Quote the sentence and cite the paper that supports the answer. "
            f"If the documents do not state it, say explicitly 'NO EVIDENCE IN CORPUS' — "
            f"do not infer it from general knowledge of the taxon. "
            f"Conflicting extractions to adjudicate: {candidates}."
        )
    return (
        f"For the species {species} ({item.get('family') or 'n/a'}) in the Gulf of California: "
        f"what value does the literature report for {label} ({item['param']}){unit_txt}? "
        f"Report the exact figure, its units, the study area and the paper it comes from. "
        f"Different extraction runs disagree: {candidates}. "
        f"State which of those values (if any) the documents actually support, and flag any "
        f"unit conversion or life-stage difference that would explain the discrepancy. "
        f"If the corpus contains no value for this species, answer 'NO EVIDENCE IN CORPUS'."
    )


# ── aplicación ──────────────────────────────────────────────────────────

app = FastAPI(title="Revisión de parámetros · Atlantis GOC", version="1.0.0")

# ── acceso ──────────────────────────────────────────────────────────────
# Sin contraseña el tablero queda abierto: cualquiera que alcance el puerto puede
# escribir decisiones y disparar consultas RAG, que cuestan créditos de API. Al
# publicarlo (ngrok, 0.0.0.0, etc.) hay que definir REVIEW_PASSWORD.

REVIEW_USER = os.environ.get("REVIEW_USER", "revisor")
_password: Optional[str] = None


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not _password:
        return await call_next(request)

    header = request.headers.get("authorization", "")
    if header.startswith("Basic "):
        try:
            user, _, password = base64.b64decode(header[6:]).decode("utf-8").partition(":")
        except (ValueError, UnicodeDecodeError):
            user = password = ""
        if secrets.compare_digest(user, REVIEW_USER) and secrets.compare_digest(password, _password):
            return await call_next(request)

    return Response(
        status_code=401,
        content="Acceso restringido",
        headers={"WWW-Authenticate": 'Basic realm="Revisión de parámetros Atlantis GOC"'},
    )


@app.get("/api/paper/{paper_id}")
def api_paper(paper_id: str):
    """Ficha del documento: portada, DOI detectado y disponibilidad del PDF."""
    load_store()
    chunks = _by_paper.get(paper_id)
    if not chunks:
        raise HTTPException(404, f"Documento desconocido: {paper_id}")

    cover = chunks[0]
    pdf = paper_pdf_path(paper_id)
    return {
        "paper_id": paper_id,
        "year": cover.get("year"),
        # Se devuelve tal cual, pero la interfaz lo etiqueta como derivado del
        # nombre de archivo: no es una lista de autores verificada.
        "authors_from_filename": cover.get("authors") or [],
        "n_chunks": len(chunks),
        "pages": max((c.get("page_number") or 0) for c in chunks),
        "cover_text": (cover.get("text") or "")[:2000],
        "doi": find_doi(cover.get("text", "")),
        "pdf_available": pdf is not None,
        "pdf_name": pdf.name if pdf else None,
    }


@app.get("/api/chunk/{chunk_id}")
def api_chunk(chunk_id: str):
    """Texto íntegro del fragmento citado, con su contexto en el documento."""
    load_store()
    record = _by_chunk.get(chunk_id)
    if not record:
        raise HTTPException(404, f"Fragmento desconocido: {chunk_id}")
    return {
        "chunk_id": chunk_id,
        "paper_id": record["paper_id"],
        "page": record.get("page_number"),
        "chunk_index": record.get("chunk_index"),
        "total_chunks": record.get("total_chunks"),
        "text": record.get("text", ""),
        "doi": find_doi(record.get("text", "")),
    }


@app.get("/api/pdf/{paper_id}")
def api_pdf(paper_id: str):
    """Sirve el PDF original para poder abrirlo en la página citada (#page=N)."""
    pdf = paper_pdf_path(paper_id)
    if not pdf:
        raise HTTPException(404, "PDF no disponible para este documento")
    return FileResponse(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{pdf.name}"'})


@app.get("/api/queue")
def api_queue():
    queue = get_queue()
    queue["decisions"] = load_json(DECISIONS_FILE, {})
    queue["rag_cached"] = sorted({k.partition("|")[0] for k in load_json(RAG_CACHE_FILE, {})})
    queue["default_engine"] = DEFAULT_ENGINE
    return queue


@app.get("/api/decisions")
def api_decisions():
    return load_json(DECISIONS_FILE, {})


@app.post("/api/decision")
def api_decision(decision: Decision):
    valid = {"accepted", "rejected", "pending", "needs_more_evidence"}
    if decision.status not in valid:
        raise HTTPException(400, f"status debe ser uno de {sorted(valid)}")
    item = item_by_id(decision.item_id)

    with _write_lock:
        decisions = load_json(DECISIONS_FILE, {})
        if decision.status == "pending":
            decisions.pop(decision.item_id, None)
        else:
            history = decisions.get(decision.item_id, {}).get("history", [])
            previous = decisions.get(decision.item_id)
            if previous:
                history = history + [{k: previous[k] for k in
                                      ("status", "value", "source", "reviewer", "updated_at")
                                      if k in previous}]
            decisions[decision.item_id] = {
                "item_id": decision.item_id,
                "species": item["species"],
                "group": item["group"],
                "param": item["param"],
                "status": decision.status,
                "value": decision.value,
                "source": decision.source,
                "reference": decision.reference.strip(),
                "reviewer": decision.reviewer.strip(),
                "comment": decision.comment.strip(),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "history": history[-10:],
            }
        save_json(DECISIONS_FILE, decisions)
    return {"ok": True, "decisions": len(load_json(DECISIONS_FILE, {}))}


@app.get("/api/rag/cached/{item_id:path}")
def api_rag_cached(item_id: str):
    """Todas las consultas guardadas de una celda, indexadas por motor."""
    cache = load_json(RAG_CACHE_FILE, {})
    out = {}
    for key, payload in cache.items():
        cell, _, engine = key.partition("|")
        if cell == item_id:
            out[engine or "semantic"] = payload
    return out


@app.post("/api/rag")
def api_rag(request: RagRequest):
    """Consulta RAG en vivo. Se cachea por celda para no repetir el gasto."""
    if not request.item_id and not request.question:
        raise HTTPException(400, "Se requiere item_id o question")

    if request.engine not in {"semantic", "hybrid"}:
        raise HTTPException(400, "engine debe ser 'semantic' o 'hybrid'")

    item = item_by_id(request.item_id) if request.item_id else None
    question = request.question or build_question(item)

    try:
        engine = init_rag_engine(request.engine)
    except Exception as exc:                      # noqa: BLE001
        logger.exception("No se pudo inicializar el RAG")
        raise HTTPException(503, f"RAG no disponible: {exc}") from exc

    start = time.time()
    try:
        result = engine.query(question)
    except Exception as exc:                      # noqa: BLE001
        logger.exception("Error en consulta RAG")
        raise HTTPException(500, f"Error en la consulta: {exc}") from exc

    sources = [{
        "chunk_id": getattr(s, "chunk_id", None),
        "paper_id": s.paper_id,
        "authors": getattr(s, "authors", None),
        "year": getattr(s, "year", None),
        "score": round(float(s.score), 3),
        "page": getattr(s, "page_number", None),
        "doi": getattr(s, "doi", None) or find_doi(getattr(s, "text", "") or ""),
        "text": (s.text[:600] if request.include_chunks and getattr(s, "text", None) else None),
    } for s in result.sources]

    payload = {
        "item_id": request.item_id,
        "engine": request.engine,
        "model": REVIEW_MODEL,
        "question": question,
        "answer": result.answer,
        "sources": sources,
        "chunks_used": len(result.sources),
        "elapsed_ms": round((time.time() - start) * 1000),
        "queried_at": datetime.now().isoformat(timespec="seconds"),
    }

    if request.item_id:
        # La caché se llava por celda Y motor: así se puede contrastar la misma
        # celda con los dos motores sin que uno pise al otro.
        with _write_lock:
            cache = load_json(RAG_CACHE_FILE, {})
            cache[f"{request.item_id}|{request.engine}"] = payload
            save_json(RAG_CACHE_FILE, cache)
    return payload



# ── FishBase ────────────────────────────────────────────────────────────
# Vive aparte de la cola de revisión a propósito. La cola sirve para dirimir
# celda a celda —qué búsqueda tiene razón, si hay respaldo en el corpus—, y eso
# no es lo que hace falta con FishBase: son 2 671 valores curados, coherentes
# entre sí, que se revisan mejor viendo la especie entera de un vistazo y
# aceptando por lotes. Mezclarlos ahogaba la cola y hacía el trabajo más lento.


def load_fb() -> dict:
    if not FB_FILE.exists():
        raise HTTPException(503, "Falta fishbase_suggestions.json. Ejecuta "
                                 "scripts/phase_7_review/fishbase_suggestions.py")
    return load_json(FB_FILE, {})


def fb_param_meta() -> list[dict]:
    """Orden y etiquetas de las columnas de la tabla, según el esquema del modelo."""
    from build_review_queue import PARAMS
    from fishbase_suggestions import PARAM_MAP
    return [{"key": k, "label": PARAMS[k]["label"], "unit": PARAMS[k]["unit"]}
            for k in PARAMS if k in PARAM_MAP]


@app.get("/api/fishbase")
def api_fishbase_index():
    """Índice por grupo: cuántas celdas propone FishBase y cuántas van revisadas."""
    fb = load_fb()
    decisions = load_json(DECISIONS_FILE, {})
    por_grupo: dict[str, dict] = {}
    for item_id, sug in fb.get("suggestions", {}).items():
        g = por_grupo.setdefault(sug["group"], {
            "group": sug["group"], "cells": 0, "species": set(),
            "accepted": 0, "rejected": 0, "pending": 0, "locked": 0,
        })
        g["cells"] += 1
        g["species"].add(sug["species"])
        d = decisions.get(item_id) or {}
        st, src = d.get("status"), d.get("source")
        if st in ("accepted", "rejected") and src != "FishBase":
            # Ya se decidió en la cola de revisión, con otra fuente. Es una
            # decisión humana sobre esa celda y FishBase no puede pisarla.
            g["locked"] += 1
        elif st == "accepted":
            g["accepted"] += 1
        elif st == "rejected":
            g["rejected"] += 1
        else:
            g["pending"] += 1
    grupos = []
    for g in por_grupo.values():
        g["n_species"] = len(g.pop("species"))
        grupos.append(g)
    grupos.sort(key=lambda x: -x["cells"])
    return {
        "generated_at": fb.get("generated_at"),
        "source": fb.get("source"),
        "warning": fb.get("warning"),
        "params": fb_param_meta(),
        "groups": grupos,
        "totals": {
            "cells": sum(g["cells"] for g in grupos),
            "accepted": sum(g["accepted"] for g in grupos),
            "rejected": sum(g["rejected"] for g in grupos),
            "locked": sum(g["locked"] for g in grupos),
            "species": sum(g["n_species"] for g in grupos),
        },
    }


@app.get("/api/fishbase/group/{group:path}")
def api_fishbase_group(group: str):
    """La tabla de un grupo: una fila por especie, una columna por parámetro."""
    fb = load_fb()
    decisions = load_json(DECISIONS_FILE, {})
    filas: dict[str, dict] = {}
    for item_id, sug in fb.get("suggestions", {}).items():
        if sug["group"] != group:
            continue
        row = item_id.split(":", 1)[0]
        f = filas.setdefault(row, {
            "row": int(row), "species": sug["species"],
            "speccode": sug.get("speccode"), "cells": {},
        })
        d = decisions.get(item_id) or {}
        f["cells"][sug["param"]] = {
            "id": item_id,
            "value": sug["value"],
            "unit": sug.get("unit", ""),
            "confidence": sug["confidence"],
            "n_records": sug.get("n_records", 1),
            "observed_range": sug.get("observed_range"),
            "citations": sug.get("citations", []),
            "rationale": sug.get("rationale", ""),
            "status": d.get("status"),
            "source": d.get("source"),
            "locked": d.get("status") in ("accepted", "rejected") and d.get("source") != "FishBase",
            "decided_value": d.get("value"),
            "reviewer": d.get("reviewer", ""),
        }
    if not filas:
        raise HTTPException(404, f"Sin sugerencias de FishBase para «{group}»")
    return {
        "group": group,
        "params": fb_param_meta(),
        "species": sorted(filas.values(), key=lambda f: f["species"]),
    }


class FBBulk(BaseModel):
    status: str                      # accepted | rejected | pending
    reviewer: str = ""
    group: Optional[str] = None      # todo un grupo…
    ids: Optional[list[str]] = None   # …o una lista concreta de celdas
    comment: str = ""


@app.post("/api/fishbase/decide")
def api_fishbase_decide(body: FBBulk):
    """Acepta, descarta o reabre celdas de FishBase, de una en una o por grupo."""
    valid = {"accepted", "rejected", "pending"}
    if body.status not in valid:
        raise HTTPException(400, f"status debe ser uno de {sorted(valid)}")
    if body.status != "pending" and not body.reviewer.strip():
        raise HTTPException(400, "hace falta el nombre del revisor")
    fb = load_fb().get("suggestions", {})

    if body.ids:
        objetivo = {i: fb[i] for i in body.ids if i in fb}
    elif body.group:
        objetivo = {i: s for i, s in fb.items() if s["group"] == body.group}
    else:
        raise HTTPException(400, "indica `group` o `ids`")
    if not objetivo:
        raise HTTPException(404, "ninguna celda coincide")

    ahora = datetime.now().isoformat(timespec="seconds")
    saltadas = []
    with _write_lock:
        decisions = load_json(DECISIONS_FILE, {})
        for item_id, sug in objetivo.items():
            # Celda ya resuelta en la cola de revisión con otra fuente. Una
            # aceptación por lote no puede deshacer una decisión que alguien
            # tomó mirando la evidencia: se salta y se informa.
            previa = decisions.get(item_id) or {}
            if (previa.get("status") in ("accepted", "rejected")
                    and previa.get("source") != "FishBase"):
                saltadas.append({
                    "item_id": item_id, "species": sug["species"], "param": sug["param"],
                    "source": previa.get("source"), "reviewer": previa.get("reviewer", ""),
                })
                continue
            if body.status == "pending":
                decisions.pop(item_id, None)
                continue
            previo = decisions.get(item_id)
            history = (previo or {}).get("history", [])
            if previo:
                history = history + [{k: previo[k] for k in
                                      ("status", "value", "source", "reviewer", "updated_at")
                                      if k in previo}]
            # La procedencia viaja con la decisión: el SpecCode y la referencia
            # primaria son lo que hace rastreable el valor más adelante.
            refs = [c["ref"] for c in sug.get("citations", [])]
            decisions[item_id] = {
                "item_id": item_id,
                "species": sug["species"],
                "group": sug["group"],
                "param": sug["param"],
                "status": body.status,
                "value": sug["value"],
                "source": "FishBase",
                "reference": " | ".join(refs),
                "reviewer": body.reviewer.strip(),
                "comment": body.comment.strip(),
                "updated_at": ahora,
                "history": history[-10:],
            }
        save_json(DECISIONS_FILE, decisions)
    return {"ok": True, "cells": len(objetivo) - len(saltadas), "status": body.status,
            "skipped": len(saltadas), "skipped_detail": saltadas[:20]}


@app.get("/api/status")
def api_status():
    queue = get_queue()
    decisions = load_json(DECISIONS_FILE, {})
    reviewed = sum(1 for d in decisions.values() if d.get("status") in {"accepted", "rejected"})
    return {
        "queue_generated_at": queue.get("generated_at"),
        "conflicts": queue["totals"]["conflicts"],
        "reviewed": reviewed,
        "pending": queue["totals"]["conflicts"] - reviewed,
        "rag_engines_loaded": [k for k in _engines if not k.startswith("_")],
        "index_chunks": getattr(_index_stats, "total_chunks", None),
    }


# ── exportación ─────────────────────────────────────────────────────────

def consolidate() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fusiona las 4 búsquedas aplicando las decisiones del revisor.

    Regla por celda:
      conflicto resuelto  → valor decidido (o se descarta si status=rejected)
      conflicto pendiente → sugerencia por consenso, marcada como provisional
      acuerdo             → mediana / valor común
      una sola búsqueda   → ese valor, marcado como no corroborado
    """
    from build_review_queue import PARAMS, SEARCHES, TAXONOMY, norm_cat, norm_num, DERIVED_FROM

    queue = get_queue()
    decisions = load_json(DECISIONS_FILE, {})
    conflicts = {item["id"]: item for item in queue["items"]}
    # FishBase ya no pasa por la cola: se revisa en su propia página. El export
    # tiene que mirarlo aparte o las aceptaciones por lote no llegarían al CSV.
    fb_sug = load_json(FB_FILE, {}).get("suggestions", {})

    frames = {k: pd.read_csv(PROJECT_ROOT / "data" / "output"
                             / f"Atlantis_GOC_parametros_biologicos_{v}.csv")
              for k, v in SEARCHES.items()}
    base = frames["B1"]
    out = base[TAXONOMY].copy()
    for param in PARAMS:
        out[param] = pd.NA
    out["citations"] = base["citations"]
    out["notes"] = pd.NA

    provenance: list[dict] = []

    for idx in range(len(base)):
        for param, meta in PARAMS.items():
            kind = meta["type"]
            raw = {}
            for key, df in frames.items():
                if param not in df.columns:
                    continue
                value = norm_num(df.at[idx, param]) if kind == "num" else norm_cat(df.at[idx, param])
                if value is not None:
                    raw[key] = value

            item_id = f"{idx}:{param}"
            # Una celda vacía en las búsquedas puede tener aun así una decisión
            # tomada sobre una sugerencia (IA, FishBase o reclasificación).
            # Descartarla aquí dejaba el canal de revisión sin efecto: el
            # revisor aceptaba el valor y no aparecía nunca en el CSV.
            if not raw and item_id not in conflicts and item_id not in fb_sug:
                continue

            item = conflicts.get(item_id)
            decision = decisions.get(item_id)
            fbs = fb_sug.get(item_id)

            if fbs and decision and decision["status"] == "accepted" \
                    and decision.get("source") == "FishBase":
                # Celda aceptada en la página de FishBase, fuera de la cola.
                value = norm_num(decision["value"]) if kind == "num" else decision["value"]
                status = "revisado_fishbase"
                marca = f"FishBase SpecCode {fbs.get('speccode')}"
                if fbs.get("n_records", 0) > 1:
                    marca += f", mediana de {fbs['n_records']} registros"
                refs = [c["ref"] for c in fbs.get("citations", [])]
                note = " · ".join(x for x in (decision.get("comment", ""), marca,
                                              "cita: " + " | ".join(refs) if refs else "") if x)
            elif fbs and not raw and not (decision and decision["status"] == "accepted"):
                # Propuesta de FishBase sin aceptar: no se escribe valor.
                provenance.append({
                    "row": idx, "Species": base.at[idx, "Species"], "Group": base.at[idx, "Group"],
                    "param": param, "value": None,
                    "status": "fishbase_rechazado" if (decision or {}).get("status") == "rejected"
                              else "fishbase_pendiente",
                    "n_searches": 0, "spread_pct": 0.0, "searches": "",
                    "reviewer": (decision or {}).get("reviewer", ""),
                    "note": f"propuesto: {fbs['value']} · FishBase SpecCode {fbs.get('speccode')}",
                })
                continue
            elif item and decision and decision["status"] == "accepted":
                value = decision["value"]
                status = {"externo": "revisado_fuente_externa",
                          "IA": "revisado_sugerencia_ia",
                          "FishBase": "revisado_fishbase",
                          "reclasificado": "revisado_reclasificacion"}.get(
                              decision.get("source"), "revisado")
                note = " · ".join(x for x in (decision.get("reference", ""),
                                              decision.get("comment", "")) if x)
                if decision.get("source") == "IA":
                    # Una sugerencia aceptada viaja al export con la cita que la
                    # respalda: si el valor sale del conocimiento del modelo, el
                    # dataset debe decir contra qué literatura se puede comprobar.
                    refs = [c["ref"] for c in (item.get("ai_suggestion") or {}).get("citations", [])]
                    if refs:
                        note = " · ".join(x for x in (note, "cita: " + " | ".join(refs)) if x)
                if decision.get("source") == "FishBase":
                    # Igual que arriba, pero el valor no lo dedujo el modelo: lo
                    # publicó alguien y FishBase lo catalogó. El export conserva
                    # el SpecCode y la referencia primaria para poder rastrearlo.
                    fbs = item.get("fb_suggestion") or {}
                    refs = [c["ref"] for c in fbs.get("citations", [])]
                    marca = f"FishBase SpecCode {fbs.get('speccode')}" if fbs.get("speccode") else "FishBase"
                    if fbs.get("n_records", 0) > 1:
                        marca += f", mediana de {fbs['n_records']} registros"
                    note = " · ".join(x for x in (note, marca) if x)
                    if refs:
                        note = " · ".join(x for x in (note, "cita: " + " | ".join(refs)) if x)
                if kind == "num":
                    value = norm_num(value)
            elif item and decision and decision["status"] == "rejected":
                provenance.append({
                    "row": idx, "Species": base.at[idx, "Species"], "Group": base.at[idx, "Group"],
                    "param": param, "value": None, "status": "descartado",
                    "n_searches": len(raw), "spread_pct": item["spread_pct"],
                    "searches": ";".join(f"{k}={v}" for k, v in raw.items()),
                    "reviewer": decision.get("reviewer", ""), "note": decision.get("comment", ""),
                })
                continue
            elif item and item.get("tipo") == "sin_respaldo":
                # B6 no halló evidencia. El valor NO se borra —eso perdería
                # información sin decisión humana— pero queda marcado para que el
                # modelador pueda filtrarlo antes de alimentar Atlantis.
                independent = {k: v for k, v in raw.items() if k != "B6"}
                if kind == "num":
                    ordered = sorted(independent.values())
                    mid = len(ordered) // 2
                    value = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
                    value = round(value, 6)
                else:
                    value = Counter(independent.values()).most_common(1)[0][0]
                status = "sin_respaldo_b6"
                note = f"{len(independent)} búsqueda(s) lo afirman; B6 no halló evidencia en el corpus"
            elif item and item.get("tipo") in ("sugerencia_ia", "fishbase", "reclasificado"):
                # Sugerencia sin revisar. NO se escribe valor: una sugerencia sólo
                # se convierte en dato cuando un humano la acepta. Queda la fila
                # de procedencia para que se vea que está pendiente.
                provenance.append({
                    "row": idx, "Species": base.at[idx, "Species"], "Group": base.at[idx, "Group"],
                    "param": param, "value": None,
                    "status": f"{item['tipo']}_pendiente",
                    "n_searches": len(raw), "spread_pct": 0.0,
                    "searches": ";".join(f"{k}={v}" for k, v in raw.items()),
                    "reviewer": "", "note": f"propuesto: {item['suggested']} · {item['suggested_method']}",
                })
                continue
            elif item:
                value = item["suggested"]
                status = "conflicto_pendiente"
                note = f"discrepancia {item['spread_pct']:.0f}% · {item['suggested_method']}"
            elif len(raw) >= 2:
                independent = dict(raw)
                for derived, parent in DERIVED_FROM.items():
                    if derived in independent and parent in independent \
                            and independent[derived] == independent[parent]:
                        independent.pop(derived)
                values = list(independent.values())
                if kind == "num":
                    ordered = sorted(values)
                    mid = len(ordered) // 2
                    value = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
                    value = round(value, 6)
                else:
                    value = values[0]
                status, note = "acuerdo", ""
            else:
                value, status, note = next(iter(raw.values())), "sin_corroborar", "una sola búsqueda"

            if value is None:
                # Empate categórico sin consenso: la celda queda vacía pero se
                # registra para que no desaparezca del rastro de procedencia.
                provenance.append({
                    "row": idx, "Species": base.at[idx, "Species"], "Group": base.at[idx, "Group"],
                    "param": param, "value": None, "status": "conflicto_sin_consenso",
                    "n_searches": len(raw), "spread_pct": item["spread_pct"] if item else 0.0,
                    "searches": ";".join(f"{k}={v}" for k, v in raw.items()),
                    "reviewer": "", "note": "requiere decisión manual",
                })
                continue
            out.at[idx, param] = value
            provenance.append({
                "row": idx, "Species": base.at[idx, "Species"], "Group": base.at[idx, "Group"],
                "param": param, "value": value, "status": status,
                "n_searches": len(raw), "spread_pct": item["spread_pct"] if item else 0.0,
                "searches": ";".join(f"{k}={v}" for k, v in raw.items()),
                "reviewer": (decision or {}).get("reviewer", ""),
                "reference": (decision or {}).get("reference", ""), "note": note,
            })

    return out, pd.DataFrame(provenance)


@app.post("/api/export")
def api_export():
    consolidated, provenance = consolidate()
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    consolidated.to_csv(EXPORT_CSV, index=False)
    provenance.to_csv(EXPORT_PROV, index=False)
    counts = provenance["status"].value_counts().to_dict() if len(provenance) else {}
    return {
        "ok": True,
        "csv": str(EXPORT_CSV.relative_to(PROJECT_ROOT)),
        "provenance_csv": str(EXPORT_PROV.relative_to(PROJECT_ROOT)),
        "cells": int(len(provenance)),
        "by_status": counts,
    }


@app.get("/api/export/download")
def api_export_download():
    if not EXPORT_CSV.exists():
        raise HTTPException(404, "Aún no se ha generado el CSV consolidado")
    return FileResponse(EXPORT_CSV, filename=EXPORT_CSV.name, media_type="text/csv")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def main() -> None:
    global _password

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8600)
    parser.add_argument("--password", default=os.environ.get("REVIEW_PASSWORD"),
                        help="Contraseña de acceso (usuario: REVIEW_USER, por defecto 'revisor'). "
                             "También se puede pasar por la variable REVIEW_PASSWORD.")
    args = parser.parse_args()

    if not QUEUE_FILE.exists():
        print("⚠  Falta la cola. Ejecuta primero:")
        print("   python3 scripts/phase_7_review/build_review_queue.py")
        sys.exit(1)

    _password = args.password or None

    print(f"\n  Tablero de revisión → http://{args.host}:{args.port}")
    if _password:
        print(f"  Acceso protegido · usuario: {REVIEW_USER}\n")
    else:
        print("  ⚠  SIN CONTRASEÑA: no lo expongas fuera de esta máquina.")
        print("     Para publicarlo: REVIEW_PASSWORD='…' python3 …/review_server.py\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
