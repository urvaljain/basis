"""Repair systematically mis-encoded text extracted from PDFs.

## Why this module exists

The Bengaluru RMP 2031 zoning regulations PDF extracts text successfully — and the text
is wrong. A custom font encoding without a correct `ToUnicode` CMap means pypdf recovers
glyph codepoints rather than characters, so the document extracts as::

    Restrictions imposed ďǇ CoŵpeteŶt Authoƌities aƌe to ďe ŵaiŶtaiŶed as ͞ďuffeƌs͟
    ...
    IŶ Đase of ǁateƌ ďodies a 7ϱ ŵ ďuffeƌ of ͚Ŷo deǀelopŵeŶt zoŶe͛

That reads as noise, but it is worse than noise: **the corruption reaches inside the
numbers**. `7ϱ ŵ` is `75 m`. In a document where the digits *are* the regulation, a
pipeline that ignores this will:

1. pass a "did we extract text?" check, because it did;
2. embed and index partly-garbage tokens;
3. miss the clause entirely on a keyword search for ``75 m buffer``;
4. and, if it does retrieve the passage, quote ``7ϱ ŵ ďuffeƌ`` to the user as verbatim
   evidence.

Step 4 is the dangerous one. A citation the user cannot read is worse than no citation:
it looks like diligence and transmits nothing.

## Why the mapping is derived, not guessed

The substitutions were established from context across the whole corpus, not inferred
from one example. Each entry in ``_LETTER_MAP`` below carries the evidence that fixes
it. Two were genuinely ambiguous and needed resolving before they could be trusted:

* ``U+201C “`` is normally a left double quotation mark. Here it is the letter **S** —
  ``“ultaŶ͛s`` → ``Sultan's``, ``“uŵŵeƌ`` → ``Summer``, ``“t.Joseph͛s`` → ``St.Joseph's``,
  ``“Đhool`` → ``School``. Real double quotes in this document are encoded as U+035E/U+035F
  instead, which is what makes the substitution unambiguous.
* ``U+2018 ‘`` is normally a left single quotation mark. Here it is the letter **R** —
  ``FA‘`` → ``FAR``, ``‘esideŶtial`` → ``Residential``, ``‘egulations`` → ``Regulations``.

The digits are not ad-hoc at all: ``U+03EC + d`` encodes digit ``d`` for 0–9, a clean
sequential offset that confirms this is a systematic encoding fault rather than damage.

``U+2019 ’`` is deliberately **not** remapped. It appears to be a genuine apostrophe and
carries no digits, so touching it would risk corrupting correct text to fix nothing.

## The rule this module does not break

Repair is never silent. :func:`repair` returns a :class:`RepairResult` that keeps the raw
text alongside the repaired text and counts every substitution. Callers persist both, and
the UI shows the user that a quoted passage was repaired, with the raw extraction one click
away. Rewriting a legal quotation and presenting the result as verbatim would be precisely
the kind of invisible transformation this product exists to argue against.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Letter substitutions. The comment on each line is the corpus evidence for it.
_LETTER_MAP: dict[str, str] = {
    "ď": "b",  # ď  Taďle → Table,          ďuffeƌs → buffers
    "Đ": "c",  # Đ  Đoǀeƌage → coverage,     IŶ Đase → In case
    "ŵ": "m",  # ŵ  deǀelopŵeŶt → development, sƋŵ → sqm
    "Ŷ": "n",  # Ŷ  thaŶ → than,             ŶoŶ → non
    "ƌ": "r",  # ƌ  foƌ → for,               otheƌ → other
    "Ƌ": "q",  # Ƌ  sƋŵ → sqm
    "ǀ": "v",  # ǀ  Đoǀeƌage → coverage,     oǀeƌ → over
    "ǁ": "w",  # ǁ  ǁith → with
    "ǆ": "x",  # ǆ  fiǆtuƌes → fixtures
    "Ǉ": "y",  # Ǉ  ďǇ → by,                 ĐoŶditioŶalitǇ → conditionality
    "“": "S",  # “  “ultaŶ͛s → Sultan's,     “Đhool → School,  “DZ → SDZ
    "‘": "R",  # ‘  FA‘ → FAR,               ‘esideŶtial → Residential
}

# Digits: U+03EC + d encodes digit d. Sequential, hence systematic.
_DIGIT_MAP: dict[str, str] = {chr(0x03EC + d): str(d) for d in range(10)}

# Punctuation. U+037E is GREEK QUESTION MARK, which merely *looks* like a semicolon —
# remapping it cannot damage a real ASCII ';'.
_PUNCT_MAP: dict[str, str] = {
    "͞": '"',  # ͞  opening double quote
    "͟": '"',  # ͟  closing double quote
    "͚": "'",  # ͚  opening single quote
    "͛": "'",  # ͛  closing single quote
    ";": "(",  # ;  ;CoŵŵoŶ → (Common
    "Ϳ": ")",  # Ϳ  RegulatioŶsͿ → Regulations)
}

REPAIR_MAP: dict[str, str] = {**_LETTER_MAP, **_DIGIT_MAP, **_PUNCT_MAP}

_TRANSLATION = str.maketrans(REPAIR_MAP)

# Codepoints that should never survive in an English-language legal document. Used to
# detect corruption and, after repair, to assert none was left behind. Legitimate
# typography (en dash, ellipsis, curly apostrophe, bullet, non-breaking hyphen) is
# excluded by construction.
_LEGITIMATE_NON_ASCII = frozenset("–—…‘’“”•‐°²³½¼¾×§")

# Ranges enumerated explicitly rather than "anything non-ASCII", because a user-uploaded
# document may legitimately contain Kannada, Devanagari or accented proper nouns, and
# flagging those as corruption would be a false alarm in exactly the workflow this product
# serves. These are the blocks that carry PDF glyph-mapping noise.
_SUSPECT_RANGES = (
    (0x0100, 0x017F),  # Latin Extended-A
    (0x0180, 0x024F),  # Latin Extended-B
    (0x0250, 0x02AF),  # IPA Extensions
    (0x02B0, 0x02FF),  # Spacing Modifier Letters
    (0x0300, 0x036F),  # Combining Diacritical Marks
    (0x0370, 0x03FF),  # Greek and Coptic
    (0x0400, 0x052F),  # Cyrillic *and* Cyrillic Supplement (0x0500-0x052F)
    (0x1E00, 0x1EFF),  # Latin Extended Additional
    (0x2C60, 0x2C7F),  # Latin Extended-C
    (0xA720, 0xA7FF),  # Latin Extended-D
)


def _is_suspect(ch: str) -> bool:
    if ch in _LEGITIMATE_NON_ASCII:
        return False
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in _SUSPECT_RANGES)


@dataclass(frozen=True)
class RepairResult:
    """Repaired text plus everything needed to audit the repair.

    ``raw`` is retained so the UI can always show the user what was actually extracted.
    A repaired quotation is still a transformation, and the product's own rules require
    transformations to be visible.
    """

    raw: str
    repaired: str
    substitutions: int
    distinct_substitutions: int
    residual_suspect_chars: dict[str, int] = field(default_factory=dict)

    @property
    def was_repaired(self) -> bool:
        return self.substitutions > 0

    @property
    def is_clean(self) -> bool:
        """True when nothing suspect survived the repair.

        A False value means the corpus contains a corruption pattern this module does
        not yet know about. That is a signal to extend the map from evidence — never a
        signal to suppress the warning.
        """
        return not self.residual_suspect_chars

    @property
    def corruption_rate(self) -> float:
        """Substitutions per 1,000 characters — comparable across documents."""
        if not self.raw:
            return 0.0
        return round(1000 * self.substitutions / len(self.raw), 3)


def count_suspect_chars(text: str) -> dict[str, int]:
    """Tally characters that indicate an encoding fault, keyed by character."""
    counts: dict[str, int] = {}
    for ch in text:
        if _is_suspect(ch):
            counts[ch] = counts.get(ch, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def repair(text: str) -> RepairResult:
    """Apply the derived substitution map, reporting exactly what changed.

    The repair is a pure character translation: it never reflows, re-wraps, spell-checks
    or paraphrases. Character offsets are therefore preserved one-to-one between ``raw``
    and ``repaired``, which is what allows a citation's character span to remain valid
    against either version.
    """
    if not text:
        return RepairResult(raw=text, repaired=text, substitutions=0, distinct_substitutions=0)

    substitutions = sum(text.count(bad) for bad in REPAIR_MAP)
    distinct = sum(1 for bad in REPAIR_MAP if bad in text)
    repaired = text.translate(_TRANSLATION)

    return RepairResult(
        raw=text,
        repaired=repaired,
        substitutions=substitutions,
        distinct_substitutions=distinct,
        residual_suspect_chars=count_suspect_chars(repaired),
    )


def describe_residual(counts: dict[str, int]) -> list[str]:
    """Human-readable lines for suspect characters the map did not cover.

    Surfaced in the ingestion report so an unknown corruption pattern is visible rather
    than silently tolerated.
    """
    return [
        f"U+{ord(ch):04X} {ch!r} ×{n} ({unicodedata.name(ch, 'unnamed')})"
        for ch, n in counts.items()
    ]


# Raw→expected pairs taken verbatim from the corpus. These are the clauses a reader will
# act on (the numeric buffer widths in RMP 2031 §6.5.3), so they get an explicit check
# rather than an assumption. Asserted in tests and by the ingest report.
CANONICAL_PROBES: tuple[tuple[str, str], ...] = (
    ("7ϱ ŵ ďuffeƌ", "75 m buffer"),
    ("ďǇ CoŵpeteŶt Authoƌities", "by Competent Authorities"),
    ("ŵaiŶtaiŶed as ͞ďuffeƌs͟", 'maintained as "buffers"'),
    ("Ŷo deǀelopŵeŶt zoŶe", "no development zone"),
    ("FA‘", "FAR"),
    ("ϱϬ", "50"),
)


def find_numeric_clauses(text: str) -> list[tuple[str, int]]:
    """Locate ``<number> m`` measurements and their offsets.

    Used by the ingest report to confirm that numeric regulatory limits survive repair —
    these are the values a reader will act on, so they get an explicit check rather than
    an assumption.
    """
    return [(m.group(0), m.start()) for m in re.finditer(r"\b\d{1,4}(?:\.\d+)?\s?m\b", text)]
