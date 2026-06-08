import argparse
import csv
import time
from pathlib import Path
from datetime import datetime

from doi2pdf import doi2pdf


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEARCH_RESULTS_DIR = PROJECT_ROOT / "outputs" / "search_results_canonical"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "PDF"
FAILED_LOG = PROJECT_ROOT / "pdf_download_failures.csv"


class ProcessedTracker:
    def __init__(self, failed_log: Path) -> None:
        self.failed_log = failed_log
        self.failed_dois: set[str] = set()
        self.failed_log_mtime: float | None = None

    def refresh(self) -> None:
        if not self.failed_log.exists():
            self.failed_dois = set()
            self.failed_log_mtime = None
            return

        current_mtime = self.failed_log.stat().st_mtime
        if self.failed_log_mtime == current_mtime:
            return

        with self.failed_log.open("r", encoding="utf-8", newline="") as handle:
            self.failed_dois = {
                (row.get("doi") or "").strip()
                for row in csv.DictReader(handle)
                if (row.get("doi") or "").strip()
            }
        self.failed_log_mtime = current_mtime

    def is_processed(self, doi: str) -> bool:
        self.refresh()
        pdf_path = OUTPUT_DIR / f"{sanitize_doi(doi)}.pdf"
        return pdf_path.exists() or doi in self.failed_dois


def sanitize_doi(doi: str) -> str:
    return doi.replace("/", "_").replace(".", "_")


def append_failed_download(article: dict[str, str], error_message: str) -> None:
    file_exists = FAILED_LOG.exists()

    with FAILED_LOG.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "doi", "species", "source", "title", "error"],
        )
        if not file_exists:
            writer.writeheader()

        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "doi": article["doi"],
                "species": article["species"],
                "source": article["source"],
                "title": article["title"],
                "error": error_message,
            }
        )


def load_pending_articles(reverse: bool = False) -> list[dict[str, str]]:
    if not SEARCH_RESULTS_DIR.exists():
        print(f"❌ Error: No existe la carpeta '{SEARCH_RESULTS_DIR}'.")
        raise SystemExit(1)

    pending_articles: list[dict[str, str]] = []
    seen_dois: set[str] = set()

    for csv_path in sorted(SEARCH_RESULTS_DIR.glob("*.csv")):
        species_name = csv_path.stem.replace("_", " ")

        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                doi = (row.get("doi") or "").strip()
                if not doi or not doi.startswith("10."):
                    continue

                if doi in seen_dois:
                    continue

                seen_dois.add(doi)
                pending_articles.append(
                    {
                        "doi": doi,
                        "species": species_name,
                        "source": (row.get("source") or "").strip(),
                        "title": (row.get("title") or "").strip(),
                    }
                )

    if reverse:
        pending_articles.reverse()

    return pending_articles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga PDFs desde los DOIs encontrados en search_results_canonical.",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Procesa la lista de DOIs en orden inverso y se detiene al detectar solapamiento.",
    )
    parser.add_argument(
        "--overlap-threshold",
        type=int,
        default=25,
        help="Cantidad de DOIs procesados consecutivos para considerar que se alcanzó el frente del otro proceso.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pending_articles = load_pending_articles(reverse=args.reverse)
    if not pending_articles:
        print("❌ No se encontraron artículos con DOI válido en search_results_canonical.")
        raise SystemExit(1)

    processed_tracker = ProcessedTracker(FAILED_LOG)
    downloaded = 0
    skipped_existing = 0
    failed = 0
    overlap_hits = 0

    print(
        "▶️ Modo inverso activado" if args.reverse else "▶️ Modo normal activado"
    )

    for article in pending_articles:
        doi = article["doi"]
        pdf_path = OUTPUT_DIR / f"{sanitize_doi(doi)}.pdf"

        if args.reverse and processed_tracker.is_processed(doi):
            overlap_hits += 1
            if overlap_hits >= args.overlap_threshold:
                print(
                    f"⏹️ Solapamiento detectado tras {overlap_hits} DOIs consecutivos ya procesados."
                )
                break
            continue

        overlap_hits = 0

        if pdf_path.exists():
            skipped_existing += 1
            continue

        print(f"\n📥 Descargando DOI: {doi}")
        print(f"   Especie: {article['species']}")
        if article["title"]:
            print(f"   Título: {article['title']}")

        try:
            doi2pdf(doi, output=str(pdf_path))
            downloaded += 1
            print(f"✅ Descargado: {pdf_path}")
        except Exception as exc:
            failed += 1
            print(f"❌ Error al descargar {doi}: {exc}")
            append_failed_download(article, str(exc))
            if pdf_path.exists():
                pdf_path.unlink()
            time.sleep(1)

    print("\n✅ Proceso completado.")
    print(f"   Artículos con DOI encontrados: {len(pending_articles)}")
    print(f"   PDFs ya existentes: {skipped_existing}")
    print(f"   PDFs descargados: {downloaded}")
    print(f"   Errores: {failed}")
    if args.reverse:
        print(f"   Umbral de solapamiento: {args.overlap_threshold}")
    print(f"   Carpeta destino: {OUTPUT_DIR}")
    print(f"   Registro de fallos: {FAILED_LOG}")


if __name__ == "__main__":
    main()
