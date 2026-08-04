"""OCR pipeline module with GROBID support for scientific papers."""

from .base import OCRExtractionError, OCRProvider
from .factory import get_ocr_provider
from .grobid_provider import GrobidProvider

__all__ = [
    "OCRProvider",
    "OCRExtractionError",
    "GrobidProvider",
    "get_ocr_provider",
]
