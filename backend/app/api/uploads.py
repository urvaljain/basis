"""User-uploaded documents, processed by the identical pipeline.

A planning report, a geotechnical survey, a tender document or an EIA gets exactly the same
treatment as the bundled corpus: page-quality classification, encoding repair with the raw
text retained, table-structure risk detection, clause-aware chunking and passage-level
citation.

That is the point. **The three failure modes are properties of PDFs, not of one document.**
Any real project PDF can contain scanned annexes, a font encoding that corrupts digits, and
tables whose columns vanish on extraction — and a reader has no way to know which, because
all three look identical from the outside: a file that opened fine.

So an upload returns an honest ingestion report *before* it answers anything. A user who
learns that 40% of the report they just uploaded is unreadable has learned something
valuable about their own document, whether or not they ask it a question afterwards.

## Scope and storage

Documents live in memory for the life of the process, keyed by a random id, and are
deletable. There is no authentication in this slice (`docs/08-non-goals.md` §10), so
confidentiality is explicitly **not** solved — a limitation stated plainly rather than
implied. Anything genuinely sensitive should not be uploaded to a prototype.
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ingest.chunker import chunk_document
from app.ingest.pdf_extract import DocumentExtraction, extract_document
from app.ingest.retriever import RegulationIndex
from app.ingest.table_risk import analyse_page

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_DOCUMENTS = 8
"""Prototype guard rails. Both are stated in the error message rather than silently applied."""


@dataclass
class UploadedDocument:
    id: str
    filename: str
    uploaded_at: datetime
    extraction: DocumentExtraction
    index: RegulationIndex
    chunk_count: int
    risky_tables: list[dict[str, Any]] = field(default_factory=list)
    stored_path: Path | None = None

    def report(self) -> dict[str, Any]:
        """The ingestion report — what could and could not be read.

        Returned before any question is answered, because it is the most useful thing the
        system knows about a document it has just met.
        """
        coverage = self.extraction.coverage_report()
        unreadable = self.extraction.contiguous_unreadable_ranges()

        headline: list[str] = []
        if coverage["unreadable_page_count"]:
            biggest = max(unreadable, key=lambda r: r[1] - r[0], default=None)
            span = f"pp. {biggest[0]}–{biggest[1]}" if biggest else ""
            headline.append(
                f"{coverage['unreadable_page_count']} of {coverage['page_count']} pages "
                f"carry no machine-readable text"
                + (f" (largest run {span})" if biggest and biggest[1] > biggest[0] else "")
                + ". Nothing in them is searchable."
            )
        if coverage["total_substitutions"]:
            headline.append(
                f"{coverage['total_substitutions']} characters across "
                f"{coverage['pages_needing_repair']} pages were mis-encoded and repaired. "
                f"Quotes from those pages are reconstructed, not verbatim."
            )
        if self.risky_tables:
            pages = sorted({t["page"] for t in self.risky_tables})
            headline.append(
                f"{len(self.risky_tables)} table(s) on "
                f"{', '.join(f'p. {p}' for p in pages[:5])} lost their column structure "
                f"during extraction. Values in them cannot be reliably attributed to a "
                f"column — and no coverage metric catches this."
            )
        if not headline:
            headline.append(
                "No unreadable pages, encoding faults or damaged tables were detected. "
                "That is unusual for a real planning document and worth a spot check."
            )

        return {
            "id": self.id,
            "filename": self.filename,
            "uploaded_at": self.uploaded_at.isoformat(),
            "sha256": self.extraction.source_sha256,
            "page_count": coverage["page_count"],
            "readable_page_count": coverage["readable_page_count"],
            "unreadable_page_count": coverage["unreadable_page_count"],
            "text_coverage": coverage["text_coverage"],
            "total_chars": coverage["total_chars"],
            "total_substitutions": coverage["total_substitutions"],
            "pages_needing_repair": coverage["pages_needing_repair"],
            "unreadable_ranges": [list(r) for r in unreadable],
            "quality_breakdown": coverage["quality_breakdown"],
            "chunk_count": self.chunk_count,
            "risky_tables": self.risky_tables,
            "findings": headline,
        }


class DocumentStore:
    """In-memory store for uploaded documents."""

    def __init__(self) -> None:
        self._documents: dict[str, UploadedDocument] = {}

    def add(self, filename: str, data: bytes) -> UploadedDocument:
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(
                f"File is {len(data) / 1e6:.1f} MB; this prototype accepts up to "
                f"{MAX_UPLOAD_BYTES / 1e6:.0f} MB."
            )
        if len(self._documents) >= MAX_DOCUMENTS:
            raise ValueError(
                f"This prototype holds at most {MAX_DOCUMENTS} documents at a time. "
                f"Remove one before adding another."
            )
        if not data.startswith(b"%PDF"):
            raise ValueError(
                "That file is not a PDF. Basis reads PDFs because that is how planning "
                "documents are published."
            )

        document_id = f"doc_{uuid.uuid4().hex[:10]}"
        # Written to a temp file because the extractors work on paths, and page
        # rasterisation needs the original bytes on disk to render an unreadable page.
        temp_dir = Path(tempfile.gettempdir()) / "basis-uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        stored = temp_dir / f"{document_id}.pdf"
        stored.write_bytes(data)

        extraction = extract_document(
            stored,
            title=filename,
            image_dir=temp_dir / f"{document_id}-pages",
            render_unreadable=False,
        )
        chunks = chunk_document(extraction, document_id)

        risky = []
        for page in extraction.pages:
            if not page.is_readable:
                continue
            for region in analyse_page(page.text):
                if region.is_risky:
                    risky.append(
                        {
                            "page": page.page_number,
                            "caption": region.caption,
                            "risk": region.risk.value,
                            "explanation": region.explanation,
                        }
                    )

        document = UploadedDocument(
            id=document_id,
            filename=filename,
            uploaded_at=datetime.now(timezone.utc),
            extraction=extraction,
            index=RegulationIndex(chunks),
            chunk_count=len(chunks),
            risky_tables=risky,
            stored_path=stored,
        )
        self._documents[document_id] = document
        logger.info(
            "ingested upload %s (%s): %d pages, %.1f%% coverage, %d risky tables",
            document_id,
            filename,
            extraction.page_count,
            extraction.text_coverage * 100,
            len(risky),
        )
        return document

    def get(self, document_id: str) -> UploadedDocument | None:
        return self._documents.get(document_id)

    def list(self) -> list[UploadedDocument]:
        return sorted(self._documents.values(), key=lambda d: d.uploaded_at, reverse=True)

    def remove(self, document_id: str) -> bool:
        document = self._documents.pop(document_id, None)
        if document is None:
            return False
        if document.stored_path and document.stored_path.exists():
            try:
                document.stored_path.unlink()
            except OSError:
                logger.warning("could not delete %s", document.stored_path)
        return True


STORE = DocumentStore()
