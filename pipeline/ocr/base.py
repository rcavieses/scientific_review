"""Base abstraction for OCR providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple


class OCRExtractionError(Exception):
    """Error during OCR text extraction from a document."""
    pass


class OCRProvider(ABC):
    """Abstract interface for OCR providers (local or API-based)."""

    @abstractmethod
    def extract_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extract text from a PDF using OCR.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of (page_number_1based, text) tuples.
            Page numbers start at 1.

        Raises:
            FileNotFoundError: If the PDF does not exist.
            OCRExtractionError: If OCR extraction fails.
        """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return a human-readable name for this provider (e.g., "baidu_api", "local_transformers")."""
