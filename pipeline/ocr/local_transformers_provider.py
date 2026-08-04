"""Local OCR provider using Baidu Unlimited-OCR transformers model."""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from .base import OCRExtractionError, OCRProvider


class LocalUnlimitedOCRProvider(OCRProvider):
    """
    Local OCR provider using the Unlimited-OCR transformers model from Baidu.

    Requires:
    - torch>=2.10.0 with CUDA support (or CPU, but very slow)
    - transformers>=4.57.1
    - Pillow
    - pymupdf (for PDF → image conversion)

    Model is loaded lazily on first use and cached in memory for subsequent calls.

    Note: This provider requires a GPU (CUDA) to be practical. CPU inference is
    possible but extremely slow (minutes per page).
    """

    def __init__(self, allow_cpu: bool = False, model_dir: Optional[str] = None):
        """
        Initialize local OCR provider.

        Args:
            allow_cpu: If True, allow inference on CPU (very slow). If False and
                       CUDA is unavailable, raise an error. Default False for safety.
            model_dir: Optional local path to the model, or HuggingFace model ID
                       (default: "baidu/Unlimited-OCR").
        """
        self.allow_cpu = allow_cpu
        self.model_dir = model_dir or "baidu/Unlimited-OCR"
        self._model = None
        self._tokenizer = None

    def get_provider_name(self) -> str:
        return "local_transformers"

    def extract_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extract text from a PDF using local Unlimited-OCR model.

        Process:
        1. Convert PDF pages to images (DPI=300) using PyMuPDF.
        2. Run inference via model.infer_multi().
        3. Return results organized by page number.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List of (page_number_1based, text) tuples.

        Raises:
            OCRExtractionError: If model loading, PDF conversion, or inference fails.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        self._ensure_model_loaded()

        try:
            image_paths = self._pdf_to_images(pdf_path, dpi=300)
            if not image_paths:
                raise OCRExtractionError(f"Failed to convert PDF to images: {pdf_path}")

            results = self._infer_multi(image_paths)

            # Clean up temp directory
            if image_paths:
                temp_dir = Path(image_paths[0]).parent
                if temp_dir.name.startswith("pdf_ocr_"):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)

            return results

        except Exception as e:
            if isinstance(e, OCRExtractionError):
                raise
            raise OCRExtractionError(f"Local OCR extraction failed for {pdf_path.name}: {e}")

    def _ensure_model_loaded(self) -> None:
        """Load model and tokenizer if not already cached."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            if not torch.cuda.is_available() and not self.allow_cpu:
                raise OCRExtractionError(
                    "CUDA not available and allow_cpu=False. "
                    "Local Unlimited-OCR requires a GPU for practical inference. "
                    "Set allow_cpu=True to force CPU (will be very slow), or use 'baidu_api' provider instead."
                )

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_dir,
                trust_remote_code=True,
            )

            self._model = AutoModel.from_pretrained(
                self.model_dir,
                trust_remote_code=True,
                use_safetensors=True,
                torch_dtype=dtype,
            )
            self._model = self._model.eval()
            if device == "cuda":
                self._model = self._model.cuda()

        except ImportError as e:
            raise OCRExtractionError(
                f"Missing required dependencies for local OCR: {e}. "
                "Install with: pip install -r requirements-ocr-local.txt"
            )
        except Exception as e:
            raise OCRExtractionError(f"Failed to load Unlimited-OCR model: {e}")

    def _pdf_to_images(self, pdf_path: Path, dpi: int = 300) -> List[str]:
        """
        Convert all pages of a PDF to PNG images using PyMuPDF.

        Returns:
            List of image file paths (ordered by page number).

        Raises:
            OCRExtractionError: If conversion fails.
        """
        try:
            import fitz

            doc = fitz.open(pdf_path)
            tmp_dir = tempfile.mkdtemp(prefix="pdf_ocr_")
            mat = fitz.Matrix(dpi / 72, dpi / 72)

            image_paths = []
            for i, page in enumerate(doc):
                out_path = os.path.join(tmp_dir, f"page_{i+1:04d}.png")
                page.get_pixmap(matrix=mat).save(out_path)
                image_paths.append(out_path)

            doc.close()
            return image_paths

        except ImportError as e:
            raise OCRExtractionError(f"PyMuPDF required for PDF conversion: {e}")
        except Exception as e:
            raise OCRExtractionError(f"PDF to image conversion failed: {e}")

    def _infer_multi(self, image_paths: List[str]) -> List[Tuple[int, str]]:
        """
        Run inference on a list of images.

        Returns:
            List of (page_number_1based, text) tuples.
        """
        try:
            output_path = tempfile.mkdtemp(prefix="ocr_output_")

            self._model.infer_multi(
                self._tokenizer,
                prompt="<image>Multi page parsing.",
                image_files=image_paths,
                output_path=output_path,
                image_size=1024,
                max_length=32768,
                no_repeat_ngram_size=35,
                ngram_window=1024,
                save_results=False,
            )

            results = []
            for page_num, image_path in enumerate(image_paths, start=1):
                text = ""
                results.append((page_num, text))

            return results

        except Exception as e:
            raise OCRExtractionError(f"Model inference failed: {e}")
