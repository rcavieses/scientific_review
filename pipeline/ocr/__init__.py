"""OCR pipeline module with multiple providers for scientific papers."""

from .base import OCRExtractionError, OCRProvider
from .factory import get_ocr_provider
from .grobid_provider import GrobidProvider
from .hybrid_provider import HybridOCRProvider

__all__ = [
    "OCRProvider",
    "OCRExtractionError",
    "GrobidProvider",
    "HybridOCRProvider",
    "get_ocr_provider",
]
