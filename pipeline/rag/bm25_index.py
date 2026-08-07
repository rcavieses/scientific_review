"""
Índice BM25 (keyword-based) sobre los mismos chunks del índice FAISS.

Complementa la búsqueda semántica: encuentra por coincidencia léxica
exacta contenido que el embedding no relaciona bien con la pregunta
(nombres de especies, tablas de datos densas en números, términos
técnicos exactos) — ver HybridRAGQueryEngine para la fusión de ambas
señales.
"""

import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rank_bm25 import BM25Okapi

_TOKEN_PATTERN = re.compile(r"[a-zA-Záéíóúñüà-ÿ0-9]+")


def tokenize(text: str) -> List[str]:
    """Tokenización simple: minúsculas, palabras/números, soporta acentos."""
    return _TOKEN_PATTERN.findall(text.lower())


class BM25IndexManager:
    """
    Gestiona un índice BM25 sobre los chunks de metadata_store.json.

    Se guarda en el mismo directorio que el índice FAISS (comparten el
    mismo conjunto de chunks, alineados por chunk_id).

    Args:
        index_dir: Directorio del índice (ej: outputs/rag_index_goc_full).
    """

    BM25_FILE = "bm25_index.pkl"

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self._bm25: BM25Okapi = None
        self._chunk_ids: List[str] = []  # orden alineado con el corpus BM25

    def build_from_metadata_store(self, metadata_store: Dict[str, Dict[str, Any]]) -> int:
        """
        Construye el índice BM25 a partir del metadata_store cargado
        (mismo formato que usa VectorDBManager: dict keyed por faiss_id
        como string, cada valor con al menos 'chunk_id' y 'text').

        Returns:
            Número de chunks indexados.
        """
        texts_by_id = {record["chunk_id"]: record["text"] for record in metadata_store.values()}
        return self.build_from_texts(texts_by_id)

    def build_from_texts(self, texts_by_id: Dict[str, str]) -> int:
        """
        Construye el índice BM25 a partir de un dict chunk_id -> texto
        arbitrario. Permite indexar sobre texto contextualizado (ver
        contextual_text.py) en vez del texto crudo del chunk.

        Returns:
            Número de chunks indexados.
        """
        chunk_ids = list(texts_by_id.keys())
        corpus_tokens = [tokenize(texts_by_id[cid]) for cid in chunk_ids]

        self._chunk_ids = chunk_ids
        self._bm25 = BM25Okapi(corpus_tokens)
        return len(chunk_ids)

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        Busca los top_k chunks más relevantes por BM25.

        Returns:
            Lista de (chunk_id, bm25_score) ordenada por score descendente.
            Chunks con score 0 (sin ningún término en común) se excluyen.
        """
        if self._bm25 is None:
            raise RuntimeError(
                "Índice BM25 no cargado. Llama a build_from_metadata_store() o load()."
            )

        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        ranked = sorted(zip(self._chunk_ids, scores), key=lambda x: x[1], reverse=True)
        return [(cid, float(s)) for cid, s in ranked[:top_k] if s > 0]

    def save(self) -> None:
        """Persiste el índice BM25 a disco (pickle)."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        path = self.index_dir / self.BM25_FILE
        with open(path, "wb") as f:
            pickle.dump({"bm25": self._bm25, "chunk_ids": self._chunk_ids}, f)

    def load(self) -> bool:
        """Carga el índice BM25 desde disco. Retorna False si no existe."""
        path = self.index_dir / self.BM25_FILE
        if not path.exists():
            return False
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._bm25 = data["bm25"]
        self._chunk_ids = data["chunk_ids"]
        return True

    @property
    def total_chunks(self) -> int:
        return len(self._chunk_ids)
