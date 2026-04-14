"""
GraphRAG: grafo de conocimiento científico + consultas combinadas grafo + vector.

Flujo de construcción:
  chunks → GraphExtractor → KnowledgeGraphStore → knowledge_graph.json

Flujo de consulta:
  pregunta → GraphQueryEngine → (grafo + FAISS) → Claude → GraphQueryResult
"""

from .models import (
    Entity,
    Relation,
    GraphSearchResult,
    GraphQueryResult,
    GraphStats,
    normalize_entity_id,
    VALID_ENTITY_TYPES,
    VALID_RELATION_TYPES,
)
from .graph_store import KnowledgeGraphStore
from .extractor import GraphExtractor
from .graph_query_engine import GraphQueryEngine

__all__ = [
    "Entity",
    "Relation",
    "GraphSearchResult",
    "GraphQueryResult",
    "GraphStats",
    "normalize_entity_id",
    "VALID_ENTITY_TYPES",
    "VALID_RELATION_TYPES",
    "KnowledgeGraphStore",
    "GraphExtractor",
    "GraphQueryEngine",
]
