"""Tests for the epistemic type system.

These assert the invariants the product's credibility rests on. If an unsourced fact can be
constructed, or a demotion can silently strengthen a claim, the audit trail is decorative.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.epistemics import (
    Assumption,
    Confidence,
    CriticAction,
    CriticNote,
    DatasetLocator,
    DocumentLocator,
    EpistemicType,
    Fact,
    Inference,
    Recommendation,
    Source,
    SourceKind,
    demote,
    summarise,
)


def _doc_source(**overrides) -> Source:
    base = dict(
        document_id="rmp2031",
        document_title="RMP 2031 Vol 6",
        page_number=80,
        char_start=100,
        char_end=180,
        quote="a 75 m buffer of 'no development zone' is to be maintained",
    )
    base.update(overrides)
    return Source(kind=SourceKind.DOCUMENT, document=DocumentLocator(**base))


def _dataset_source(**overrides) -> Source:
    base = dict(
        provider="open-meteo",
        endpoint="/v1/archive",
        retrieved_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        limitation="ERA5 grid centroid is 4.71 km from the requested point",
    )
    base.update(overrides)
    return Source(kind=SourceKind.DATASET, dataset=DatasetLocator(**base))


# ------------------------------------------------------------------- the core invariant


def test_a_fact_cannot_be_constructed_without_a_source():
    """The central invariant. Not a warning — a construction failure."""
    with pytest.raises(ValidationError) as exc:
        Fact(text="the plot is in a valley zone", source=Source(kind=SourceKind.ABSENT))
    assert "cannot have an absent source" in str(exc.value)


def test_a_document_source_requires_a_locator():
    with pytest.raises(ValidationError):
        Source(kind=SourceKind.DOCUMENT)


def test_a_dataset_source_requires_a_locator():
    with pytest.raises(ValidationError):
        Source(kind=SourceKind.DATASET)


def test_a_fact_with_a_source_is_fine():
    f = Fact(text="A 75 m no-development buffer applies around water bodies.", source=_doc_source())
    assert f.type is EpistemicType.FACT
    assert f.source.document.page_number == 80
    assert not f.was_weakened


def test_span_must_be_non_empty():
    with pytest.raises(ValidationError) as exc:
        DocumentLocator(
            document_id="d", document_title="t", page_number=1,
            char_start=50, char_end=50, quote="x",
        )
    assert "end must exceed start" in str(exc.value)


# -------------------------------------------------------------------------- inferences


def test_an_inference_must_name_what_it_derives_from():
    with pytest.raises(ValidationError):
        Inference(
            text="the site is highly accessible",
            derived_from=[],
            transformation="proximity to transit",
            confidence_basis="single proxy",
        )


def test_an_inference_must_state_its_transformation():
    with pytest.raises(ValidationError):
        Inference(
            text="the site is highly accessible",
            derived_from=["stm_1"],
            transformation="",
            confidence_basis="single proxy",
        )


def test_confidence_requires_a_stated_basis():
    """A band without a reason is decoration."""
    with pytest.raises(ValidationError):
        Inference(
            text="flat site",
            derived_from=["stm_1"],
            transformation="1 m relief over 490 m",
            confidence_basis="",
        )


def test_confidence_reduction_is_recorded():
    inf = Inference(
        text="Transit accessibility appears favourable.",
        derived_from=["stm_1"],
        transformation="distance to nearest station used as proxy",
        confidence=Confidence.HIGH,
        confidence_basis="station 600 m away",
    )
    inf.reduce_confidence(Confidence.LOW, "pedestrian connectivity unverified")
    assert inf.confidence is Confidence.LOW
    assert inf.was_weakened
    note = inf.critic_notes[0]
    assert note.action is CriticAction.REDUCE_CONFIDENCE
    assert note.from_value == "high" and note.to_value == "low"


def test_confidence_can_never_be_raised():
    """Nothing in the system may strengthen a claim after the fact."""
    inf = Inference(
        text="x", derived_from=["a"], transformation="t",
        confidence=Confidence.LOW, confidence_basis="weak evidence",
    )
    inf.reduce_confidence(Confidence.HIGH, "trying to strengthen")
    assert inf.confidence is Confidence.LOW
    assert not inf.was_weakened


# --------------------------------------------------------------------------- demotion


def test_fact_demotes_to_inference_preserving_identity_and_trail():
    f = Fact(text="The plot lies outside the buffer.", source=_doc_source())
    out = demote(f, "the buffer extent is defined by revenue records, which were not consulted")

    assert isinstance(out, Inference)
    assert out.id == f.id, "identity must survive demotion so the UI can track the claim"
    assert out.text == f.text
    assert out.confidence is Confidence.LOW
    assert out.critic_notes[-1].action is CriticAction.DEMOTE
    assert out.critic_notes[-1].from_value == "fact"
    assert out.critic_notes[-1].to_value == "inference"


def test_inference_demotes_to_assumption():
    inf = Inference(
        text="Accessibility is favourable.",
        derived_from=["stm_1"],
        transformation="proximity proxy",
        confidence_basis="one station within 600 m",
    )
    out = demote(inf, "proximity does not establish pedestrian connectivity")
    assert isinstance(out, Assumption)
    assert out.demoted_from is EpistemicType.INFERENCE
    assert out.falsified_by


def test_cannot_demote_below_assumption():
    a = Assumption(text="assume no valley zone", falsified_by="obtain the RMP sheet")
    with pytest.raises((ValueError, AttributeError)):
        demote(a, "reason")  # type: ignore[arg-type]


def test_demotion_preserves_earlier_critic_notes():
    f = Fact(text="x", source=_doc_source())
    f.record_critic(CriticNote(action=CriticAction.FLAG_MISLEADING, reason="phrasing"))
    out = demote(f, "unsupported")
    assert len(out.critic_notes) == 2


# ---------------------------------------------------------------------------- caveats


def test_dataset_limitation_travels_with_the_fact():
    """ERA5's grid drift must not be strippable from the value it qualifies."""
    f = Fact(text="Annual precipitation 1009.9 mm (2024).", source=_dataset_source())
    assert "4.71 km" in f.needs_caveat


