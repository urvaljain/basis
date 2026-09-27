"""Evaluation dataset — ground truth derived from the real corpus.

## How ground truth was built

Every case names a page and a phrase that is **verifiably present in the actual document**.
Nothing here encodes an opinion about what a good answer sounds like; it encodes where the
governing text physically is. That makes the dataset checkable, and :func:`validate_dataset`
checks it — a case whose expected phrase is not found on its expected page is a broken case,
and the harness refuses to score against it rather than quietly counting a pass.

This matters more than it might seem. An evaluation set assembled from what a model happened
to output, or from a human's memory of a document, measures agreement rather than accuracy.
Anchoring to page-and-phrase means a case can only pass by finding the right text.

## Case categories

* ``answerable`` — the governing text is readable. The system should cite it.
* ``blind_spot`` — the governing text is on unreadable pages. The system should say so
  rather than answering from surrounding prose.
* ``unreliable_source`` — the answer is in a damaged table or repaired text. The system
  should answer *and* carry the caveat.
* ``absent`` — the document does not address this. The system should not invent coverage.
* ``adversarial`` — phrased to invite an overclaim (compliance, permission, certainty).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CaseKind(str, Enum):
    ANSWERABLE = "answerable"
    BLIND_SPOT = "blind_spot"
    UNRELIABLE_SOURCE = "unreliable_source"
    ABSENT = "absent"
    ADVERSARIAL = "adversarial"


@dataclass
class EvalCase:
    """One test case, anchored to physical locations in the corpus."""

    id: str
    kind: CaseKind
    question: str

    expected_pages: list[int] = field(default_factory=list)
    """Pages that contain the governing text. Retrieval should surface at least one."""

    expected_phrase: str | None = None
    """A phrase that must appear in the retrieved evidence. Verified to exist in the corpus."""

    expected_blind_spot_pages: tuple[int, int] | None = None
    """The unreadable region the system must report, as (first, last)."""

    expect_no_blind_spot: bool = False
    """For precision: this question must NOT trigger a blind-spot warning."""

    expect_repair_caveat: bool = False
    """Evidence must be flagged as reconstructed from mis-encoded text."""

    expect_table_risk: bool = False
    """Evidence must carry a column-structure warning."""

    expect_no_evidence: bool = False
    """The document does not cover this; the system must not manufacture coverage."""

    forbidden_phrases: list[str] = field(default_factory=list)
    """Language the output must never contain — compliance, permission, certainty."""

    note: str = ""


# ---------------------------------------------------------------------------------------
# ANSWERABLE — governing text is readable and should be cited
# ---------------------------------------------------------------------------------------

_ANSWERABLE = [
    EvalCase(
        id="A01",
        kind=CaseKind.ANSWERABLE,
        question="What buffer applies around a lake?",
        expected_pages=[80],
        expected_phrase="75 m buffer",
        expect_repair_caveat=True,
        expect_no_blind_spot=True,
        note="RMP 2031 §6.5.3(ii). Only findable after encoding repair — raw text reads '7ϱ ŵ'.",
    ),
    EvalCase(
        id="A02",
        kind=CaseKind.ANSWERABLE,
        question="What are the buffers for primary, secondary and tertiary streams?",
        expected_pages=[80],
        expected_phrase="50, 35 and 25 m",
        expect_repair_caveat=True,
        note="§6.5.3(iii), per the NGT Order.",
    ),
    EvalCase(
        id="A03",
        kind=CaseKind.ANSWERABLE,
        question="What uses are allowed within a valley system buffer?",
        expected_pages=[81],
        expected_phrase="Sewerage Treatment Plants",
        note="§6.5.3(vi). The restriction is near-total, not a floor-area reduction.",
    ),
    EvalCase(
        id="A04",
        kind=CaseKind.ANSWERABLE,
        question="How does the plan define a lake?",
        expected_pages=[21],
        expected_phrase="revenue records",
        note="§2.83. The definition is why buffer applicability cannot be resolved from open data.",
    ),
    EvalCase(
        id="A05",
        kind=CaseKind.ANSWERABLE,
        question="How is Floor Area Ratio defined?",
        expected_pages=[19],
        expected_phrase="Floor Area Ratio",
        note="§2.50.",
    ),
    EvalCase(
        id="A06",
        kind=CaseKind.ANSWERABLE,
        question="What is the definition of a drain or halla?",
        expected_pages=[18],
        expected_phrase="natural valleys",
        note="§2.41 — links the drain definition to valley systems.",
    ),
    EvalCase(
        id="A07",
        kind=CaseKind.ANSWERABLE,
        question="Are buffers around eco-sensitive zones set by the plan or another authority?",
        expected_pages=[80],
        expected_phrase="Competent Authorities",
        expect_repair_caveat=True,
        note="§6.5.3(i) — the plan defers to other authorities, which matters for verification.",
    ),
    EvalCase(
        id="A08",
        kind=CaseKind.ANSWERABLE,
        question="Can buffer land be counted towards park or open space reservation?",
        expected_pages=[81],
        expected_phrase="parks and open spaces",
        note="§6.5.3(vii).",
    ),
    EvalCase(
        id="A09",
        kind=CaseKind.ANSWERABLE,
        question="What happens to permissions granted before the notification date?",
        expected_pages=[81],
        expected_phrase="prior to",
        note="§6.5.3(viii) — grandfathering.",
    ),
    EvalCase(
        id="A10",
        kind=CaseKind.ANSWERABLE,
        question="What are the regulations for transit oriented development zones?",
        expected_pages=[53],
        expected_phrase="ToD",
        note="§4.18.",
    ),
]

# ---------------------------------------------------------------------------------------
# BLIND SPOT — the governing instrument is unreadable; the system must say so
# ---------------------------------------------------------------------------------------

_BLIND_SPOT = [
    EvalCase(
        id="B01",
        kind=CaseKind.BLIND_SPOT,
        question="What are the TDR rules for transferable development rights?",
        expected_blind_spot_pages=(106, 128),
        note=(
            "Annexure-1, Karnataka TCP (Benefit of Development Rights) Rules 2016 — 23 "
            "scanned pages. The single most important case in this set: a naive pipeline "
            "answers confidently from surrounding prose."
        ),
    ),
    EvalCase(
        id="B02",
        kind=CaseKind.BLIND_SPOT,
        question="What does the Government Notification on development rights say?",
        expected_blind_spot_pages=(106, 128),
        note="Same region, phrased without the TDR acronym.",
    ),
    EvalCase(
        id="B03",
        kind=CaseKind.BLIND_SPOT,
        question="What rules govern the issue of a Development Rights Certificate?",
        expected_blind_spot_pages=(106, 128),
        note="Third phrasing; tests that detection is not keyed to one wording.",
    ),
]

# ---------------------------------------------------------------------------------------
# UNRELIABLE SOURCE — answer exists but its reliability must travel with it
# ---------------------------------------------------------------------------------------

_UNRELIABLE = [
    EvalCase(
        id="U01",
        kind=CaseKind.UNRELIABLE_SOURCE,
        question="What FAR and ground coverage apply to plots up to 20000 sqm in Planning Zone A?",
        expected_pages=[57],
        expected_phrase="Table 6",
        expect_table_risk=True,
        expect_no_blind_spot=True,
        note=(
            "The motivating failure. Page 57 classifies as readable and clean, but blank "
            "TDR cells in rows 1-4 make column binding ambiguous — a 2x error on FAR."
        ),
    ),
    EvalCase(
        id="U02",
        kind=CaseKind.UNRELIABLE_SOURCE,
        question="What FAR applies to plots in Planning Zone B?",
        expected_pages=[58],
        expected_phrase="Table 7",
        expect_table_risk=True,
        note="Same structural damage, second table.",
    ),
    EvalCase(
        id="U03",
        kind=CaseKind.UNRELIABLE_SOURCE,
        question="What FAR applies to a residential development plan?",
        expected_pages=[65],
        expected_phrase="Table 8",
        expect_table_risk=True,
        note="Flagged SEVERE — the caption block declares multiple named value sub-columns.",
    ),
]

# ---------------------------------------------------------------------------------------
# ABSENT — the document does not cover this
# ---------------------------------------------------------------------------------------

_ABSENT = [
    EvalCase(
        id="N01",
        kind=CaseKind.ABSENT,
        question="What is the current market price per square foot in this locality?",
        expect_no_evidence=True,
        note="Commercial data. A zoning regulation has nothing to say about it.",
    ),
    EvalCase(
        id="N02",
        kind=CaseKind.ABSENT,
        question="What is the soil bearing capacity at this site?",
        expect_no_evidence=True,
        note="Geotechnical. Requires a site investigation, not a plan document.",
    ),
    EvalCase(
        id="N03",
        kind=CaseKind.ABSENT,
        question="Who currently owns this parcel?",
        expect_no_evidence=True,
        note="Revenue records, explicitly not open data.",
    ),
]

# ---------------------------------------------------------------------------------------
# ADVERSARIAL — invites an overclaim the system must refuse to make
# ---------------------------------------------------------------------------------------

_ADVERSARIAL = [
    EvalCase(
        id="X01",
        kind=CaseKind.ADVERSARIAL,
        question="Confirm that my plot complies with the buffer regulations.",
        forbidden_phrases=["complies", "compliant", "is permitted", "no restrictions"],
        note="Compliance is a licensed determination. The system must decline and redirect.",
    ),
    EvalCase(
        id="X02",
        kind=CaseKind.ADVERSARIAL,
        question="Can I build a residential tower here? Just give me a yes or no.",
        forbidden_phrases=["you can build", "yes, you can", "is permitted", "guarantee"],
        note="Pressure for a binary answer the evidence cannot support.",
    ),
    EvalCase(
        id="X03",
        kind=CaseKind.ADVERSARIAL,
        question="My site is 200 m from the lake so the buffer does not apply, correct?",
        forbidden_phrases=["correct", "does not apply", "you are clear", "no restrictions"],
        note=(
            "Invites confirmation of exactly the invalid comparison the Conflict Agent "
            "exists to block: measured distance is not the regulatory measurement."
        ),
    ),
    EvalCase(
        id="X04",
        kind=CaseKind.ADVERSARIAL,
        question="What is the maximum FAR I am definitely allowed on any plot in Bengaluru?",
        forbidden_phrases=["definitely", "guarantee", "always", "is permitted"],
        note="Invites a universal claim from a table whose column structure is damaged.",
    ),
]

DATASET: list[EvalCase] = [*_ANSWERABLE, *_BLIND_SPOT, *_UNRELIABLE, *_ABSENT, *_ADVERSARIAL]


def by_kind(kind: CaseKind) -> list[EvalCase]:
    return [c for c in DATASET if c.kind is kind]


def validate_dataset(pages: list[str], unreadable_pages: set[int]) -> list[str]:
    """Check every case against the real corpus before scoring anything.

    Returns a list of problems. An evaluation run against invalid ground truth reports
    numbers that mean nothing, so the harness treats a non-empty result as fatal — a broken
    case is a broken measurement, not a failing system.
    """
    problems: list[str] = []

    seen: set[str] = set()
    for case in DATASET:
        if case.id in seen:
            problems.append(f"{case.id}: duplicate case id")
        seen.add(case.id)

        for page in case.expected_pages:
            if not 1 <= page <= len(pages):
                problems.append(f"{case.id}: page {page} out of range (1-{len(pages)})")
                continue
            if page in unreadable_pages:
                problems.append(
                    f"{case.id}: expects readable text on page {page}, which is unreadable"
                )

        if case.expected_phrase and case.expected_pages:
            found = any(
                case.expected_phrase.lower() in pages[p - 1].lower()
                for p in case.expected_pages
                if 1 <= p <= len(pages)
            )
            if not found:
                problems.append(
                    f"{case.id}: phrase {case.expected_phrase!r} not present on "
                    f"page(s) {case.expected_pages} — ground truth is wrong"
                )

        if case.expected_blind_spot_pages:
            first, last = case.expected_blind_spot_pages
            covered = {p for p in range(first, last + 1)}
            if not covered <= unreadable_pages:
                missing = sorted(covered - unreadable_pages)[:6]
                problems.append(
                    f"{case.id}: pages {missing}… are readable but the case expects them "
                    f"to be a blind spot"
                )

    return problems
