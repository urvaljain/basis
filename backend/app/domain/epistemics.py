"""The epistemic type system: what kind of thing each statement is.

This is the core of the product, and it is a data model rather than a UI concern on purpose.

Most AI systems emit a single undifferentiated kind of output — "text the model produced" —
and then decorate it with a confidence number. That flattens four genuinely different
epistemic objects into one:

* something **measured**, which is reproducible and checkable;
* something **derived** from measurements by a stated transformation, which can be wrong if
  the transformation is wrong;
* something **assumed**, which nothing established at all;
* something **suggested**, which is a proposed action rather than a statement about the world.

A reader who cannot tell these apart cannot calibrate their trust, and a confidence score
does not help: 80% attached to a measurement means something different from 80% attached to
a guess. Conflating them is how a fluent system misleads a competent professional.

So the distinction is enforced here, in code, with invariants that raise rather than warn:

1. A :class:`Fact` cannot be constructed without a source. Not "should not" — cannot.
2. An :class:`Inference` must name at least one statement it derives from, and the
   transformation that produced it.
3. Confidence may only be attached to an :class:`Inference`. A fact is not 80% true; an
   assumption is not 60% assumed; a recommendation is not probabilistic.
4. Demotion is visible and recorded. The Critic weakens claims rather than deleting them,
   because a deletion leaves no trace and an audit trail with gaps is not an audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class EpistemicType(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    ASSUMPTION = "assumption"
    RECOMMENDATION = "recommendation"


# Ordered weakest-last. Demotion moves rightwards and never leftwards: nothing in the
# system is allowed to strengthen a claim after the fact.
_DEMOTION_ORDER: tuple[EpistemicType, ...] = (
    EpistemicType.FACT,
    EpistemicType.INFERENCE,
    EpistemicType.ASSUMPTION,
)


class Confidence(str, Enum):
    """Coarse bands, deliberately not a percentage.

    A percentage implies a calibrated probability. Nothing here produces one, so showing
    one would be a fabricated metric — the exact thing ``docs/08-non-goals.md`` forbids.
    Bands are honest about their own resolution.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return {"high": 3, "medium": 2, "low": 1}[self.value]


class SourceKind(str, Enum):
    DOCUMENT = "document"
    """A passage in a PDF, with page and character span."""

    DATASET = "dataset"
    """A value returned by a data provider (OSM, ERA5, SRTM, geocoding)."""

    USER = "user"
    """Supplied by the person using the system."""

    ABSENT = "absent"
    """No source exists. Only valid on an Assumption, never on a Fact."""


class DocumentLocator(BaseModel):
    """Points at an exact passage — the unit that makes a citation checkable.

    Document-level attribution ("Source: RMP 2031") is unfalsifiable in practice: nobody
    reads 206 pages to verify a claim. A page plus a character span is checkable in
    seconds, and that difference is the product.
    """

    document_id: str
    document_title: str
    page_number: int = Field(ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    quote: str = Field(min_length=1)

    # Provenance of the text itself. Set by the ingestion pipeline.
    text_was_repaired: bool = False
    raw_quote: str | None = None
    page_quality: str | None = None
    caveat: str | None = None
    """Warning that must travel with any display of this quote (repaired text, damaged
    table structure, unreadable neighbourhood)."""

    @model_validator(mode="after")
    def _span_is_sane(self) -> Self:
        if self.char_end <= self.char_start:
            raise ValueError(
                f"invalid span [{self.char_start}, {self.char_end}) — end must exceed start"
            )
        return self

    @property
    def is_verbatim(self) -> bool:
        """False when the quote was reconstructed and must be labelled as such."""
        return not self.text_was_repaired

    def display_reference(self) -> str:
        return f"{self.document_title}, p. {self.page_number}"


class DatasetLocator(BaseModel):
    """Points at a provider response, with enough detail to re-run it."""

    provider: str
    endpoint: str
    retrieved_at: datetime
    query: dict[str, Any] = Field(default_factory=dict)
    licence: str | None = None
    limitation: str | None = None
    """The provider's honest caveat, e.g. ERA5's 4.71 km grid drift at this site. Displayed
    with the value, never stripped."""

    def display_reference(self) -> str:
        return f"{self.provider} ({self.retrieved_at:%Y-%m-%d})"


class Source(BaseModel):
    kind: SourceKind
    document: DocumentLocator | None = None
    dataset: DatasetLocator | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _locator_matches_kind(self) -> Self:
        if self.kind is SourceKind.DOCUMENT and self.document is None:
            raise ValueError("SourceKind.DOCUMENT requires a DocumentLocator")
        if self.kind is SourceKind.DATASET and self.dataset is None:
            raise ValueError("SourceKind.DATASET requires a DatasetLocator")
        return self

    def display_reference(self) -> str:
        if self.document:
            return self.document.display_reference()
        if self.dataset:
            return self.dataset.display_reference()
        return self.note or "unsourced"

    @property
    def caveat(self) -> str | None:
        if self.document:
            return self.document.caveat
        if self.dataset:
            return self.dataset.limitation
        return None


class CriticAction(str, Enum):
    DEMOTE = "demote"
    REDUCE_CONFIDENCE = "reduce_confidence"
    FLAG_MISLEADING = "flag_misleading"
    REQUIRE_VERIFICATION = "require_verification"
    REJECT = "reject"


class CriticNote(BaseModel):
    """A recorded critic intervention.

    Kept on the statement rather than in a side-channel so the UI can always show that a
    claim was weakened and why. An invisible critic cannot be audited, which would make it
    indistinguishable from no critic at all.
    """

    action: CriticAction
    reason: str
    applied_at: datetime = Field(default_factory=_now)
    from_value: str | None = None
    to_value: str | None = None


class Statement(BaseModel):
    """Base class for anything the system asserts."""

    id: str = Field(default_factory=lambda: _new_id("stm"))
    type: EpistemicType
    text: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_now)
    agent: str | None = None
    critic_notes: list[CriticNote] = Field(default_factory=list)
    rejected: bool = False

    @property
    def was_weakened(self) -> bool:
        return bool(self.critic_notes)

    def record_critic(self, note: CriticNote) -> None:
        self.critic_notes.append(note)
        if note.action is CriticAction.REJECT:
            self.rejected = True


