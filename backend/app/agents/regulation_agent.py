"""Regulation Agent — what the governing document says, and what it could not read.

The judgement here is twofold, and the second half is the one that matters:

1. Which passages of the regulation bear on this question?
2. **Can the agent actually see the part of the document that governs?**

Most retrieval-augmented systems answer only the first and present the result as complete.
Over this corpus that is unsafe: 54 of 206 pages carry no machine-readable text, including
the entire 23-page statutory instrument governing Transferable Development Rights. A system
that answers a TDR question from the surrounding prose is not wrong about the prose — it is
silently answering a different question than the one asked.

## Extractive by default

With no language model configured, every claim is a **verbatim passage** with its page,
character span and section reference. The agent selects, orders and qualifies evidence; it
writes nothing of its own about what the regulation means. It cannot hallucinate a provision,
because it never composes one.

With a model configured, the same evidence is additionally synthesised into prose — but the
claims still carry their spans, the critic still checks every sentence against retrieved
text, and anything unsupported is demoted. Generation adds readability on top of guarantees
that do not depend on it.

## Numeric provisions get special handling

In a planning regulation the numbers *are* the rule: 75 m, 50/35/25 m, FAR 1.50. Those are
also exactly what the corpus's encoding fault corrupted (``75 m`` extracted as ``7ϱ ŵ``) and
what flattened tables made unattributable. So numeric provisions are extracted explicitly and
carry the quality caveats of the page and table they came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.epistemics import (
    AnyStatement,
    Assumption,
    Confidence,
    DocumentLocator,
    Fact,
    Inference,
    Recommendation,
    Source,
    SourceKind,
)
from app.ingest.retriever import BlindSpot, RegulationIndex, RetrievalResult
from app.providers.llm import LLMMode, LLMProvider, get_llm

AGENT = "regulation"

# Measurements and ratios that constitute a regulatory limit.
_MEASURE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(m\b|metre|meter|sqm|sq\.?\s?m|%|ha\b)", re.IGNORECASE
)


@dataclass
class NumericProvision:
    """A number that carries regulatory force, with its reliability attached."""

    value: float
    unit: str
    context: str
    page_number: int
    section: str | None
    from_repaired_text: bool
    from_risky_table: bool

    @property
    def is_reliable(self) -> bool:
        return not (self.from_repaired_text or self.from_risky_table)

    @property
    def caveat(self) -> str | None:
        if self.from_risky_table:
            return (
                "Read from a table whose column structure was lost in extraction — this "
                "value may belong to a different column than it appears to."
            )
        if self.from_repaired_text:
            return (
                "Read from text that was mis-encoded and repaired. The digits were "
                "reconstructed; confirm against the source page."
            )
        return None


@dataclass
class RegulationReading:
    """What the document said, and what remained unread."""

    question: str
    mode: LLMMode

    claims: list[Fact] = field(default_factory=list)
    interpretations: list[Inference] = field(default_factory=list)
    gaps: list[Assumption] = field(default_factory=list)
    verifications: list[Recommendation] = field(default_factory=list)

    numeric_provisions: list[NumericProvision] = field(default_factory=list)
    retrieval: RetrievalResult | None = None
    synthesis: str | None = None
    """Generated prose. None in extractive mode — never a fabricated stand-in."""

    @property
    def statements(self) -> list[AnyStatement]:
        return [*self.claims, *self.interpretations, *self.gaps, *self.verifications]

    @property
    def blind_spots(self) -> list[BlindSpot]:
        return self.retrieval.relevant_blind_spots if self.retrieval else []

    @property
    def has_evidence(self) -> bool:
        return bool(self.claims)

    @property
    def evidence_is_complete(self) -> bool:
        """False when relevant regions of the document could not be read."""
        return not self.blind_spots

    @property
    def has_table_risk(self) -> bool:
        """True when any retrieved passage came from a structurally damaged table.

        Deliberately chunk-level rather than derived from extracted numbers. Keying this to
        numeric provisions missed the case where retrieval surfaces a table's *caption* —
        which names the subject and therefore ranks highly — while the numbers sit in a
        neighbouring chunk. The warning belongs to the table, not to the digits.
        """
        return bool(self.retrieval and self.retrieval.risky_table_hits)


SYNTHESIS_SYSTEM = """You summarise planning-regulation passages for a professional audience.