def test_repaired_quote_is_not_verbatim():
    src = _doc_source(text_was_repaired=True, raw_quote="a 7ϱ ŵ ďuffeƌ")
    assert not src.document.is_verbatim


def test_clean_quote_is_verbatim():
    assert _doc_source().document.is_verbatim


def test_proxy_for_records_the_leap():
    f = Fact(
        text="Nearest rail station is 1.4 km away.",
        source=_dataset_source(provider="overpass"),
        proxy_for="accessibility",
    )
    assert f.proxy_for == "accessibility"


# --------------------------------------------------------------------- recommendations


def test_recommendation_must_respond_to_something():
    with pytest.raises(ValidationError):
        Recommendation(text="Obtain the RMP valley-zone sheet.", responds_to="")


def test_recommendation_carries_no_confidence():
    r = Recommendation(
        text="Obtain the RMP valley-zone sheet for this survey number.",
        responds_to="buffer applicability cannot be determined from open data",
        who="BDA planning office",
        priority=1,
    )
    assert not hasattr(r, "confidence")


def test_rejection_marks_the_statement():
    f = Fact(text="x", source=_doc_source())
    f.record_critic(CriticNote(action=CriticAction.REJECT, reason="quote does not support claim"))
    assert f.rejected


# ----------------------------------------------------------------------------- summary


def test_summarise_counts_by_type_and_excludes_rejected():
    rejected = Fact(text="bad", source=_doc_source())
    rejected.record_critic(CriticNote(action=CriticAction.REJECT, reason="unsupported"))
    statements = [
        Fact(text="a", source=_doc_source()),
        Inference(text="b", derived_from=["x"], transformation="t", confidence_basis="c"),
        Assumption(text="c", falsified_by="check the plan"),
        Recommendation(text="d", responds_to="gap"),
        rejected,
    ]
    counts = summarise(statements)
    assert counts["fact"] == 1
    assert counts["inference"] == 1
    assert counts["assumption"] == 1
    assert counts["recommendation"] == 1
    assert counts["rejected"] == 1
