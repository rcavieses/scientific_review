"""
Orquestador del pipeline RAG: PDF → chunks → embeddings → FAISS.

Conecta PDFExtractor, TextChunker, EmbeddingGenerator y VectorDBManager
manteniendo cada componente independiente entre sí.
"""

import re
import unicodedata
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import ChunkData, ChunkVector
from .pdf_extractor import PDFExtractor, PdfPlumberExtractor, PDFExtractionError
from .text_chunker import TextChunker
from .vector_db import VectorDBManager
from .metadata_registry import MetadataRegistry


class RAGPipelineOrchestrator:
    """
    Orquesta el pipeline completo: PDF → chunks → embeddings → índice FAISS.

    Flujo por cada PDF:
      1. PdfPlumberExtractor.extract_by_pages()  → List[(page, text)]
      2. TextChunker.chunk_pages()               → List[ChunkData]
      3. EmbeddingGenerator.batch_generate()     → np.ndarray (N, dim)
      4. VectorDBManager.add_chunks()            → índice actualizado
      5. VectorDBManager.save()                  → persistido en disco

    Args:
        pdf_dir: Directorio con PDFs (default: outputs/pdfs).
        index_dir: Directorio para el índice FAISS (default: outputs/rag_index).
        extractor: PDFExtractor a usar (default: PdfPlumberExtractor).
        chunker: TextChunker a usar (default: TextChunker con parámetros default).
        embedding_generator: EmbeddingGenerator (default: LocalEmbeddingGenerator).
        skip_indexed: Si True, omite PDFs ya indexados (default: True).
        batch_size: Número de chunks a pasar juntos al EmbeddingGenerator (default: 64).
        verbose: Mostrar progreso detallado.
    """

    def __init__(
        self,
        pdf_dir: Path = Path("outputs/pdfs"),
        index_dir: Path = Path("outputs/rag_index"),
        extractor: Optional[PDFExtractor] = None,
        chunker: Optional[TextChunker] = None,
        embedding_generator=None,
        skip_indexed: bool = True,
        batch_size: int = 64,
        verbose: bool = False,
    ):
        self.pdf_dir = Path(pdf_dir)
        self.index_dir = Path(index_dir)
        self.skip_indexed = skip_indexed
        self.batch_size = batch_size
        self.verbose = verbose

        # Componentes con defaults lazy
        self._extractor = extractor
        self._chunker = chunker
        self._embedding_generator = embedding_generator

        # DB se inicializa cuando tengamos la dimensión del modelo
        self._db: Optional[VectorDBManager] = None

        # Registro de metadatos (opcional, enriquece title/authors/year/doi en chunks)
        self._metadata_registry: Optional[MetadataRegistry] = None

    # ── API pública ──────────────────────────────────────────────────────────

    def run(
        self,
        pdf_paths: Optional[List[Path]] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo.

        Args:
            pdf_paths: Lista específica de PDFs. Si None, procesa todos en pdf_dir.

        Returns:
            Dict con estadísticas de la ejecución:
            {processed, skipped, failed, total_chunks, index_stats}
        """
        if pdf_paths is None:
            pdf_paths = sorted(self.pdf_dir.glob("*.pdf"))

        if not pdf_paths:
            print(f"No se encontraron PDFs en {self.pdf_dir}")
            return {"processed": 0, "skipped": 0, "failed": [], "total_chunks": 0}

        # Inicializar componentes (lazy)
        self._init_components()

        # Cargar índice existente si hay
        self._db.load()

        processed = 0
        skipped = 0
        failed: List[str] = []
        total_chunks = 0

        print(f"Indexando {len(pdf_paths)} PDFs en {self.index_dir}/")

        for i, pdf_path in enumerate(pdf_paths, 1):
            paper_id = self._derive_paper_id(pdf_path)
            prefix = f"  [{i}/{len(pdf_paths)}] {pdf_path.name}"

            # Verificar si ya está indexado
            if self.skip_indexed and self._db.is_paper_indexed(paper_id):
                if self.verbose:
                    print(f"{prefix} — ya indexado, omitiendo")
                skipped += 1
                continue

            print(f"{prefix}")
            try:
                chunk_vectors = self.index_single_pdf(pdf_path)
                n = len(chunk_vectors)
                total_chunks += n
                processed += 1
                print(f"    -> {n} chunks indexados")

            except PDFExtractionError as e:
                print(f"    [error extraccion] {e}")
                failed.append(str(pdf_path))
            except Exception as e:
                print(f"    [error] {type(e).__name__}: {e}")
                failed.append(str(pdf_path))

        # Guardar índice final
        if processed > 0:
            self._db.save()

        stats = self._db.get_stats()
        print(
            f"\nResumen: {processed} indexados | {skipped} omitidos | "
            f"{len(failed)} errores | {total_chunks} chunks nuevos"
        )
        print(f"Indice total: {stats.total_chunks} chunks de {stats.total_papers} papers")

        return {
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "total_chunks": total_chunks,
            "index_stats": stats,
        }

    def index_single_pdf(self, pdf_path: Path) -> List[ChunkVector]:
        """
        Procesa un solo PDF: extrae → chunkea → embeds → agrega al índice.

        Args:
            pdf_path: Ruta al PDF.

        Returns:
            Lista de ChunkVector agregados al índice.

        Raises:
            PDFExtractionError: Si el PDF no se puede leer.
        """
        self._init_components()

        paper_id = self._derive_paper_id(pdf_path)
        source_pdf = str(pdf_path)

        # 1. Extraer texto por páginas
        pages = self._extractor.extract_by_pages(pdf_path)

        # 2. Chunkear
        chunks: List[ChunkData] = self._chunker.chunk_pages(pages, paper_id, source_pdf)

        if not chunks:
            if self.verbose:
                print(f"    Sin chunks generados para {pdf_path.name}")
            return []

        # 2b. Enriquecer chunks con metadatos si hay registry
        if self._metadata_registry:
            meta = self._metadata_registry.get(paper_id)
            if meta:
                for chunk in chunks:
                    chunk.title = meta.get("title")
                    chunk.authors = meta.get("authors")
                    chunk.year = meta.get("year")
                    chunk.doi = meta.get("doi")
                if self.verbose:
                    print(f"    Metadatos vinculados: '{meta.get('title', '')[:60]}'")
            elif self.verbose:
                print(f"    [metadata] Sin coincidencia para paper_id={paper_id}")

        # 3. Generar embeddings en batches
        texts = [c.text for c in chunks]
        vectors = self._embedding_generator.batch_generate(
            texts,
            batch_size=self.batch_size,
            show_progress=self.verbose,
        )

        model_name = self._embedding_generator.get_model_name()

        # 4. Ensamblar ChunkVector
        chunk_vectors = [
            ChunkVector(chunk=chunk, vector=vectors[i], embedding_model=model_name)
            for i, chunk in enumerate(chunks)
        ]

        # 5. Agregar al índice (sin guardar aún — save() se llama en run())
        self._db.add_chunks(chunk_vectors)

        return chunk_vectors

    def get_db(self) -> VectorDBManager:
        """Retorna el VectorDBManager (inicializado si hace falta)."""
        self._init_components()
        return self._db

    def load_metadata_registry(self, search_results_dir: Path) -> int:
        """
        Carga los metadatos de artículos desde los CSVs de búsqueda.

        Llama a este método antes de run() para que los chunks queden enriquecidos
        con título, autores, año y DOI.

        Args:
            search_results_dir: Directorio con los CSV de búsqueda (outputs/search_results/).

        Returns:
            Número de artículos registrados.
        """
        self._metadata_registry = MetadataRegistry()
        n = self._metadata_registry.load_from_search_results(Path(search_results_dir))
        if self.verbose:
            print(f"  MetadataRegistry: {n} artículos cargados desde {search_results_dir}")
        return n

    # ── Métodos internos ────────────────────────────────────────────────────

    def _init_components(self) -> None:
        """Inicializa los componentes con defaults si no se proporcionaron."""
        if self._extractor is None:
            self._extractor = PdfPlumberExtractor(verbose=self.verbose)

        if self._chunker is None:
            self._chunker = TextChunker(verbose=self.verbose)

        if self._embedding_generator is None:
            from pipeline.embeddings.embedding_generator import get_embedding_generator
            self._embedding_generator = get_embedding_generator(
                provider="local", verbose=self.verbose
            )

        if self._db is None:
            dim = self._embedding_generator.get_dimension()
            self._db = VectorDBManager(
                index_dir=self.index_dir,
                embedding_dim=dim,
                verbose=self.verbose,
            )

    @staticmethod
    def _derive_paper_id(pdf_path: Path) -> str:
        """
        Deriva un paper_id limpio del nombre del archivo PDF.

        "2024_Smith et al._Deep Learning.pdf" → "2024_Smith_et_al_Deep_Learning"
        """
        name = pdf_path.stem

        # Normalizar unicode → ASCII
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")

        # Reemplazar caracteres no alfanuméricos/guión/punto por _
        name = re.sub(r"[^\w\-]", "_", name)

        # Colapsar guiones bajos múltiples
        name = re.sub(r"_+", "_", name)

        return name.strip("_") or "paper"
