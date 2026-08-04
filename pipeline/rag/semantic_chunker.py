"""
Chunking semántico basado en embeddings BERT.

Estrategia:
  1. Dividir en oraciones
  2. Generar embeddings para cada oración
  3. Calcular similitud entre oraciones consecutivas
  4. Hacer cortes cuando similitud cae (cambio de tema)
  5. Combinar oraciones en chunks de tamaño razonable

Ventaja: Mantiene contexto semántico, no corta a mitad de temas.
"""

import re
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

from .models import ChunkData


class SemanticChunker:
    """
    Divide texto en chunks manteniendo coherencia semántica.

    Usa embeddings BERT para detectar cambios de tema y hacer cortes
    inteligentes que preservan el contexto.

    Args:
        embedding_generator: Generador de embeddings (ej: LocalEmbeddingGenerator).
        similarity_threshold: Umbral de similitud para hacer corte (default: 0.5).
        min_chunk_size: Mínimo de caracteres por chunk (default: 300).
        max_chunk_size: Máximo de caracteres por chunk (default: 1000).
        verbose: Mostrar estadísticas.
    """

    def __init__(
        self,
        embedding_generator,
        similarity_threshold: float = 0.5,
        min_chunk_size: int = 300,
        max_chunk_size: int = 1000,
        verbose: bool = False,
    ):
        self.embedding_generator = embedding_generator
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.verbose = verbose

    def chunk_pages(
        self,
        pages: List[Tuple[int, str]],
        paper_id: str,
        source_pdf: str,
    ) -> List[ChunkData]:
        """Chunkea directamente desde páginas separadas."""
        if not pages:
            return []

        # Construir texto completo con mapa de páginas
        full_text_parts: List[str] = []
        page_map: List[Tuple[int, int, int]] = []  # (page_num, char_start, char_end)
        cursor = 0

        for page_num, text in pages:
            start = cursor
            full_text_parts.append(text)
            cursor += len(text)
            end = cursor
            page_map.append((page_num, start, end))
            cursor += 2  # separador \n\n entre páginas
            full_text_parts.append("\n\n")

        full_text = "".join(full_text_parts).rstrip()
        return self.chunk_text(full_text, paper_id, source_pdf, page_map=page_map)

    def chunk_text(
        self,
        text: str,
        paper_id: str,
        source_pdf: str,
        page_map: Optional[List[Tuple[int, int, int]]] = None,
    ) -> List[ChunkData]:
        """Divide texto completo en chunks semánticamente coherentes."""
        if not text or len(text) < self.min_chunk_size:
            return []

        # 1. Dividir en oraciones
        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        # 2. Generar embeddings para cada oración
        sentence_texts = [s["text"] for s in sentences]
        embeddings = self.embedding_generator.batch_generate(sentence_texts)

        # 3. Calcular similitudes y puntos de corte
        cut_indices = self._find_semantic_breaks(embeddings)

        # 4. Agrupar oraciones en chunks
        chunks = self._create_chunks(
            sentences, cut_indices, paper_id, source_pdf, page_map
        )

        if self.verbose:
            self._print_stats(paper_id, chunks, len(text), len(sentences))

        return chunks

    def get_stats(self, chunks: List[ChunkData]) -> Dict[str, Any]:
        """Estadísticas de chunking."""
        if not chunks:
            return {"total": 0}

        sizes = [len(c.text) for c in chunks]
        return {
            "total": len(chunks),
            "chars_min": min(sizes),
            "chars_max": max(sizes),
            "chars_avg": round(sum(sizes) / len(sizes)),
            "chars_total": sum(sizes),
            "papers": len({c.paper_id for c in chunks}),
        }

    # ── Métodos internos ───────────────────────────────────────────────────

    def _split_into_sentences(self, text: str) -> List[Dict[str, Any]]:
        """
        Divide texto en oraciones.

        Retorna lista de {"text": str, "char_start": int, "char_end": int}
        """
        # Patrón: fin de oración (punto/exclamación/interrogación seguido de espacio)
        # Pero no en abreviaturas comunes como "et al.", "e.g.", etc.
        pattern = r"(?<!\.\s)(?<!\betal)(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)([.!?])\s+"

        sentences = []
        last_end = 0

        for match in re.finditer(pattern, text):
            end = match.start(1) + 1
            sentence_text = text[last_end:end].strip()

            if sentence_text:
                sentences.append({
                    "text": sentence_text,
                    "char_start": last_end,
                    "char_end": end,
                })

            last_end = end + 1

        # Añadir última oración si existe
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                sentences.append({
                    "text": remaining,
                    "char_start": last_end,
                    "char_end": len(text),
                })

        return sentences

    def _find_semantic_breaks(self, embeddings: np.ndarray) -> List[int]:
        """
        Identifica índices de oraciones donde hacer cortes (cambios de tema).

        Retorna lista de índices donde las similitudes son bajas.
        """
        if len(embeddings) < 2:
            return []

        breaks = []

        # Normalizar embeddings (coseno necesita unit norm)
        embeddings_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)

        # Calcular similitud entre oraciones consecutivas
        for i in range(len(embeddings_norm) - 1):
            similarity = np.dot(embeddings_norm[i], embeddings_norm[i + 1])

            if similarity < self.similarity_threshold:
                breaks.append(i)  # Corte DESPUÉS de la oración i

        return breaks

    def _create_chunks(
        self,
        sentences: List[Dict[str, Any]],
        cut_indices: List[int],
        paper_id: str,
        source_pdf: str,
        page_map: Optional[List[Tuple[int, int, int]]],
    ) -> List[ChunkData]:
        """
        Agrupa oraciones en chunks respetando los cortes semánticos.

        Respeta min/max chunk size, evitando chunks muy pequeños o muy grandes.
        """
        chunks = []
        chunk_index = 0

        # Definir límites de segmentos usando cut_indices
        segment_boundaries = [0] + [i + 1 for i in cut_indices] + [len(sentences)]
        segment_boundaries = sorted(set(segment_boundaries))

        for seg_start, seg_end in zip(segment_boundaries[:-1], segment_boundaries[1:]):
            segment_sentences = sentences[seg_start:seg_end]

            if not segment_sentences:
                continue

            # Subdividir si el segmento es muy grande
            sub_chunks = self._subdivide_segment(segment_sentences)

            for chunk_sentences in sub_chunks:
                if not chunk_sentences:
                    continue

                chunk_text = " ".join(s["text"] for s in chunk_sentences).strip()

                if len(chunk_text) < self.min_chunk_size:
                    continue

                char_start = chunk_sentences[0]["char_start"]
                char_end = chunk_sentences[-1]["char_end"]
                page_number = self._find_page(char_start, page_map) if page_map else -1

                chunk_id = f"{paper_id}_chunk_{chunk_index:03d}"

                chunks.append(ChunkData(
                    chunk_id=chunk_id,
                    paper_id=paper_id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    char_start=char_start,
                    char_end=char_end,
                    total_chunks=0,  # se actualiza abajo
                    source_pdf=source_pdf,
                ))
                chunk_index += 1

        # Actualizar total_chunks
        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def _subdivide_segment(
        self, sentences: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Subdivide un segmento semántico si excede max_chunk_size.

        Agrupa oraciones hasta alcanzar max_chunk_size.
        """
        if not sentences:
            return []

        sub_chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence["text"])

            # Si agregar esta oración excede el máximo, guardar chunk actual
            if current_size + sentence_size > self.max_chunk_size and current_chunk:
                sub_chunks.append(current_chunk)
                current_chunk = []
                current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_size + 1  # +1 para el espacio

        # Agregar último chunk
        if current_chunk:
            sub_chunks.append(current_chunk)

        return sub_chunks

    @staticmethod
    def _find_page(
        char_pos: int,
        page_map: List[Tuple[int, int, int]],
    ) -> int:
        """Determina el número de página dado un char_pos."""
        for page_num, start, end in page_map:
            if start <= char_pos < end:
                return page_num
        if page_map:
            return page_map[-1][0]
        return -1

    def _print_stats(
        self,
        paper_id: str,
        chunks: List[ChunkData],
        total_chars: int,
        total_sentences: int,
    ) -> None:
        sizes = [len(c.text) for c in chunks]
        avg = sum(sizes) / len(sizes) if sizes else 0
        print(
            f"  {paper_id}: {len(chunks)} chunks from {total_sentences} sentences | "
            f"avg {avg:.0f} chars | total {total_chars} chars"
        )
