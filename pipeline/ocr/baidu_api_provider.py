"""Baidu Cloud OCR API provider for document parsing."""

import base64
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from .base import OCRExtractionError, OCRProvider


class BaiduCloudOCRProvider(OCRProvider):
    """
    OCR provider using Baidu Cloud's Unlimited-OCR document parsing API.

    API is asynchronous: submit task → poll for completion → download results.

    Rate limits: QPS=2 for submit, QPS=5 for query. This provider serializes
    requests and respects rate limits with backoff.

    Free quota: 200 pages (personal) / 1000 (enterprise). The user must manage
    quota and upgrade plan if processing large corpora.
    """

    SUBMIT_ENDPOINT = "https://aip.baidubce.com/rest/2.0/brain/online/v2/unlimited-ocr-parser/task"
    QUERY_ENDPOINT = "https://aip.baidubce.com/rest/2.0/brain/online/v2/unlimited-ocr-parser/task/query"
    TOKEN_ENDPOINT = "https://aip.baidubce.com/oauth/2.0/token"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        poll_interval: float = 8.0,
        max_wait_seconds: int = 600,
    ):
        """
        Initialize Baidu Cloud OCR provider.

        Args:
            api_key: Baidu Cloud API Key. If None, reads from BAIDU_OCR_API_KEY env var.
            secret_key: Baidu Cloud Secret Key. If None, reads from BAIDU_OCR_SECRET_KEY env var.
            poll_interval: Seconds to wait between status checks (backoff friendly).
            max_wait_seconds: Max total time to wait for a task before giving up.
        """
        self.api_key = api_key or os.getenv("BAIDU_OCR_API_KEY")
        self.secret_key = secret_key or os.getenv("BAIDU_OCR_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise OCRExtractionError(
                "Baidu OCR credentials not found. "
                "Set BAIDU_OCR_API_KEY and BAIDU_OCR_SECRET_KEY env vars or pass them to the constructor."
            )

        self.poll_interval = poll_interval
        self.max_wait_seconds = max_wait_seconds
        self._access_token: Optional[str] = None
        self._token_fetched_at = 0
        self._session = requests.Session()

    def get_provider_name(self) -> str:
        return "baidu_api"

    def extract_pdf(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """
        Extract text from a PDF via Baidu Cloud API.

        Process:
        1. Base64-encode the PDF file.
        2. Submit a task via the submit endpoint.
        3. Poll the query endpoint until status=success.
        4. Download the markdown result from markdown_url.
        5. Parse markdown to extract text by page (if page markers exist).

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List of (page_number, text) tuples.

        Raises:
            OCRExtractionError: If submission, polling, or parsing fails.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            pdf_data = self._read_and_encode_pdf(pdf_path)

            task_id = self._submit_task(pdf_data, pdf_path.name)

            markdown = self._poll_and_get_result(task_id)

            pages = self._parse_markdown_to_pages(markdown)

            return pages

        except (requests.RequestException, ValueError, KeyError) as e:
            raise OCRExtractionError(
                f"Baidu Cloud OCR extraction failed for {pdf_path.name}: {e}"
            )

    def _get_access_token(self) -> str:
        """
        Obtain or refresh OAuth access token.

        Tokens are valid for ~30 days, but we regenerate on each API call
        for simplicity (can be optimized later with caching).
        """
        try:
            params = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key,
            }
            response = self._session.get(self.TOKEN_ENDPOINT, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if "error" in data:
                raise ValueError(f"Token auth error: {data.get('error_description', data['error'])}")

            return data["access_token"]

        except Exception as e:
            raise OCRExtractionError(f"Failed to obtain access token: {e}")

    def _read_and_encode_pdf(self, pdf_path: Path) -> str:
        """Read PDF and base64-encode it."""
        try:
            with open(pdf_path, "rb") as f:
                file_bytes = f.read()

            if len(file_bytes) > 100 * 1024 * 1024:
                raise ValueError(f"PDF too large: {pdf_path.name} exceeds 100MB limit")

            return base64.b64encode(file_bytes).decode("utf-8")
        except OSError as e:
            raise OCRExtractionError(f"Failed to read PDF: {e}")

    def _submit_task(self, file_data_b64: str, filename: str) -> str:
        """
        Submit a task to the Baidu Cloud OCR API.

        Returns:
            task_id string.

        Raises:
            OCRExtractionError: If submission fails.
        """
        access_token = self._get_access_token()
        url = f"{self.SUBMIT_ENDPOINT}?access_token={access_token}"

        payload = {
            "file_data": file_data_b64,
            "file_name": filename,
        }

        try:
            response = self._session.post(
                url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=120,
            )
            response.raise_for_status()

            result = response.json()

            # Check for API-level errors
            if result.get("error_code") != 0:
                error_msg = result.get("error_msg", "Unknown error")
                if "quota" in error_msg.lower() or result.get("error_code") == 216:
                    raise OCRExtractionError(
                        f"Baidu OCR quota exceeded. Free tier: 200 (personal) / 1000 (enterprise) pages. "
                        f"Upgrade plan at console.bce.baidu.com. Error: {error_msg}"
                    )
                raise OCRExtractionError(f"API error: {error_msg}")

            task_id = result.get("result", {}).get("task_id")
            if not task_id:
                raise ValueError("No task_id in response")

            return task_id

        except requests.RequestException as e:
            if "429" in str(e):
                raise OCRExtractionError("Rate limit (QPS=2) hit on submit. Retry after a delay.")
            raise

    def _poll_and_get_result(self, task_id: str) -> str:
        """
        Poll the query endpoint until the task completes, then download markdown.

        Returns:
            Markdown text content.

        Raises:
            OCRExtractionError: If polling times out or query fails.
        """
        start_time = time.time()
        access_token = self._get_access_token()
        query_url = f"{self.QUERY_ENDPOINT}?access_token={access_token}"

        while time.time() - start_time < self.max_wait_seconds:
            try:
                payload = {"task_id": task_id}
                response = self._session.post(
                    query_url,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30,
                )
                response.raise_for_status()

                result = response.json()

                if result.get("error_code") != 0:
                    error_msg = result.get("error_msg", "Unknown error")
                    raise OCRExtractionError(f"Query API error: {error_msg}")

                status = result.get("result", {}).get("status")

                if status == "success":
                    markdown_url = result.get("result", {}).get("markdown_url")
                    if not markdown_url:
                        raise ValueError("No markdown_url in success response")

                    markdown_text = self._download_url(markdown_url)
                    return markdown_text

                elif status == "failed":
                    raise OCRExtractionError(
                        f"Task {task_id} failed: {result.get('result', {}).get('error_msg', 'Unknown')}"
                    )

                elif status == "processing":
                    time.sleep(self.poll_interval)
                    continue

                else:
                    raise OCRExtractionError(f"Unknown status: {status}")

            except requests.RequestException as e:
                if "429" in str(e):
                    time.sleep(self.poll_interval)
                    continue
                raise

        raise OCRExtractionError(f"Task {task_id} timed out after {self.max_wait_seconds}s")

    def _download_url(self, url: str) -> str:
        """Download content from a URL (e.g., markdown_url from API response)."""
        try:
            response = self._session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            raise OCRExtractionError(f"Failed to download {url}: {e}")

    def _parse_markdown_to_pages(self, markdown: str) -> List[Tuple[int, str]]:
        """
        Parse the markdown returned by Baidu API into (page_number, text) tuples.

        The API returns a single markdown document. Attempt to identify page
        breaks (if they exist); otherwise, treat the entire document as page 1.

        Markdown may contain page markers like "---" or explicit page breaks.
        For now, we heuristically look for common patterns.
        """
        if not markdown.strip():
            return [(1, "")]

        lines = markdown.split("\n")
        pages: Dict[int, List[str]] = {1: []}
        current_page = 1

        for line in lines:
            # Common markdown page break patterns
            if re.match(r"^[\-\*]{3,}$", line.strip()):
                current_page += 1
                pages[current_page] = []
            elif re.match(r"^#+\s+Page\s+\d+", line, re.IGNORECASE):
                match = re.search(r"\d+", line)
                if match:
                    current_page = int(match.group())
                    if current_page not in pages:
                        pages[current_page] = []
            else:
                pages[current_page].append(line)

        result = []
        for page_num in sorted(pages.keys()):
            text = "\n".join(pages[page_num]).strip()
            result.append((page_num, text))

        return result if result else [(1, markdown)]
