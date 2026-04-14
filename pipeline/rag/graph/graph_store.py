"""
Almacenamiento y consulta del grafo de conocimiento científico.

Usa NetworkX DiGraph internamente y persiste en JSON plano (human-readable).

Estructura de archivos en graph_dir/:
  knowledge_graph.json  — entidades y relaciones serializadas
  graph_config.json     — metadatos: modelo usado, chunks procesados, timestamp
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from .models import (
    Entity,
    GraphSearchResult,
    GraphStats,
    Relation,
    VALID_ENTITY_TYPES,
    VALID_RELATION_TYPES,
    normalize_entity_id,
)


class KnowledgeGraphStore:
    """
    Grafo de conocimiento respaldado por NetworkX + persistencia JSON.

    Los nodos son entity_ids (strings). Cada nodo tiene los atributos del Entity
    correspondiente. Las aristas llevan relation_type, confidence, source_chunk_ids.

    Args:
        graph_dir: Directorio donde persistir el grafo.
        verbose: Mostrar información de depuración.
    """

    GRAPH_FILE = "knowledge_graph.json"
    CONFIG_FILE = "graph_config.json"

    def __init__(self, graph_dir: Path = Path("outputs/graph_index"), verbose: bool = False):
        self.graph_dir = Path(graph_dir)
        self.verbose = verbose

        self.graph_dir.mkdir(parents=True, exist_ok=True)

        self._graph: nx.DiGraph = nx.DiGraph()
        self._entities: Dict[str, Entity] = {}   # entity_id → Entity
        self._relations: Dict[str, Relation] = {}  # relation_id → Relation
        self._processed_chunk_ids: Set[str] = set()

    # ── Inserción ────────────────────────────────────────────────────────────

    def add_entity(self, entity: Entity) -> Entity:
        """
        Inserta o fusiona una entidad en el grafo.

        Si el entity_id ya existe: une aliases y source_chunk/paper_ids.
        Si es nuevo: añade el nodo.

        Returns:
            La entidad final (posiblemente fusionada).
        """
        if entity.entity_id in self._entities:
            existing = self._entities[entity.entity_id]
            existing.aliases = list(set(existing.aliases) | set(entity.aliases))
            existing.source_chunk_ids = list(
                set(existing.source_chunk_ids) | set(entity.source_chunk_ids)
            )
            existing.source_paper_ids = list(
                set(existing.source_paper_ids) | set(entity.source_paper_ids)
            )
            existing.properties.update(entity.properties)
            return existing
        else:
            self._entities[entity.entity_id] = entity
            self._graph.add_node(entity.entity_id, **entity.to_dict())
            return entity

    def add_relation(self, relation: Relation) -> None:
        """
        Inserta una relación. Si ya existe (mismo relation_id), une source_chunk_ids.
        """
        if relation.relation_id in self._relations:
            existing = self._relations[relation.relation_id]
            existing.source_chunk_ids = list(
                set(existing.source_chunk_ids) | set(relation.source_chunk_ids)
            )
            existing.source_paper_ids = list(
                set(existing.source_paper_ids) | set(relation.source_paper_ids)
            )
            return

        self._relations[relation.relation_id] = relation
        self._graph.add_edge(
            relation.subject_id,
            relation.object_id,
            relation_id=relation.relation_id,
            relation_type=relation.relation_type,
            confidence=relation.confidence,
            source_chunk_ids=relation.source_chunk_ids,
        )

    def mark_chunk_processed(self, chunk_id: str) -> None:
        """Registra un chunk_id como ya procesado (para extracción incremental)."""
        self._processed_chunk_ids.add(chunk_id)

    def is_chunk_processed(self, chunk_id: str) -> bool:
        return chunk_id in self._processed_chunk_ids

    def ingest_extraction(
        self,
        raw: Dict[str, Any],
        chunk_id: str,
        paper_id: str,
    ) -> Tuple[int, int]:
        """
        Convierte la salida cruda de Claude en entidades y relaciones e ingesta al grafo.

        Args:
            raw: Dict con keys 'entities' y 'relations' tal como devuelve GraphExtractor.
            chunk_id: ID del chunk fuente.
            paper_id: ID del paper fuente.

        Returns:
            (nuevas_entidades, nuevas_relaciones)
        """
        raw_entities = raw.get("entities", [])
        raw_relations = raw.get("relations", [])

        # Primero crear todas las entidades y guardar el mapping nombre → entity_id
        name_to_id: Dict[str, str] = {}
        new_entities = 0

        for re_dict in raw_entities:
            name = re_dict.get("name", "").strip()
            etype = re_dict.get("type", "").strip()
            if not name or etype not in VALID_ENTITY_TYPES:
                continue

            eid = normalize_entity_id(etype, name)
            aliases = [a for a in re_dict.get("aliases", []) if a != name]
            props = re_dict.get("properties", {}) or {}

            entity = Entity(
                entity_id=eid,
                entity_type=etype,
                name=name,
                aliases=aliases,
                source_chunk_ids=[chunk_id],
                source_paper_ids=[paper_id],
                properties=props,
            )

            was_new = eid not in self._entities
            self.add_entity(entity)
            if was_new:
                new_entities += 1

            # Registrar todas las variantes del nombre
            name_to_id[name.lower()] = eid
            for alias in aliases:
                name_to_id[alias.lower()] = eid

        # Luego crear relaciones
        new_relations = 0

        for rel_dict in raw_relations:
            subj_name = rel_dict.get("subject", "").strip()
            obj_name = rel_dict.get("object", "").strip()
            rtype = rel_dict.get("relation", "").strip()

            if rtype not in VALID_RELATION_TYPES:
                continue

            subj_id = name_to_id.get(subj_name.lower())
            obj_id = name_to_id.get(obj_name.lower())

            if not subj_id or not obj_id:
                continue

            rid = f"{subj_id}::{rtype}::{obj_id}"
            confidence = float(rel_dict.get("confidence", 1.0))
            confidence = max(0.0, min(1.0, confidence))
            snippet = rel_dict.get("context", "")[:200]

            relation = Relation(
                relation_id=rid,
                subject_id=subj_id,
                relation_type=rtype,
                object_id=obj_id,
                source_chunk_ids=[chunk_id],
                source_paper_ids=[paper_id],
                confidence=confidence,
                context_snippet=snippet,
            )

            was_new = rid not in self._relations
            self.add_relation(relation)
            if was_new:
                new_relations += 1

        self.mark_chunk_processed(chunk_id)
        return new_entities, new_relations

    # ── Consulta ─────────────────────────────────────────────────────────────

    def search_entities(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Entity]:
        """
        Búsqueda de entidades por nombre (substring, case-insensitive, incluye aliases).

        Args:
            query: Texto a buscar.
            entity_types: Filtrar por tipo (None = todos).
            top_k: Máximo de resultados.

        Returns:
            Lista de entidades ordenadas por calidad de coincidencia y centralidad de grado.
        """
        query_lower = query.lower()
        candidates: List[Tuple[float, Entity]] = []

        for entity in self._entities.values():
            if entity_types and entity.entity_type not in entity_types:
                continue

            # Score por coincidencia de nombre
            score = 0.0
            if query_lower == entity.name.lower():
                score = 1.0
            elif query_lower in entity.name.lower():
                score = 0.8
            else:
                for alias in entity.aliases:
                    if query_lower == alias.lower():
                        score = 0.9
                        break
                    elif query_lower in alias.lower():
                        score = 0.7
                        break

            if score > 0:
                # Bonus por centralidad (nodos más conectados = más relevantes)
                degree = self._graph.degree(entity.entity_id) if entity.entity_id in self._graph else 0
                candidates.append((score + degree * 0.01, entity))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in candidates[:top_k]]

    def get_neighborhood(
        self,
        entity_id: str,
        hops: int = 1,
    ) -> Tuple[List[Entity], List[Relation]]:
        """
        BFS hasta `hops` saltos desde entity_id.

        Returns:
            (entidades_en_vecindad, relaciones_en_subgrafo)
        """
        if entity_id not in self._graph:
            return [], []

        # BFS
        visited_nodes: Set[str] = {entity_id}
        frontier = {entity_id}

        for _ in range(hops):
            next_frontier: Set[str] = set()
            for node in frontier:
                for neighbor in list(self._graph.successors(node)) + list(
                    self._graph.predecessors(node)
                ):
                    if neighbor not in visited_nodes:
                        visited_nodes.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier

        entities = [self._entities[nid] for nid in visited_nodes if nid in self._entities]

        # Relaciones dentro del subgrafo
        relations: List[Relation] = []
        for rid, rel in self._relations.items():
            if rel.subject_id in visited_nodes and rel.object_id in visited_nodes:
                relations.append(rel)

        return entities, relations

    def get_papers_for_entity(self, entity_id: str) -> List[str]:
        """Retorna los paper_ids que mencionan esta entidad."""
        entity = self._entities.get(entity_id)
        return entity.source_paper_ids if entity else []

    def get_entities_for_paper(self, paper_id: str) -> List[Entity]:
        """Retorna todas las entidades extraídas de un paper."""
        return [e for e in self._entities.values() if paper_id in e.source_paper_ids]

    # ── Persistencia ─────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persiste el grafo completo en knowledge_graph.json + graph_config.json."""
        graph_data = {
            "entities": {eid: e.to_dict() for eid, e in self._entities.items()},
            "relations": {rid: r.to_dict() for rid, r in self._relations.items()},
        }
        graph_path = self.graph_dir / self.GRAPH_FILE
        with open(graph_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        config = {
            "total_entities": len(self._entities),
            "total_relations": len(self._relations),
            "processed_chunk_ids": sorted(self._processed_chunk_ids),
            "last_updated": datetime.now().isoformat(),
        }
        config_path = self.graph_dir / self.CONFIG_FILE
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        if self.verbose:
            print(
                f"  Grafo guardado: {len(self._entities)} entidades, "
                f"{len(self._relations)} relaciones → {graph_path}"
            )

    def load(self) -> bool:
        """
        Carga el grafo desde disco.

        Returns:
            True si se cargó exitosamente, False si no había archivos.
        """
        graph_path = self.graph_dir / self.GRAPH_FILE
        config_path = self.graph_dir / self.CONFIG_FILE

        if not graph_path.exists():
            return False

        with open(graph_path, encoding="utf-8") as f:
            data = json.load(f)

        for eid, edict in data.get("entities", {}).items():
            entity = Entity.from_dict(edict)
            self._entities[eid] = entity
            self._graph.add_node(eid, **edict)

        for rid, rdict in data.get("relations", {}).items():
            relation = Relation.from_dict(rdict)
            self._relations[rid] = relation
            self._graph.add_edge(
                relation.subject_id,
                relation.object_id,
                relation_id=rid,
                relation_type=relation.relation_type,
                confidence=relation.confidence,
            )

        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            self._processed_chunk_ids = set(config.get("processed_chunk_ids", []))

        if self.verbose:
            print(
                f"  Grafo cargado: {len(self._entities)} entidades, "
                f"{len(self._relations)} relaciones"
            )
        return True

    # ── Estadísticas ─────────────────────────────────────────────────────────

    def get_stats(self) -> GraphStats:
        entity_type_counts: Dict[str, int] = defaultdict(int)
        for e in self._entities.values():
            entity_type_counts[e.entity_type] += 1

        relation_type_counts: Dict[str, int] = defaultdict(int)
        for r in self._relations.values():
            relation_type_counts[r.relation_type] += 1

        all_papers: Set[str] = set()
        for e in self._entities.values():
            all_papers.update(e.source_paper_ids)

        return GraphStats(
            total_entities=len(self._entities),
            total_relations=len(self._relations),
            entity_type_counts=dict(entity_type_counts),
            relation_type_counts=dict(relation_type_counts),
            total_papers_covered=len(all_papers),
            total_chunks_processed=len(self._processed_chunk_ids),
            graph_path=str(self.graph_dir),
            last_updated=datetime.now(),
        )

    def build_graph_search_result(
        self,
        entity: Entity,
        hops: int = 1,
    ) -> GraphSearchResult:
        """Construye un GraphSearchResult para una entidad con su vecindad."""
        all_entities, relations = self.get_neighborhood(entity.entity_id, hops=hops)
        related = [e for e in all_entities if e.entity_id != entity.entity_id]

        # Score = grado normalizado
        degree = self._graph.degree(entity.entity_id) if entity.entity_id in self._graph else 0
        max_degree = max(
            (self._graph.degree(n) for n in self._graph.nodes), default=1
        )
        score = degree / max_degree if max_degree > 0 else 0.0

        return GraphSearchResult(
            entity=entity,
            related_entities=related,
            relations=relations,
            relevance_score=score,
        )
