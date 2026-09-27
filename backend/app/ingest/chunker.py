"""Split a regulatory document into citable units.

## Why not fixed-size chunks

The default approach — 512 tokens with 50 tokens of overlap — is wrong for this document,
and wrong in a way that damages citations specifically.

A planning regulation is not prose. It is a hierarchy of numbered provisions::

    6.5.3 Regulations for Eco-sensitive Zones and Water Bodies including Valley/ Streams
      i.   Restrictions imposed by Competent Authorities ...
      ii.  The buffer for Water bodies ... a 75 m buffer of 'no development zone' ...
      iii. The Streams have been categorized into 3 types ... 50, 35 and 25 m ...

Each numbered item is a self-contained rule. Cutting between ``ii.`` and its measurement, or
merging ``ii.`` and ``iii.`` into one blob, produces a citation that points at a span the
claim cannot actually be read out of. A user who clicks through to check finds either half a
rule or two rules jumbled together, and the checkability that justifies the whole design is
gone.

So chunking follows the document's own structure: section headings and enumerated clauses
are boundaries. Where a clause is very long it is split on sentence boundaries, never
mid-sentence.

## Offsets are sacred

Every chunk records its exact character span within its page. Those offsets are what let a
citation resolve to a highlighted passage in the viewer. :mod:`app.ingest.text_repair`
guarantees offsets survive repair (it is a pure character translation), so a span computed
here is valid against both the repaired and the raw text — which is what allows the UI to
show a user the original extraction alongside the repaired quote.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingest.pdf_extract import DocumentExtraction, ExtractedPage, PageQuality
from app.ingest.table_risk import TableRegion, analyse_page

# A numbered section heading: "6.5.3 Regulations for ...", "4.16 Tree Planting".
_SECTION = re.compile(r"^\s*(\d+(?:\.\d+){1,3})\s+([A-Z][^\n]{3,120})$", re.MULTILINE)

# An enumerated clause: "i.", "ii.", "(a)", "1.", "vii."  — the atoms of a regulation.
_CLAUSE = re.compile(
    r"(?m)^\s*(?:"
    r"(?P<roman>(?=[ivxlcdm])[ivxlcdm]{1,7})\.|"
    r"\((?P<paren_alpha>[a-z])\)|"
    r"(?P<arabic>\d{1,2})\.(?!\d)"
    r")\s+"
)

# A table caption line: "Table 8: FAR & Ground coverage for Residential Development Plan".
_TABLE_CAPTION_LINE = re.compile(r"^.*\bTable\s+\d+\s*:.*$", re.MULTILINE)

# Sentence boundary for splitting over-long clauses. Avoids breaking on "6.5.3" or "1.50".
_SENTENCE = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")

MAX_CHUNK_CHARS = 1400
"""Above this a clause is split on sentence boundaries. Chosen so a chunk stays readable in
an evidence panel without scrolling — the citation has to be inspectable at a glance."""

MIN_CHUNK_CHARS = 60
"""Below this a fragment is merged forward. Page headers and stray numbers are not citable
units and only add retrieval noise."""

# Running header repeated on almost every page. Stripped from chunk text but *not* from the
# page text, so character offsets stay aligned with the source.
_RUNNING_HEADER = re.compile(
    r"Revised Master Plan for Bengaluru\s*-\s*2031\s*\(Draft\)\s*", re.IGNORECASE
)


@dataclass
class Chunk:
    """One citable unit of a document."""

    chunk_id: str
    document_id: str
    page_number: int
    char_start: int
    char_end: int
    text: str

    section_number: str | None = None
    section_title: str | None = None
    clause_marker: str | None = None

    # Provenance carried from the page, so a citation never loses its caveats.
    page_quality: PageQuality = PageQuality.CLEAN
    text_was_repaired: bool = False
    table_risk: str | None = None
    table_caption: str | None = None
    caveats: list[str] = field(default_factory=list)

    @property
    def citation_label(self) -> str:
        bits = []
        if self.section_number:
            bits.append(f"§{self.section_number}")
        if self.clause_marker:
            bits.append(f"({self.clause_marker})")
        bits.append(f"p. {self.page_number}")
        return " ".join(bits)

    @property
    def is_safe_to_quote_verbatim(self) -> bool:
        """False when the text was reconstructed or its table structure was damaged."""
        return not self.text_was_repaired and self.table_risk in (None, "none", "low")


def _strip_header(text: str) -> str:
    return _RUNNING_HEADER.sub("", text)


def _section_map(page_text: str) -> list[tuple[int, str, str]]:
    """Section headings on a page, as (offset, number, title)."""
    return [(m.start(), m.group(1), m.group(2).strip()) for m in _SECTION.finditer(page_text)]


def _section_at(sections: list[tuple[int, str, str]], offset: int) -> tuple[str | None, str | None]:
    """The most recent heading at or before this offset."""
    current: tuple[str | None, str | None] = (None, None)
    for pos, number, title in sections:
        if pos <= offset:
            current = (number, title)
        else:
            break
    return current


def _hard_split(text: str, base_offset: int) -> list[tuple[int, str]]:
    """Last-resort split on whitespace for text with no sentence boundaries.

    Table bodies are the case that needs this: a flattened table is one long run of values
    with no full stops, so sentence splitting cannot reduce it. Breaking on whitespace at
    least keeps a chunk inspectable, and the table-risk caveat already warns the reader that
    the structure is unreliable.
    """
    out: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_CHARS, len(text))
        if end < len(text):
            space = text.rfind(" ", start + MAX_CHUNK_CHARS // 2, end)
            if space > start:
                end = space
        out.append((base_offset + start, text[start:end].strip()))
        start = end
    return [(o, t) for o, t in out if t]


def _split_long(text: str, base_offset: int) -> list[tuple[int, str]]:
    """Split over-long text on sentence boundaries, returning (offset, text).

    Falls back to a whitespace split for any piece that sentence boundaries could not
    reduce, so ``MAX_CHUNK_CHARS`` is a guarantee rather than an aspiration. Tail fragments
    below ``MIN_CHUNK_CHARS`` are merged back into the previous piece rather than emitted as
    their own chunk — a 13-character chunk is retrieval noise, not a citable unit.
    """
    if len(text) <= MAX_CHUNK_CHARS:
        return [(base_offset, text)]

    pieces: list[tuple[int, str]] = []
    cursor = 0
    buf_start = 0
    buf: list[str] = []

    for part in _SENTENCE.split(text):
        if buf and sum(len(b) + 1 for b in buf) + len(part) > MAX_CHUNK_CHARS:
            pieces.append((base_offset + buf_start, " ".join(buf)))
            buf = []
            buf_start = cursor
        if not buf:
            buf_start = cursor
        buf.append(part)
        cursor += len(part) + 1

    if buf:
        pieces.append((base_offset + buf_start, " ".join(buf)))

    # Enforce the cap even where no sentence boundary existed.
    expanded: list[tuple[int, str]] = []
    for offset, piece in pieces:
        if len(piece) > MAX_CHUNK_CHARS:
            expanded.extend(_hard_split(piece, offset))
        else:
            expanded.append((offset, piece))

    # Merge undersized tails backwards.
    merged: list[tuple[int, str]] = []
    for offset, piece in expanded:
        if merged and len(piece) < MIN_CHUNK_CHARS:
            prev_offset, prev_text = merged[-1]
            merged[-1] = (prev_offset, f"{prev_text} {piece}".strip())
        else:
            merged.append((offset, piece))
    return merged


def chunk_page(
    page: ExtractedPage,
    document_id: str,
    tables: list[TableRegion] | None = None,
) -> list[Chunk]:
    """Split one page into clause-level chunks with exact spans.

    Unreadable pages yield a single placeholder chunk rather than nothing. That is
    deliberate: retrieval must be able to *find* a blind spot in order to report it. A page
    silently absent from the index is a page the system cannot tell you it is missing.
    """
    if not page.is_readable:
        return [
            Chunk(
                chunk_id=f"{document_id}:p{page.page_number}:unreadable",
                document_id=document_id,
                page_number=page.page_number,
                char_start=0,
                char_end=max(len(page.raw_text), 1),
                text=(
                    f"[Page {page.page_number} contains no machine-readable text. "
                    f"It is a scan or drawing and has been rendered as an image.]"
                ),
                page_quality=page.quality,
                caveats=[page.citation_caveat] if page.citation_caveat else [],
            )
        ]

    text = page.text
    sections = _section_map(text)
    tables = tables if tables is not None else analyse_page(text)

    # Line-based region bounds → character bounds, computed once.
    _line_starts = [0]
    for _line in text.splitlines(keepends=True):
        _line_starts.append(_line_starts[-1] + len(_line))

    def _region_span(region: TableRegion) -> tuple[int, int]:
        start = _line_starts[min(region.start_line, len(_line_starts) - 1)]
        end = _line_starts[min(region.end_line + 1, len(_line_starts) - 1)]
        return start, end

    def table_for(chunk_start: int, chunk_end: int) -> TableRegion | None:
        """Find a table region this chunk *overlaps*.

        Overlap, not containment. Testing only whether the chunk's start offset falls
        inside the region missed the chunk holding the table's caption — which begins
        before the region's first data line and is the chunk most likely to be retrieved
        for a question about that table. The warning was therefore absent from precisely
        the passage a user would see. Found by a test asserting the FAR query surfaces the
        structural-damage flag.
        """
        for region in tables:
            r_start, r_end = _region_span(region)
            if chunk_start < r_end and chunk_end > r_start:
                return region
        return None

    # Clause markers are the primary boundaries; section headings and table captions also
    # split.
    #
    # Table captions get their own boundary because of a measured retrieval failure: a
    # whole flattened table extracts as one ~1400-character chunk, and BM25 length
    # normalisation then buries it beneath short definition clauses. "What FAR applies to a
    # residential development plan?" could not reach Table 8 on page 65 at all, even though
    # the caption names every term in the question. Splitting the caption from the body
    # gives the table a short, highly matchable heading that still carries the body's
    # structural-damage warning.
    boundaries = sorted(
        {0}
        | {m.start() for m in _CLAUSE.finditer(text)}
        | {pos for pos, _, _ in sections}
        | {m.start() for m in _TABLE_CAPTION_LINE.finditer(text)}
        | {m.end() for m in _TABLE_CAPTION_LINE.finditer(text)}
        | {len(text)}
    )

    chunks: list[Chunk] = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        raw_segment = text[start:end]
        cleaned = _strip_header(raw_segment).strip()
        if len(cleaned) < MIN_CHUNK_CHARS:
            continue

        marker_match = _CLAUSE.match(raw_segment)
        marker = None
        if marker_match:
            marker = (
                marker_match.group("roman")
                or marker_match.group("paren_alpha")
                or marker_match.group("arabic")
            )

        section_number, section_title = _section_at(sections, start)

        for offset, piece in _split_long(cleaned, start):
            region = table_for(offset, offset + len(piece))
            caveats: list[str] = []
            if page.citation_caveat:
                caveats.append(page.citation_caveat)
            if region and region.citation_warning():
                caveats.append(region.citation_warning())

            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}:p{page.page_number}:{offset}",
                    document_id=document_id,
                    page_number=page.page_number,
                    char_start=offset,
                    char_end=min(offset + len(piece), len(text)),
                    text=piece,
                    section_number=section_number,
                    section_title=section_title,
                    clause_marker=marker,
                    page_quality=page.quality,
                    text_was_repaired=page.was_transformed,
                    table_risk=region.risk.value if region else None,
                    table_caption=region.caption if region else None,
                    caveats=caveats,
                )
            )

    return chunks


def chunk_document(doc: DocumentExtraction, document_id: str) -> list[Chunk]:
    """Chunk a whole document, preserving unreadable pages as findable placeholders."""
    out: list[Chunk] = []
    for page in doc.pages:
        out.extend(chunk_page(page, document_id))
    return out
