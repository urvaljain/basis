"""Tests for the PDF encoding repair layer.

These run against the real Bengaluru RMP 2031 corpus where it is present, because the
whole point of the module is that it handles a specific real document correctly. The
corpus-dependent tests skip cleanly when the PDF is absent so CI stays green without a
7.5 MB binary in the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingest.text_repair import (
    CANONICAL_PROBES,
    REPAIR_MAP,
    count_suspect_chars,
    describe_residual,
    find_numeric_clauses,
    repair,
)

CORPUS = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "corpus"
    / "bengaluru-rmp-2031-vol6-zoning-regulations.pdf"
)


# --------------------------------------------------------------------------- unit


def test_empty_text_is_a_noop():
    r = repair("")
    assert r.repaired == ""
    assert not r.was_repaired
    assert r.is_clean
    assert r.corruption_rate == 0.0


def test_clean_text_is_untouched():
    clean = "The buffer for water bodies shall be 75 m, measured from the edge."
    r = repair(clean)
    assert r.repaired == clean
    assert r.substitutions == 0
    assert not r.was_repaired
    assert r.is_clean


def test_canonical_probes_from_the_real_corpus():
    """Every probe is a verbatim fragment of the corpus with its known-correct reading."""
    for raw, expected in CANONICAL_PROBES:
        assert repair(raw).repaired == expected, f"{raw!r} should repair to {expected!r}"


def test_digits_map_sequentially_from_u03ec():
    """The digit encoding is a clean offset, which is why it is trustworthy."""
    raw = "".join(chr(0x03EC + d) for d in range(10))
    assert repair(raw).repaired == "0123456789"


def test_numbers_inside_regulatory_limits_survive():
    """The failure that matters: corruption reaching inside the measurement."""
    raw = "a 7ϱ ŵ ďuffeƌ of ͚Ŷo deǀelopŵeŶt zoŶe͛"
    out = repair(raw).repaired
    assert out == "a 75 m buffer of 'no development zone'"
    assert ("75 m", 2) in [(t, o) for t, o in find_numeric_clauses(out)]


def test_stream_buffer_widths_are_recovered():
    """RMP 2031 6.5.3(iii): primary/secondary/tertiary drains at 50/35/25 m."""
    raw = "a ďuffeƌ of ϱϬ, ϯϱ aŶd Ϯϱ ŵ"
    assert repair(raw).repaired == "a buffer of 50, 35 and 25 m"


def test_character_offsets_are_preserved():
    """Citations carry character spans, so repair must not shift them."""
    raw = "Restrictions imposed ďǇ CoŵpeteŶt Authoƌities"
    r = repair(raw)
    assert len(r.repaired) == len(r.raw)
    assert r.repaired.index("imposed") == r.raw.index("imposed")


def test_raw_is_always_retained():
    raw = "ďuffeƌ"
    r = repair(raw)
    assert r.raw == raw
    assert r.repaired == "buffer"
    assert r.raw != r.repaired


def test_legitimate_typography_is_not_flagged():
    """En dashes, ellipses and curly apostrophes are correct text, not corruption."""
    text = "Width’s range – 10–20 m … see §6.5.3 • note"
    assert count_suspect_chars(text) == {}
    assert repair(text).repaired == text


def test_u2019_apostrophe_is_deliberately_left_alone():
    """U+2019 carries no digits and appears genuine; remapping it would only add risk."""
    assert "’" not in REPAIR_MAP
    assert repair("Resident’s").repaired == "Resident’s"


def test_unknown_corruption_is_reported_not_swallowed():
    """A pattern outside the map must surface, so the map can be extended from evidence."""
    r = repair("some ԁ text")  # Cyrillic, not in the map
    assert not r.is_clean
    assert "ԁ" in r.residual_suspect_chars
    assert describe_residual(r.residual_suspect_chars)[0].startswith("U+0501")


def test_corruption_rate_is_normalised():
    r = repair("ď" * 5 + "x" * 995)
    assert r.substitutions == 5
    assert r.corruption_rate == 5.0


# ------------------------------------------------------------------ against the corpus


@pytest.mark.skipif(not CORPUS.exists(), reason="corpus PDF not present")
class TestAgainstRealCorpus:
    @staticmethod
    def _pages() -> list[str]:
        import pypdf

        reader = pypdf.PdfReader(str(CORPUS))
        return [(p.extract_text() or "") for p in reader.pages]

    def test_corpus_is_actually_corrupted(self):
        """Guards the premise. If this fails, the document changed and docs need revisiting."""
        full = "\n".join(self._pages())
        assert count_suspect_chars(full), "expected encoding corruption in the corpus"

    def test_repair_leaves_nothing_suspect_behind(self):
        """The map must fully cover this corpus — no residue, no silent tolerance."""
        full = "\n".join(self._pages())
        r = repair(full)
        assert r.is_clean, f"unhandled corruption: {describe_residual(r.residual_suspect_chars)}"
        assert r.substitutions > 400

    def test_the_lake_buffer_clause_becomes_searchable(self):
        """The product-level assertion.

        Before repair, a user searching the corpus for "75 m buffer" finds nothing —
        the clause exists but is spelled ``7ϱ ŵ ďuffeƌ``. After repair it is findable.
        This is the difference between a citation that informs and one that misleads.
        """
        pages = self._pages()
        page_80 = pages[79]  # 6.5.3, eco-sensitive zones and water bodies

        assert "75 m buffer" not in page_80
        assert "no development zone" not in page_80

        fixed = repair(page_80).repaired
        assert "75 m buffer" in fixed
        assert "no development zone" in fixed
        assert "NGT" in fixed

    def test_stream_buffers_are_present_after_repair(self):
        fixed = repair(self._pages()[79]).repaired
        assert "50, 35 and 25 m" in fixed

    def test_far_acronym_is_recoverable(self):
        """``FA‘`` → ``FAR``: an acronym central to every question about buildable area."""
        full = repair("\n".join(self._pages())).repaired
        assert "FAR" in full
