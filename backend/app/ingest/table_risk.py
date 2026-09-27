"""Detect tables whose column structure was destroyed by text extraction.

## The failure this exists to catch

Of the three ways the corpus document defeats a retrieval pipeline, two are survivable:

* a page that yields no text is *detectable* — the system knows it is blind;
* text corrupted by a bad font encoding is *detectable and repairable* — see
  :mod:`app.ingest.text_repair`.

The third is not detectable by any coverage metric, and it is the one that causes harm.

Page 57 of the Bengaluru RMP 2031 corpus carries *Table 6: FAR and Ground Coverage*. The page
extracts cleanly. Every quality signal reports success. But a PDF table is a visual grid, and
text extraction flattens it into a stream, discarding the one thing that made it meaningful:
which value sits under which column.

The header declares three FAR sub-columns — ``Base``, ``Allowable against TDR/any other
Rules``, ``Total Maximum allowable``. Then::

    1 Up to 60           Up to 75 %  1.50        1.50   Below 6
    5 Above 360 & up to 750  Up to 65 %  1.80  0.45  2.25  15.5 and below 18.5

Row 5 has three FAR figures. Row 1 has **two**, because its TDR cell is blank — a blank that
is obvious to a human looking at the PDF and completely invisible in the flattened text.

For a 100 sqm plot the correct reading is *total FAR 1.50, no TDR uplift*. From the flat text
a model may equally read *base 1.50 + TDR 1.50 = 3.00*. **That is a 2× error on the number
that decides what can be built**, produced fluently, from a page that passes every check.

## What this module does, and what it deliberately does not

It detects **risk**, not error. It cannot recover the true grid — that needs layout-aware
extraction, which is future work (see ``docs/15-future-roadmap.md``). What it can do is
notice that a table's rows disagree about how many values they hold, and refuse to let a
citation from that table be presented as though it were unambiguous.

Being a heuristic, it is tuned to favour false negatives over false positives: flagging a
sound table as risky would train users to ignore the warning, which is worse than not warning
at all. Every flag carries the evidence that produced it so a user can judge for themselves.

## Known limitation, stated rather than buried

The detector counts **decimal values per row**. It does not know which column any value
belongs to — that binding is exactly what extraction destroyed, and recovering it is the
problem, not the method. So on Table 6 it counts road-width figures (``9.5``, ``15.5``)
alongside FAR figures, and reports a modal arity of 4 rather than the semantically
interesting 3.

The *conclusion* is unaffected: rows genuinely disagree, blanks genuinely exist, and the
table is genuinely unsafe to quote without checking the page. But the module reports what it
measured — inconsistent decimal counts — and does not dress that up as column analysis it did
not perform. Measured against the corpus this flags 6 tables, every one of them a FAR /
Ground Coverage table, with no false positives on prose pages.

Recovering true column binding requires layout-aware extraction (word bounding boxes rather
than a text stream). That is scoped in ``docs/15-future-roadmap.md``.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from enum import Enum

# A table is anchored by an explicit caption. Relying on the caption rather than on
# generic "looks tabular" heuristics is what keeps the false-positive rate near zero on
# prose pages, which make up most of the corpus.
_TABLE_CAPTION = re.compile(r"^\s*(Table\s+(\d+)\s*[:.]\s*(.+?))\s*$", re.MULTILINE)

# Decimal values are the payload of a regulatory table: FAR, coverage ratios, setbacks.
# Integers are excluded deliberately — serial numbers, plot sizes and road widths are
# integers, and counting them would drown the signal.
_DECIMAL = re.compile(r"(?<![\w.])\d+\.\d+(?![\w.])")

# A run of 2+ spaces in extracted text often marks a column boundary the extractor
# preserved. Where it sits between two decimals it is weak evidence of an empty cell.
_WIDE_GAP = re.compile(r"\d\.\d+(\s{2,})\d+\.\d")

# Sub-column headers seen in this corpus. Used to infer how many value columns a table
# *should* have, so observed arity can be compared against a declared expectation rather
# than only against other rows.
_SUBCOLUMN_HINTS = (
    "base",
    "total",
    "maximum allowable",
    "allowable against",
    "permissible",
    "minimum",
)

MIN_VALUE_ROWS = 3
"""Below this, row-to-row arity comparison is not statistically meaningful."""


class TableRiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    """Rows are consistent. No structural ambiguity detected."""

    AMBIGUOUS_COLUMNS = "ambiguous_columns"
    """Rows disagree on value count: at least one cell is blank and unattributable."""

    SEVERE = "severe"
    """Arity disagreement *and* the table declares named value sub-columns.

    The combination means a specific, nameable column cannot be bound — the case where a
    confident wrong answer is most likely and most costly.
    """


@dataclass
class ValueRow:
    """One candidate data row and the decimal values found in it."""

    line_number: int
    text: str
    values: list[float]
    has_wide_gap: bool

    @property
    def arity(self) -> int:
        return len(self.values)


@dataclass
class TableRegion:
    """A captioned table found on a page, with its structural assessment."""

    caption: str
    table_number: int | None
    start_line: int
    end_line: int
    header_text: str
    value_rows: list[ValueRow] = field(default_factory=list)
    declared_subcolumns: list[str] = field(default_factory=list)

    risk: TableRiskLevel = TableRiskLevel.NONE
    modal_arity: int | None = None
    inconsistent_rows: list[int] = field(default_factory=list)
    explanation: str = ""

    @property
    def is_risky(self) -> bool:
        return self.risk in (TableRiskLevel.AMBIGUOUS_COLUMNS, TableRiskLevel.SEVERE)

    def citation_warning(self) -> str | None:
        """Warning to attach to any claim quoting this table."""
        if not self.is_risky:
            return None
        return (
            f"{self.caption.strip()} — this table's column structure was lost during text "
            f"extraction. {self.explanation} A value quoted from it cannot be reliably "
            f"attributed to a specific column. Read the source page before relying on it."
        )


def _find_regions(text: str) -> list[tuple[str, int | None, int, int]]:
    """Locate captioned tables and their line spans."""
    lines = text.splitlines()
    anchors: list[tuple[int, str, int | None]] = []
    for i, line in enumerate(lines):
        m = _TABLE_CAPTION.match(line)
        if m:
            anchors.append((i, m.group(1).strip(), int(m.group(2))))

    regions = []
    for idx, (line_no, caption, number) in enumerate(anchors):
        end = anchors[idx + 1][0] - 1 if idx + 1 < len(anchors) else len(lines) - 1
        regions.append((caption, number, line_no, end))
    return regions


def _extract_value_rows(lines: list[str], start: int, end: int) -> list[ValueRow]:
    rows = []
    for i in range(start, min(end + 1, len(lines))):
        line = lines[i]
        values = [float(v) for v in _DECIMAL.findall(line)]
        if len(values) >= 2:  # a single decimal carries no column-binding information
            rows.append(
                ValueRow(
                    line_number=i,
                    text=line.strip(),
                    values=values,
                    has_wide_gap=bool(_WIDE_GAP.search(line)),
                )
            )
    return rows


def _declared_subcolumns(header: str) -> list[str]:
    low = header.lower()
    return [h for h in _SUBCOLUMN_HINTS if h in low]


def analyse_page(text: str) -> list[TableRegion]:
    """Find captioned tables on a page and assess each for structural damage."""
    lines = text.splitlines()
    out: list[TableRegion] = []

    for caption, number, start, end in _find_regions(text):
        value_rows = _extract_value_rows(lines, start, end)
        header_text = "\n".join(lines[start : min(start + 12, end + 1)])
        region = TableRegion(
            caption=caption,
            table_number=number,
            start_line=start,
            end_line=end,
            header_text=header_text,
            value_rows=value_rows,
            declared_subcolumns=_declared_subcolumns(header_text),
        )

        if len(value_rows) < MIN_VALUE_ROWS:
            region.risk = TableRiskLevel.NONE
            region.explanation = "Too few value rows to assess column consistency."
            out.append(region)
            continue

        arities = [r.arity for r in value_rows]
        modal = statistics.mode(arities)
        region.modal_arity = modal
        odd = [r.line_number for r in value_rows if r.arity != modal]
        region.inconsistent_rows = odd

        if not odd:
            region.risk = TableRiskLevel.LOW
            region.explanation = (
                f"All {len(value_rows)} value rows carry {modal} values — consistent."
            )
        else:
            short = [r for r in value_rows if r.arity < modal]
            gap_evidence = sum(1 for r in short if r.has_wide_gap)
            named = region.declared_subcolumns
            region.risk = (
                TableRiskLevel.SEVERE if len(named) >= 2 else TableRiskLevel.AMBIGUOUS_COLUMNS
            )
            # Deliberately phrased as "decimal values per row" rather than "columns".
            # The detector counts decimals; it does not know which column each belongs to
            # — that binding is precisely what extraction destroyed. Claiming more than
            # was measured here would repeat the error the module exists to catch.
            detail = (
                f"{len(odd)} of {len(value_rows)} rows contain a different count of decimal "
                f"values than the majority ({modal} per row); {len(short)} row(s) contain "
                f"fewer, which implies blank cells. Because the grid is gone, the extracted "
                f"text does not say which column those blanks belong to."
            )
            if named:
                detail += (
                    f" The caption block declares multiple value sub-columns "
                    f"({', '.join(named)}), so a reader must bind each number to a named "
                    f"column — the binding that was lost."
                )
            if gap_evidence:
                detail += (
                    f" Column whitespace survived on {gap_evidence} short row(s), weak "
                    f"corroboration of an empty cell rather than a missing number."
                )
            region.explanation = detail

        out.append(region)

    return out


def page_risk(text: str) -> TableRiskLevel:
    """Highest risk level present on a page. Convenience for indexing."""
    regions = analyse_page(text)
    if any(r.risk is TableRiskLevel.SEVERE for r in regions):
        return TableRiskLevel.SEVERE
    if any(r.risk is TableRiskLevel.AMBIGUOUS_COLUMNS for r in regions):
        return TableRiskLevel.AMBIGUOUS_COLUMNS
    if regions:
        return TableRiskLevel.LOW
    return TableRiskLevel.NONE
