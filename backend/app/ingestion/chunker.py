"""Structure-aware chunking: split on Markdown/HTML-style '#' headings when
present, falling back to fixed-size word windows with overlap for
unstructured text (e.g. PDF/DOCX bodies with no reliable heading markers).

Chunk size/overlap are in whitespace-delimited words, used as a cheap proxy
for tokens -- fine for a PoC; swap for a real tokenizer if precision matters.
"""
import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)


@dataclass
class Chunk:
    text: str
    section: str | None


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> list[Chunk]:
    text = text.strip()
    if not text:
        return []
    if _HEADING_RE.search(text):
        return _chunk_by_sections(text, chunk_size, overlap)
    return _chunk_by_words(text, None, chunk_size, overlap)


def _chunk_by_sections(text: str, chunk_size: int, overlap: int) -> list[Chunk]:
    matches = list(_HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        sections.append(("", text[: matches[0].start()]))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        heading = m.group().lstrip("#").strip()
        sections.append((heading, text[m.start() : end]))

    chunks: list[Chunk] = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        word_count = len(body.split())
        if word_count <= chunk_size:
            chunks.append(Chunk(text=body, section=heading or None))
        else:
            chunks.extend(_chunk_by_words(body, heading or None, chunk_size, overlap))
    return chunks


def _chunk_by_words(
    text: str, section: str | None, chunk_size: int, overlap: int
) -> list[Chunk]:
    words = text.split()
    if not words:
        return []
    step = max(chunk_size - overlap, 1)
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        if not window:
            break
        chunks.append(Chunk(text=" ".join(window), section=section))
        if start + chunk_size >= len(words):
            break
    return chunks