Rules, without exception:
- Use ONLY the numbered passages provided. Introduce no provision, number or requirement \
that is not in them.
- Cite every statement as [n], matching the passage numbers given.
- Where passages carry a reliability caveat, repeat that caveat in the sentence that uses \
the value. Do not quietly drop it.
- If the passages do not answer the question, say so plainly and stop. Do not assemble a \
plausible answer from adjacent material.
- Never state or imply compliance. This is a draft document and interpretation is a \
licensed professional activity.
- Do not soften or omit a restriction to make an answer more useful."""


class RegulationAgent:
    """Grounded retrieval over a regulation, with blind spots reported as results."""

    def __init__(self, index: RegulationIndex, llm: LLMProvider | None = None) -> None:
        self.index = index
        self.llm = llm or get_llm()

    async def run(self, question: str, *, top_k: int = 6) -> RegulationReading:
        mode = LLMMode.GENERATIVE if self.llm.available else LLMMode.EXTRACTIVE
        reading = RegulationReading(question=question, mode=mode)

        result = self.index.search(question, top_k=top_k)
        reading.retrieval = result

        self._record_blind_spots(reading, result)

        if not result.has_usable_evidence:
            reading.gaps.append(
                Assumption(
                    text=(
                        "No passage in the indexed regulation matched this question. This "
                        "does not mean the regulation is silent — the governing provision "
                        "may be on a page that could not be read, or phrased in terms the "
                        "search did not match."
                    ),
                    falsified_by="Rephrasing using the document's own terminology, or consulting the source directly.",
                    why_needed="Lexical retrieval found no matching passage.",
                    agent=AGENT,
                )
            )
            return reading

        self._record_claims(reading, result)
        self._record_numeric_provisions(reading, result)

        if mode is LLMMode.GENERATIVE:
            await self._synthesise(reading, result)

        return reading

    # ------------------------------------------------------------------- claims

    def _record_claims(self, reading: RegulationReading, result: RetrievalResult) -> None:
        for hit in result.readable_hits:
            chunk = hit.chunk
            quote = " ".join(chunk.text.split())

            caveat_parts = list(chunk.caveats)
            locator = DocumentLocator(
                document_id=chunk.document_id,
                document_title="RMP 2031 (Draft) Vol. 6 — Zoning Regulations",
                page_number=chunk.page_number,
                char_start=chunk.char_start,
                char_end=max(chunk.char_end, chunk.char_start + 1),
                quote=quote,
                text_was_repaired=chunk.text_was_repaired,
                page_quality=chunk.page_quality.value,
                caveat=" ".join(caveat_parts) if caveat_parts else None,
            )

            # The claim IS the passage. In extractive mode this is the entire mechanism:
            # nothing is asserted that is not quoted, so there is nothing to hallucinate.
            reading.claims.append(
                Fact(
                    text=quote,
                    source=Source(kind=SourceKind.DOCUMENT, document=locator),
                    agent=AGENT,
                )
            )

    def _record_numeric_provisions(
        self, reading: RegulationReading, result: RetrievalResult
    ) -> None:
        for hit in result.readable_hits:
            chunk = hit.chunk
            risky = chunk.table_risk in ("ambiguous_columns", "severe")
            text = " ".join(chunk.text.split())

            for match in _MEASURE.finditer(text):
                start = max(0, match.start() - 110)
                end = min(len(text), match.end() + 110)
                reading.numeric_provisions.append(
                    NumericProvision(
                        value=float(match.group(1)),
                        unit=match.group(2).lower().replace(".", "").replace(" ", ""),
                        context=text[start:end],
                        page_number=chunk.page_number,
                        section=chunk.section_number,
                        from_repaired_text=chunk.text_was_repaired,
                        from_risky_table=risky,
                    )
                )

        # A damaged table warrants a verification task even when no number was extracted
        # from the retrieved chunk — the reader is being shown a table whose columns cannot
        # be trusted, and that is true whether or not this particular passage holds digits.
        if reading.has_table_risk:
            risky_pages = sorted(
                {h.chunk.page_number for h in (reading.retrieval.risky_table_hits)}
            )
            captions = sorted(
                {
                    h.chunk.table_caption
                    for h in reading.retrieval.risky_table_hits
                    if h.chunk.table_caption
                }
            )
            reading.gaps.append(
                Assumption(
                    text=(
                        "Evidence here includes a table whose column structure was lost "
                        "during text extraction"
                        + (f" ({'; '.join(c[:60] for c in captions[:2])})" if captions else "")
                        + ". Values in it cannot be reliably attributed to a column."
                    ),
                    falsified_by=(
                        f"Reading the table on {', '.join(f'p. {p}' for p in risky_pages)} "
                        f"directly in the source PDF."
                    ),
                    why_needed=(
                        "A PDF table is a visual grid; extraction flattens it to a stream "
                        "and blank cells become unattributable."
                    ),
                    agent=AGENT,
                )
            )
            reading.verifications.append(
                Recommendation(
                    text=(
                        f"Read the table(s) on "
                        f"{', '.join(f'p. {p}' for p in risky_pages)} in the source PDF "
                        f"before relying on any figure from them."
                    ),
                    responds_to="table column structure lost in extraction",
                    priority=1,
                    who="whoever is relying on the figure",
                    agent=AGENT,
                )
            )

        # Surface unreliable numbers as an explicit verification task rather than letting a
        # caveat sit quietly beside a value the reader has already copied down.
        unreliable = [p for p in reading.numeric_provisions if not p.is_reliable]
        if unreliable:
            pages = sorted({p.page_number for p in unreliable})
            reading.verifications.append(
                Recommendation(
                    text=(
                        f"Confirm {len(unreliable)} numeric value(s) against the source pages "
                        f"({', '.join(f'p. {p}' for p in pages)}). They were read from "
                        f"repaired text or from tables whose column structure was lost."
                    ),
                    responds_to="numeric provisions extracted from unreliable page regions",
                    priority=1,
                    who="whoever is relying on the figure",
                    agent=AGENT,
                )
            )

    # -------------------------------------------------------------- blind spots

    def _record_blind_spots(self, reading: RegulationReading, result: RetrievalResult) -> None:
        for spot in result.relevant_blind_spots:
            reading.gaps.append(
                Assumption(
                    text=(
                        f"Any answer here excludes {spot.page_count} page(s) "
                        f"({spot.page_start}–{spot.page_end}) that bear on this question but "
                        f"carry no machine-readable text."
                        + (f" That region is introduced as: “{spot.descriptor[:170]}”" if spot.descriptor else "")
                    ),
                    falsified_by=(
                        f"Reading pages {spot.page_start}–{spot.page_end} of the source "
                        f"document directly, or obtaining a text-based version."
                    ),
                    why_needed="These pages are scans or drawings; text extraction returns nothing.",
                    agent=AGENT,
                )
            )
            reading.verifications.append(
                Recommendation(
                    text=(
                        f"Read pages {spot.page_start}–{spot.page_end} of the source document. "
                        f"They could not be parsed and may contain the governing provision."
                    ),
                    responds_to=f"unreadable document region pp. {spot.page_start}–{spot.page_end}",
                    priority=1 if spot.page_count > 5 else 2,
                    who="whoever is relying on this answer",
                    agent=AGENT,
                )
            )

    # --------------------------------------------------------------- synthesis

    async def _synthesise(self, reading: RegulationReading, result: RetrievalResult) -> None:
        """Generate prose from the retrieved passages, with citations required."""
        passages = []
        for i, hit in enumerate(result.readable_hits, start=1):
            chunk = hit.chunk
            caveat = f"\n   RELIABILITY: {' '.join(chunk.caveats)}" if chunk.caveats else ""
            passages.append(
                f"[{i}] ({chunk.citation_label}) {' '.join(chunk.text.split())}{caveat}"
            )

        gap_note = ""
        if reading.blind_spots:
            described = "; ".join(
                f"pp. {s.page_start}-{s.page_end} ({s.descriptor[:90]})"
                for s in reading.blind_spots
            )
            gap_note = (
                f"\n\nIMPORTANT — the following regions of the document bear on this "
                f"question and could NOT be read: {described}. Your answer must state this "
                f"limitation explicitly."
            )

        prompt = (
            f"QUESTION: {reading.question}\n\nPASSAGES:\n"
            + "\n\n".join(passages)
            + gap_note
            + "\n\nAnswer using only these passages, citing [n] for every statement."
        )

        response = await self.llm.complete(
            prompt, system=SYNTHESIS_SYSTEM, max_tokens=1200, temperature=0.0
        )

        if not response.ok:
            # Falling back to extractive is the correct failure mode: the evidence is
            # already complete and citable without prose.
            reading.gaps.append(
                Assumption(
                    text=(
                        "Narrative synthesis was unavailable for this question; the evidence "
                        "below is presented as verbatim passages."
                    ),
                    falsified_by="Re-running with a working model configuration.",
                    why_needed=f"Model call failed: {response.error}",
                    agent=AGENT,
                )
            )
            reading.mode = LLMMode.EXTRACTIVE
            return

        reading.synthesis = response.text.strip()
        reading.interpretations.append(
            Inference(
                text=reading.synthesis,
                derived_from=[c.id for c in reading.claims],
                transformation=(
                    f"Generated summary of {len(reading.claims)} retrieved passages by "
                    f"{response.usage.model}, constrained to cite each statement."
                ),
                confidence=Confidence.MEDIUM if reading.evidence_is_complete else Confidence.LOW,
                confidence_basis=(
                    "Synthesis of retrieved passages; every sentence is checked against "
                    "source text by the critic."
                    + (
                        ""
                        if reading.evidence_is_complete
                        else " Confidence reduced because relevant pages could not be read."
                    )
                ),
                agent=AGENT,
            )
        )
