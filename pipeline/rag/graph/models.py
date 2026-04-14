"""
Modelos de datos para el grafo de conocimiento científico (GraphRAG).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.rag.models import RAGSearchResult


# ── Entidades y relaciones ────────────────────────────────────────────────────

VALID_ENTITY_TYPES = {"Species", "Method", "Location", "Concept", "Author", "Paper"}
VALID_RELATION_TYPES = {
    "studies", "found_in", "interacts_with", "measured_by",
    "published_in", "co_occurs_with",
}


@dataclass
class Entity:
    """Una entidad del grafo de conocimiento extraída de chunks científicos."""

    entity_id: str
    """Identificador único: '{type_lower}::{name_normalized}'. Ej: 'species::lutjanus_peru'."""

    entity_type: str
    """Tipo: Species | Method | Location | Concept | Author | Paper."""

    name: str
    """Nombre canónico."""

    aliases: List[str] = field(default_factory=list)
    """Variantes del nombre encontradas en el texto (ej: 'L. peru', 'red snapper')."""

    source_chunk_ids: List[str] = field(default_factory=list)
    """IDs de chunks donde se mencionó esta entidad."""

    source_paper_ids: List[str] = field(default_factory=list)
    """IDs de papers donde se mencionó esta entidad."""

    properties: Dict[str, Any] = field(default_factory=dict)
    """Propiedades adicionales extraídas (ej: {'family': 'Lutjanidae'})."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "aliases": self.aliases,
            "source_chunk_ids": self.source_chunk_ids,
            "source_paper_ids": self.source_paper_ids,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        return cls(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            name=data["name"],
            aliases=data.get("aliases", []),
            source_chunk_ids=data.get("source_chunk_ids", []),
            source_paper_ids=data.get("source_paper_ids", []),
            properties=data.get("properties", {}),
        )

    def __str__(self) -> str:
        return f"Entity({self.entity_type}: {self.name})"


