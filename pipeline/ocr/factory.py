"""Factory function for OCR provider instantiation."""

from typing import Optional

from .base import OCRProvider
from .grobid_provider import GrobidProvider


def get_ocr_provider(
    provider: str = "grobid",
    grobid_url: Optional[str] = None,
    **kwargs,
) -> OCRProvider:
    """
    Factory function to instantiate an OCR provider by name.

    Args:
        provider: Provider name ("grobid" — main provider for scientific papers).
                  Default: "grobid"
        grobid_url: For "grobid" — URL of GROBID service.
                    If None, reads from env var GROBID_URL or uses default (http://localhost:8070)
        **kwargs: Additional arguments passed to the provider constructor.

    Returns:
        An OCRProvider instance.

    Raises:
        ValueError: If provider name is not recognized.
    """
    provider = provider.lower().strip()

    if provider == "grobid":
        return GrobidProvider(grobid_url=grobid_url, **kwargs)
    else:
        raise ValueError(
            f"Unknown OCR provider: {provider}. "
            f"Supported providers: 'grobid'"
        )
