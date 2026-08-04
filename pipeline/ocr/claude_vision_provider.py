"""
OCR provider using Claude Vision API.

Estrategia:
1. Convertir PDF a imágenes (una o más páginas)
2. Enviar imágenes a Claude Vision
3. Extraer texto con alta precisión

Ventajas:
- Excelente para artículos científicos
- Maneja layouts complejos bien
- No requiere GPU
- Preciso con matemáticas y tablas
"""

import base64
import os
from pathlib import Path
from typing import List, Optional, Tuple
import logging

import anthropic

from .base import OCRProvider, OCRExtractionError

logger = logging.getLogger(__name__)


class ClaudeVisionOCRProvider(OCRProvider):
    """
    OCR provider using Claude Vision API for text extraction.

    Converts PDF pages to images and sends them to Claude for OCR.
    Excellent for scientific papers with complex layouts.

    Args:
        model: Claude model to use (default: claude-opus-4-1-20250805).
        api_key: Anthropic API key (default: from ANTHROPIC_API_KEY env).
        max_tokens: Max tokens for response (default: 4096).
    """

    def __init__(
        self,
        model: str = "claude-opus-4-1-20250805",
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=self.api_key)

        if not self.api_key:
            raise OCRExtractionError("ANTHROPIC_API_KEY not set")

    def get_provider_name(self) -> str:
        return "claude_vision"

    def extract_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extract text from PDF using Claude Vision.

        Process:
        1. Convert PDF pages to images (max 3 pages for efficiency)
        2. Send to Claude Vision for OCR
        3. Return extracted text by page

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List of (page_number_1based, text) tuples.

        Raises:
            OCRExtractionError: If PDF conversion or Claude call fails.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        try:
            # Convertir PDF a imágenes
            image_paths = self._pdf_to_images(pdf_path, max_pages=3, dpi=200)
            if not image_paths:
                raise OCRExtractionError(f"No se pudo convertir PDF a imágenes: {pdf_path}")

            results = []

            # Procesar cada página/imagen
            for page_num, image_path in enumerate(image_paths, 1):
                text = self._extract_text_from_image(image_path, page_num)
                if text.strip():
                    results.append((page_num, text))

            # Limpiar imágenes temporales
            self._cleanup_images(image_paths)

            return results

        except Exception as e:
            raise OCRExtractionError(f"Error extrayendo {pdf_path.name}: {e}") from e

    def _pdf_to_images(self, pdf_path: Path, max_pages: int = 3, dpi: int = 200) -> List[str]:
        """Convierte PDF a imágenes PNG temporales."""
        try:
            import fitz  # pymupdf
        except ImportError:
            raise OCRExtractionError(
                "pymupdf requerido para OCR con Claude Vision: pip install pymupdf"
            )

        doc = fitz.open(pdf_path)
        image_paths = []

        # Procesar máximo N páginas (por eficiencia)
        num_pages = min(len(doc), max_pages)

        for page_num in range(num_pages):
            page = doc[page_num]

            # Renderizar página a imagen
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # Guardar en archivo temporal
            temp_path = f"/tmp/pdf_ocr_{pdf_path.stem}_page_{page_num}.png"
            pix.save(temp_path)
            image_paths.append(temp_path)

        doc.close()
        return image_paths

    def _extract_text_from_image(self, image_path: str, page_num: int) -> str:
        """Envía imagen a Claude Vision para extraer texto."""

        # Leer imagen como base64
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # Llamar a Claude Vision
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extrae TODO el texto de esta imagen de documento científico. "
                                "Mantén la estructura del documento (párrafos, listas, tablas). "
                                "Si hay ecuaciones o símbolos matemáticos, transcribe lo más fielmente posible. "
                                "Retorna SOLO el texto extraído, sin comentarios."
                            ),
                        },
                    ],
                }
            ],
        )

        return message.content[0].text

    @staticmethod
    def _cleanup_images(image_paths: List[str]) -> None:
        """Limpia archivos de imagen temporales."""
        import os

        for path in image_paths:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception as e:
                logger.warning(f"No se pudo limpiar {path}: {e}")
