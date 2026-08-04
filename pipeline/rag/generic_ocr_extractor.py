"""
Extractor genérico que usa cualquier proveedor OCR.

Permite usar:
- ClaudeVisionOCRProvider (máxima calidad)
- HybridOCRProvider (cascada inteligente)
- GrobidProvider (fallback)
- Cualquier OCRProvider personalizado
"""

from pathlib import Path
from typing import List, Tuple, Optional

from pipeline.ocr.base import OCRProvider
from .pdf_extractor import PDFExtractionError, _clean_extracted_text


class GenericOCRExtractor:
    """
    Extractor de PDFs usando un proveedor OCR genérico.

    Ventaja: Puede usar cualquier OCRProvider sin limitaciones.

    Args:
        ocr_provider: Instancia de OCRProvider (ClaudeVision, Hybrid, GROBID, etc).
        min_page_chars: Mínimo de caracteres por página.
        strip_headers: Eliminar headers/footers repetitivos.
        verbose: Mostrar progreso.
    """

    def __init__(
        self,
        ocr_provider: OCRProvider,
        min_page_chars: int = 50,
        strip_headers: bool = True,
        verbose: bool = False,
    ):
        self.ocr_provider = ocr_provider
        self.min_page_chars = min_page_chars
        self.strip_headers = strip_headers
        self.verbose = verbose

    def extract(self, pdf_path: Path) -> str:
        """Extrae y concatena el texto de todas las secciones."""
        pages = self.extract_by_pages(pdf_path)
        return "\n\n".join(text for _, text in pages)

    def extract_by_pages(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extrae texto página por página usando el proveedor OCR.

        Returns:
            Lista de (page_number, text) tuples.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        try:
            if self.verbose:
                print(f"  Extrayendo (OCR) {pdf_path.name}...")

            # Usar proveedor OCR
            raw_pages = self.ocr_provider.extract_pdf(pdf_path)

            pages: List[Tuple[int, str]] = []
            for page_num, text in raw_pages:
                # Limpiar texto
                text = _clean_extracted_text(text)

                if len(text) >= self.min_page_chars:
                    pages.append((page_num, text))
                elif self.verbose:
                    print(f"    Página {page_num} ignorada ({len(text)} chars)")

            if not pages:
                raise PDFExtractionError(
                    f"No se pudo extraer texto útil de {pdf_path.name}."
                )

            if self.verbose:
                total_chars = sum(len(t) for _, t in pages)
                print(f"  Extraidas {len(pages)} páginas, {total_chars} caracteres")

            return pages

        except PDFExtractionError:
            raise
        except Exception as e:
            raise PDFExtractionError(
                f"Error extrayendo {pdf_path.name}: {type(e).__name__}: {e}"
            ) from e
