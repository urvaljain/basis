"""Conflict Agent — holds measurement and regulation against each other.

This is the agent that makes Basis a decision aid rather than a report, and it is the one
absent from the original brief.

A site analysis that returns *"Outer Ring Road 216 m away, hospital 108 m away, 193 mapped
features"* is accurate and encouraging. A regulation summary that returns *"a 75 m
no-development buffer applies around water bodies"* is accurate and alarming. Delivered
separately, each is misleading. The decision lives in the tension between them.

## The conflict that matters most here is not "A contradicts B"

It is **"the number you would naturally compute is not the number the regulation uses."**

The measured distance to the nearest mapped stream at the reference site is 153 m. The
regulation's stream buffers are 50, 35 and 25 m. The obvious inference — 153 > 50, therefore
clear — is invalid, for three separate reasons the system can name precisely:

* the regulation's buffer depends on whether the stream is Primary, Secondary or Tertiary
  under the NGT Order, and OpenStreetMap does not record that classification;
* for water bodies the buffer is measured from the lake boundary *as per revenue records*,
  which are not open data, while OSM geometry is a contributor's tracing;
* the valley-system overlay is "marked on the proposed land use plans" — drawings that are
  among the unreadable pages of the corpus.

So the honest output is not *"you are clear"* nor *"you are affected"*. It is: **this
comparison cannot be made with available data, here is exactly why, and here is who holds
the answer.** Most conflicts in this domain are of that shape — unresolvable with open data —
and a system that resolves them anyway is inventing the resolution.

No LLM is required. Conflict detection is rule-based over typed statements, which makes it
reproducible and testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from app.agents.regulation_agent import RegulationReading
from app.agents.site_agent import SiteReading
from app.domain.epistemics import (
    AnyStatement,
    Assumption,
    Confidence,
    Inference,
    Recommendation,
)

AGENT = "conflict"

# Regulatory buffer language. Matched against retrieved passages to detect that a
# proximity-triggered provision is in play.
_BUFFER_LANGUAGE = re.compile(
    r"\bbuffer\b|\bno development zone\b|eco[- ]sensitive|setback from|from the edge",
    re.IGNORECASE,
)
_WATER_LANGUAGE = re.compile(
    r"\blake|water bod|\bstream|\bdrain|valley|\braja\b|\bhalla\b|watercourse", re.IGNORECASE
)


class ConflictKind(str, Enum):
    CONTEXT_VS_REGULATION = "context_vs_regulation"
    """A measured property meets a provision that turns on that property."""

    SOURCE_VS_SOURCE = "source_vs_source"
    """Two pieces of evidence disagree, or a value is internally unreliable."""

    EVIDENCE_VS_ABSENCE = "evidence_vs_absence"
    """The decisive factor is precisely what could not be established."""


class Resolvability(str, Enum):
    RESOLVED = "resolved"
    RESOLVABLE = "resolvable"
    """Could be settled with data the user can obtain."""

    UNRESOLVABLE_WITH_OPEN_DATA = "unresolvable_with_open_data"
    """Cannot be settled from anything public. The common case."""


@dataclass
class Conflict:
    """A tension between two things that are each true."""

    kind: ConflictKind
    title: str
    measured_side: str
    regulatory_side: str
    why_it_matters: str
    resolvability: Resolvability
    blocking_reasons: list[str] = field(default_factory=list)
    """Specific reasons the two sides cannot be compared. Each one is separately checkable."""

    what_would_resolve_it: list[str] = field(default_factory=list)
    related_statement_ids: list[str] = field(default_factory=list)
    severity: int = 3  # 1 highest

    @property
    def is_decisive(self) -> bool:
        return self.severity <= 2

    def summary(self) -> str:
        return f"{self.title} — {self.why_it_matters}"


@dataclass
class ConflictReading:
    conflicts: list[Conflict] = field(default_factory=list)
    statements: list[AnyStatement] = field(default_factory=list)

    @property
    def decisive(self) -> list[Conflict]:
        return [c for c in self.conflicts if c.is_decisive]

    @property
    def unresolvable(self) -> list[Conflict]:
        return [
            c
            for c in self.conflicts
            if c.resolvability is Resolvability.UNRESOLVABLE_WITH_OPEN_DATA
        ]


class ConflictAgent:
    """Rule-based detection of tension between site measurement and regulation."""

    def run(self, site: SiteReading, regulation: RegulationReading) -> ConflictReading:
        reading = ConflictReading()

        self._water_proximity_vs_buffer(reading, site, regulation)
        self._unreliable_numbers(reading, regulation)
        self._blind_spot_conflicts(reading, regulation)
        self._absent_structured_data(reading, site, regulation)

        reading.conflicts.sort(key=lambda c: c.severity)
        return reading

    # ------------------------------------------- the central, domain-specific rule

    def _water_proximity_vs_buffer(
        self, reading: ConflictReading, site: SiteReading, regulation: RegulationReading
    ) -> None:
        if site.osm is None:
            return

        buffer_hits = [
            c
            for c in regulation.claims
            if _BUFFER_LANGUAGE.search(c.text) and _WATER_LANGUAGE.search(c.text)
        ]
        if not buffer_hits:
            return

        nearest_water = site.osm.nearest("water")
        nearest_stream = site.osm.nearest("stream")
        if nearest_water is None and nearest_stream is None:
            return

        measured_parts = []
        if nearest_stream:
            measured_parts.append(
                f"nearest mapped watercourse ({nearest_stream.label}) at "
                f"{nearest_stream.distance_m:.0f} m"
            )
        if nearest_water:
            measured_parts.append(
                f"nearest mapped water body ({nearest_water.label}) at "
                f"{nearest_water.distance_m:.0f} m"
            )

        buffers = sorted(
            {
                p.value
                for p in regulation.numeric_provisions
                if p.unit == "m" and _BUFFER_LANGUAGE.search(p.context)
            }
        )
        buffer_text = (
            f"buffers of {', '.join(f'{b:g} m' for b in buffers)} appear in the retrieved provisions"
            if buffers
            else "buffer provisions apply"
        )

        reading.conflicts.append(
            Conflict(
                kind=ConflictKind.CONTEXT_VS_REGULATION,
                title="Measured distance to water cannot be compared with the regulatory buffer",
                measured_side=(
                    "OpenStreetMap places the " + " and the ".join(measured_parts) + "."
                ),
                regulatory_side=(
                    f"RMP 2031 §6.5.3 imposes no-development buffers around water bodies and "
                    f"watercourses; {buffer_text}."
                ),
                why_it_matters=(
                    "If the site falls inside a buffer, development is not merely restricted "
                    "but largely prohibited — the permitted uses are treatment plants and "
                    "non-obstructing infrastructure. That is a different order of constraint "
                    "from a reduction in permissible floor area."
                ),
                resolvability=Resolvability.UNRESOLVABLE_WITH_OPEN_DATA,
                blocking_reasons=[
                    "The applicable buffer depends on whether the watercourse is Primary, "
                    "Secondary or Tertiary under the NGT Order (50 / 35 / 25 m). "
                    "OpenStreetMap does not record that classification.",
                    "For water bodies the buffer is measured from the lake boundary as per "
                    "revenue records. Those are not open data, and the OpenStreetMap polygon "
                    "is a contributor's tracing, not the regulatory boundary.",
                    "Valley-system extents are marked on the proposed land use plans, which "
                    "are drawings among the pages of this document that carry no "
                    "machine-readable text.",
                    "Straight-line distance to a feature's representative point is not the "
                    "distance from the plot boundary to the watercourse edge.",
                ],
                what_would_resolve_it=[
                    "The RMP 2031 Planning District sheet covering this survey number, "
                    "showing the mapped valley/buffer overlay.",
                    "The revenue record defining the lake boundary.",
                    "The NGT classification of the specific watercourse.",
                    "A surveyed plot boundary rather than an area centroid.",
                ],
                related_statement_ids=[c.id for c in buffer_hits[:3]],
                severity=1,
            )
        )

        reading.statements.append(
            Assumption(
                text=(
                    "Whether this site falls within a regulated water buffer has not been "
                    "established. Distances measured here do not answer that question."
                ),
                falsified_by=(
                    "The RMP 2031 Planning District sheet for this survey number, read "
                    "against a surveyed plot boundary."
                ),
                why_needed=(
                    "Buffer applicability depends on data that is not open: watercourse "
                    "classification, revenue-record lake boundaries and master-plan overlays."
                ),
                agent=AGENT,
            )
        )
        reading.statements.append(
            Recommendation(
                text=(
                    "Obtain the RMP 2031 Planning District sheet covering this location and "
                    "confirm the mapped valley/buffer overlay against the plot boundary."
                ),
                responds_to="buffer applicability cannot be determined from open data",
                priority=1,
                who="Bangalore Development Authority planning office, or a local licensed planner",
                agent=AGENT,
            )
        )

    # ---------------------------------------------------- evidence quality conflicts

    def _unreliable_numbers(self, reading: ConflictReading, regulation: RegulationReading) -> None:
        if regulation.has_table_risk:
            risky_hits = regulation.retrieval.risky_table_hits
            risky = [p for p in regulation.numeric_provisions if p.from_risky_table]
            pages = sorted({h.chunk.page_number for h in risky_hits})
            reading.conflicts.append(
                Conflict(
                    kind=ConflictKind.SOURCE_VS_SOURCE,
                    title="Governing figures come from tables whose structure was lost",
                    measured_side=(
                        f"{len(risky_hits)} retrieved passage(s) came from tables on "
                        f"{', '.join(f'p. {p}' for p in pages)} whose grid was lost"
                        + (f", including {len(risky)} numeric value(s)" if risky else "")
                        + "."
                    ),
                    regulatory_side=(
                        "Those tables declare multiple value columns (base, uplift, total). "
                        "Text extraction flattened the grid, so a value cannot be reliably "
                        "attributed to its column."
                    ),
                    why_it_matters=(
                        "Mis-binding a column changes the answer by a factor, not a margin. "
                        "A base figure read as a total, or a total read as a base, is the "
                        "difference between two very different buildings."
                    ),
                    resolvability=Resolvability.RESOLVABLE,
                    blocking_reasons=[
                        "Flattened text does not preserve which column a blank cell belonged to."
                    ],
                    what_would_resolve_it=[
                        f"Reading the table on {', '.join(f'p. {p}' for p in pages)} directly "
                        f"in the source PDF."
                    ],
                    severity=2,
                )
            )

        repaired = [p for p in regulation.numeric_provisions if p.from_repaired_text]
        if repaired:
            pages = sorted({p.page_number for p in repaired})
            reading.conflicts.append(
                Conflict(
                    kind=ConflictKind.SOURCE_VS_SOURCE,
                    title="Some figures were reconstructed from mis-encoded text",
                    measured_side=(
                        f"{len(repaired)} value(s) on {', '.join(f'p. {p}' for p in pages)} "
                        f"came from text that extracted incorrectly and was repaired."
                    ),
                    regulatory_side=(
                        "The source PDF uses a font encoding that maps digits to unrelated "
                        "characters; repair is a validated character mapping, not OCR."
                    ),
                    why_it_matters=(
                        "The repair is tested and reversible, and the raw extraction is "
                        "retained — but a reconstructed digit in a legal limit warrants a "
                        "glance at the source page."
                    ),
                    resolvability=Resolvability.RESOLVABLE,
                    what_would_resolve_it=[
                        f"Confirming the figure on {', '.join(f'p. {p}' for p in pages)}."
                    ],
                    severity=3,
                )
            )

    def _blind_spot_conflicts(
        self, reading: ConflictReading, regulation: RegulationReading
    ) -> None:
        for spot in regulation.blind_spots:
            severity = 1 if spot.page_count > 10 else 2
            reading.conflicts.append(
                Conflict(
                    kind=ConflictKind.EVIDENCE_VS_ABSENCE,
                    title=(
                        f"{spot.page_count} page(s) bearing on this question could not be read"
                    ),
                    measured_side=(
                        f"Evidence was retrieved from the readable portion of the document."
                    ),
                    regulatory_side=(
                        f"Pages {spot.page_start}–{spot.page_end} carry no machine-readable "
                        f"text."
                        + (f" Introduced as: “{spot.descriptor[:160]}”" if spot.descriptor else "")
                    ),
                    why_it_matters=(
                        "An answer assembled from the readable pages may be contradicted or "
                        "superseded by a provision in the region that could not be parsed. "
                        "The system cannot tell which, and neither can the reader."
                    ),
                    resolvability=Resolvability.RESOLVABLE,
                    blocking_reasons=[
                        "These pages are scans or drawings; text extraction returns nothing."
                    ],
                    what_would_resolve_it=[
                        f"Reading pages {spot.page_start}–{spot.page_end} of the source "
                        f"document, which are rendered as images in the evidence panel."
                    ],
                    severity=severity,
                )
            )

    def _absent_structured_data(
        self, reading: ConflictReading, site: SiteReading, regulation: RegulationReading
    ) -> None:
        """The standing conflict: the site layer can never confirm a zoning question.

        Raised only when the question actually turns on it, so it does not become a banner
        the user learns to scroll past.
        """
        if not regulation.claims:
            return
        turns_on_zoning = any(
            _BUFFER_LANGUAGE.search(c.text) or re.search(r"\bFAR\b|land use|zoning", c.text)
            for c in regulation.claims
        )
        if not turns_on_zoning:
            return

        reading.statements.append(
            Inference(
                text=(
                    "The regulation's requirements are triggered by attributes of this "
                    "specific plot — land-use zone, overlay status, plot dimensions — none of "
                    "which exist as open data for this jurisdiction. The document layer can "
                    "state the rule; it cannot determine which rule applies here."
                ),
                derived_from=[c.id for c in regulation.claims[:3]],
                transformation=(
                    "Retrieved provisions are conditional on plot attributes; the site layer "
                    "reported no structured source for those attributes."
                ),
                confidence=Confidence.HIGH,
                confidence_basis=(
                    "Both sides are directly observed: the provisions are quoted, and the "
                    "absence of the datasets was verified by probing the sources."
                ),
                agent=AGENT,
            )
        )
