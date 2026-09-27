"""Tests for structural-damage detection in extracted tables.

The corpus-backed tests are the ones that matter: this module exists because of a specific
real failure on page 57 of the Bengaluru RMP 2031 zoning regulations, and the test asserts
that exact page is caught.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest

from app.ingest.table_risk import (
    TableRiskLevel,
    analyse_page,
    page_risk,
)

CORPUS = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "corpus"
    / "bengaluru-rmp-2031-vol6-zoning-regulations.pdf"
)

# Verbatim from page 57, including the double-space that marks the blank TDR cell.
TABLE_6 = """Table 6: FAR and Ground Coverage for Plots/ Sites up to 20000 sqm for Planning Zone A
Sl.No. Plot/ Site
Size (sqm)
Maximum
Ground
Coverage
FAR Road Width
(m)
Base Allowable
against TDR/
any other
Rules
Total
Maximum
allowable
1 Up to 60 Up to 75 % 1.50  1.50 Below 6
2 Above 60 & Up to 120 Up to 75 % 1.50  1.50 6 and below
3 Above 120 & Up to 240 Up to 70 % 1.50  1.50 9.5 and below
5 Above 360 & up to 750 Up to 65 % 1.80 0.45 2.25 15.5 and below 18.5
6 Above 750 & up to 2000 Up to 60 % 1.80 0.60 2.40 18.5 and below 24.5
7 Above 2000 & up to 4000 Up to 50 % 1.80 0.70 2.50 24.5 and below 30.5
"""

CONSISTENT_TABLE = """Table 99: Consistent example
Sl.No. Item Base Total
1 Alpha 1.50 2.00 6.0
2 Beta 1.80 2.40 9.0
3 Gamma 2.00 2.60 12.0
4 Delta 2.20 2.80 15.0
"""

PROSE = """6.5.3 Regulations for Eco-sensitive Zones and Water Bodies including Valley/ Streams
i. Restrictions imposed by Competent Authorities are to be maintained as "buffers" for
various eco-sensitive zones. In case of water bodies a 75 m buffer of 'no development
zone' is to be maintained around the lake as per revenue records.
ii. The Streams have been categorized into 3 types namely Primary, Secondary and
Tertiary. These drains will have a buffer of 50, 35 and 25 m respectively.
"""


# ------------------------------------------------------------------------------ unit


def test_prose_produces_no_table_regions():
    """Most of the corpus is prose. A detector that fires here is useless."""
    assert analyse_page(PROSE) == []
    assert page_risk(PROSE) is TableRiskLevel.NONE


def test_empty_text_is_safe():
    assert analyse_page("") == []
    assert page_risk("") is TableRiskLevel.NONE


def test_consistent_table_is_not_flagged():
    regions = analyse_page(CONSISTENT_TABLE)
    assert len(regions) == 1
    assert regions[0].risk is TableRiskLevel.LOW
    assert not regions[0].is_risky
    assert regions[0].citation_warning() is None


def test_table_6_is_flagged_as_risky():
    """The motivating case: blank TDR cells make column binding impossible."""
    regions = analyse_page(TABLE_6)
    assert len(regions) == 1
    r = regions[0]
    assert r.is_risky
    assert r.table_number == 6
    assert r.inconsistent_rows, "expected rows disagreeing on decimal count"


def test_flagged_table_produces_an_actionable_warning():
    r = analyse_page(TABLE_6)[0]
    warning = r.citation_warning()
    assert warning is not None
    assert "column structure was lost" in warning
    assert "Read the source page" in warning


def test_warning_does_not_overclaim_column_knowledge():
    """The detector counts decimals; it must not imply it resolved columns.

    Guards against the module committing the error it exists to catch.
    """
    r = analyse_page(TABLE_6)[0]
    assert "decimal values" in r.explanation
    assert "which column those blanks belong to" in r.explanation


def test_too_few_rows_is_not_flagged():
    tiny = "Table 3: Two rows only\nSl No Base Total\n1 Alpha 1.50 2.00\n2 Beta 1.80\n"
    r = analyse_page(tiny)[0]
    assert r.risk is TableRiskLevel.NONE
    assert "Too few value rows" in r.explanation


def test_multiple_tables_on_one_page_are_separated():
    regions = analyse_page(TABLE_6 + "\n" + CONSISTENT_TABLE)
    assert len(regions) == 2
    assert {r.table_number for r in regions} == {6, 99}


def test_page_risk_reports_the_worst_table():
    assert page_risk(CONSISTENT_TABLE + "\n" + TABLE_6) in (
        TableRiskLevel.AMBIGUOUS_COLUMNS,
        TableRiskLevel.SEVERE,
    )


# --------------------------------------------------------------------- against corpus


@functools.lru_cache(maxsize=1)
def _corpus_pages() -> tuple[str, ...]:
    """Extract once and reuse — the full ingest is slow."""
    from app.ingest.pdf_extract import extract_document

    doc = extract_document(str(CORPUS), render_unreadable=False)
    return tuple(p.text if p.is_readable else "" for p in doc.pages)


@pytest.mark.skipif(not CORPUS.exists(), reason="corpus PDF not present")
class TestAgainstRealCorpus:
    def test_page_57_far_table_is_flagged(self):
        """Page 57 is classified readable and clean, yet is unsafe to quote."""
        regions = analyse_page(_corpus_pages()[56])
        far = [r for r in regions if r.table_number == 6]
        assert far, "Table 6 not found on page 57"
        assert far[0].is_risky

    def test_every_flagged_table_is_a_far_or_coverage_table(self):
        """Precision check: the flags land on the numbers that decide buildable area."""
        flagged = [
            r
            for text in _corpus_pages()
            if text
            for r in analyse_page(text)
            if r.is_risky
        ]
        assert flagged, "expected risky tables in the corpus"
        for r in flagged:
            cap = r.caption.lower()
            assert "far" in cap or "ground coverage" in cap, f"unexpected flag: {r.caption}"

    def test_prose_pages_in_the_corpus_are_not_flagged(self):
        """False-positive check on real prose, including the valley-zone clause page."""
        for page_number in (18, 27, 80):
            assert not [
                r for r in analyse_page(_corpus_pages()[page_number - 1]) if r.is_risky
            ], f"false positive on prose page {page_number}"
