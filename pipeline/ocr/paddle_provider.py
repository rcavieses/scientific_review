"""
Proveedor OCR usando PaddleOCR.

Ventajas:
- Gratuito
- Rápido (CPU)
- Bueno para documentos científicos
- No requiere GPU (pero GPU lo acelera)

Requisitos:
    pip install paddleocr
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional

from .base import OCRProvider, OCRExtractionError

logger = logging.getLogger(__name__)


class PaddleOCRProvider(OCRProvider):
    """
    OCR provider usando PaddleOCR (Baidu).

    Rápido, confiable y gratuito. Buena opción para artículos científicos
    cuando no tienes GPU o presupuesto para APIs.

    Args:
        lang: Idioma(s) para OCR (default: ['en', 'es'] para inglés/español).
        use_gpu: Si True, usa GPU si está disponible (default: False).
        verbose: Mostrar progreso.
    """

    def __init__(
        self,
        lang: Optional[List[str]] = None,
        use_gpu: bool = False,
        verbose: bool = False,
    ):
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            raise OCRExtractionError(
                "paddleocr requerido: pip install paddleocr"
            )

        # PaddleOCR espera un string o list, pero los idiomas se especifican como string
        self.lang = lang or ["en"]  # Por defecto: inglés
        self.use_gpu = use_gpu
        self.verbose = verbose

        # Inicializar modelo lazily
        self._ocr = None

    def get_provider_name(self) -> str:
        return "paddle_ocr"

    def extract_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extrae texto de PDF usando PaddleOCR.

        Convierte PDF a imágenes y las procesa con OCR.

        Args:
            pdf_path: Path al PDF.

        Returns:
            List de (page_number, text) tuples.

        Raises:
            OCRExtractionError: Si la extracción falla.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        try:
            # Convertir PDF a imágenes
            image_paths = self._pdf_to_images(pdf_path)
            if not image_paths:
                raise OCRExtractionError(f"No se pudo convertir {pdf_path.name} a imágenes")

            # Inicializar OCR si es necesario
            self._ensure_model_loaded()

            results = []

            # Procesar cada imagen con OCR
            for page_num, image_path in enumerate(image_paths, 1):
                text = self._extract_text_from_image(image_path)

                if text.strip():
                    results.append((page_num, text))

                # Limpiar imagen temporal
                import os
                try:
                    os.unlink(image_path)
                except:
                    pass

            return results

        except Exception as e:
            raise OCRExtractionError(
                f"Error extrayendo {pdf_path.name} con PaddleOCR: {e}"
            ) from e

    def _ensure_model_loaded(self) -> None:
        """Carga el modelo PaddleOCR si no está cargado."""
        if self._ocr is None:
            from paddleocr import PaddleOCR

            if self.verbose:
                logger.info(f"  Cargando modelo PaddleOCR...")

            # PaddleOCR espera lang como string
            lang = self.lang[0] if isinstance(self.lang, list) else self.lang

            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
            )

    def _pdf_to_images(self, pdf_path: Path, max_pages: Optional[int] = None) -> List[str]:
        """Convierte PDF a imágenes PNG."""
        try:
            import fitz  # pymupdf
        except ImportError:
            raise OCRExtractionError(
                "pymupdf requerido: pip install pymupdf"
            )

        doc = fitz.open(pdf_path)
        image_paths = []

        num_pages = len(doc) if max_pages is None else min(len(doc), max_pages)

        for page_num in range(num_pages):
            page = doc[page_num]

            # Renderizar a imagen
            mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI
            pix = page.get_pixmap(matrix=mat)

            # Guardar temporalmente
            temp_path = f"/tmp/paddle_ocr_{pdf_path.stem}_p{page_num}.png"
            pix.save(temp_path)
            image_paths.append(temp_path)

        doc.close()
        return image_paths

    def _extract_text_from_image(self, image_path: str) -> str:
        """Extrae texto de una imagen usando PaddleOCR."""
        results = self._ocr.ocr(image_path, cls=True)

        # results es una lista de páginas, cada página es una lista de líneas
        # Cada línea es: [[x1,y1],[x2,y2],...], (text, confidence)
        text_lines = []

        if results:
            for page_results in results:
                for line in page_results:
                    if line and len(line) >= 2:
                        text = line[1][0]  # Extraer texto
                        if text.strip():
                            text_lines.append(text)

        return " ".join(text_lines)
