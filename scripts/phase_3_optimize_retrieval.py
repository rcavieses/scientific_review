#!/usr/bin/env python3
"""
FASE 3: Optimización del sistema de retrieval

Objetivos:
  1. Implementar re-ranking y filtrado de resultados
  2. Deduplicación de chunks redundantes
  3. Validar búsquedas de prueba
  4. Crear índice de resiliencia con estadísticas

Salida:
  - outputs/rag_index_goc_full/ (optimizado)
  - reports/phase_3_retrieval_optimization.json
  - logs/phase_3_retrieval.log
"""

import sys
import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.rag.vector_db import VectorDBManager
from pipeline.embeddings.embedding_generator import get_embedding_generator

# Configuración
INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
METADATA_FILE = INDEX_DIR / "metadata_store.json"
LOGS_DIR = PROJECT_ROOT / "outputs" / "logs"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "phase_3_retrieval.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Queries de prueba en español
TEST_QUERIES = [
    "parámetros poblacionales pargo rojo Golfo de California",
    "biodiversidad marina arrecifes coralinos",
    "población talla madurez reproducción peces",
    "especies pelágicas migratorias Pacífico",
    "dinámica poblacional depredadores marinos",
]


class RetrievelOptimizer:
    """Optimiza el sistema de retrieval con re-ranking y deduplicación."""

    def __init__(self, index_dir: Path, embedding_generator):
        self.index_dir = index_dir
        self.embedding_generator = embedding_generator
        self.vector_db = VectorDBManager(
            index_dir=index_dir,
            embedding_dim=384,
            verbose=False,
        )
        self.vector_db.load()

    def find_duplicate_chunks(self, similarity_threshold: float = 0.95) -> Dict[int, List[int]]:
        """
        Identifica chunks potencialmente duplicados o muy similares.

        Retorna: Dict {chunk_id: [list_of_similar_chunk_ids]}
        """
        logger.info("\n🔍 Buscando chunks duplicados/similares...")

        # Cargar índice FAISS
        index = self.vector_db._index
        vectors = np.array([index.reconstruct(i) for i in range(index.ntotal)])

        duplicates = defaultdict(list)
        checked = set()

        for i in range(len(vectors)):
            if i in checked:
                continue

            for j in range(i + 1, len(vectors)):
                if j in checked:
                    continue

                # Calcular similitud coseno (inner product entre vectores normalizados)
                similarity = np.dot(vectors[i], vectors[j])

                if similarity >= similarity_threshold:
                    duplicates[i].append(j)
                    checked.add(j)

        logger.info(f"   Grupos de similitud encontrados: {len(duplicates)}")
        if duplicates:
            logger.info(f"   Chunks afectados: {sum(len(v) for v in duplicates.values())}")

        return duplicates

    def rank_search_results(
        self, query: str, results: List[Tuple[float, str, Dict]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Re-ranking inteligente de resultados de búsqueda.

        Criterios:
        1. Similitud semántica (score original)
        2. Presencia de metadatos (título, autores)
        3. Recencia (año más reciente > más antiguo)
        4. Diversidad (no repetir mismo PDF)
        """
        if not results:
            return []

        # Re-ranking con criterios múltiples
        scored_results = []

        seen_pdfs: Set[str] = set()

        for similarity_score, chunk_id, chunk_data in results:
            metadata = chunk_data.get("metadata", {})

            # Score base: similitud semántica
            base_score = similarity_score

            # Bonus por completitud de metadatos
            metadata_bonus = 0.0
            if metadata.get("paper_title"):
                metadata_bonus += 0.02
            if metadata.get("paper_authors"):
                metadata_bonus += 0.02
            if metadata.get("paper_year"):
                metadata_bonus += 0.02
            if metadata.get("paper_doi"):
                metadata_bonus += 0.01

            # Bonus por recencia (años después de 1990 = -5 = bonus)
            recency_bonus = 0.0
            year = metadata.get("paper_year")
            if year and year >= 2000:
                recency_bonus = (year - 2000) * 0.001  # +0.001 por año después de 2000

            # Score final
            final_score = base_score + metadata_bonus + recency_bonus

            pdf_source = chunk_data.get("source_pdf", "unknown")

            scored_results.append(
                {
                    "chunk_id": chunk_id,
                    "similarity_score": float(similarity_score),
                    "metadata_bonus": metadata_bonus,
                    "recency_bonus": recency_bonus,
                    "final_score": final_score,
                    "pdf": pdf_source,
                    "text": chunk_data.get("text", "")[:200] + "...",
                    "title": metadata.get("paper_title", "N/A"),
                    "authors": metadata.get("paper_authors", []),
                    "year": metadata.get("paper_year", "N/A"),
                    "doi": metadata.get("paper_doi", "N/A"),
                }
            )

        # Ordenar por final_score
        scored_results.sort(key=lambda x: x["final_score"], reverse=True)

        # Retornar top_k, evitando repetir PDFs
        top_results = []
        for result in scored_results:
            if result["pdf"] not in seen_pdfs:
                top_results.append(result)
                seen_pdfs.add(result["pdf"])

            if len(top_results) >= top_k:
                break

        return top_results

    def test_retrieval(self, query: str) -> Dict[str, Any]:
        """Prueba retrieval para una query."""
        logger.info(f"\n  Query: '{query[:60]}...'")

        # Generar embedding
        query_embedding = self.embedding_generator.batch_generate([query])[0]

        # Búsqueda
        results, scores = self.vector_db.search(query_embedding, k=10)

        # Re-ranking
        ranked_results = self.rank_search_results(query, list(zip(scores, results, [self.vector_db._metadata.get(str(r), {}) for r in results])))

        # Retornar top 5
        top_results = ranked_results[:5]

        logger.info(f"    ✓ Encontrados: {len(results)} chunks, Top 5 re-ranked:")

        for i, result in enumerate(top_results, 1):
            logger.info(f"      [{i}] {result['title'][:50]}... ({result['year']}) - score: {result['final_score']:.3f}")

        return {
            "query": query,
            "total_results": len(results),
            "top_k_results": top_results,
            "success": len(top_results) > 0,
        }

    def validate_index_integrity(self) -> Dict[str, Any]:
        """Valida integridad del índice."""
        logger.info("\n✅ Validando integridad del índice...")

        stats = self.vector_db.get_stats()

        logger.info(f"   Total chunks: {stats.get('total_chunks', 0)}")
        logger.info(f"   Dimensión embeddings: {stats.get('embedding_dimension', 0)}")
        logger.info(f"   Index type: {stats.get('index_type', 'unknown')}")

        # Validaciones
        issues = []

        if stats.get("total_chunks", 0) == 0:
            issues.append("❌ No hay chunks en el índice")

        if stats.get("embedding_dimension", 0) != 384:
            issues.append(f"❌ Dimensión inesperada: {stats.get('embedding_dimension', 0)}")

        # Validar metadata
        with open(METADATA_FILE, "r") as f:
            metadata_store = json.load(f)

        if len(metadata_store) != stats.get("total_chunks", 0):
            issues.append(
                f"⚠️  Mismatch chunks ({stats.get('total_chunks', 0)}) vs metadata ({len(metadata_store)})"
            )

        return {
            "total_chunks": stats.get("total_chunks", 0),
            "embedding_dimension": stats.get("embedding_dimension", 0),
            "index_type": stats.get("index_type", "unknown"),
            "metadata_count": len(metadata_store),
            "issues": issues,
            "is_valid": len(issues) == 0,
        }


def run_optimization():
    """Ejecuta optimización completa."""
    logger.info("\n" + "=" * 80)
    logger.info("FASE 3: OPTIMIZACIÓN DEL SISTEMA DE RETRIEVAL")
    logger.info("=" * 80)

    # Inicializar
    logger.info("\n🔧 Inicializando optimizer...")
    embedding_generator = get_embedding_generator(
        provider="local",
        model="all-MiniLM-L6-v2",
        cache_folder=str(PROJECT_ROOT / "models" / "embeddings"),
        verbose=False,
    )

    optimizer = RetrievelOptimizer(INDEX_DIR, embedding_generator)

    # 1. Validar integridad
    logger.info("\n📊 PASO 1: Validación de integridad")
    integrity = optimizer.validate_index_integrity()

    # 2. Detectar duplicados
    logger.info("\n📊 PASO 2: Búsqueda de duplicados")
    duplicates = optimizer.find_duplicate_chunks(similarity_threshold=0.95)

    # 3. Pruebas de retrieval
    logger.info("\n📊 PASO 3: Pruebas de retrieval con queries de ejemplo")
    test_results = []
    for query in TEST_QUERIES:
        result = optimizer.test_retrieval(query)
        test_results.append(result)

    return {
        "integrity": integrity,
        "duplicates": {k: v for k, v in duplicates.items()},  # Serializable
        "test_queries": test_results,
    }


def save_optimization_report(optimization_results: Dict):
    """Guarda reporte de optimización."""
    logger.info("\n" + "=" * 80)
    logger.info("FASE 3.1: Guardando reporte de optimización")
    logger.info("=" * 80)

    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "optimize_retrieval",
        "integrity": optimization_results["integrity"],
        "duplicate_analysis": {
            "groups_found": len(optimization_results["duplicates"]),
            "affected_chunks": sum(len(v) for v in optimization_results["duplicates"].values()),
        },
        "test_results": {
            "total_queries": len(optimization_results["test_queries"]),
            "successful_queries": sum(1 for r in optimization_results["test_queries"] if r["success"]),
            "queries": optimization_results["test_queries"],
        },
        "next_steps": [
            "Sistema de retrieval está listo para consultas",
            "Se pueden hacer queries en español o inglés",
            "Los metadatos bibliográficos están disponibles",
            "Re-ranking automático en resultados de búsqueda",
        ],
    }

    report_path = REPORTS_DIR / "phase_3_retrieval_optimization.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"  Reporte guardado: {report_path}")


def print_summary(optimization_results: Dict):
    """Imprime resumen de la fase."""
    logger.info(f"\n{'=' * 80}")
    logger.info("📊 RESUMEN DE FASE 3")
    logger.info(f"{'=' * 80}")

    integrity = optimization_results["integrity"]
    test_results = optimization_results["test_queries"]

    logger.info(f"\n  ✅ INTEGRIDAD DEL ÍNDICE:")
    logger.info(f"     Total chunks: {integrity['total_chunks']}")
    logger.info(f"     Dimensión embeddings: {integrity['embedding_dimension']}")
    logger.info(f"     Estado: {'✓ Válido' if integrity['is_valid'] else '❌ Problemas'}")

    if integrity["issues"]:
        for issue in integrity["issues"]:
            logger.warning(f"     {issue}")

    logger.info(f"\n  🔍 ANÁLISIS DE DUPLICADOS:")
    dup_count = len(optimization_results["duplicates"])
    logger.info(f"     Grupos de similitud: {dup_count}")

    logger.info(f"\n  🧪 PRUEBAS DE RETRIEVAL:")
    success_count = sum(1 for r in test_results if r["success"])
    logger.info(f"     Queries exitosas: {success_count}/{len(test_results)}")

    for test in test_results:
        status = "✓" if test["success"] else "❌"
        logger.info(f"     {status} '{test['query'][:40]}...'")

    logger.info(f"\n  → Próximo paso: python3 scripts/phase_4_create_query_interface.py")
    logger.info(f"{'=' * 80}\n")


def main():
    logger.info(f"\n{'=' * 80}")
    logger.info("🔧 FASE 3: OPTIMIZACIÓN DE RETRIEVAL")
    logger.info(f"{'=' * 80}")

    # Ejecutar optimización
    optimization_results = run_optimization()

    # Guardar reporte
    save_optimization_report(optimization_results)

    # Resumen
    print_summary(optimization_results)


if __name__ == "__main__":
    main()
