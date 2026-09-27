"""Wire format for the API.

The serialisation is deliberately verbose in one respect: **every caveat travels with the
value it qualifies, inside the same object.** A citation carries its own repair flag and
warning text; a measurement carries its provider's limitation. Nothing is put in a separate
"notes" array that a front-end could render in a collapsed panel, or forget to render at all.

That is a design constraint, not an accident of modelling. The moment a caveat becomes a
sibling of the value rather than a property of it, some future screen shows the number
without it — and the product's whole argument fails quietly.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CitationOut(BaseModel):
    """A passage-level citation — the unit that makes a claim checkable."""

    document_id: str
    document_title: str
    page_number: int
    char_start: int
    char_end: int
    quote: str

    # Reliability, attached rather than adjacent.
    is_verbatim: bool
    text_was_repaired: bool
    raw_quote: str | None = None
    page_quality: str | None = None
    caveat: str | None = None
    reference: str


class StatementOut(BaseModel):
    """One typed statement with its epistemic status made explicit."""

    id: str
    type: Literal["fact", "inference", "assumption", "recommendation"]
    text: str
    agent: str | None = None

    # fact
    citation: CitationOut | None = None
    dataset_provider: str | None = None
    dataset_retrieved_at: str | None = None
    dataset_limitation: str | None = None
    proxy_for: str | None = None

    # inference
    derived_from: list[str] = Field(default_factory=list)
    transformation: str | None = None
    confidence: str | None = None
    confidence_basis: str | None = None

    # assumption
    falsified_by: str | None = None
    why_needed: str | None = None
    demoted_from: str | None = None

    # recommendation
    responds_to: str | None = None
    priority: int | None = None
    who: str | None = None

    # critic
    was_weakened: bool = False
    rejected: bool = False
    critic_notes: list[dict[str, Any]] = Field(default_factory=list)


class ConflictOut(BaseModel):
    kind: str
    title: str
    measured_side: str
    regulatory_side: str
    why_it_matters: str
    resolvability: str
    blocking_reasons: list[str] = Field(default_factory=list)
    what_would_resolve_it: list[str] = Field(default_factory=list)
    severity: int
    is_decisive: bool


class BlindSpotOut(BaseModel):
    page_start: int
    page_end: int
    page_count: int
    descriptor: str = ""
    following_context: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    page_image_urls: list[str] = Field(default_factory=list)
    """Rendered images of the pages the system could not parse.

    The point of the unreadable surface: rather than apologising, hand the reader the actual
    page and let them do what the machine could not.
    """


class ChangeMyMindOut(BaseModel):
    current_position: str
    would_change_if: str
    type: str


class AgentTraceOut(BaseModel):
    agent: str
    duration_ms: int
    ok: bool
    statements_produced: int = 0
    error: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class CriticFindingOut(BaseModel):
    statement_id: str
    action: str
    reason: str
    check: str


class SitePanelOut(BaseModel):
    """One panel of measured context, or an honest empty state."""

    key: str
    title: str
    available: bool
    facts: list[StatementOut] = Field(default_factory=list)
    limitation: str | None = None
    unavailable_reason: str | None = None


class FindingOut(BaseModel):
    """The full eight-part anatomy."""

    id: str
    question: str
    location_query: str
    created_at: str
    mode: str
    total_duration_ms: int

    resolved_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    needs_disambiguation: bool = False
    geocode_candidates: list[dict[str, Any]] = Field(default_factory=list)

    # anatomy
    context: list[StatementOut] = Field(default_factory=list)
    evidence: list[StatementOut] = Field(default_factory=list)
    conflicts: list[ConflictOut] = Field(default_factory=list)
    unreadable: list[BlindSpotOut] = Field(default_factory=list)
    answer: str | None = None
    change_my_mind: list[ChangeMyMindOut] = Field(default_factory=list)
    verify_next: list[StatementOut] = Field(default_factory=list)
    assumptions: list[StatementOut] = Field(default_factory=list)

    # supporting
    site_panels: list[SitePanelOut] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)
    traces: list[AgentTraceOut] = Field(default_factory=list)
    critic_findings: list[CriticFindingOut] = Field(default_factory=list)
    critic_checks_run: list[str] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)

    # map
    map_features: list[dict[str, Any]] = Field(default_factory=list)


class AnalyseRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    location: str = Field(min_length=2, max_length=200)
    latitude: float | None = None
    longitude: float | None = None


class CompareRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    sites: list[str] = Field(min_length=2, max_length=3)
    """Two or three. Beyond three the matrix stops being readable at a glance, which is the
    only thing a comparison view is for."""


class CorpusOut(BaseModel):
    """What the system can and cannot read — surfaced, not buried."""

    title: str
    sha256: str
    page_count: int
    readable_page_count: int
    unreadable_page_count: int
    text_coverage: float
    total_chars: int
    total_substitutions: int
    pages_needing_repair: int
    unreadable_ranges: list[list[int]] = Field(default_factory=list)
    quality_breakdown: dict[str, int] = Field(default_factory=dict)
    chunk_count: int = 0
    risky_tables: list[dict[str, Any]] = Field(default_factory=list)
    is_draft: bool = True