@dataclass
class Relation:
    """Una relación dirigida entre dos entidades del grafo."""

    relation_id: str
    """Triple compuesto: '{subject_id}::{relation_type}::{object_id}'."""

    subject_id: str
    """entity_id del sujeto."""

    relation_type: str
    """Tipo: studies | found_in | interacts_with | measured_by | published_in | co_occurs_with."""

    object_id: str
    """entity_id del objeto."""

    source_chunk_ids: List[str] = field(default_factory=list)
    source_paper_ids: List[str] = field(default_factory=list)

    confidence: float = 1.0
    """Confianza asignada por Claude (0.0–1.0)."""

    context_snippet: str = ""
    """Fragmento de texto (<= 200 chars) donde se encontró la relación."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "subject_id": self.subject_id,
            "relation_type": self.relation_type,
            "object_id": self.object_id,
            "source_chunk_ids": self.source_chunk_ids,
            "source_paper_ids": self.source_paper_ids,
            "confidence": self.confidence,
            "context_snippet": self.context_snippet,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Relation":
        return cls(
            relation_id=data["relation_id"],
            subject_id=data["subject_id"],
            relation_type=data["relation_type"],
            object_id=data["object_id"],
            source_chunk_ids=data.get("source_chunk_ids", []),
            source_paper_ids=data.get("source_paper_ids", []),
            confidence=float(data.get("confidence", 1.0)),
            context_snippet=data.get("context_snippet", ""),
        )

    def __str__(self) -> str:
        return f"Relation({self.subject_id} --[{self.relation_type}]--> {self.object_id})"


# ── Resultados de consulta ────────────────────────────────────────────────────

@dataclass
class GraphSearchResult:
    """Resultado de una búsqueda en el grafo: entidad + vecindad."""

    entity: Entity
    """Entidad central recuperada."""

    related_entities: List[Entity] = field(default_factory=list)
    """Entidades vecinas a 1 hop."""

    relations: List[Relation] = field(default_factory=list)
    """Relaciones que conectan la entidad con sus vecinos."""

    relevance_score: float = 1.0
    """Score de relevancia estructural (mayor degree = más relevante)."""

    def format_as_context(self) -> str:
        """Formatea la entidad y su vecindad como bloque de texto para el prompt de Claude."""
        lines = [
            f"### Entidad: {self.entity.name} ({self.entity.entity_type})",
        ]
        if self.entity.source_paper_ids:
            lines.append(f"Mencionada en: {', '.join(self.entity.source_paper_ids)}")
        if self.relations:
            lines.append("Relaciones:")
            for rel in self.relations:
                # Encontrar el nombre del objeto en related_entities
                obj_entity = next(
                    (e for e in self.related_entities if e.entity_id == rel.object_id), None
                )
                obj_name = obj_entity.name if obj_entity else rel.object_id
                lines.append(
                    f"  - [{rel.relation_type}] {obj_name} "
                    f"({rel.object_id.split('::')[0].title()})  "
                    f"[conf={rel.confidence:.2f}]"
                )
        return "\n".join(lines)


@dataclass
class GraphQueryResult:
    """Resultado de una consulta combinada grafo + vector (GraphRAG)."""

    question: str
    answer: str
    sources: List["RAGSearchResult"]
    """Chunks recuperados del índice FAISS."""

    graph_results: List[GraphSearchResult]
    """Entidades y vecindades recuperadas del grafo."""

    chunks_used: int
    graph_entities_used: int
    model: str
    timestamp: datetime = field(default_factory=datetime.now)

    def format_sources(self) -> str:
        """Fuentes bibliográficas (de los chunks FAISS)."""
        if not self.sources:
            return "Sin fuentes."
        lines = []
        seen: set = set()
        for r in self.sources:
            if r.paper_id in seen:
                continue
            seen.add(r.paper_id)
            authors_str = ", ".join(r.authors[:2]) if r.authors else "N/A"
            if r.authors and len(r.authors) > 2:
                authors_str += " et al."
            lines.append(f"  • {r.title or r.paper_id} ({r.year or 'N/A'}) — {authors_str}")
        return "\n".join(lines)

    def format_graph_context(self) -> str:
        """Resumen de las entidades del grafo usadas."""
        if not self.graph_results:
            return "Sin entidades en el grafo."
        return "\n\n".join(gr.format_as_context() for gr in self.graph_results)

    def __str__(self) -> str:
        return (
            f"Pregunta: {self.question}\n\n"
            f"{self.answer}\n\n"
            f"Entidades del grafo ({self.graph_entities_used}):\n"
            f"{self.format_graph_context()}\n\n"
            f"Fuentes ({len(set(r.paper_id for r in self.sources))} papers):\n"
            f"{self.format_sources()}"
        )


# ── Estadísticas ──────────────────────────────────────────────────────────────

@dataclass
class GraphStats:
    """Estadísticas del grafo de conocimiento."""

    total_entities: int
    total_relations: int
    entity_type_counts: Dict[str, int]
    relation_type_counts: Dict[str, int]
    total_papers_covered: int
    total_chunks_processed: int
    graph_path: str
    last_updated: datetime

    def __str__(self) -> str:
        types = ", ".join(f"{k}={v}" for k, v in sorted(self.entity_type_counts.items()))
        return (
            f"GraphStats({self.total_entities} entities [{types}], "
            f"{self.total_relations} relations, "
            f"{self.total_papers_covered} papers, "
            f"{self.total_chunks_processed} chunks processed)"
        )


# ── Utilidad de normalización ─────────────────────────────────────────────────

def normalize_entity_id(entity_type: str, name: str) -> str:
    """
    Convierte tipo + nombre en un entity_id determinista y seguro.

    normalize_entity_id("Species", "Lutjanus peru") → "species::lutjanus_peru"
    normalize_entity_id("Method", "otolith microchemistry") → "method::otolith_microchemistry"
    """
    type_part = entity_type.lower().strip()
    name_part = unicodedata.normalize("NFKD", name.lower().strip())
    name_part = name_part.encode("ascii", "ignore").decode("ascii")
    name_part = re.sub(r"[^\w]", "_", name_part)
    name_part = re.sub(r"_+", "_", name_part).strip("_")
    return f"{type_part}::{name_part}"