class Fact(Statement):
    """A directly measured or directly quoted statement.

    The invariant that matters: a Fact **cannot exist without a source**. This is checked at
    construction, so an unsourced fact is not a bug that reaches the interface — it is an
    object that cannot be built.
    """

    type: Literal[EpistemicType.FACT] = EpistemicType.FACT
    source: Source
    proxy_for: str | None = None
    """What this fact is being used to stand in for, when it is a proxy.

    Distance to a station is a fact. *Accessibility* is not — it is an interpretation of
    that fact. Naming the leap here stops the interface from implying it silently, which is
    how a measurement quietly becomes a judgement.
    """

    @model_validator(mode="after")
    def _must_be_sourced(self) -> Self:
        if self.source.kind is SourceKind.ABSENT:
            raise ValueError(
                f"a Fact cannot have an absent source (fact: {self.text[:60]!r}). "
                "Use an Assumption instead."
            )
        return self

    @property
    def needs_caveat(self) -> str | None:
        return self.source.caveat


class Inference(Statement):
    """Derived from other statements by a named transformation."""

    type: Literal[EpistemicType.INFERENCE] = EpistemicType.INFERENCE
    derived_from: list[str] = Field(min_length=1)
    """IDs of the statements this rests on."""

    transformation: str = Field(min_length=1)
    """How the derivation was made, in plain language. A reader must be able to disagree
    with the reasoning without re-deriving it."""

    confidence: Confidence = Confidence.MEDIUM
    confidence_basis: str = Field(min_length=1)
    """Why this confidence band and not another. Without this a band is decoration."""

    def reduce_confidence(self, to: Confidence, reason: str) -> None:
        if to.rank >= self.confidence.rank:
            return
        note = CriticNote(
            action=CriticAction.REDUCE_CONFIDENCE,
            reason=reason,
            from_value=self.confidence.value,
            to_value=to.value,
        )
        self.confidence = to
        self.record_critic(note)


class Assumption(Statement):
    """Something the reasoning requires but nothing established."""

    type: Literal[EpistemicType.ASSUMPTION] = EpistemicType.ASSUMPTION
    falsified_by: str = Field(min_length=1)
    """What evidence would show this to be false. An assumption nobody can test is not an
    assumption, it is a hope — and stating the test is what makes it actionable."""

    why_needed: str | None = None
    demoted_from: EpistemicType | None = None


class Recommendation(Statement):
    """A suggested human action. Never carries confidence."""

    type: Literal[EpistemicType.RECOMMENDATION] = EpistemicType.RECOMMENDATION
    responds_to: str = Field(min_length=1)
    """The uncertainty or conflict this action addresses."""

    priority: int = Field(default=3, ge=1, le=5)
    effort: str | None = None
    who: str | None = None
    """Who would actually do this — a surveyor, the planning authority, a structural
    engineer. A verification task without an addressee rarely gets done."""


AnyStatement = Fact | Inference | Assumption | Recommendation


def demote(statement: Fact | Inference, reason: str, agent: str = "critic") -> AnyStatement:
    """Weaken a statement by one level, preserving the audit trail.

    Demotion rather than deletion is deliberate: removing a claim leaves no evidence that
    it was ever made or why it was withdrawn, and a reader cannot audit an absence.

    * Fact → Inference (the measurement is no longer considered direct)
    * Inference → Assumption (the derivation no longer holds)
    """
    current = statement.type
    idx = _DEMOTION_ORDER.index(current)
    if idx + 1 >= len(_DEMOTION_ORDER):
        raise ValueError(f"cannot demote below {current.value}")
    target = _DEMOTION_ORDER[idx + 1]

    note = CriticNote(
        action=CriticAction.DEMOTE,
        reason=reason,
        from_value=current.value,
        to_value=target.value,
    )

    if target is EpistemicType.INFERENCE:
        assert isinstance(statement, Fact)
        out: AnyStatement = Inference(
            id=statement.id,
            text=statement.text,
            created_at=statement.created_at,
            agent=agent,
            derived_from=[statement.id],
            transformation=(
                f"Originally asserted as a fact sourced to "
                f"{statement.source.display_reference()}; demoted by the critic."
            ),
            confidence=Confidence.LOW,
            confidence_basis=reason,
            critic_notes=[*statement.critic_notes, note],
        )
        return out

    return Assumption(
        id=statement.id,
        text=statement.text,
        created_at=statement.created_at,
        agent=agent,
        falsified_by=reason,
        why_needed="Retained after demotion so the original claim remains auditable.",
        demoted_from=current,
        critic_notes=[*statement.critic_notes, note],
    )


def summarise(statements: list[AnyStatement]) -> dict[str, int]:
    """Count statements by epistemic type.

    Used for the coverage figures shown in the UI. These are counts of real objects, not a
    quality score — see ``docs/08-non-goals.md`` on why there is no score.
    """
    counts = {t.value: 0 for t in EpistemicType}
    for s in statements:
        if not s.rejected:
            counts[s.type.value] += 1
    counts["rejected"] = sum(1 for s in statements if s.rejected)
    counts["weakened_by_critic"] = sum(1 for s in statements if s.was_weakened)
    return counts
