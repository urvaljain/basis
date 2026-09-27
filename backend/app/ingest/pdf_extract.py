"""Page-level PDF extraction that records what it could *not* read.

Most extraction pipelines answer one question: "give me the text." This one answers three,
because in a high-stakes document the second and third decide whether an answer can be
trusted:

1. What text is on this page?
2. Was this page readable at all, or is it a scan or drawing?
3. Did the text that came out need repairing, and how badly?

The corpus this was built against — Bengaluru RMP 2031 Volume 6, 206 pages — fails in both
ways at once. Roughly a quarter of its pages yield no text (they are scanned dimensional
matrices and land-use drawings), and a further set extract text that is systematically
mis-encoded (see :mod:`app.ingest.text_repair`).

A retrieval system that flattens all of this into one text blob will answer a question about
setbacks from the surrounding prose while the governing table sits invisible two pages away.
It will sound completely confident. That is the failure this module exists to make impossible
to hide: every page carries its own :class:`PageQuality`, and a page that could not be read
is rendered to an image and handed to the user instead of being quietly dropped.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.ingest.text_repair import RepairResult, describe_residual, repair

logger = logging.getLogger(__name__)

# Below this many extracted characters a page is treated as carrying no usable text.
# Scanned pages routinely yield a handful of stray characters from a header stamp or a
# stray vector label, which is not text a citation can rest on. Tuned against the corpus:
# readable body pages there run 1,000-4,000 characters, so the gap is wide and the
# threshold is not delicately balanced.
MIN_TEXT_CHARS = 120

# A page needing more repairs than this per 1,000 characters is flagged as heavily
# corrupted. Repair still applies; the flag travels with any citation drawn from it so a
# reader knows the quotation was reconstructed rather than read.
HEAVY_CORRUPTION_PER_1000 = 4.0

# Rasterisation scale for unreadable pages. 1.6 ≈ 115 dpi — legible for reading a scanned
# clause or a dimensional matrix, at roughly a third of the bytes of 2.0.
#
# Pre-rendering every unreadable page at ingest was the original approach and it was wrong
# twice over: 54 pages at 2.0 consumed 108 MB (and filled the development disk), while in
# practice a reader opens one or two of them. Rendering is now on demand and cached, so the
# cost is paid only for pages someone actually looks at.
RENDER_SCALE = 1.6


class PageQuality(str, Enum):
    """How much a citation from this page can be trusted."""

    CLEAN = "clean"
    """Text extracted and needed no repair."""

    REPAIRED = "repaired"
    """Text extracted but was mis-encoded; repaired, and the raw form is retained."""

    HEAVILY_REPAIRED = "heavily_repaired"
    """Extracted with dense corruption. Usable, but every quote must be shown as repaired."""

    UNREADABLE = "unreadable"
    """No usable text. A scan, drawing or matrix. Rendered to an image for the human."""

    RESIDUAL_CORRUPTION = "residual_corruption"
    """Repaired, but characters remain that the repair map does not recognise.

    Deliberately distinct from HEAVILY_REPAIRED: this means the pipeline met a corruption
    pattern it does not understand, which is a signal to extend the map from evidence
    rather than something to tolerate silently.
    """


@dataclass
class ExtractedPage:
    """One page, with its provenance and its limits attached rather than inferred."""

    page_number: int  # 1-indexed, matching what a reader sees in a PDF viewer
    text: str  # repaired text — what retrieval indexes
    raw_text: str  # exactly what the extractor produced, kept for audit
    quality: PageQuality
    char_count: int
    substitutions: int
    corruption_rate: float
    residual_notes: list[str] = field(default_factory=list)
    image_path: str | None = None  # set for UNREADABLE pages

    @property
    def is_readable(self) -> bool:
        return self.quality is not PageQuality.UNREADABLE

    @property
    def was_transformed(self) -> bool:
        """True when the indexed text differs from what was extracted.

        Any citation from such a page must be presented to the user as repaired, with the
        raw extraction available. Silently quoting reconstructed text as verbatim would be
        the same class of dishonesty this product is built to expose.
        """
        return self.substitutions > 0

    @property
    def citation_caveat(self) -> str | None:
        """Plain-language warning to attach to any quote from this page."""
        match self.quality:
            case PageQuality.UNREADABLE:
                return (
                    "This page contains no machine-readable text. It is a scan or drawing "
                    "and must be read by a person."
                )
            case PageQuality.HEAVILY_REPAIRED:
                return (
                    f"This page was densely mis-encoded ({self.substitutions} characters "
                    "corrected). The quotation is reconstructed, not verbatim."
                )
            case PageQuality.RESIDUAL_CORRUPTION:
                return (
                    "This page contains an encoding fault the pipeline does not fully "
                    "recognise. Treat the quotation as unreliable and check the source."
                )
            case PageQuality.REPAIRED:
                return (
                    f"{self.substitutions} mis-encoded character(s) were corrected on this "
                    "page. Raw extraction available."
                )
            case _:
                return None


@dataclass
class DocumentExtraction:
    """A whole document plus an honest account of how well it was read."""

    source_path: str
    source_sha256: str
    title: str
    page_count: int
    pages: list[ExtractedPage]

    # --- coverage, all measured rather than asserted ---

    @property
    def readable_pages(self) -> list[int]:
        return [p.page_number for p in self.pages if p.is_readable]

    @property
    def unreadable_pages(self) -> list[int]:
        return [p.page_number for p in self.pages if not p.is_readable]

    @property
    def total_chars(self) -> int:
        return sum(p.char_count for p in self.pages)

    @property
    def total_substitutions(self) -> int:
        return sum(p.substitutions for p in self.pages)

    @property
    def text_coverage(self) -> float:
        """Fraction of pages yielding usable text. The headline honesty number."""
        if not self.page_count:
            return 0.0
        return round(len(self.readable_pages) / self.page_count, 4)

    @property
    def pages_needing_repair(self) -> list[int]:
        return [p.page_number for p in self.pages if p.was_transformed]

    @property
    def problem_pages(self) -> list[int]:
        return [
            p.page_number
            for p in self.pages
            if p.quality
            in (
                PageQuality.UNREADABLE,
                PageQuality.HEAVILY_REPAIRED,
                PageQuality.RESIDUAL_CORRUPTION,
            )
        ]

    def page(self, number: int) -> ExtractedPage | None:
        """Fetch by 1-indexed page number."""
        idx = number - 1
        if 0 <= idx < len(self.pages):
            return self.pages[idx]
        return None

    def contiguous_unreadable_ranges(self) -> list[tuple[int, int]]:
        """Collapse unreadable pages into ranges.

        A run of 17 consecutive unreadable pages is a different problem from 17 scattered
        ones — it usually means an entire annexe of tables or drawings is invisible. The UI
        reports ranges because that is what tells a user what is actually missing.
        """
        nums = sorted(self.unreadable_pages)
        if not nums:
            return []
        ranges: list[tuple[int, int]] = []
        start = prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
                continue
            ranges.append((start, prev))
            start = prev = n
        ranges.append((start, prev))
        return ranges

    def coverage_report(self) -> dict[str, object]:
        """Machine-readable ingestion summary. Surfaced in the UI and the eval harness."""
        return {
            "title": self.title,
            "sha256": self.source_sha256,
            "page_count": self.page_count,
            "readable_page_count": len(self.readable_pages),
            "unreadable_page_count": len(self.unreadable_pages),
            "text_coverage": self.text_coverage,
            "total_chars": self.total_chars,
            "total_substitutions": self.total_substitutions,
            "pages_needing_repair": len(self.pages_needing_repair),
            "unreadable_ranges": self.contiguous_unreadable_ranges(),
            "quality_breakdown": {
                q.value: sum(1 for p in self.pages if p.quality is q) for q in PageQuality
            },
        }


def _classify(text: str, repaired: RepairResult) -> PageQuality:
    if len(text.strip()) < MIN_TEXT_CHARS:
        return PageQuality.UNREADABLE
    if not repaired.is_clean:
        return PageQuality.RESIDUAL_CORRUPTION
    if repaired.corruption_rate > HEAVY_CORRUPTION_PER_1000:
        return PageQuality.HEAVILY_REPAIRED
    if repaired.was_repaired:
        return PageQuality.REPAIRED
    return PageQuality.CLEAN


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def render_page_image(pdf_path: Path, page_number: int, out_dir: Path) -> str | None:
    """Rasterise one page so a human can read what the pipeline could not.

    This is what makes the unreadable surface a real feature rather than an apology: the
    user is shown the actual governing table, at the actual page, and told plainly that
    the system cannot parse it.

    Returns a path relative to ``out_dir``'s parent, or None if rendering is unavailable.
    """
    try:
        import pymupdf  # imported lazily: ingestion works without it, minus the images
    except ImportError:
        logger.warning(
            "pymupdf not installed — page %d cannot be rendered. The unreadable-page "
            "surface will show a placeholder instead of the real page.",
            page_number,
        )
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"page-{page_number:04d}.png"
    if out_path.exists():
        return out_path.name

    try:
        with pymupdf.open(str(pdf_path)) as doc:
            page = doc[page_number - 1]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE))
            pix.save(str(out_path))
    except Exception:
        logger.exception("failed to render page %d of %s", page_number, pdf_path)
        return None

    return out_path.name


def extract_document(
    pdf_path: str | Path,
    *,
    title: str | None = None,
    image_dir: str | Path | None = None,
    render_unreadable: bool = True,
) -> DocumentExtraction:
    """Extract a PDF page by page, repairing text and recording every limitation.

    Args:
        pdf_path: the PDF to read.
        title: display title; defaults to the filename stem.
        image_dir: where rasterised unreadable pages are written.
        render_unreadable: set False to skip rasterisation (faster tests).
    """
    import pypdf

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"corpus document not found: {path}")

    reader = pypdf.PdfReader(str(path))
    img_dir = Path(image_dir) if image_dir else path.parent / f"{path.stem}-pages"

    pages: list[ExtractedPage] = []
    for i, raw_page in enumerate(reader.pages, start=1):
        try:
            raw_text = raw_page.extract_text() or ""
        except Exception:
            # One malformed page must not abort a 206-page ingest. It is recorded as
            # unreadable, which is exactly what it is from the reader's point of view.
            logger.exception("text extraction failed on page %d", i)
            raw_text = ""

        fixed = repair(raw_text)
        quality = _classify(raw_text, fixed)

        # An unreadable page always advertises an image; the file itself is rendered on
        # first request. ``render_unreadable=True`` pre-renders eagerly, which only the
        # fixture-capture path wants.
        image_name: str | None = None
        if quality is PageQuality.UNREADABLE:
            image_name = (
                render_page_image(path, i, img_dir)
                if render_unreadable
                else f"page-{i:04d}.png"
            )

        pages.append(
            ExtractedPage(
                page_number=i,
                text=fixed.repaired,
                raw_text=raw_text,
                quality=quality,
                char_count=len(fixed.repaired.strip()),
                substitutions=fixed.substitutions,
                corruption_rate=fixed.corruption_rate,
                residual_notes=describe_residual(fixed.residual_suspect_chars),
                image_path=image_name,
            )
        )

    doc = DocumentExtraction(
        source_path=str(path),
        source_sha256=_sha256(path),
        title=title or path.stem.replace("-", " "),
        page_count=len(pages),
        pages=pages,
    )

    logger.info(
        "extracted %s: %d pages, %.1f%% text coverage, %d unreadable, %d substitutions",
        doc.title,
        doc.page_count,
        doc.text_coverage * 100,
        len(doc.unreadable_pages),
        doc.total_substitutions,
    )
    return doc
