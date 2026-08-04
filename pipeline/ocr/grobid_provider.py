"""GROBID-based PDF extractor for scientific papers."""

import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple

import requests

from .base import OCRExtractionError as PDFExtractionError, OCRProvider


class GrobidProvider(OCRProvider):
    """
    Extract text and structured metadata from scientific PDFs using GROBID.

    GROBID (GeneRation Of BIbliographic Data) is a machine-learning tool
    specifically designed for extracting and parsing metadata and structure
    from scientific PDF documents.

    Capabilities:
    - Extracts title, authors, abstract, sections, references (structured)
    - Handles multi-column layouts
    - Recognizes document structure (sections, subsections)
    - Identifies and parses bibliographic references
    - Detects figures and tables

    GROBID runs as a local service (via Docker or standalone).

    Args:
        grobid_url: URL of the GROBID service (default: http://localhost:8070)
        timeout: Request timeout in seconds (default: 60)
        retry_attempts: Number of retries on failure (default: 3)
        retry_delay: Delay between retries in seconds (default: 2)
    """

    GROBID_URL_DEFAULT = "http://localhost:8070"
    FULLTEXT_ENDPOINT = "/api/processFulltextDocument"

    def __init__(
        self,
        grobid_url: Optional[str] = None,
        timeout: int = 60,
        retry_attempts: int = 3,
        retry_delay: float = 2.0,
    ):
        self.grobid_url = (grobid_url or os.getenv("GROBID_URL", self.GROBID_URL_DEFAULT)).rstrip("/")
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._session = requests.Session()

    def get_provider_name(self) -> str:
        return "grobid"

    def extract_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extract text from a PDF using GROBID.

        Process:
        1. Send PDF to GROBID API
        2. Receive XML response with document structure
        3. Parse XML to extract text by section (not by page, since GROBID
           restructures the document logically rather than by layout)
        4. Return as list of (page_number, text) tuples

        Note: GROBID returns a single structured document, not page-by-page
        text. We approximate page boundaries by section or document regions.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List of (page_number_1based, text) tuples.
            For GROBID, "pages" are logical sections, not physical pages.

        Raises:
            OCRExtractionError: If GROBID processing fails.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            self._check_grobid_available()

            xml_response = self._process_pdf(pdf_path)

            pages = self._parse_grobid_xml(xml_response)

            if not pages:
                raise OCRExtractionError(
                    f"GROBID extracted no text from {pdf_path.name}"
                )

            return pages

        except OCRExtractionError:
            raise
        except Exception as e:
            raise OCRExtractionError(
                f"GROBID extraction failed for {pdf_path.name}: {e}"
            )

    def _check_grobid_available(self) -> None:
        """Check if GROBID service is running."""
        try:
            response = self._session.get(
                f"{self.grobid_url}/api/isalive",
                timeout=5
            )
            if response.status_code != 200:
                raise OCRExtractionError(
                    f"GROBID service at {self.grobid_url} is not responding. "
                    f"Make sure GROBID is running: docker run -p 8070:8070 lfoppiano/grobid:latest"
                )
        except requests.ConnectionError:
            raise OCRExtractionError(
                f"Cannot connect to GROBID at {self.grobid_url}. "
                f"Ensure GROBID is running via Docker:\n"
                f"  docker run -p 8070:8070 lfoppiano/grobid:latest"
            )
        except Exception as e:
            raise OCRExtractionError(f"GROBID availability check failed: {e}")

    def _process_pdf(self, pdf_path: Path) -> str:
        """
        Send PDF to GROBID and return XML response.

        Retries on failure with exponential backoff.
        """
        url = f"{self.grobid_url}{self.FULLTEXT_ENDPOINT}"

        for attempt in range(self.retry_attempts):
            try:
                with open(pdf_path, "rb") as f:
                    files = {"input": f}
                    response = self._session.post(
                        url,
                        files=files,
                        timeout=self.timeout
                    )

                if response.status_code == 200:
                    return response.text

                elif response.status_code == 503:
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_delay)
                        continue
                    raise OCRExtractionError("GROBID service temporarily unavailable (503)")

                else:
                    raise OCRExtractionError(
                        f"GROBID returned {response.status_code}: {response.text[:200]}"
                    )

            except requests.Timeout:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise OCRExtractionError(f"GROBID request timed out after {self.timeout}s")

            except requests.RequestException as e:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise

        raise OCRExtractionError(f"GROBID processing failed after {self.retry_attempts} attempts")

    def _parse_grobid_xml(self, xml_response: str) -> List[Tuple[int, str]]:
        """
        Parse GROBID XML response and extract text by logical sections.

        GROBID returns TEI XML with structure:
        - <teiHeader>: metadata (title, authors, abstract)
        - <text><body>: main content organized by <div> sections
        - <back>: references and appendix

        We extract text from each major section as a separate "page".

        Returns:
            List of (section_number_1based, text) tuples.
        """
        try:
            root = ET.fromstring(xml_response)
        except ET.ParseError as e:
            raise OCRExtractionError(f"Failed to parse GROBID XML: {e}")

        namespaces = {
            "tei": "http://www.tei-c.org/ns/1.0",
            "": "http://www.tei-c.org/ns/1.0"
        }

        pages: List[Tuple[int, str]] = []
        page_num = 1

        # 1. Extract abstract if present
        abstract_elem = root.find(".//tei:abstract", namespaces)
        if abstract_elem is not None:
            abstract_text = self._extract_text_from_element(abstract_elem)
            if abstract_text.strip():
                pages.append((page_num, abstract_text))
                page_num += 1

        # 2. Extract body sections
        body_elem = root.find(".//tei:body", namespaces)
        if body_elem is not None:
            # Each <div> in body is a section
            divs = body_elem.findall("tei:div", namespaces)

            if divs:
                for div in divs:
                    section_text = self._extract_text_from_element(div)
                    if section_text.strip():
                        pages.append((page_num, section_text))
                        page_num += 1
            else:
                # No divs, just extract all body text
                body_text = self._extract_text_from_element(body_elem)
                if body_text.strip():
                    pages.append((page_num, body_text))
                    page_num += 1

        # 3. Extract references if present
        back_elem = root.find(".//tei:back", namespaces)
        if back_elem is not None:
            ref_list = back_elem.find("tei:listBibl", namespaces)
            if ref_list is not None:
                refs_text = self._extract_text_from_element(ref_list)
                if refs_text.strip():
                    pages.append((page_num, refs_text))
                    page_num += 1

        # Fallback: if no sections extracted, try to extract all text
        if not pages:
            all_text = self._extract_all_text(root)
            if all_text.strip():
                pages.append((1, all_text))

        return pages

    def _extract_text_from_element(self, elem: ET.Element) -> str:
        """Recursively extract text from an XML element."""
        text_parts = []

        if elem.text:
            text_parts.append(elem.text)

        for child in elem:
            child_text = self._extract_text_from_element(child)
            if child_text:
                text_parts.append(child_text)

            if child.tail:
                text_parts.append(child.tail)

        return "".join(text_parts)

    def _extract_all_text(self, root: ET.Element) -> str:
        """Extract all text from the XML document."""
        text = self._extract_text_from_element(root)

        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def get_metadata(self, pdf_path: Path) -> dict:
        """
        Extract structured metadata from a PDF (title, authors, abstract, etc.).

        Returns:
            Dict with keys: title, authors, abstract, keywords, publication_date
        """
        pdf_path = Path(pdf_path)

        try:
            self._check_grobid_available()
            xml_response = self._process_pdf(pdf_path)
            root = ET.fromstring(xml_response)

            namespaces = {"tei": "http://www.tei-c.org/ns/1.0"}

            metadata = {
                "title": self._extract_title(root, namespaces),
                "authors": self._extract_authors(root, namespaces),
                "abstract": self._extract_abstract(root, namespaces),
                "keywords": self._extract_keywords(root, namespaces),
                "publication_date": self._extract_pub_date(root, namespaces),
            }

            return metadata

        except Exception as e:
            return {
                "title": None,
                "authors": [],
                "abstract": None,
                "keywords": [],
                "publication_date": None,
                "error": str(e)
            }

    def _extract_title(self, root: ET.Element, ns: dict) -> Optional[str]:
        """Extract paper title."""
        title_elem = root.find(".//tei:titleStmt/tei:title", ns)
        if title_elem is not None:
            return self._extract_text_from_element(title_elem).strip()
        return None

    def _extract_authors(self, root: ET.Element, ns: dict) -> List[str]:
        """Extract list of author names."""
        authors = []
        author_elems = root.findall(".//tei:author", ns)

        for author in author_elems:
            name_elem = author.find("tei:persName", ns)
            if name_elem is not None:
                forename = name_elem.findtext("tei:forename", default="", namespaces=ns)
                surname = name_elem.findtext("tei:surname", default="", namespaces=ns)
                if surname or forename:
                    name = f"{forename} {surname}".strip()
                    if name:
                        authors.append(name)
            else:
                text = self._extract_text_from_element(author).strip()
                if text:
                    authors.append(text)

        return authors

    def _extract_abstract(self, root: ET.Element, ns: dict) -> Optional[str]:
        """Extract abstract."""
        abstract_elem = root.find(".//tei:abstract", ns)
        if abstract_elem is not None:
            return self._extract_text_from_element(abstract_elem).strip()
        return None

    def _extract_keywords(self, root: ET.Element, ns: dict) -> List[str]:
        """Extract keywords."""
        keywords = []
        keyword_elems = root.findall(".//tei:keywords/tei:term", ns)

        for kw in keyword_elems:
            text = self._extract_text_from_element(kw).strip()
            if text:
                keywords.append(text)

        return keywords

    def _extract_pub_date(self, root: ET.Element, ns: dict) -> Optional[str]:
        """Extract publication date."""
        pub_date = root.find(".//tei:publicationStmt/tei:date", ns)
        if pub_date is not None and pub_date.get("when"):
            return pub_date.get("when")
        return None
