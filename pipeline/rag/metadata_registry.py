"""
Registro de metadatos de artículos científicos para enriquecer los chunks del índice FAISS.

Escanea los CSVs generados por la búsqueda y construye un lookup paper_id → metadatos,
usando la misma normalización de nombres que RAGPipelineOrchestrator._derive_paper_id().

Ejemplo de uso:
    registry = MetadataRegistry()
    registry.load_from_search_results(Path("outputs/search_results"))
    meta = registry.get(paper_id)
    # meta = {"title": "...", "authors": [...], "year": 2022, "doi": "..."}
"""

import csv
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional


class MetadataRegistry:
    """
    Lookup de metadatos indexados por paper_id.

    Carga automáticamente todos los CSVs encontrados en el directorio de
    resultados de búsqueda y los vincula a los PDFs del índice FAISS usando
    la misma normalización de nombre de archivo que el downloader y el
    RAGPipelineOrchestrator.
    """

    def __init__(self):
        # paper_id → {"title": str, "authors": List[str], "year": int|None, "doi": str|None}
        self._registry: Dict[str, Dict] = {}

    # ── API pública ──────────────────────────────────────────────────────────

    def load_from_search_results(self, search_dir: Path) -> int:
        """
        Escanea todos los CSVs en search_dir y registra los metadatos de cada artículo.

        Args:
            search_dir: Directorio que contiene los archivos search_*.csv.

        Returns:
            Número de artículos registrados.
        """
        search_dir = Path(search_dir)
        if not search_dir.exists():
            return 0

        csv_files = sorted(search_dir.glob("*.csv"))
        loaded = 0

        for csv_path in csv_files:
            loaded += self._load_csv(csv_path)

        return loaded

    def get(self, paper_id: str) -> Optional[Dict]:
        """
        Retorna los metadatos para un paper_id, o None si no se encontró.

        Args:
            paper_id: Identificador derivado del nombre del PDF (ya normalizado).

        Returns:
            Dict con keys: title, authors, year, doi; o None.
        """
        return self._registry.get(paper_id)

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, paper_id: str) -> bool:
        return paper_id in self._registry

    # ── Carga interna ────────────────────────────────────────────────────────

    def _load_csv(self, csv_path: Path) -> int:
        """Carga un archivo CSV de resultados de búsqueda. Retorna artículos registrados."""
        try:
            with open(csv_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception:
            return 0

        registered = 0
        for row in rows:
            title = row.get("title", "").strip()
            year_str = row.get("year", "").strip()

            if not title:
                continue

            year = int(year_str) if year_str.isdigit() else None
            authors = self._parse_authors(row.get("authors", ""))
            doi = row.get("doi", "").strip() or None

            paper_id = self._paper_id_from_title(title, year)
            if paper_id and paper_id not in self._registry:
                self._registry[paper_id] = {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "doi": doi,
                }
                registered += 1

        return registered

    # ── Normalización ────────────────────────────────────────────────────────

    @staticmethod
    def _paper_id_from_title(title: str, year: Optional[int]) -> str:
        """
        Reproduce la cadena de transformaciones que el downloader + _derive_paper_id aplican
        al pasar de título de artículo → nombre de archivo PDF → paper_id del índice.

        Pasos:
          1. Reemplazar caracteres inválidos en filename (como _sanitize_filename)
          2. Colapsar espacios → underscore (como _sanitize_filename)
          3. Truncar a 80 caracteres (como _sanitize_filename)
          4. Anteponer año (como downloader)
          5. Normalizar unicode → ASCII (como _derive_paper_id)
          6. Reemplazar no-alfanumérico por _ (como _derive_paper_id)
          7. Colapsar underscores múltiples
        """
        # Paso 1-3: simular _sanitize_filename
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        safe = title
        for char in invalid_chars:
            safe = safe.replace(char, "_")
        safe = "_".join(safe.strip().split())
        safe = safe[:80]

        # Paso 4: anteponer año
        if year:
            safe = f"{year}_{safe}"

        # Paso 5-7: simular _derive_paper_id
        safe = unicodedata.normalize("NFKD", safe)
        safe = safe.encode("ascii", "ignore").decode("ascii")
        safe = re.sub(r"[^\w\-]", "_", safe)
        safe = re.sub(r"_+", "_", safe)
        return safe.strip("_") or ""

    @staticmethod
    def _parse_authors(raw: str) -> List[str]:
        """
        Convierte una cadena de autores (separados por ';' o ',') en lista.

        "Smith, J.; Doe, A." → ["Smith, J.", "Doe, A."]
        "Smith J, Doe A" → ["Smith J", "Doe A"]
        """
        raw = raw.strip()
        if not raw:
            return []

        # Separador principal: punto y coma
        if ";" in raw:
            parts = [p.strip() for p in raw.split(";")]
        else:
            # Separar por coma, pero solo cuando el segmento no parece "Apellido, Inicial"
            # Heurística: si la coma va seguida de un espacio y UNA letra/inicial → apellido, nombre
            # → dividir por punto y coma simulado (no dividir)
            parts = [p.strip() for p in raw.split(",")]
            # Si cada parte es muy corta probablemente son iniciales, reensamblar de 2 en 2
            if all(len(p) <= 3 for p in parts[1::2]):
                it = iter(parts)
                parts = [f"{a}, {b}" for a, b in zip(it, it)]

        return [p for p in parts if p]
