"""Tests for lexical retrieval and blind-spot reporting.

The behaviour under test is not "does search work" but "does the system report what it
cannot see". The TDR case is the regression test for a real failure found during the build:
asking about Transferable Development Rights returned passages about tree plantation,
because the 23-page statutory instrument governing TDR is scanned and therefore invisible.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest

from app.ingest.retriever import (
    DISTINCTIVE_IDF,
    RegulationIndex,
    expand_query,
    tokenize,
)

CORPUS = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "corpus"
    / "bengaluru-rmp-2031-vol6-zoning-regulations.pdf"
)


# ------------------------------------------------------------------------ tokenisation


def test_decimals_survive_tokenisation():
    """'1.50' and '6.5.3' are the most precise query terms in this corpus."""
    assert "1.50" in tokenize("Base FAR of 1.50 applies")
    assert "6.5.3" in tokenize("see section 6.5.3 for buffers")


def test_stopwords_are_dropped():
    assert "the" not in tokenize("the buffer for the lake")
    assert "buffer" in tokenize("the buffer for the lake")


def test_query_expansion_adds_without_replacing():
    expanded = expand_query(tokenize("TDR rules"))
    assert "tdr" in expanded, "the user's own term must survive expansion"
    assert "transferable" in expanded and "rights" in expanded


# ------------------------------------------------------------------- against the corpus


@functools.lru_cache(maxsize=1)
def _index() -> RegulationIndex:
    from app.ingest.chunker import chunk_document
    from app.ingest.pdf_extract import extract_document

    doc = extract_document(str(CORPUS), render_unreadable=False)
    return RegulationIndex(chunk_document(doc, "rmp2031"))


@pytest.mark.skipif(not CORPUS.exists(), reason="corpus PDF not present")
class TestAgainstRealCorpus:
    def test_lake_buffer_question_finds_the_governing_clause(self):
        result = _index().search("What buffer applies around a lake?")
        top = result.readable_hits[0].chunk
        assert top.page_number == 80
        assert top.section_number == "6.5.3"
        assert top.clause_marker == "ii"
        assert "75 m buffer" in top.text

    def test_stream_buffer_question_finds_the_widths(self):
        result = _index().search("buffers for primary secondary and tertiary streams")
        top = result.readable_hits[0].chunk
        assert "50, 35 and 25 m" in top.text

    def test_citation_carries_a_repair_caveat_where_text_was_repaired(self):
        """Page 80 was densely mis-encoded; a quote from it is reconstructed, not verbatim."""
        top = _index().search("What buffer applies around a lake?").readable_hits[0].chunk
        assert top.text_was_repaired
        assert not top.is_safe_to_quote_verbatim
        assert any("reconstructed" in c for c in top.caveats)

    # --- the regression test this module exists for ---

    def test_tdr_question_reports_the_scanned_statutory_instrument(self):
        result = _index().search("What are the TDR rules for transferable development rights?")
        relevant = result.relevant_blind_spots
        assert relevant, "TDR question must report a blind spot"

        top = relevant[0]
        assert (top.page_start, top.page_end) == (106, 128)
        assert top.page_count == 23
        assert "Development Rights" in top.descriptor
        assert {"rights", "rules"} <= set(top.matched_terms)

    def test_tdr_coverage_note_states_the_real_extent(self):
        result = _index().search("What are the TDR rules for transferable development rights?")
        note = result.coverage_note()
        assert note is not None
        assert "23 page(s)" in note
        assert "106-128" in note

    # --- precision: a warning that cries wolf is worse than no warning ---

    def test_lake_question_does_not_flag_the_heritage_annexe(self):
        """Regression: both mention 'zone', which is not evidence of relevance."""
        result = _index().search("What buffer applies around a lake?")
        flagged = {(b.page_start, b.page_end) for b in result.relevant_blind_spots}
        assert (173, 190) not in flagged
        assert result.coverage_note() is None

    def test_common_terms_are_not_distinctive_enough_to_flag(self):
        idx = _index()
        for common in ("zone", "development", "heritage", "site", "area", "planning"):
            assert idx._idf(common) < DISTINCTIVE_IDF, f"{common} should be common"
        for distinctive in ("rights", "buffer", "rules", "lake"):
            assert idx._idf(distinctive) >= DISTINCTIVE_IDF

    def test_ordinary_questions_do_not_flag_blind_spots(self):
        """Precision sweep. Only a question whose vocabulary genuinely points at an
        unreadable region should produce a warning."""
        idx = _index()
        for question in (
            "What buffer applies around a lake?",
            "What FAR can I get on a 500 sqm plot in Planning Zone A?",
            "What setbacks apply to a residential plot?",
            "Is this site affected by a water body or valley buffer?",
        ):
            assert not idx.search(question).relevant_blind_spots, f"false positive: {question}"

    def test_known_false_negative_is_documented_not_accidental(self):
        """A heritage question no longer flags pages 173-190.

        This is a deliberate, measured trade-off rather than a regression. Requiring one
        distinctive term was the only rule of three tried that separated the TDR case from
        the coincidental matches (see the comment above ``MIN_DISTINCTIVE_TERMS``), and
        "heritage" appears on 136 chunks, so it carries no signal. The case was weak in any
        event: Annexure-5 begins on page 191, so 173-190 is not the heritage list.

        If this starts passing, the threshold changed and the precision sweep above should
        be re-checked before celebrating.
        """
        result = _index().search("Is this building on the heritage list?")
        flagged = {(b.page_start, b.page_end) for b in result.relevant_blind_spots}
        assert (173, 190) not in flagged

    # --- table risk propagation ---

    def test_far_question_surfaces_the_structurally_damaged_table(self):
        result = _index().search("What FAR can I get on a 500 sqm plot in Planning Zone A?")
        pages = {h.chunk.page_number for h in result.readable_hits}
        assert 57 in pages, "Table 6 should be retrieved"
        assert result.risky_table_hits, "the FAR table's structural damage must propagate"

    # --- general invariants ---

    def test_unreadable_placeholders_never_rank_as_evidence(self):
        result = _index().search("buffer")
        assert all(not h.is_blind_spot for h in result.hits)

    def test_nonsense_query_returns_nothing_rather_than_something(self):
        result = _index().search("zxqwv unrelated gibberish token")
        assert not result.has_usable_evidence

    def test_every_hit_can_justify_itself(self):
        for hit in _index().search("setback requirements").readable_hits:
            assert hit.why_matched().startswith("Matched on:")
            assert hit.matched_terms
