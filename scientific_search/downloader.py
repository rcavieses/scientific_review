"""
Sistema de descarga de artículos científicos con detección de acceso abierto.

Estrategias de resolución de PDF (en orden de prioridad):
  1. Unpaywall API  — mejor fuente para PDFs en acceso abierto dado un DOI
  2. PubMed Central — si el artículo tiene PMCID
  3. arXiv directo  — convierte URL de abstract a URL de PDF
  4. Validación HEAD — comprueba Content-Type de la URL original
"""

import re
import time
import shutil
import tempfile
import requests
from pathlib import Path
from typing import List, Optional, Callable, NamedTuple
from urllib.parse import urlparse

from .models import Article


# ──────────────────────────────────────────────
# Resultado de descarga individual
# ──────────────────────────────────────────────

class DownloadResult(NamedTuple):
    article: Article
    status: str          # "ok" | "paywall" | "no_pdf" | "error"
    filepath: Optional[Path] = None
    pdf_url: Optional[str] = None
    message: str = ""


# ──────────────────────────────────────────────
# Resolución de URL libre (open access)
# ──────────────────────────────────────────────

class PdfResolver:
    """
    Intenta encontrar una URL de PDF libre para un artículo.

    Usa Unpaywall, PubMed Central y detección directa por Content-Type.
    No descarga nada; solo devuelve la URL o None.
    """

    UNPAYWALL_BASE = "https://api.unpaywall.org/v2/{doi}"
    PMC_PDF_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"

    def __init__(self, email: str = "research@scientific-search.org", timeout: int = 12):
        """
        Args:
            email: Email requerido por Unpaywall (solo para rate-limit, no se valida).
            timeout: Segundos de espera máxima por request.
        """
        self.email = email
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "scientific-search/1.0 (open-access-resolver)"})

    def resolve(self, article: Article) -> Optional[str]:
        """
        Devuelve la mejor URL de PDF libre disponible, o None si está tras paywall.

        Args:
            article: Artículo a resolver.

        Returns:
            URL del PDF libre, o None si no hay acceso.
        """
        # 1. Unpaywall — funciona con cualquier DOI
        if article.doi:
            url = self._try_unpaywall(article.doi)
            if url:
                return url

        # 2. PubMed Central — si el full_data tiene pmcid
        pmcid = self._extract_pmcid(article)
        if pmcid:
            pmc_url = self.PMC_PDF_BASE.format(pmcid=pmcid)
            if self._url_serves_pdf(pmc_url):
                return pmc_url

        # 3. arXiv — la URL de abstract se convierte a PDF directamente
        if article.source == "arxiv" and article.url:
            pdf_url = self._arxiv_to_pdf(article.url)
            if pdf_url:
                return pdf_url

        # 4. Validación directa de la URL del artículo
        if article.url and self._url_serves_pdf(article.url):
            return article.url

        return None

    # ── Estrategias individuales ──────────────────────────────────────

    def _try_unpaywall(self, doi: str) -> Optional[str]:
        """Consulta Unpaywall y retorna la URL del PDF libre si existe."""
        try:
            resp = self._session.get(
                self.UNPAYWALL_BASE.format(doi=doi),
                params={"email": self.email},
                timeout=self.timeout,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

            # Primero intenta la mejor ubicación OA con PDF directo
            best = data.get("best_oa_location") or {}
            url = best.get("url_for_pdf") or best.get("url")
            if url:
                return url

            # Fallback: cualquier ubicación OA con PDF
            for loc in data.get("oa_locations", []):
                url = loc.get("url_for_pdf") or loc.get("url")
                if url:
                    return url

        except Exception:
            pass
        return None

    def _extract_pmcid(self, article: Article) -> Optional[str]:
        """Extrae el PMCID del full_data o de la URL si está disponible."""
        if article.full_data:
            pmcid = article.full_data.get("pmcid") or article.full_data.get("pmc")
            if pmcid:
                return str(pmcid)

        # Intentar extraer de la URL (ej. /pmc/articles/PMC1234567/)
        if article.url:
            match = re.search(r"PMC\d+", article.url)
            if match:
                return match.group(0)

        return None

    def _arxiv_to_pdf(self, url: str) -> Optional[str]:
        """Convierte URL de abstract de arXiv a URL de PDF."""
        # https://arxiv.org/abs/2301.12345 → https://arxiv.org/pdf/2301.12345
        pdf_url = re.sub(r"arxiv\.org/abs/", "arxiv.org/pdf/", url)
        if pdf_url != url:
            return pdf_url
        # También maneja URLs con versión: .../abs/2301.12345v2
        return None

    def _url_serves_pdf(self, url: str) -> bool:
        """HEAD request para verificar que la URL sirve un PDF real."""
        try:
            resp = self._session.head(
                url, timeout=self.timeout, allow_redirects=True
            )
            content_type = resp.headers.get("Content-Type", "").lower()
            return "application/pdf" in content_type
        except Exception:
            return False


# ──────────────────────────────────────────────
# Descargador principal
# ──────────────────────────────────────────────

class ArticleDownloader:
    """Gestiona la descarga de PDFs de artículos científicos."""

    def __init__(
        self,
        download_directory: Optional[Path] = None,
        timeout: int = 30,
        email: str = "research@scientific-search.org",
        delay: float = 1.0,
    ):
        """
        Args:
            download_directory: Directorio donde guardar los PDFs.
                                Si es None usa un directorio temporal.
            timeout: Segundos de espera máxima por descarga.
            email: Email para Unpaywall API.
            delay: Pausa entre descargas (segundos) para no sobrecargar servidores.
        """
        self.timeout = timeout
        self.delay = delay
        self.resolver = PdfResolver(email=email, timeout=15)

        if download_directory is None:
            self.temp_dir = Path(tempfile.gettempdir()) / "scientific_search_downloads"
        else:
            self.temp_dir = Path(download_directory)

        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (compatible; scientific-search/1.0)"
            )
        })

    def download_article(
        self,
        article: Article,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> DownloadResult:
        """
        Descarga el PDF de un artículo si está disponible en acceso abierto.

        Args:
            article: Artículo a descargar.
            progress_callback: Función para reportar progreso.

        Returns:
            DownloadResult con status "ok", "paywall", "no_pdf" o "error".
        """
        short_title = article.title[:55] + ("…" if len(article.title) > 55 else "")

        # Resolver URL libre
        pdf_url = self.resolver.resolve(article)

        if not pdf_url:
            msg = f"[sin acceso] {short_title}"
            if progress_callback:
                progress_callback(msg)
            return DownloadResult(article=article, status="paywall", message=msg)

        # Nombre de archivo
        safe_name = self._sanitize_filename(article.title)
        if article.year:
            safe_name = f"{article.year}_{safe_name}"
        filepath = self.temp_dir / f"{safe_name}.pdf"

        # Evitar re-descarga
        if filepath.exists():
            msg = f"[ya existe] {short_title}"
            if progress_callback:
                progress_callback(msg)
            return DownloadResult(
                article=article, status="ok", filepath=filepath,
                pdf_url=pdf_url, message=msg,
            )

        # Descargar
        try:
            resp = self._session.get(pdf_url, timeout=self.timeout, stream=True)
            resp.raise_for_status()

            # Verificar que realmente sea un PDF (no página de paywall)
            content_type = resp.headers.get("Content-Type", "").lower()
            if "application/pdf" not in content_type:
                msg = f"[paywall/html] {short_title}"
                if progress_callback:
                    progress_callback(msg)
                return DownloadResult(
                    article=article, status="paywall",
                    pdf_url=pdf_url, message=msg,
                )

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            size_kb = filepath.stat().st_size // 1024
            msg = f"[ok {size_kb} KB] {short_title}"
            if progress_callback:
                progress_callback(msg)
            return DownloadResult(
                article=article, status="ok", filepath=filepath,
                pdf_url=pdf_url, message=msg,
            )

        except Exception as e:
            msg = f"[error] {short_title} — {str(e)[:60]}"
            if progress_callback:
                progress_callback(msg)
            return DownloadResult(article=article, status="error", message=msg)

    def download_articles(
        self,
        articles: List[Article],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[DownloadResult]:
        """
        Descarga múltiples artículos respetando un delay entre requests.

        Args:
            articles: Lista de artículos.
            progress_callback: Función para reportar progreso.

        Returns:
            Lista de DownloadResult para cada artículo.
        """
        results = []

        if progress_callback:
            progress_callback(f"Iniciando descarga de {len(articles)} artículos...\n")

        for i, article in enumerate(articles, 1):
            if progress_callback:
                progress_callback(f"  [{i}/{len(articles)}] ", end="")

            result = self.download_article(article, progress_callback)
            results.append(result)

            # Pausa entre requests para no sobrecargar servidores
            if i < len(articles):
                time.sleep(self.delay)

        # Resumen
        ok = sum(1 for r in results if r.status == "ok")
        paywall = sum(1 for r in results if r.status == "paywall")
        errors = sum(1 for r in results if r.status == "error")

        if progress_callback:
            progress_callback(
                f"\nResumen: {ok} descargados | {paywall} sin acceso abierto | {errors} errores"
            )

        return results

    def print_results(self, results: List[DownloadResult]) -> None:
        """Imprime un resumen tabular de los resultados de descarga."""
        SEP = "-" * 60
        ok = [r for r in results if r.status == "ok"]
        payw = [r for r in results if r.status == "paywall"]
        errs = [r for r in results if r.status == "error"]

        print(f"\n{SEP}")
        print(f"  PDFs DESCARGADOS ({len(ok)})")
        print(SEP)
        for r in ok:
            size = f"{r.filepath.stat().st_size // 1024} KB" if r.filepath else ""
            print(f"  [ok] {r.article.title[:55]}  [{size}]")
            print(f"       {r.filepath}")

        if payw:
            print(f"\n{SEP}")
            print(f"  SIN ACCESO ABIERTO ({len(payw)})")
            print(SEP)
            for r in payw:
                print(f"  [--] {r.article.title[:55]}")

        if errs:
            print(f"\n{SEP}")
            print(f"  ERRORES ({len(errs)})")
            print(SEP)
            for r in errs:
                print(f"  [!!] {r.message}")

        print(f"\n  Directorio: {self.temp_dir}")

    def get_temp_directory(self) -> Path:
        """Obtiene la ruta del directorio de descargas."""
        return self.temp_dir

    def clear_temp_directory(self) -> int:
        """
        Limpia el directorio de descargas.

        Returns:
            Número de archivos eliminados.
        """
        if not self.temp_dir.exists():
            return 0
        count = 0
        for file in self.temp_dir.glob("*.pdf"):
            try:
                file.unlink()
                count += 1
            except OSError:
                pass
        return count

    def get_download_stats(self) -> dict:
        """Obtiene estadísticas de descargas en el directorio."""
        if not self.temp_dir.exists():
            return {"total_files": 0, "total_size_mb": 0.0, "directory": str(self.temp_dir)}

        files = list(self.temp_dir.glob("*.pdf"))
        total_size = sum(f.stat().st_size for f in files)
        return {
            "total_files": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "directory": str(self.temp_dir),
        }

    @staticmethod
    def _sanitize_filename(filename: str, max_length: int = 80) -> str:
        """Convierte un título en nombre de archivo seguro."""
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        safe = filename
        for char in invalid_chars:
            safe = safe.replace(char, "_")
        safe = "_".join(safe.strip().split())
        return safe[:max_length] or "article"
