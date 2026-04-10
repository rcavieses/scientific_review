"""
Gestión del índice FAISS para chunks de papers científicos.

Estructura de archivos persistidos en index_dir/:
  index.faiss          — índice FAISS binario
  metadata_store.json  — Dict[str(faiss_id), ChunkData serializado]
  index_config.json    — modelo, dimensión, tipo de índice, timestamp
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import faiss

from .models import ChunkData, ChunkVector, IndexStats, RAGSearchResult


class VectorDBManager:
    """
    Gestiona un índice FAISS para búsqueda semántica sobre chunks de papers.

    Usa FlatIP (inner product) con vectores normalizados a unit norm, lo que
    equivale a similitud coseno. Los embeddings de SentenceTransformers ya
    están normalizados, por lo que el score resultante es directamente la
    similitud coseno en el rango [0, 1].

    El metadata_store es un dict en memoria sincronizado con disco en cada
    llamada a save(). La clave es str(faiss_id) para compatibilidad JSON.

    Args:
        index_dir: Directorio donde persistir el índice.
        embedding_dim: Dimensión de los vectores (ej: 384 para MiniLM).
        index_type: "FlatIP" (recomendado) o "FlatL2".
        verbose: Mostrar progreso en operaciones de escritura.
    """

    INDEX_FILE = "index.faiss"
    METADATA_FILE = "metadata_store.json"
    CONFIG_FILE = "index_config.json"

    def __init__(
        self,
        index_dir: Path,
        embedding_dim: int,
        index_type: str = "FlatIP",
        verbose: bool = False,
    ):
        self.index_dir = Path(index_dir)
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        self.verbose = verbose

        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Estado interno
        self._index: Optional[faiss.Index] = None
        self._metadata: Dict[str, Dict[str, Any]] = {}  # str(faiss_id) → ChunkData dict
        self._next_id: int = 0
        self._embedding_model: str = "unknown"

        # Crear índice vacío
        self._index = self._create_index()

    # ── API pública ─────────────────────────────────────────────────────────

    def add_chunks(self, chunk_vectors: List[ChunkVector]) -> int:
        """
        Agrega chunks al índice.

        Args:
            chunk_vectors: Lista de ChunkVector con vector y metadata.

        Returns:
            Número de chunks agregados exitosamente.
        """
        if not chunk_vectors:
            return 0

        # Preparar matriz de vectores
        vectors = np.stack([cv.vector for cv in chunk_vectors]).astype(np.float32)
        vectors = self._normalize(vectors)

        # Asignar IDs y registrar en metadata
        start_id = self._next_id
        for i, cv in enumerate(chunk_vectors):
            faiss_id = start_id + i
            cv.faiss_id = faiss_id
            self._metadata[str(faiss_id)] = cv.chunk.to_dict()

        self._next_id += len(chunk_vectors)

        # Insertar en FAISS
        self._index.add(vectors)

        # Guardar modelo usado (del primero no vacío)
        if self._embedding_model == "unknown" and chunk_vectors:
            self._embedding_model = chunk_vectors[0].embedding_model

        if self.verbose:
            print(f"  Agregados {len(chunk_vectors)} chunks (total: {self._index.ntotal})")

        return len(chunk_vectors)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
    ) -> List[RAGSearchResult]:
        """
        Busca los top_k chunks más similares al query_vector.

        Args:
            query_vector: Vector de la query (float32, 1D shape (dim,)).
            top_k: Número de resultados a devolver.

        Returns:
            Lista de RAGSearchResult ordenada por score descendente.
        """
        if self._index.ntotal == 0:
            return []

        # Preparar query
        q = query_vector.astype(np.float32).reshape(1, -1)
        q = self._normalize(q)

        k = min(top_k, self._index.ntotal)
        scores, ids = self._index.search(q, k)

        results: List[RAGSearchResult] = []
        for score, faiss_id in zip(scores[0], ids[0]):
            if faiss_id == -1:
                continue

            meta = self._metadata.get(str(faiss_id))
            if not meta:
                continue

            # Convertir score a similitud coseno 0-1
            similarity = float(self._score_to_similarity(float(score)))

            results.append(RAGSearchResult(
                chunk_id=meta["chunk_id"],
                paper_id=meta["paper_id"],
                text=meta["text"],
                score=similarity,
                page_number=meta["page_number"],
                chunk_index=meta["chunk_index"],
                source_pdf=meta["source_pdf"],
                title=meta.get("title"),
                authors=meta.get("authors"),
                year=meta.get("year"),
                doi=meta.get("doi"),
            ))

        return sorted(results, key=lambda r: r.score, reverse=True)

    def save(self) -> None:
        """Persiste el índice FAISS, metadata_store y config a disco."""
        faiss.write_index(self._index, str(self.index_dir / self.INDEX_FILE))

        with open(self.index_dir / self.METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2, default=str)

        config = {
            "embedding_model": self._embedding_model,
            "embedding_dimension": self.embedding_dim,
            "index_type": self.index_type,
            "total_chunks": self._index.ntotal,
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.index_dir / self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        if self.verbose:
            print(f"  Indice guardado en {self.index_dir} ({self._index.ntotal} chunks)")

    def load(self) -> bool:
        """
        Carga un índice existente desde disco.

        Returns:
            True si se cargó correctamente, False si no existe.
        """
        index_path = self.index_dir / self.INDEX_FILE
        meta_path = self.index_dir / self.METADATA_FILE
        config_path = self.index_dir / self.CONFIG_FILE

        if not index_path.exists():
            return False

        self._index = faiss.read_index(str(index_path))

        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                self._metadata = json.load(f)

        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            self._embedding_model = config.get("embedding_model", "unknown")

        # Restaurar next_id
        if self._metadata:
            self._next_id = max(int(k) for k in self._metadata.keys()) + 1

        if self.verbose:
            print(f"  Indice cargado: {self._index.ntotal} chunks desde {self.index_dir}")

        return True

    def get_stats(self) -> IndexStats:
        """Retorna estadísticas del índice actual."""
        index_file = self.index_dir / self.INDEX_FILE
        size_mb = index_file.stat().st_size / (1024 * 1024) if index_file.exists() else 0.0

        papers = self.get_papers_indexed()

        return IndexStats(
            total_chunks=self._index.ntotal if self._index else 0,
            total_papers=len(papers),
            embedding_model=self._embedding_model,
            embedding_dimension=self.embedding_dim,
            index_size_mb=round(size_mb, 3),
            index_path=str(self.index_dir),
            last_updated=datetime.now(),
        )

    def get_papers_indexed(self) -> List[str]:
        """Retorna lista de paper_ids únicos en el índice."""
        paper_ids = {meta["paper_id"] for meta in self._metadata.values()}
        return sorted(paper_ids)

    def is_paper_indexed(self, paper_id: str) -> bool:
        """Verifica si un paper ya está indexado."""
        return any(
            meta["paper_id"] == paper_id
            for meta in self._metadata.values()
        )

    def delete_paper(self, paper_id: str) -> int:
        """
        Elimina todos los chunks de un paper del índice.

        FAISS FlatIndex no soporta borrado directo, por lo que se
        reconstruye el índice completo sin los chunks del paper eliminado.

        Returns:
            Número de chunks eliminados.
        """
        ids_to_keep = [
            int(fid) for fid, meta in self._metadata.items()
            if meta["paper_id"] != paper_id
        ]
        ids_to_delete = [
            int(fid) for fid, meta in self._metadata.items()
            if meta["paper_id"] == paper_id
        ]

        if not ids_to_delete:
            return 0

        # Reconstruir índice con solo los IDs a conservar
        new_index = self._create_index()
        new_metadata: Dict[str, Dict] = {}

        if ids_to_keep:
            # Extraer vectores a conservar (reconstrucción desde el índice)
            vectors = np.zeros((len(ids_to_keep), self.embedding_dim), dtype=np.float32)
            self._index.reconstruct_batch(
                np.array(ids_to_keep, dtype=np.int64), vectors
            )
            new_index.add(vectors)

            for new_id, old_id in enumerate(ids_to_keep):
                new_metadata[str(new_id)] = self._metadata[str(old_id)]

        self._index = new_index
        self._metadata = new_metadata
        self._next_id = len(ids_to_keep)

        if self.verbose:
            print(f"  Eliminados {len(ids_to_delete)} chunks de '{paper_id}'")

        return len(ids_to_delete)

    # ── Métodos internos ─────────────────────────────────────────────────────

    def _create_index(self) -> faiss.Index:
        """Crea un índice FAISS vacío del tipo configurado."""
        if self.index_type == "FlatIP":
            return faiss.IndexFlatIP(self.embedding_dim)
        elif self.index_type == "FlatL2":
            return faiss.IndexFlatL2(self.embedding_dim)
        else:
            raise ValueError(f"index_type desconocido: {self.index_type}. Usa 'FlatIP' o 'FlatL2'.")

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        """Normaliza vectores a unit norm (necesario para FlatIP = cosine similarity)."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)  # evitar división por cero
        return vectors / norms

    def _score_to_similarity(self, raw_score: float) -> float:
        """
        Convierte el score raw de FAISS a similitud [0, 1].

        Para FlatIP con vectores normalizados: raw_score ya es cosine similarity
        en [-1, 1]. Lo escalamos a [0, 1].
        Para FlatL2: convierte distancia euclidiana a similitud aproximada.
        """
        if self.index_type == "FlatIP":
            return (raw_score + 1.0) / 2.0
        else:
            # Similitud aproximada desde distancia L2: sim = 1 / (1 + dist)
            return 1.0 / (1.0 + raw_score)
