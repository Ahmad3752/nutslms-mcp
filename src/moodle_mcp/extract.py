"""Turn course files into plain text.

Coursework is routinely published as Office documents rather than as Moodle
activities, so the real instructions and dates live inside these files. Office
formats are ZIP+XML, so the common cases need no third-party dependency; PDF
falls back to pypdf when it is installed.
"""

from __future__ import annotations

import html
import logging
import re
import warnings
import zipfile
from pathlib import Path

TEXTUAL = {".txt", ".md", ".csv", ".json", ".py", ".ipynb", ".html", ".htm"}


def _xml_text(xml: str) -> str:
    """Strip XML tags, keeping paragraph and line breaks as newlines."""
    xml = re.sub(r"</w:p>|</a:p>|<w:br/>|<a:br/>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def from_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        parts = [n for n in z.namelist()
                 if n == "word/document.xml" or n.startswith("word/footnotes")]
        return _tidy("\n".join(_xml_text(z.read(p).decode("utf8", "replace"))
                               for p in parts))


def from_pptx(path: Path) -> str:
    out = []
    with zipfile.ZipFile(path) as z:
        slides = sorted(
            (n for n in z.namelist()
             if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n.split("/")[-1]).group(1)),
        )
        for i, s in enumerate(slides, 1):
            body = _xml_text(z.read(s).decode("utf8", "replace"))
            if body.strip():
                out.append(f"--- Slide {i} ---\n{body.strip()}")
    return _tidy("\n\n".join(out))


def from_xlsx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            raw = z.read("xl/sharedStrings.xml").decode("utf8", "replace")
            shared = [html.unescape(re.sub(r"<[^>]+>", "", m))
                      for m in re.findall(r"<si>(.*?)</si>", raw, re.S)]
        return _tidy("\n".join(shared))


def from_pdf(path: Path) -> str:
    # pypdf is chatty about font quirks it can still read past; those warnings
    # are noise here and would otherwise swamp the caller's output.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from pypdf import PdfReader
    except ImportError:
        return ("[pdf text extraction needs pypdf — install with "
                "`pip install pypdf`]")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = PdfReader(str(path))
            return _tidy("\n\n".join(
                f"--- Page {i} ---\n{(p.extract_text() or '').strip()}"
                for i, p in enumerate(reader.pages, 1)))
    except Exception as e:  # encrypted, malformed, scanned
        return f"[could not read pdf: {e}]"


def from_doc_legacy(path: Path) -> str:
    """Pre-2007 .doc/.ppt are binary; salvage readable ASCII runs."""
    raw = path.read_bytes()
    runs = re.findall(rb"[\x20-\x7e]{6,}", raw)
    text = "\n".join(r.decode("ascii", "ignore") for r in runs)
    return _tidy(text)


def extract(path: Path) -> str:
    """Best-effort plain text for any course file."""
    ext = path.suffix.lower()
    try:
        if ext == ".docx":
            return from_docx(path)
        if ext == ".pptx":
            return from_pptx(path)
        if ext == ".xlsx":
            return from_xlsx(path)
        if ext == ".pdf":
            return from_pdf(path)
        if ext in (".doc", ".ppt", ".xls"):
            return from_doc_legacy(path)
        if ext in TEXTUAL:
            body = path.read_text("utf8", errors="replace")
            if ext in (".html", ".htm"):
                body = _xml_text(body)
            return _tidy(body)
    except zipfile.BadZipFile:
        return from_doc_legacy(path)
    except Exception as e:
        return f"[extraction failed: {e}]"
    return f"[no text extractor for '{ext}' files]"
