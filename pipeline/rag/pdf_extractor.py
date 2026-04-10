"""
Extracción de texto de PDFs científicos.

Usa pdfplumber para manejar correctamente layouts de dos columnas,
tablas y texto con símbolos matemáticos típicos de papers científicos.
"""

import re
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import List, Tuple, Optional

import pdfplumber


class PDFExtractionError(Exception):
    """Error durante la extracción de texto de un PDF."""
    pass


class PDFExtractor(ABC):
    """Interfaz base para extractores de texto de PDFs."""

    @abstractmethod
    def extract(self, pdf_path: Path) -> str:
        """
        Extrae el texto completo de un PDF.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Texto completo como string limpio.

        Raises:
            FileNotFoundError: Si el PDF no existe.
            PDFExtractionError: Si el PDF no se puede leer.
        """

    @abstractmethod
    def extract_by_pages(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extrae texto página por página.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Lista de (numero_pagina_1based, texto_de_pagina).
            Solo incluye páginas con contenido suficiente.

        Raises:
            FileNotFoundError: Si el PDF no existe.
            PDFExtractionError: Si el PDF no se puede leer.
        """


class PdfPlumberExtractor(PDFExtractor):
    """
    Extractor de texto usando pdfplumber.

    Maneja correctamente:
    - Layouts de una y dos columnas
    - Guiones de fin de línea (hy-\\nphen → hyphen)
    - Headers y footers repetitivos (filtrado automático)
    - Páginas con poco texto (portadas, figuras)

    Args:
        min_page_chars: Mínimo de caracteres para considerar una página válida.
        strip_headers: Detectar y eliminar headers/footers repetitivos.
        verbose: Mostrar progreso página a página.
    """

    def __init__(
        self,
        min_page_chars: int = 50,
        strip_headers: bool = True,
        verbose: bool = False,
    ):
        self.min_page_chars = min_page_chars
        self.strip_headers = strip_headers
        self.verbose = verbose

    def extract(self, pdf_path: Path) -> str:
        """Extrae y concatena el texto de todas las páginas."""
        pages = self.extract_by_pages(pdf_path)
        return "\n\n".join(text for _, text in pages)

    def extract_by_pages(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extrae texto página a página.

        Returns:
            Lista de (page_num_1based, texto_limpio). Solo páginas con
            al menos min_page_chars caracteres.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        try:
            raw_pages: List[Tuple[int, str]] = []

            with pdfplumber.open(pdf_path) as pdf:
                if self.verbose:
                    print(f"  Extrayendo {len(pdf.pages)} páginas de {pdf_path.name}...")

                for page in pdf.pages:
                    page_num = page.page_number  # 1-based en pdfplumber
                    text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                    text = self._clean_extracted_text(text)

                    if len(text) >= self.min_page_chars:
                        raw_pages.append((page_num, text))
                    elif self.verbose:
                        print(f"    Página {page_num} ignorada ({len(text)} chars)")

            if not raw_pages:
                raise PDFExtractionError(
                    f"No se pudo extraer texto útil de {pdf_path.name}. "
                    "El PDF puede ser un scan o estar protegido."
                )

            if self.strip_headers:
                raw_pages = self._strip_repeated_headers(raw_pages)

            if self.verbose:
                total_chars = sum(len(t) for _, t in raw_pages)
                print(f"  Extraidas {len(raw_pages)} páginas, {total_chars} caracteres")

            return raw_pages

        except PDFExtractionError:
            raise
        except Exception as e:
            raise PDFExtractionError(
                f"Error leyendo {pdf_path.name}: {type(e).__name__}: {e}"
            ) from e

    def _clean_extracted_text(self, text: str) -> str:
        """
        Limpieza específica para texto extraído de PDFs científicos.

        - Une guiones de fin de línea: "hy-\\nphen" → "hyphen"
        - Colapsa saltos de línea en medio de párrafo
        - Preserva doble \\n (límites de párrafo)
        - Elimina números de página aislados
        - Normaliza espacios
        """
        if not text:
            return ""

        # 1. Unir palabras partidas con guión al final de línea
        text = re.sub(r"-\n(\w)", r"\1", text)

        # 2. Preservar separadores de párrafo (doble salto)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 3. Colapsar saltos de línea simples dentro de un párrafo
        # (no afecta dobles \n ya normalizados)
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

        # 4. Eliminar números de página aislados (línea con solo dígitos)
        text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)

        # 5. Normalizar espacios múltiples
        text = re.sub(r" {2,}", " ", text)

        # 6. Eliminar caracteres de control (excepto \n)
        text = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32)

        return text.strip()

    def _strip_repeated_headers(
        self, pages: List[Tuple[int, str]]
    ) -> List[Tuple[int, str]]:
        """
        Detecta y elimina líneas que aparecen en ≥3 páginas (headers/footers).

        Compara la primera y última línea de cada página. Si una línea
        aparece en al menos la mitad de las páginas, se considera header/footer.
        """
        if len(pages) < 4:
            return pages

        # Recopilar primera y última línea de cada página
        first_lines: List[str] = []
        last_lines: List[str] = []

        for _, text in pages:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if lines:
                first_lines.append(lines[0])
                last_lines.append(lines[-1])

        threshold = max(3, len(pages) // 2)

        # Detectar patrones repetidos
        repeated_headers = {
            line for line, count in Counter(first_lines).items()
            if count >= threshold and len(line) > 3
        }
        repeated_footers = {
            line for line, count in Counter(last_lines).items()
            if count >= threshold and len(line) > 3
        }
        to_remove = repeated_headers | repeated_footers

        if not to_remove:
            return pages

        # Limpiar cada página
        cleaned: List[Tuple[int, str]] = []
        for page_num, text in pages:
            lines = text.split("\n")
            filtered = [l for l in lines if l.strip() not in to_remove]
            clean_text = "\n".join(filtered).strip()
            if len(clean_text) >= self.min_page_chars:
                cleaned.append((page_num, clean_text))

        return cleaned if cleaned else pages
