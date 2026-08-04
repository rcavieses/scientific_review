"""
Proveedor OCR híbrido con fallback en cascada.

Estrategia:
1. Intenta con primer provider (ej: Claude Vision para máxima calidad)
2. Si falla o extrae poco contenido → intenta siguiente
3. Registra cuál provider se usó para cada PDF
4. Eficiente: no hace llamadas innecesarias

Ejemplo de cascada:
  1. Claude Vision (mejor calidad, puede fallar por API)
  2. PaddleOCR (bueno, gratuito, confiable)
  3. GROBID (fallback, rápido)
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from .base import OCRProvider, OCRExtractionError

logger = logging.getLogger(__name__)


class HybridOCRProvider(OCRProvider):
    """
    Proveedor OCR que intenta múltiples extractores en cascada.

    Útil para robustez: si un provider falla, intenta con el siguiente.

    Args:
        providers: Lista de providers a intentar en orden.
        min_chars_threshold: Mínimo de caracteres para considerar éxito.
                            Si un provider extrae menos, intenta siguiente.
        verbose: Registrar qué provider se usó para cada PDF.
    """

    def __init__(
        self,
        providers: List[Tuple[str, OCRProvider]],
        min_chars_threshold: int = 500,
        verbose: bool = False,
    ):
        if not providers:
            raise ValueError("Al menos un provider es requerido")

        self.providers = providers  # Lista de (name, provider)
        self.min_chars_threshold = min_chars_threshold
        self.verbose = verbose
        self.stats = {}  # paper_id → provider usado

    def get_provider_name(self) -> str:
        return "hybrid"

    def extract_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extrae texto usando múltiples providers en cascada.

        Args:
            pdf_path: Path al PDF.

        Returns:
            List de (page_number, text) tuples.

        Raises:
            OCRExtractionError: Si todos los providers fallan.
        """
        pdf_path = Path(pdf_path)
        paper_id = pdf_path.stem

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        last_error = None

        for provider_name, provider in self.providers:
            try:
                if self.verbose:
                    logger.info(f"  [{paper_id}] Intentando {provider_name}...")

                result = provider.extract_pdf(pdf_path)

                # Calcular total de caracteres extraídos
                total_chars = sum(len(text) for _, text in result)

                # Verificar si la extracción fue suficiente
                if total_chars < self.min_chars_threshold:
                    if self.verbose:
                        logger.warning(
                            f"  [{paper_id}] {provider_name} extrajo solo "
                            f"{total_chars} chars (< {self.min_chars_threshold}), "
                            f"intentando siguiente..."
                        )
                    last_error = f"Contenido insuficiente ({total_chars} chars)"
                    continue

                # Éxito: extracción suficiente
                self.stats[paper_id] = {
                    "provider": provider_name,
                    "chars": total_chars,
                    "pages": len(result),
                }

                if self.verbose:
                    logger.info(
                        f"  [{paper_id}] ✓ {provider_name}: "
                        f"{total_chars} chars en {len(result)} página(s)"
                    )

                return result

            except Exception as e:
                error_msg = f"{provider_name} falló: {e}"
                last_error = error_msg

                if self.verbose:
                    logger.warning(f"  [{paper_id}] {error_msg}, intentando siguiente...")

                continue

        # Si llegamos aquí, todos los providers fallaron
        raise OCRExtractionError(
            f"Todos los providers fallaron para {pdf_path.name}. "
            f"Último error: {last_error}"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de uso de providers."""
        if not self.stats:
            return {"total_pdfs": 0}

        # Agrupar por provider
        by_provider = {}
        for paper_id, info in self.stats.items():
            provider_name = info["provider"]
            if provider_name not in by_provider:
                by_provider[provider_name] = {
                    "count": 0,
                    "total_chars": 0,
                    "total_pages": 0,
                }
            by_provider[provider_name]["count"] += 1
            by_provider[provider_name]["total_chars"] += info["chars"]
            by_provider[provider_name]["total_pages"] += info["pages"]

        return {
            "total_pdfs": len(self.stats),
            "by_provider": by_provider,
            "average_chars": sum(info["chars"] for info in self.stats.values())
            // max(len(self.stats), 1),
        }

    def print_statistics(self) -> None:
        """Imprime estadísticas formateadas."""
        stats = self.get_statistics()

        if stats["total_pdfs"] == 0:
            print("No statistics available yet")
            return

        print(f"\n{'='*70}")
        print("📊 ESTADÍSTICAS DE OCR HÍBRIDO")
        print(f"{'='*70}")
        print(f"Total PDFs procesados: {stats['total_pdfs']}")
        print(f"Promedio de caracteres: {stats['average_chars']:,}")

        print(f"\nPor provider:")
        for provider_name, provider_stats in stats["by_provider"].items():
            print(
                f"  • {provider_name:<20} {provider_stats['count']:<4} PDFs "
                f"({provider_stats['total_chars']:,} chars totales, "
                f"{provider_stats['total_chars'] // max(provider_stats['count'], 1):,} promedio)"
            )
