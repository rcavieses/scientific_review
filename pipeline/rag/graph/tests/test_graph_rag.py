"""
Tests para GraphRAG - Fase 5.

Todos los tests usan mocks: sin API real ni archivos reales (tempfile para persistencia).

Cubre:
  1. TestEntityModel           — serialización, normalización de IDs
  2. TestRelationModel         — serialización, construction del relation_id
  3. TestKnowledgeGraphStore   — inserción, merge, búsqueda, vecindad, persistencia
  4. TestGraphStoreIngestion   — ingest_extraction con datos crudos de Claude
  5. TestGraphExtractor        — llamada a API, parsing defensivo
  6. TestGraphQueryEngine      — consulta combinada, fallback a solo-vector
  7. TestGraphModelsFormat     — format_as_context, format_sources
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from pipeline.rag.graph.models import (
    Entity, Relation, GraphSearchResult, GraphQueryResult,
    GraphStats, normalize_entity_id, VALID_ENTITY_TYPES, VALID_RELATION_TYPES,
)
from pipeline.rag.graph.graph_store import KnowledgeGraphStore
from pipeline.rag.graph.extractor import GraphExtractor
from pipeline.rag.graph.graph_query_engine import GraphQueryEngine
from pipeline.rag.models import ChunkData, RAGSearchResult, IndexStats


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_chunk(
    chunk_id: str = "paper_a_chunk_000",
    paper_id: str = "paper_a",
    text: str = "Lutjanus peru is found in the Gulf of California at depths of 10-80m.",
    title: str = "Sample Paper",
    year: int = 2022,
) -> ChunkData:
    return ChunkData(
        chunk_id=chunk_id,
        paper_id=paper_id,
        text=text,
        chunk_index=0,
        page_number=1,
        char_start=0,
        char_end=len(text),
        total_chunks=1,
        source_pdf=f"outputs/pdfs/{paper_id}.pdf",
        title=title,
        authors=["Smith, J.", "Doe, A."],
        year=year,
        doi="10.1234/example",
    )


def make_entity(
    name: str = "Lutjanus peru",
    etype: str = "Species",
    chunk_id: str = "chunk_001",
    paper_id: str = "paper_a",
) -> Entity:
    eid = normalize_entity_id(etype, name)
    return Entity(
        entity_id=eid,
        entity_type=etype,
        name=name,
        aliases=["L. peru"],
        source_chunk_ids=[chunk_id],
        source_paper_ids=[paper_id],
        properties={"family": "Lutjanidae"},
    )


def make_relation(
    subj_id: str = "species::lutjanus_peru",
    rtype: str = "found_in",
    obj_id: str = "location::gulf_of_california",
    chunk_id: str = "chunk_001",
    paper_id: str = "paper_a",
) -> Relation:
    rid = f"{subj_id}::{rtype}::{obj_id}"
    return Relation(
        relation_id=rid,
        subject_id=subj_id,
        relation_type=rtype,
        object_id=obj_id,
        source_chunk_ids=[chunk_id],
        source_paper_ids=[paper_id],
        confidence=0.9,
        context_snippet="found in the Gulf of California",
    )


def make_raw_extraction(
    entity_name: str = "Lutjanus peru",
    entity_type: str = "Species",
    location: str = "Gulf of California",
) -> dict:
    """Simula la salida JSON de Claude para extract_from_chunk."""
    return {
        "entities": [
            {"name": entity_name, "type": entity_type, "aliases": ["L. peru"], "properties": {}},
            {"name": location, "type": "Location", "aliases": [], "properties": {}},
        ],
        "relations": [
            {
                "subject": entity_name,
                "relation": "found_in",
                "object": location,
                "confidence": 0.92,
                "context": f"{entity_name} is found in the {location}.",
            }
        ],
    }


def make_index_stats(total_chunks: int = 10) -> IndexStats:
    return IndexStats(
        total_chunks=total_chunks,
        total_papers=2,
        embedding_model="all-MiniLM-L6-v2",
        embedding_dimension=8,
        index_size_mb=0.1,
        index_path="outputs/rag_index",
        last_updated=datetime.now(),
    )


def make_mock_vector_db(results=None) -> MagicMock:
    db = MagicMock()
    db.get_stats.return_value = make_index_stats()
    db.search.return_value = results or []
    return db


def make_mock_embedding_gen(dim: int = 8) -> MagicMock:
    gen = MagicMock()
    gen.generate.return_value = np.ones(dim, dtype=np.float32) / np.sqrt(dim)
    return gen


def make_mock_claude(response_text: str = "Respuesta de prueba.") -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
    return client


def make_search_result(paper_id: str = "paper_a", score: float = 0.8) -> RAGSearchResult:
    return RAGSearchResult(
        chunk_id=f"{paper_id}_chunk_000",
        paper_id=paper_id,
        text="Sample text about marine biology.",
        score=score,
        page_number=1,
        chunk_index=0,
        source_pdf=f"outputs/pdfs/{paper_id}.pdf",
        title="Sample Paper",
        authors=["Smith, J.", "Doe, A."],
        year=2022,
        doi="10.1234/example",
    )


# ── 1. TestEntityModel ────────────────────────────────────────────────────────

class TestEntityModel(unittest.TestCase):

    def test_normalize_entity_id_species(self):
        eid = normalize_entity_id("Species", "Lutjanus peru")
        self.assertEqual(eid, "species::lutjanus_peru")

    def test_normalize_entity_id_method(self):
        eid = normalize_entity_id("Method", "otolith microchemistry")
        self.assertEqual(eid, "method::otolith_microchemistry")

    def test_normalize_entity_id_location(self):
        eid = normalize_entity_id("Location", "Gulf of California")
        self.assertEqual(eid, "location::gulf_of_california")

    def test_normalize_strips_special_chars(self):
        eid = normalize_entity_id("Species", "L. peru (red snapper)")
        self.assertNotIn("(", eid)
        self.assertNotIn(")", eid)

    def test_entity_to_dict_round_trip(self):
        entity = make_entity()
        restored = Entity.from_dict(entity.to_dict())
        self.assertEqual(restored.entity_id, entity.entity_id)
        self.assertEqual(restored.name, entity.name)
        self.assertEqual(restored.aliases, entity.aliases)
        self.assertEqual(restored.source_chunk_ids, entity.source_chunk_ids)
        self.assertEqual(restored.source_paper_ids, entity.source_paper_ids)
        self.assertEqual(restored.properties, entity.properties)

    def test_entity_str(self):
        entity = make_entity()
        s = str(entity)
        self.assertIn("Lutjanus peru", s)
        self.assertIn("Species", s)


# ── 2. TestRelationModel ──────────────────────────────────────────────────────

class TestRelationModel(unittest.TestCase):

    def test_relation_id_is_triple(self):
        rel = make_relation()
        parts = rel.relation_id.split("::")
        # relation_id = subj::type::obj = 4 parts (subj has one ::, type has none, obj has one ::)
        self.assertIn("found_in", rel.relation_id)
        self.assertTrue(rel.relation_id.startswith(rel.subject_id))

    def test_relation_to_dict_round_trip(self):
        rel = make_relation()
        restored = Relation.from_dict(rel.to_dict())
        self.assertEqual(restored.relation_id, rel.relation_id)
        self.assertEqual(restored.subject_id, rel.subject_id)
        self.assertEqual(restored.relation_type, rel.relation_type)
        self.assertEqual(restored.object_id, rel.object_id)
        self.assertAlmostEqual(restored.confidence, rel.confidence)
        self.assertEqual(restored.context_snippet, rel.context_snippet)

    def test_relation_confidence_preserved(self):
        rel = make_relation()
        rel.confidence = 0.73
        restored = Relation.from_dict(rel.to_dict())
        self.assertAlmostEqual(restored.confidence, 0.73)

    def test_relation_str(self):
        rel = make_relation()
        s = str(rel)
        self.assertIn("found_in", s)


# ── 3. TestKnowledgeGraphStore ────────────────────────────────────────────────

class TestKnowledgeGraphStore(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = KnowledgeGraphStore(graph_dir=Path(self._tmpdir.name))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_add_entity_creates_node(self):
        entity = make_entity()
        self.store.add_entity(entity)
        self.assertIn(entity.entity_id, self.store._entities)

    def test_add_entity_merges_aliases(self):
        e1 = make_entity(name="Lutjanus peru")
        e1.aliases = ["L. peru"]
        self.store.add_entity(e1)

        e2 = Entity(
            entity_id=e1.entity_id,
            entity_type="Species",
            name="Lutjanus peru",
            aliases=["red snapper"],
            source_chunk_ids=["chunk_002"],
            source_paper_ids=["paper_b"],
        )
        self.store.add_entity(e2)

        merged = self.store._entities[e1.entity_id]
        self.assertIn("L. peru", merged.aliases)
        self.assertIn("red snapper", merged.aliases)
        self.assertIn("chunk_002", merged.source_chunk_ids)
        self.assertIn("paper_b", merged.source_paper_ids)

    def test_add_relation_creates_edge(self):
        subj = make_entity("Lutjanus peru", "Species")
        obj = make_entity("Gulf of California", "Location")
        self.store.add_entity(subj)
        self.store.add_entity(obj)
        rel = make_relation(subj.entity_id, "found_in", obj.entity_id)
        self.store.add_relation(rel)
        self.assertIn(rel.relation_id, self.store._relations)

    def test_add_relation_is_idempotent(self):
        subj = make_entity("Lutjanus peru", "Species")
        obj = make_entity("Gulf of California", "Location")
        self.store.add_entity(subj)
        self.store.add_entity(obj)
        rel = make_relation(subj.entity_id, "found_in", obj.entity_id)
        self.store.add_relation(rel)
        self.store.add_relation(rel)
        self.assertEqual(len(self.store._relations), 1)

    def test_search_entities_exact_match(self):
        self.store.add_entity(make_entity("Lutjanus peru", "Species"))
        results = self.store.search_entities("Lutjanus peru")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Lutjanus peru")

    def test_search_entities_substring_match(self):
        self.store.add_entity(make_entity("Lutjanus peru", "Species"))
        results = self.store.search_entities("Lutjanus")
        self.assertGreater(len(results), 0)

    def test_search_entities_alias_match(self):
        self.store.add_entity(make_entity("Lutjanus peru", "Species"))
        results = self.store.search_entities("L. peru")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].name, "Lutjanus peru")

    def test_search_entities_type_filter(self):
        self.store.add_entity(make_entity("Lutjanus peru", "Species"))
        self.store.add_entity(make_entity("Gulf of California", "Location"))
        results = self.store.search_entities("Gulf", entity_types=["Location"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].entity_type, "Location")

    def test_search_entities_no_match(self):
        self.store.add_entity(make_entity("Lutjanus peru", "Species"))
        results = self.store.search_entities("xyz_nonexistent")
        self.assertEqual(results, [])

    def test_get_neighborhood_returns_neighbors(self):
        subj = make_entity("Lutjanus peru", "Species")
        obj = make_entity("Gulf of California", "Location")
        self.store.add_entity(subj)
        self.store.add_entity(obj)
        rel = make_relation(subj.entity_id, "found_in", obj.entity_id)
        self.store.add_relation(rel)

        entities, relations = self.store.get_neighborhood(subj.entity_id, hops=1)
        entity_ids = [e.entity_id for e in entities]
        self.assertIn(subj.entity_id, entity_ids)
        self.assertIn(obj.entity_id, entity_ids)
        self.assertEqual(len(relations), 1)

    def test_get_neighborhood_empty_for_unknown(self):
        entities, relations = self.store.get_neighborhood("nonexistent::entity")
        self.assertEqual(entities, [])
        self.assertEqual(relations, [])

    def test_get_papers_for_entity(self):
        entity = make_entity(paper_id="paper_a")
        self.store.add_entity(entity)
        papers = self.store.get_papers_for_entity(entity.entity_id)
        self.assertIn("paper_a", papers)

    def test_get_entities_for_paper(self):
        self.store.add_entity(make_entity("Lutjanus peru", "Species", paper_id="paper_a"))
        self.store.add_entity(make_entity("Gulf of California", "Location", paper_id="paper_b"))
        entities = self.store.get_entities_for_paper("paper_a")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].name, "Lutjanus peru")

    def test_save_and_load_round_trip(self):
        entity = make_entity()
        self.store.add_entity(entity)
        subj = entity
        obj = make_entity("Gulf of California", "Location")
        self.store.add_entity(obj)
        rel = make_relation(subj.entity_id, "found_in", obj.entity_id)
        self.store.add_relation(rel)
        self.store.mark_chunk_processed("chunk_001")
        self.store.save()

        # Cargar en nuevo store
        store2 = KnowledgeGraphStore(graph_dir=Path(self._tmpdir.name))
        loaded = store2.load()
        self.assertTrue(loaded)
        self.assertIn(entity.entity_id, store2._entities)
        self.assertIn(rel.relation_id, store2._relations)
        self.assertIn("chunk_001", store2._processed_chunk_ids)

    def test_load_returns_false_when_no_file(self):
        loaded = self.store.load()
        self.assertFalse(loaded)

    def test_get_stats(self):
        self.store.add_entity(make_entity("Lutjanus peru", "Species"))
        self.store.add_entity(make_entity("Gulf of California", "Location"))
        stats = self.store.get_stats()
        self.assertEqual(stats.total_entities, 2)
        self.assertEqual(stats.entity_type_counts.get("Species"), 1)
        self.assertEqual(stats.entity_type_counts.get("Location"), 1)


# ── 4. TestGraphStoreIngestion ────────────────────────────────────────────────

class TestGraphStoreIngestion(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = KnowledgeGraphStore(graph_dir=Path(self._tmpdir.name))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_ingest_adds_entities_and_relations(self):
        raw = make_raw_extraction()
        new_ent, new_rel = self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        self.assertEqual(new_ent, 2)
        self.assertEqual(new_rel, 1)

    def test_ingest_normalizes_entity_ids(self):
        raw = make_raw_extraction("Lutjanus peru", "Species")
        self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        expected_id = normalize_entity_id("Species", "Lutjanus peru")
        self.assertIn(expected_id, self.store._entities)

    def test_ingest_attaches_chunk_and_paper_ids(self):
        raw = make_raw_extraction()
        self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        expected_id = normalize_entity_id("Species", "Lutjanus peru")
        entity = self.store._entities[expected_id]
        self.assertIn("chunk_001", entity.source_chunk_ids)
        self.assertIn("paper_a", entity.source_paper_ids)

    def test_ingest_marks_chunk_as_processed(self):
        raw = make_raw_extraction()
        self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        self.assertTrue(self.store.is_chunk_processed("chunk_001"))

    def test_ingest_empty_extraction_adds_nothing(self):
        raw = {"entities": [], "relations": []}
        new_ent, new_rel = self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        self.assertEqual(new_ent, 0)
        self.assertEqual(new_rel, 0)

    def test_ingest_skips_invalid_entity_type(self):
        raw = {
            "entities": [{"name": "X", "type": "InvalidType", "aliases": [], "properties": {}}],
            "relations": [],
        }
        new_ent, _ = self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        self.assertEqual(new_ent, 0)

    def test_ingest_skips_invalid_relation_type(self):
        raw = {
            "entities": [
                {"name": "Lutjanus peru", "type": "Species", "aliases": [], "properties": {}},
                {"name": "Ocean", "type": "Location", "aliases": [], "properties": {}},
            ],
            "relations": [
                {"subject": "Lutjanus peru", "relation": "likes", "object": "Ocean",
                 "confidence": 0.9, "context": "..."},
            ],
        }
        _, new_rel = self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        self.assertEqual(new_rel, 0)

    def test_ingest_confidence_clamped(self):
        raw = {
            "entities": [
                {"name": "Lutjanus peru", "type": "Species", "aliases": [], "properties": {}},
                {"name": "Ocean", "type": "Location", "aliases": [], "properties": {}},
            ],
            "relations": [
                {"subject": "Lutjanus peru", "relation": "found_in", "object": "Ocean",
                 "confidence": 1.5, "context": "..."},  # > 1.0
            ],
        }
        self.store.ingest_extraction(raw, "chunk_001", "paper_a")
        rel = list(self.store._relations.values())[0]
        self.assertLessEqual(rel.confidence, 1.0)


# ── 5. TestGraphExtractor ─────────────────────────────────────────────────────

class TestGraphExtractor(unittest.TestCase):

    def setUp(self):
        self.chunk = make_chunk()
        self.claude = make_mock_claude(json.dumps(make_raw_extraction()))
        self.extractor = GraphExtractor(client=self.claude, request_delay=0)

    def test_extract_calls_api_once(self):
        self.extractor.extract_from_chunk(self.chunk)
        self.claude.messages.create.assert_called_once()

    def test_extract_returns_entities_and_relations(self):
        result = self.extractor.extract_from_chunk(self.chunk)
        self.assertIn("entities", result)
        self.assertIn("relations", result)
        self.assertGreater(len(result["entities"]), 0)

    def test_extract_system_prompt_has_entity_types(self):
        self.extractor.extract_from_chunk(self.chunk)
        call_kwargs = self.claude.messages.create.call_args[1]
        system = call_kwargs["system"]
        self.assertIn("Species", system)
        self.assertIn("found_in", system)

    def test_extract_user_message_contains_chunk_text(self):
        self.extractor.extract_from_chunk(self.chunk)
        call_kwargs = self.claude.messages.create.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        self.assertIn("Lutjanus peru", user_content)

    def test_extract_graceful_fallback_on_invalid_json(self):
        bad_claude = make_mock_claude("this is not json {")
        extractor = GraphExtractor(client=bad_claude, request_delay=0)
        result = extractor.extract_from_chunk(self.chunk)
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["relations"], [])

    def test_extract_strips_markdown_fences(self):
        json_str = json.dumps(make_raw_extraction())
        fenced = f"```json\n{json_str}\n```"
        fenced_claude = make_mock_claude(fenced)
        extractor = GraphExtractor(client=fenced_claude, request_delay=0)
        result = extractor.extract_from_chunk(self.chunk)
        self.assertGreater(len(result["entities"]), 0)

    def test_extract_raises_on_api_failure(self):
        bad_claude = MagicMock()
        bad_claude.messages.create.side_effect = Exception("timeout")
        extractor = GraphExtractor(client=bad_claude, request_delay=0)
        with self.assertRaises(RuntimeError):
            extractor.extract_from_chunk(self.chunk)

    def test_extract_from_chunks_skips_processed(self):
        chunks = [make_chunk("chunk_001"), make_chunk("chunk_002")]
        self.extractor.extract_from_chunks(chunks, skip_chunk_ids={"chunk_001"})
        # Solo chunk_002 debería haberse procesado
        self.assertEqual(self.claude.messages.create.call_count, 1)

    def test_extract_from_chunks_adds_chunk_id_to_result(self):
        chunks = [make_chunk("chunk_001")]
        results = self.extractor.extract_from_chunks(chunks)
        self.assertEqual(results[0]["chunk_id"], "chunk_001")


# ── 6. TestGraphQueryEngine ───────────────────────────────────────────────────

class TestGraphQueryEngine(unittest.TestCase):

    def setUp(self):
        # Graph store con una entidad conocida
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = KnowledgeGraphStore(graph_dir=Path(self._tmpdir.name))
        entity = make_entity("Lutjanus peru", "Species")
        loc = make_entity("Gulf of California", "Location")
        self.store.add_entity(entity)
        self.store.add_entity(loc)
        rel = make_relation(entity.entity_id, "found_in", loc.entity_id)
        self.store.add_relation(rel)

        self.vector_db = make_mock_vector_db([make_search_result()])
        self.emb = make_mock_embedding_gen()
        self.claude = make_mock_claude("Respuesta combinada grafo + vector.")

        self.engine = GraphQueryEngine(
            graph_store=self.store,
            vector_db=self.vector_db,
            embedding_generator=self.emb,
            client=self.claude,
            top_k=5,
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_query_returns_graph_query_result(self):
        result = self.engine.query("Where does Lutjanus peru live?")
        self.assertIsInstance(result, GraphQueryResult)

    def test_query_calls_vector_db(self):
        self.engine.query("Lutjanus peru habitat")
        self.vector_db.search.assert_called_once()

    def test_query_calls_claude(self):
        self.engine.query("Lutjanus peru habitat")
        self.claude.messages.create.assert_called_once()

    def test_query_raises_on_empty_question(self):
        with self.assertRaises(ValueError):
            self.engine.query("")

    def test_query_raises_when_index_empty(self):
        db = make_mock_vector_db()
        db.get_stats.return_value = make_index_stats(total_chunks=0)
        engine = GraphQueryEngine(
            graph_store=self.store, vector_db=db,
            embedding_generator=self.emb, client=self.claude,
        )
        with self.assertRaises(ValueError):
            engine.query("question")

    def test_combined_context_has_graph_section(self):
        self.engine.query("Lutjanus peru habitat in Gulf of California")
        call_kwargs = self.claude.messages.create.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        self.assertIn("Grafo de conocimiento", user_content)

    def test_combined_context_has_fragment_section(self):
        self.engine.query("question")
        call_kwargs = self.claude.messages.create.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        self.assertIn("Fragmentos", user_content)

    def test_fallback_to_vector_only_when_no_graph_entities(self):
        empty_store = KnowledgeGraphStore(graph_dir=Path(self._tmpdir.name + "_empty"))
        engine = GraphQueryEngine(
            graph_store=empty_store,
            vector_db=self.vector_db,
            embedding_generator=self.emb,
            client=self.claude,
        )
        result = engine.query("some question")
        self.assertEqual(result.graph_entities_used, 0)
        # Debe seguir llamando a Claude con solo los fragmentos
        self.claude.messages.create.assert_called_once()

    def test_result_answer_matches_claude_response(self):
        result = self.engine.query("Lutjanus peru question")
        self.assertEqual(result.answer, "Respuesta combinada grafo + vector.")

    def test_raises_runtime_error_on_api_failure(self):
        bad_claude = MagicMock()
        bad_claude.messages.create.side_effect = Exception("API error")
        engine = GraphQueryEngine(
            graph_store=self.store,
            vector_db=self.vector_db,
            embedding_generator=self.emb,
            client=bad_claude,
        )
        with self.assertRaises(RuntimeError):
            engine.query("question")


# ── 7. TestGraphModelsFormat ──────────────────────────────────────────────────

class TestGraphModelsFormat(unittest.TestCase):

    def test_graph_search_result_format_contains_entity_name(self):
        entity = make_entity("Lutjanus peru", "Species")
        gr = GraphSearchResult(entity=entity, related_entities=[], relations=[])
        context = gr.format_as_context()
        self.assertIn("Lutjanus peru", context)
        self.assertIn("Species", context)

    def test_graph_search_result_format_lists_relations(self):
        entity = make_entity("Lutjanus peru", "Species")
        loc = make_entity("Gulf of California", "Location")
        rel = make_relation(entity.entity_id, "found_in", loc.entity_id)
        gr = GraphSearchResult(
            entity=entity, related_entities=[loc], relations=[rel]
        )
        context = gr.format_as_context()
        self.assertIn("found_in", context)
        self.assertIn("Gulf of California", context)

    def test_graph_search_result_empty_relations(self):
        entity = make_entity()
        gr = GraphSearchResult(entity=entity, related_entities=[], relations=[])
        context = gr.format_as_context()
        # No debe crashear
        self.assertIn("Lutjanus peru", context)

    def test_graph_query_result_format_sources(self):
        sources = [make_search_result("paper_a"), make_search_result("paper_b")]
        result = GraphQueryResult(
            question="q", answer="a", sources=sources,
            graph_results=[], chunks_used=2, graph_entities_used=0,
            model="m",
        )
        formatted = result.format_sources()
        self.assertEqual(formatted.count("•"), 2)

    def test_graph_query_result_format_graph_context_empty(self):
        result = GraphQueryResult(
            question="q", answer="a", sources=[],
            graph_results=[], chunks_used=0, graph_entities_used=0,
            model="m",
        )
        formatted = result.format_graph_context()
        self.assertIn("Sin entidades", formatted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
