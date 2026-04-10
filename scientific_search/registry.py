"""
Sistema de registro y guardado de resultados de búsquedas en CSV.
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import Article, SearchResult


class SearchRegistry:
    """Gestiona el registro de búsquedas y resultados en archivos."""

    def __init__(self, base_directory: Optional[Path] = None):
        """
        Inicializa el registro.

        Args:
            base_directory: Directorio base para guardar registros.
                           Si es None, usa el directorio actual.
        """
        self.base_directory = Path(base_directory) or Path.cwd()
        self.base_directory.mkdir(parents=True, exist_ok=True)

        # Crear subdirectorios
        self.results_dir = self.base_directory / "search_results"
        self.logs_dir = self.base_directory / "search_logs"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def save_to_csv(
        self,
        articles: List[Article],
        filename: str,
        search_query: Optional[str] = None,
    ) -> Path:
        """
        Guarda artículos en archivo CSV.

        Args:
            articles: Lista de artículos a guardar.
            filename: Nombre del archivo CSV.
            search_query: Término de búsqueda (se incluye en metadatos).

        Returns:
            Ruta del archivo guardado.
        """
        filepath = self.results_dir / filename

        # Preparar datos para CSV
        fieldnames = [
            "title",
            "authors",
            "year",
            "doi",
            "url",
            "journal",
            "source",
            "abstract",
            "keywords",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for article in articles:
                writer.writerow(article.to_dict())

        # Guardar metadatos en archivo complementario
        metadata = {
            "filename": filename,
            "query": search_query or "unknown",
            "total_articles": len(articles),
            "sources": list(set(a.source for a in articles)),
            "creation_date": datetime.now().isoformat(),
        }

        metadata_filepath = filepath.with_suffix(".json")
        with open(metadata_filepath, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return filepath

    def save_search_result(
        self,
        search_result: SearchResult,
        csv_filename: Optional[str] = None,
    ) -> Dict[str, Path]:
        """
        Guarda el resultado completo de una búsqueda.

        Args:
            search_result: Objeto SearchResult a guardar.
            csv_filename: Nombre personalizado para el CSV
                         (si es None, se genera automáticamente).

        Returns:
            Diccionario con rutas de archivos generados.
        """
        if not csv_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            query_safe = (
                search_result.query.replace(" ", "_")
                .replace("/", "_")
                .replace("\\", "_")[:50]
            )
            csv_filename = f"search_{query_safe}_{timestamp}.csv"

        # Guardar CSV
        csv_path = self.save_to_csv(
            search_result.articles,
            csv_filename,
            search_result.query,
        )

        # Guardar resumen en archivo de texto
        summary_filename = csv_filename.replace(".csv", "_summary.txt")
        summary_path = self.results_dir / summary_filename

        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(search_result.summary())
            f.write("\n\nErrores encontrados:\n")
            if search_result.errors:
                for source, error in search_result.errors.items():
                    f.write(f"  - {source}: {error}\n")
            else:
                f.write("  Ninguno\n")

        # Guardar log detallado
        log_filename = csv_filename.replace(".csv", "_full_log.json")
        log_path = self.logs_dir / log_filename

        log_data = {
            "query": search_result.query,
            "search_date": search_result.search_date.isoformat(),
            "total_articles_found": len(search_result.articles),
            "total_results_available": search_result.total_results,
            "sources_queried": search_result.sources_queried,
            "articles": [
                {
                    "title": a.title,
                    "authors": a.authors,
                    "year": a.year,
                    "doi": a.doi,
                    "url": a.url,
                    "source": a.source,
                }
                for a in search_result.articles
            ],
            "errors": search_result.errors or {},
        }

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        return {
            "csv": csv_path,
            "summary": summary_path,
            "log": log_path,
        }

    def load_from_csv(self, csv_filename: str) -> List[Article]:
        """
        Carga artículos desde un archivo CSV guardado anteriormente.

        Args:
            csv_filename: Nombre del archivo CSV.

        Returns:
            Lista de artículos cargados.
        """
        filepath = self.results_dir / csv_filename

        if not filepath.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

        articles = []

        with open(filepath, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                authors = (
                    [a.strip() for a in row["authors"].split(";")]
                    if row["authors"]
                    else []
                )
                keywords = (
                    [k.strip() for k in row["keywords"].split(";")]
                    if row["keywords"]
                    else []
                )

                article = Article(
                    title=row["title"],
                    authors=authors,
                    year=int(row["year"]) if row["year"] else None,
                    doi=row["doi"] or None,
                    url=row["url"] or None,
                    abstract=row["abstract"] or None,
                    keywords=keywords if keywords else None,
                    journal=row["journal"] or None,
                    source=row["source"],
                )
                articles.append(article)

        return articles

    def get_search_history(self) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de búsquedas realizadas.

        Returns:
            Lista de diccionarios con información de búsquedas previas.
        """
        history = []

        for json_file in self.results_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    history.append(metadata)
            except (json.JSONDecodeError, IOError):
                continue

        # Ordenar por fecha de creación (más reciente primero)
        history.sort(
            key=lambda x: x.get("creation_date", ""),
            reverse=True,
        )

        return history

    def list_saved_searches(self) -> List[str]:
        """
        Lista todas las búsquedas guardadas.

        Returns:
            Lista de nombres de archivos de búsquedas guardadas.
        """
        csv_files = [
            f.name for f in self.results_dir.glob("search_*.csv")
        ]
        return sorted(csv_files)
