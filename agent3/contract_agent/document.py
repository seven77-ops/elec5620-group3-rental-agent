"""Local document conversion. Imported text is data, never an instruction."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from xml.etree import ElementTree

from .errors import ContractError, ResubmissionRequired

MAX_BYTES = 2_000_000
MAX_TEXT = 120_000
MAX_PDF_PAGES = 10


def _ocr_pdf(raw: bytes, page_count: int) -> list[str]:
    """Optional local OCR; no network or shell interpolation."""
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise ResubmissionRequired("Image-only PDF needs local pdftoppm and tesseract OCR; supply a text-based copy")
    with tempfile.TemporaryDirectory(prefix="agent3-ocr-") as temporary:
        pdf = Path(temporary) / "agreement.pdf"
        pdf.write_bytes(raw)
        prefix = Path(temporary) / "page"
        try:
            subprocess.run(["pdftoppm", "-png", "-r", "180", str(pdf), str(prefix)],
                           check=True, capture_output=True, timeout=45)
            images = sorted(Path(temporary).glob("page-*.png"))
            if len(images) != page_count:
                raise ResubmissionRequired("OCR page count did not match the agreement")
            pages = []
            for image in images:
                result = subprocess.run(["tesseract", str(image), "stdout", "--psm", "6"],
                                        check=True, capture_output=True, timeout=30)
                pages.append(result.stdout.decode("utf-8", errors="replace"))
            return pages
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ResubmissionRequired("Local OCR failed; supply a clearer agreement") from exc


def load_document(path: str | Path, *, consent: bool, max_pdf_pages: int = MAX_PDF_PAGES) -> dict:
    # Consent is checked before opening the document.
    if consent is not True:
        raise ContractError("Explicit consent is required before reading a rental agreement")
    if type(max_pdf_pages) is not int or not 1 <= max_pdf_pages <= 30:
        raise ContractError("PDF page allowance must be an integer between 1 and 30")
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".txt", ".docx", ".pdf"}:
        raise ContractError("Supported agreement formats: TXT, DOCX and text-based PDF")
    if path.stat().st_size > MAX_BYTES:
        raise ContractError("Agreement exceeds the 2 MB prototype limit")
    raw = path.read_bytes()
    if suffix == ".txt":
        try:
            pages = [raw.decode("utf-8-sig")]
        except UnicodeDecodeError as exc:
            raise ResubmissionRequired("TXT must be readable UTF-8") from exc
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > MAX_TEXT * 20:
                    raise ContractError("DOCX text exceeds the prototype limit")
                root = ElementTree.fromstring(archive.read(info))
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                text = "\n".join("".join(node.text or "" for node in p.iter(ns + "t"))
                                 for p in root.iter(ns + "p"))
                pages = [text]
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise ResubmissionRequired("DOCX is unreadable; supply a clearer copy") from exc
    else:
        extraction_mode = "text"
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ContractError("Text-based PDF support requires pypdf") from exc
        try:
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > max_pdf_pages:
                raise ContractError(f"PDF exceeds the {max_pdf_pages}-page prototype limit")
            pages = [page.extract_text() or "" for page in reader.pages]
        except ContractError:
            raise
        except Exception as exc:
            raise ResubmissionRequired("PDF is unreadable; supply a clearer copy") from exc
        if not any(page.strip() for page in pages):
            if len(pages) > MAX_PDF_PAGES:
                raise ResubmissionRequired("Image-only PDF exceeds the 10-page OCR allowance; supply a text-based copy")
            pages = _ocr_pdf(raw, len(pages))
            extraction_mode = "ocr"
        if not any(page.strip() for page in pages):
            raise ResubmissionRequired("OCR found no readable agreement text; supply a clearer copy")
    text = "\n".join(f"[page {i}]\n{page}" for i, page in enumerate(pages, 1))
    if len(text.strip()) < 30:
        raise ResubmissionRequired("Agreement text is too short or unreadable")
    if len(text) > MAX_TEXT:
        raise ContractError("Extracted agreement text exceeds the prototype limit")
    return {"source_name": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
            "format": suffix[1:], "text": text, "page_count": len(pages),
            "extraction_mode": extraction_mode if suffix == ".pdf" else "text"}
