"""Parses PDF / DOCX / HTML / Markdown into normalized (text, title) pairs.
Markdown and HTML keep their heading markers in the returned text so the
chunker can split on document structure instead of raw token windows.
"""
from pathlib import Path


class UnsupportedFileType(ValueError):
    pass


def parse_file(path: str | Path) -> tuple[str, str]:
    """Returns (normalized_text, title). `title` falls back to the filename."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _parse_pdf(path)
    elif suffix == ".docx":
        text = _parse_docx(path)
    elif suffix in (".html", ".htm"):
        text = _parse_html(path)
    elif suffix in (".md", ".markdown", ".txt"):
        text = path.read_text(encoding="utf-8")
    else:
        raise UnsupportedFileType(f"Unsupported file type: {suffix}")
    title = _extract_title(text) or path.stem
    return text, title


def _parse_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_docx(path: Path) -> str:
    import docx

    doc = docx.Document(str(path))
    lines = []
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading"):
            level = "".join(ch for ch in style if ch.isdigit()) or "1"
            lines.append(f"{'#' * int(level)} {para.text}")
        else:
            lines.append(para.text)
    return "\n\n".join(lines)


def _parse_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    lines = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = el.get_text(strip=True)
        if not text:
            continue
        if el.name.startswith("h"):
            lines.append(f"{'#' * int(el.name[1])} {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return None
