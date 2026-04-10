"""
División de texto en chunks con overlap para RAG.

Estrategia: sliding window por caracteres, con preferencia por cortar
en límites de párrafo > oración > espacio. Nunca corta palabras a la mitad.
"""

import re
from typing import List, Tuple, Optional, Dict, Any

from .models import ChunkData


class TextChunker:
    """
    Divide texto en chunks solapados para indexación RAG.

    Para papers científicos se recomienda chunk_size=2000 chars (~512 tokens)
    con overlap=200 chars, lo que preserva típicamente 1-2 párrafos por chunk
    con suficiente contexto semántico para el modelo de embedding.

    Args:
        chunk_size: Tamaño objetivo del chunk en caracteres (default: 2000).
        overlap: Solapamiento entre chunks consecutivos en caracteres (default: 200).
        min_chunk_size: Chunks más pequeños se descartan (default: 100).
        split_on_paragraph: Preferir cortar en doble newline (default: True).
        verbose: Mostrar estadísticas por paper.
    """

    # Patrones de fin de oración (punto seguido de espacio/mayúscula)
    _SENTENCE_END = re.compile(r"[.!?]\s")

    def __init__(
        self,
        chunk_size: int = 2000,
        overlap: int = 200,
        min_chunk_size: int = 100,
        split_on_paragraph: bool = True,
        verbose: bool = False,
    ):
        if overlap >= chunk_size:
            raise ValueError(f"overlap ({overlap}) debe ser menor que chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
        self.split_on_paragraph = split_on_paragraph
        self.verbose = verbose

    def chunk_pages(
        self,
        pages: List[Tuple[int, str]],
        paper_id: str,
        source_pdf: str,
    ) -> List[ChunkData]:
        """
        Chunkea directamente desde páginas separadas.

        Forma preferida: preserva page_number exacto por chunk porque
        se conoce en qué página comienza cada porción de texto.

        Args:
            pages: Salida de PDFExtractor.extract_by_pages() —
                   lista de (page_num_1based, texto_de_pagina).
            paper_id: Identificador del paper.
            source_pdf: Ruta relativa al PDF.

        Returns:
            Lista de ChunkData con page_number correcto.
        """
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
        """
        Divide texto completo en chunks.

        Args:
            text: Texto completo del paper.
            paper_id: Identificador del paper.
            source_pdf: Ruta relativa al PDF.
            page_map: Lista de (page_num, char_start, char_end) para
                      asignar page_number a cada chunk. Si None → -1.

        Returns:
            Lista de ChunkData.
        """
        if not text or len(text) < self.min_chunk_size:
            return []

        # Calcular puntos de corte
        split_points = self._compute_split_points(text)

        chunks: List[ChunkData] = []
        chunk_index = 0

        for char_start, char_end in split_points:
            chunk_text = text[char_start:char_end].strip()

            if len(chunk_text) < self.min_chunk_size:
                continue

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

        # Actualizar total_chunks en todos los chunks
        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        if self.verbose:
            self._print_stats(paper_id, chunks, len(text))

        return chunks

    def get_stats(self, chunks: List[ChunkData]) -> Dict[str, Any]:
        """Estadísticas de chunking para un conjunto de chunks."""
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

    def _compute_split_points(self, text: str) -> List[Tuple[int, int]]:
        """
        Calcula los rangos (char_start, char_end) de cada chunk.

        Usa sliding window con tamaño chunk_size y paso (chunk_size - overlap).
        """
        total = len(text)
        step = self.chunk_size - self.overlap
        split_points: List[Tuple[int, int]] = []

        start = 0
        while start < total:
            end = min(start + self.chunk_size, total)

            # Si no llegamos al final, buscar mejor punto de corte
            if end < total:
                end = self._find_split_point(text, end)

            split_points.append((start, end))

            if end >= total:
                break

            # Siguiente inicio: retrocede el overlap desde el punto de corte
            next_start = end - self.overlap
            # Ajustar inicio al comienzo de una palabra
            while next_start < end and text[next_start] in " \n\t":
                next_start += 1
            start = max(next_start, start + 1)  # garantiza avance

        return split_points

    def _find_split_point(self, text: str, target: int) -> int:
        """
        Busca el mejor punto de corte cerca de target.

        Prioridad (ventana de búsqueda = overlap):
          1. Fin de párrafo (doble \\n)
          2. Fin de oración ([.!?] seguido de espacio)
          3. Espacio simple
          4. target exacto (fallback)
        """
        window = self.overlap
        search_start = max(0, target - window)
        search_end = min(len(text), target + window // 2)
        segment = text[search_start:search_end]

        # 1. Doble salto de línea (párrafo)
        if self.split_on_paragraph:
            idx = segment.rfind("\n\n", 0, target - search_start + window // 2)
            if idx != -1:
                return search_start + idx + 2  # después del \n\n

        # 2. Fin de oración
        best_sentence = -1
        for m in self._SENTENCE_END.finditer(segment):
            pos = search_start + m.end()
            if pos <= target + window // 2:
                best_sentence = pos
        if best_sentence != -1:
            return best_sentence

        # 3. Espacio simple
        idx = segment.rfind(" ", 0, target - search_start + window // 2)
        if idx != -1:
            return search_start + idx + 1

        # 4. Fallback: target exacto
        return target

    @staticmethod
    def _find_page(
        char_pos: int,
        page_map: List[Tuple[int, int, int]],
    ) -> int:
        """
        Determina el número de página dado un char_pos y el mapa de páginas.

        Devuelve el page_num de la página que contiene char_pos, o el de
        la página más cercana si cae en el separador entre páginas.
        """
        for page_num, start, end in page_map:
            if start <= char_pos < end:
                return page_num
        # Fallback: página más cercana
        if page_map:
            return page_map[-1][0]
        return -1

    def _print_stats(
        self, paper_id: str, chunks: List[ChunkData], total_chars: int
    ) -> None:
        sizes = [len(c.text) for c in chunks]
        avg = sum(sizes) / len(sizes) if sizes else 0
        print(
            f"  {paper_id}: {len(chunks)} chunks | "
            f"avg {avg:.0f} chars | total {total_chars} chars"
        )
