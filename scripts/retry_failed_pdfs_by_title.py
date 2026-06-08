"""Segunda pasada para recuperar PDFs fallidos resolviendo DOI/URL OA por titulo.

Flujo:
1. Lee `pdf_download_status.csv` y toma filas con `status=failed`.
2. Normaliza el titulo y busca candidatos en Crossref y OpenAlex.
3. Puntua candidatos por similitud de titulo.
4. Si el puntaje supera el umbral, intenta descargar con `ArticleDownloader`.
5. Escribe un reporte CSV con el resultado de la resolucion y descarga.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = PROJECT_ROOT / "pdf_download_status.csv"
OUTPUT_CSV = PROJECT_ROOT / "pdf_retry_resolution.csv"
PDF_DIR = PROJECT_ROOT / "outputs" / "PDF"
REPORT_FIELDS = [
    "original_doi",
    "resolved_doi",
    "species",
    "source",
    "title",
    "candidate_title",
    "candidate_source",
    "match_score",
    "retry_status",
    "pdf_path",
    "pdf_url",
    "error",
]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scientific_search.downloader import ArticleDownloader
from scientific_search.models import Article

CROSSREF_API = "https://api.crossref.org/works"
OPENALEX_API = "https://api.openalex.org/works"
USER_AGENT = "scientific-review/1.0 (title-retry-resolver)"


@dataclass
class Candidate:
    source: str
    title: str
    doi: str
    url: str
    oa_url: str
    journal: str
    year: int | None
    authors: list[str]
    score: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reintenta PDFs fallidos resolviendo DOI o URL OA por titulo.",
    )
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_CSV)
    parser.add_argument(
        "--resume-from",
        type=Path,
        default=OUTPUT_CSV,
        help="CSV existente con filas ya procesadas que deben omitirse al reanudar.",
    )
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--status", default="failed", help="Status a reintentar.")
    parser.add_argument("--limit", type=int, default=0, help="Limita filas procesadas.")
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="Indice del shard a ejecutar (base 0).",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="Cantidad total de shards disjuntos.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.78,
        help="Puntaje minimo de similitud para aceptar un candidato.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Resuelve metadatos pero no intenta descargar PDFs.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Pausa entre requests de resolucion de metadatos.",
    )
    return parser.parse_args()


def resolve_output_path(output_path: Path, shard_index: int, shard_count: int) -> Path:
    if shard_count <= 1:
        return output_path
    return output_path.with_name(
        f"{output_path.stem}.part_{shard_index:02d}_of_{shard_count:02d}{output_path.suffix}"
    )


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def normalize_title(value: str) -> str:
    value = html.unescape(value or "")
    value = strip_tags(value)
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def similarity_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


class TitleResolver:
    def __init__(self, delay: float = 0.2):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def search(self, title: str) -> list[Candidate]:
        candidates: list[Candidate] = []
        candidates.extend(self._search_crossref(title))
        candidates.extend(self._search_openalex(title))
        return candidates

    def _search_crossref(self, title: str) -> list[Candidate]:
        try:
            time.sleep(self.delay)
            response = self.session.get(
                CROSSREF_API,
                params={"query.bibliographic": title, "rows": 5},
                timeout=20,
            )
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])
        except Exception:
            return []

        candidates: list[Candidate] = []
        for item in items:
            candidate_title = " ".join(item.get("title", []))
            doi = (item.get("DOI") or "").strip()
            if not candidate_title or not doi:
                continue

            year = None
            issued = item.get("issued", {}).get("date-parts", [])
            if issued and issued[0]:
                year = issued[0][0]

            authors = []
            for author in item.get("author", [])[:5]:
                name = " ".join(
                    part for part in [author.get("given", ""), author.get("family", "")] if part
                ).strip()
                if name:
                    authors.append(name)

            candidates.append(
                Candidate(
                    source="crossref",
                    title=candidate_title,
                    doi=doi,
                    url=item.get("URL", f"https://doi.org/{doi}"),
                    oa_url="",
                    journal=" ".join(item.get("container-title", [])[:1]),
                    year=year,
                    authors=authors,
                )
            )
        return candidates

    def _search_openalex(self, title: str) -> list[Candidate]:
        try:
            time.sleep(self.delay)
            response = self.session.get(
                OPENALEX_API,
                params={"search": title, "per-page": 5},
                timeout=20,
            )
            response.raise_for_status()
            items = response.json().get("results", [])
        except Exception:
            return []

        candidates: list[Candidate] = []
        for item in items:
            doi = (item.get("doi") or "").replace("https://doi.org/", "").strip()
            candidate_title = (item.get("display_name") or "").strip()
            if not candidate_title or not doi:
                continue

            authors = []
            for authorship in item.get("authorships", [])[:5]:
                author = authorship.get("author", {})
                name = (author.get("display_name") or "").strip()
                if name:
                    authors.append(name)

            location = item.get("primary_location") or {}
            source = location.get("source") or {}
            best_oa_location = item.get("best_oa_location") or {}
            open_access = item.get("open_access") or {}
            oa_url = (
                (best_oa_location.get("pdf_url") or "").strip()
                or (location.get("pdf_url") or "").strip()
                or (open_access.get("oa_url") or "").strip()
                or (location.get("landing_page_url") or "").strip()
            )
            candidates.append(
                Candidate(
                    source="openalex",
                    title=candidate_title,
                    doi=doi,
                    url=item.get("id", f"https://doi.org/{doi}"),
                    oa_url=oa_url,
                    journal=(source.get("display_name") or "").strip(),
                    year=item.get("publication_year"),
                    authors=authors,
                )
            )
        return candidates


def load_failed_rows(path: Path, status: str, limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("status") or "").strip() != status:
                continue
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    return rows


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return ((row.get("doi") or "").strip(), (row.get("title") or "").strip())


def load_processed_keys(path: Path | None) -> set[tuple[str, str]]:
    if path is None or not path.exists():
        return set()

    processed: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            processed.add(
                (
                    (row.get("original_doi") or "").strip(),
                    (row.get("title") or "").strip(),
                )
            )
    return processed


def filter_pending_rows(
    rows: list[dict[str, str]],
    processed_keys: set[tuple[str, str]],
    shard_index: int,
    shard_count: int,
) -> list[dict[str, str]]:
    pending_rows: list[dict[str, str]] = []
    pending_position = 0

    for row in rows:
        if row_key(row) in processed_keys:
            continue

        if pending_position % shard_count == shard_index:
            pending_rows.append(row)
        pending_position += 1

    return pending_rows


def choose_best_candidate(title: str, candidates: Iterable[Candidate]) -> Candidate | None:
    best: Candidate | None = None
    for candidate in candidates:
        candidate.score = similarity_score(title, candidate.title)

        normalized_input = normalize_title(title)
        normalized_candidate = normalize_title(candidate.title)
        if normalized_input == normalized_candidate:
            candidate.score += 0.15
        elif normalized_input and normalized_input in normalized_candidate:
            candidate.score += 0.05

        if candidate.oa_url:
            candidate.score += 0.05

        if best is None or candidate.score > best.score:
            best = candidate
    return best


def build_article(row: dict[str, str], candidate: Candidate) -> Article:
    return Article(
        title=candidate.title,
        authors=candidate.authors,
        year=candidate.year,
        doi=None if candidate.oa_url else candidate.doi,
        url=candidate.oa_url or candidate.url,
        journal=candidate.journal,
        source=candidate.source,
        full_data={"species": row.get("species", "")},
    )


def main() -> None:
    args = parse_args()

    if args.shard_count < 1:
        raise ValueError("--shard-count debe ser >= 1")
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError("--shard-index debe estar entre 0 y shard-count-1")

    args.output = resolve_output_path(args.output, args.shard_index, args.shard_count)

    failed_rows = load_failed_rows(args.input, args.status, args.limit)
    if not failed_rows:
        print("No hay filas para reintentar.")
        return

    processed_keys = load_processed_keys(args.resume_from)
    failed_rows = filter_pending_rows(
        failed_rows,
        processed_keys,
        args.shard_index,
        args.shard_count,
    )
    if not failed_rows:
        print(
            f"No hay filas pendientes para shard {args.shard_index}/{args.shard_count}."
        )
        return

    print(
        f"Shard {args.shard_index + 1}/{args.shard_count} | "
        f"saltando {len(processed_keys)} filas ya resueltas | "
        f"pendientes en shard: {len(failed_rows)}"
    )

    resolver = TitleResolver(delay=args.delay)
    downloader = ArticleDownloader(download_directory=args.pdf_dir)

    recovered = 0
    unresolved = 0
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        handle.flush()

        for index, row in enumerate(failed_rows, 1):
            title = (row.get("title") or "").strip()
            print(f"[{index}/{len(failed_rows)}] Resolviendo: {title[:120]}")

            candidates = resolver.search(title)
            best = choose_best_candidate(title, candidates)

            report = {
                "original_doi": (row.get("doi") or "").strip(),
                "resolved_doi": "",
                "species": (row.get("species") or "").strip(),
                "source": (row.get("source") or "").strip(),
                "title": title,
                "candidate_title": "",
                "candidate_source": "",
                "match_score": "0.00",
                "retry_status": "unresolved",
                "pdf_path": "",
                "pdf_url": "",
                "error": "No se encontro candidato confiable",
            }

            if best is None or best.score < args.min_score:
                unresolved += 1
                if best is not None:
                    report["candidate_title"] = best.title
                    report["candidate_source"] = best.source
                    report["match_score"] = f"{best.score:.4f}"
                    report["error"] = f"Puntaje insuficiente: {best.score:.4f}"
                writer.writerow(report)
                handle.flush()
                continue

            report["resolved_doi"] = best.doi
            report["candidate_title"] = best.title
            report["candidate_source"] = best.source
            report["match_score"] = f"{best.score:.4f}"

            if args.report_only:
                report["retry_status"] = "resolved"
                report["error"] = ""
                writer.writerow(report)
                handle.flush()
                continue

            article = build_article(row, best)
            result = downloader.download_article(article)
            report["retry_status"] = result.status
            report["pdf_path"] = str(result.filepath) if result.filepath else ""
            report["pdf_url"] = result.pdf_url or ""
            report["error"] = result.message
            writer.writerow(report)
            handle.flush()

            if result.status == "ok":
                recovered += 1
            else:
                unresolved += 1

    print(f"Reporte generado: {args.output}")
    print(f"Filas procesadas: {len(failed_rows)}")
    print(f"Recuperados: {recovered}")
    print(f"No recuperados: {unresolved}")


if __name__ == "__main__":
    main()