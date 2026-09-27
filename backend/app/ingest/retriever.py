"""Lexical retrieval over a chunked regulation, with blind spots as first-class output.

## Why BM25 and not embeddings

Embedding search is the reflex choice. For this corpus it is the wrong one, for three
reasons that all come back to what the product has to prove:

1. **The questions are lexical.** Real questions here name things exactly: "FAR for a
   500 sqm plot in Zone A", "buffer for a secondary stream", "TDR rules", "§6.5.3". Defined
   terms in a regulation are terms of art — *Floor Area Ratio*, *raja kaluve*, *no
   development zone* — and matching them literally is a feature, not a limitation.
2. **It is gradeable without an LLM.** Retrieval quality can be measured against
   hand-built ground truth (does the retrieved span contain the governing clause?) with no
   model in the loop and no API key. That matters: it means the evaluation numbers in this
   project are real measurements rather than an unrun script.
3. **It is inspectable.** When BM25 returns a passage, the reason is visible — these terms
   matched, with these weights. An embedding's reason is a cosine distance, which cannot be
   shown to a sceptical professional as justification.

Embeddings are a genuine improvement for paraphrase-heavy questions and are scoped as
future work in ``docs/15-future-roadmap.md``. They are not a prerequisite for the thesis,
and adding them before measuring the lexical baseline would be optimising blind.

## Blind spots are results

The distinguishing behaviour: a retriever that silently omits what it cannot read produces
confident answers over a corpus with holes in it. This one indexes unreadable pages as
placeholder chunks and reports, with every result set, which regions of the document bear on
the query but could not be read. A question about Transferable Development Rights over this
corpus should return *"the governing instrument is 23 scanned pages I cannot parse"* — not a
plausible answer assembled from the prose that happens to surround it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from app.ingest.chunker import Chunk
from app.ingest.pdf_extract import PageQuality

# Split on non-alphanumerics but keep decimals intact: "1.50" and "6.5.3" are meaningful
# tokens in this corpus, and splitting them would destroy the most precise query terms.
_TOKEN = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)*")

_STOPWORDS = frozenset(
    """a an the of for to in on at by and or as be is are was were shall may can with
    which that this these those such any all not no if then than from into within under
    over per it its their there here have has had been being do does did""".split()
)

# Domain synonyms. A planner asks about "setback"; the document may say "margin". Expansion
# is conservative and one-directional: it only adds terms, never replaces the user's.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "far": ("floor", "area", "ratio"),
    "tdr": ("transferable", "development", "rights"),
    "setback": ("margin", "setbacks"),
    "buffer": ("buffers", "zone"),
    "coverage": ("ground",),
    "height": ("storeys", "floors"),
    "parking": ("parkings",),
    "lake": ("water", "bodies", "tank"),
    "drain": ("stream", "valley", "kaluve", "halla"),
    "plot": ("site", "sites", "plots"),
    # Expansion must run in BOTH directions. A regulation writes the acronym ("ToD Zones",
    # "FAR") while a professional asks in words ("transit oriented development"), and an
    # expansion that only unfolds acronyms leaves the reverse query unmatched — which is
    # how a question about transit-oriented development missed the section defining it.
    "transit": ("tod",),
    "oriented": ("tod",),
    "transferable": ("tdr",),
    "floor": ("far",),
    "ratio": ("far",),
}

# Queries asking what a term *means* rather than what rule applies to it. A regulation
# keeps its definitions in a dedicated chapter, and the defined term appears far more often
# in the substantive clauses that use it than in the one clause that defines it — so plain
# term-frequency ranking reliably buries the definition. This is a general property of
# legal documents, not a quirk of this corpus.
_DEFINITION_INTENT = re.compile(
    r"\b(define[sd]?|definition|what is (a|an|the)\b|what does .{1,30} mean|meaning of)\b",
    re.IGNORECASE,
)

DEFINITION_BOOST = 2.0
"""Multiplier applied to definition chunks when the query asks for a definition."""

# How this corpus writes a definition: "2.83 Lakes: means, inland water-body ..." —
# a clause number, the defined term, a colon, then "means".
_DEFINITION_CLAUSE = re.compile(r"\d+\.\d+\s+[A-Z][^:\n]{1,60}:\s*means", re.IGNORECASE)


DISTINCTIVE_IDF = 3.0
"""Inverse-document-frequency above which a single term carries real signal.

Calibrated against this corpus, where distinctiveness separates cleanly at 3.0: "zone"
(1.95), "development" (2.05) and "heritage" (2.00) each appear on 130+ chunks, while
"rights" (5.21), "buffer" (4.47) and "rules" (3.94) appear on fewer than 20. A corpus with
different term statistics needs this re-measured, not re-guessed.
"""

# A blind region is reported only when the query shares at least one genuinely distinctive
# term with the text leading into it. Two weaker rules were tried and measured first:
#
#   rule                     TDR    heritage  water   FAR-a   FAR-b     separates?
#   ------------------------ -----  --------  ------  ------  --------  ----------
#   >= 2 matched terms       yes    yes       yes     yes     yes       no
#   sum(idf) >= threshold    11.20   3.59      4.10    4.96    3.74     NO — the
#                                                                       unwanted cases
#                                                                       outscore a wanted
#                                                                       one
#   max(idf) >= 3.0           5.21   2.00      2.15    2.78    2.15     yes, cleanly
#
# Summing rewards accumulating generic words, which is exactly the coincidence being
# guarded against. Requiring one distinctive term asks the right question: does this
# question share vocabulary with that region that it would not share with any region?
#
# The cost is a known false negative — a heritage question no longer flags pages 173-190.
# That is the intended direction of error (see the module docstring), and the case was
# always weak: Annexure-5 actually begins on page 191, so those pages are not the heritage
# list they appeared to be.
MIN_DISTINCTIVE_TERMS = 1


def _stem(word: str) -> str | None:
    """Crude plural stripping — enough to match a query term to its inflected form.

    Not a linguistic stemmer, deliberately. A regulation asks to be matched on exact terms
    of art, and aggressive stemming ("building" → "build") would blur distinctions the
    document depends on. Plurals are the one inflection that reliably blocks a correct
    match: a question about a "drain" must find the clause defining "Drains/ Halla", and
    without this it does not — a real evaluation failure, where the governing definition
    was present, indexed and unreachable.

    Returns None when there is nothing to strip.
    """
    if len(word) <= 3 or not word.isalpha():
        return None
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return None


def tokenize(text: str) -> list[str]:
    """Tokens plus their singular forms, so a query matches inflected text."""
    out: list[str] = []
    for match in _TOKEN.finditer(text):
        token = match.group(0).lower()
        if token in _STOPWORDS or (len(token) <= 1 and not token.isdigit()):
            continue
        out.append(token)
        if (stem := _stem(token)) and stem not in _STOPWORDS:
            out.append(stem)
    return out


def expand_query(tokens: list[str]) -> list[str]:
    out = list(tokens)
    for t in tokens:
        out.extend(_SYNONYMS.get(t, ()))
    return out


@dataclass
class RetrievalHit:
    """One retrieved chunk, with everything a citation needs."""

    chunk: Chunk
    score: float
    matched_terms: list[str] = field(default_factory=list)

    @property
    def is_blind_spot(self) -> bool:
        return self.chunk.page_quality is PageQuality.UNREADABLE

    def why_matched(self) -> str:
        """Plain-language justification, shown in the evidence inspector."""
        if self.is_blind_spot:
            return f"Page {self.chunk.page_number} is adjacent to matching content but is unreadable."
        terms = ", ".join(sorted(set(self.matched_terms))[:8])
        return f"Matched on: {terms}"


@dataclass
class BlindSpot:
    """A region of the document bearing on the query that could not be read.

    Blind spots are matched against the query directly, not merely reported when they
    happen to sit near a hit. The reason is a failure found while building this: asking
    *"what are the TDR rules?"* over this corpus returned passages about tree plantation,
    because the 23-page statutory instrument that actually governs TDR is scanned and
    therefore invisible to ranking. Proximity-based detection then pointed at an unrelated
    scanned page near one of the wrong hits.

    A blind spot nobody can retrieve is not reported uncertainty — it is a hole the system
    does not know it has. So each unreadable region is given a *descriptor* built from the
    readable text that introduces it (a heading, an annexure title, the tail of the previous
    page), and that descriptor is searchable.
    """

    page_start: int
    page_end: int
    reason: str
    descriptor: str = ""
    """Readable text immediately BEFORE this region — what leads into it.

    This is what the region is matched on. It is not a claim about the region's contents:
    nothing can be known about pages that cannot be read. It is the last thing the document
    said before going dark, which for an annexure is usually its title.
    """

    following_context: str = ""
    """Readable text immediately AFTER the region. Shown to the user, never scored.

    Text after a gap frequently begins something new rather than describing what was
    missed — page 191 opens "ANNEXURE-5 List of Heritage Buildings", which is the section
    *after* pages 173-190, not a description of them. Scoring on it made a TDR question
    flag pages 103-104, because the page following them happens to announce Annexure-1.
    """

    match_score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    query_relevant: bool = False
    """Whether this region cleared the relevance bar for *this* query.

    Recorded rather than derived from ``match_score > 0``. A region can be reported because
    it sits near a hit while scoring below the distinctiveness threshold, and counting such
    a region as query-relevant inflated a coverage note from "23 pages" to "24 pages across
    2 regions" on the TDR question. An honesty feature that overstates is still inaccurate.
    """

    nearest_readable_context: str | None = None

    @property
    def page_count(self) -> int:
        return self.page_end - self.page_start + 1

    @property
    def is_query_relevant(self) -> bool:
        return self.query_relevant

    def describe(self) -> str:
        pages = (
            f"page {self.page_start}"
            if self.page_start == self.page_end
            else f"pages {self.page_start}–{self.page_end} ({self.page_count} pages)"
        )
        base = f"{pages}: {self.reason}."
        if self.descriptor:
            base += f" The text immediately before it reads: “{self.descriptor[:200]}”"
        if self.following_context:
            base += f" The text immediately after it reads: “{self.following_context[:160]}”"
        return base


@dataclass
class RetrievalResult:
    """Results plus an honest account of what was not searchable."""

    query: str
    hits: list[RetrievalHit]
    blind_spots: list[BlindSpot] = field(default_factory=list)
    total_indexed_chunks: int = 0
    unreadable_page_count: int = 0

    @property
    def readable_hits(self) -> list[RetrievalHit]:
        return [h for h in self.hits if not h.is_blind_spot]

    @property
    def has_usable_evidence(self) -> bool:
        return bool(self.readable_hits)

    @property
    def risky_table_hits(self) -> list[RetrievalHit]:
        return [
            h
            for h in self.readable_hits
            if h.chunk.table_risk in ("ambiguous_columns", "severe")
        ]

    @property
    def relevant_blind_spots(self) -> list[BlindSpot]:
        """Blind spots the query actually bears on, as opposed to ones merely near a hit."""
        return [b for b in self.blind_spots if b.is_query_relevant]

    def coverage_note(self) -> str | None:
        """The sentence shown above an answer when evidence is incomplete.

        Counts only query-relevant regions. Counting every unreadable page near any hit
        inflated this to "30 pages" on a question whose actual blind spot was 23 — and an
        honesty feature that overstates is still inaccurate.
        """
        relevant = self.relevant_blind_spots
        if not relevant:
            return None
        pages = sum(b.page_count for b in relevant)
        regions = len(relevant)
        where = ", ".join(
            f"pp. {b.page_start}-{b.page_end}" if b.page_count > 1 else f"p. {b.page_start}"
            for b in relevant[:3]
        )
        return (
            f"{pages} page(s) of this document bearing on your question could not be read "
            f"({regions} region(s): {where}) and are not included in the evidence below."
        )


class RegulationIndex:
    """BM25 index over chunks, aware of what it cannot see.

    BM25 is implemented directly rather than pulled from a dependency: it is ~30 lines, and
    owning it means the matched terms behind every hit can be surfaced in the UI, which an
    opaque `get_scores()` call does not give.
    """

    K1 = 1.5
    B = 0.75

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._tokens: list[list[str]] = [tokenize(c.text) for c in chunks]
        self._lengths = [len(t) for t in self._tokens]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0

        self._tf: list[dict[str, int]] = []
        self._df: dict[str, int] = {}
        for toks in self._tokens:
            counts: dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self._tf.append(counts)
            for t in counts:
                self._df[t] = self._df.get(t, 0) + 1

        self._n = len(chunks)
        self._unreadable_pages = sorted(
            {c.page_number for c in chunks if c.page_quality is PageQuality.UNREADABLE}
        )
        self._blind_regions = self._build_blind_regions()

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def _score(self, idx: int, terms: list[str]) -> tuple[float, list[str]]:
        tf = self._tf[idx]
        length = self._lengths[idx] or 1
        score = 0.0
        matched: list[str] = []
        for term in terms:
            f = tf.get(term, 0)
            if not f:
                continue
            matched.append(term)
            idf = self._idf(term)
            score += idf * (f * (self.K1 + 1)) / (
                f + self.K1 * (1 - self.B + self.B * length / (self._avg_len or 1))
            )
        return score, matched

    # --- blind regions -------------------------------------------------------------

    def _readable_text_on(self, page_number: int) -> str:
        return " ".join(
            " ".join(c.text.split())
            for c in self.chunks
            if c.page_number == page_number and c.page_quality is not PageQuality.UNREADABLE
        )

    def _build_blind_regions(self) -> list[BlindSpot]:
        """Collapse unreadable pages into runs and give each a searchable descriptor.

        The descriptor comes from the readable text that introduces the region — for the
        TDR annexe that is page 105's closing line, *"Annexure-1: Government Notification
        ... Karnataka Town and Country Planning (Benefit of Development Rights) Rules,
        2016"*. That sentence is what makes the blind spot findable by someone asking about
        TDR, which is the whole point.
        """
        if not self._unreadable_pages:
            return []

        runs: list[tuple[int, int]] = []
        start = prev = self._unreadable_pages[0]
        for p in self._unreadable_pages[1:]:
            if p == prev + 1:
                prev = p
                continue
            runs.append((start, prev))
            start = prev = p
        runs.append((start, prev))

        regions: list[BlindSpot] = []
        for first, last in runs:
            # Prefer the tail of the preceding readable page; fall back to the head of the
            # following one, which is how the heritage annexure identifies itself.
            before = self._readable_text_on(first - 1)
            after = self._readable_text_on(last + 1)
            descriptor = before[-260:].strip() if before else ""
            following = after[:200].strip() if after else ""

            regions.append(
                BlindSpot(
                    page_start=first,
                    page_end=last,
                    reason="no machine-readable text; scanned pages or drawings",
                    descriptor=descriptor,
                    following_context=following,
                    nearest_readable_context=before[-180:] if before else None,
                )
            )
        return regions

    def _match_blind_regions(self, terms: list[str], hit_pages: set[int]) -> list[BlindSpot]:
        """Score blind regions against the query, and also include any near a hit.

        Two routes to being reported, because they catch different things: descriptor
        matching finds the region a question is *about*, proximity finds the region a good
        answer happens to sit next to.
        """
        out: list[BlindSpot] = []
        term_set = set(terms)

        for region in self._blind_regions:
            desc_tokens = tokenize(region.descriptor)
            if not desc_tokens:
                matched: list[str] = []
                score = 0.0
            else:
                counts: dict[str, int] = {}
                for t in desc_tokens:
                    counts[t] = counts.get(t, 0) + 1
                matched = sorted(term_set & counts.keys())
                # Weight by idf so common words ("development") do not dominate, and
                # normalise by descriptor length.
                score = sum(self._idf(t) * counts[t] for t in matched) / (
                    1 + math.log(1 + len(desc_tokens))
                )

            # A blind spot must clear a relevance bar before it is called query-relevant.
            # Without one, asking about a lake buffer flagged an 18-page heritage annexe
            # because both mention "site" and "zone". A warning that fires on coincidence
            # teaches users to dismiss warnings, which costs more than the missed blind spot
            # it was trying to catch.
            distinctive = [t for t in matched if self._idf(t) >= DISTINCTIVE_IDF]
            is_relevant = len(distinctive) >= MIN_DISTINCTIVE_TERMS

            near_hit = any(
                region.page_start - 3 <= hp <= region.page_end + 3 for hp in hit_pages
            )
            if (score > 0 and is_relevant) or near_hit:
                out.append(
                    BlindSpot(
                        page_start=region.page_start,
                        page_end=region.page_end,
                        reason=region.reason,
                        descriptor=region.descriptor,
                        following_context=region.following_context,
                        match_score=round(score, 4),
                        matched_terms=matched,
                        query_relevant=bool(score > 0 and is_relevant),
                        nearest_readable_context=region.nearest_readable_context,
                    )
                )

        # Query-relevant regions first, then largest — a 23-page hole outranks a 1-page one.
        out.sort(key=lambda b: (not b.query_relevant, -b.match_score, -b.page_count))
        return out

    def search(self, query: str, *, top_k: int = 8) -> RetrievalResult:
        terms = expand_query(tokenize(query))
        wants_definition = bool(_DEFINITION_INTENT.search(query))

        scored: list[tuple[float, int, list[str]]] = []
        for i in range(self._n):
            # Placeholder chunks for unreadable pages carry no real content and would
            # otherwise pollute ranking. They surface via blind-spot detection instead.
            if self.chunks[i].page_quality is PageQuality.UNREADABLE:
                continue
            s, matched = self._score(i, terms)
            if s <= 0:
                continue
            if wants_definition and _DEFINITION_CLAUSE.search(self.chunks[i].text):
                s *= DEFINITION_BOOST
            scored.append((s, i, matched))

        scored.sort(key=lambda x: (-x[0], x[1]))
        hits = [
            RetrievalHit(chunk=self.chunks[i], score=round(s, 4), matched_terms=m)
            for s, i, m in scored[:top_k]
        ]

        hits = self._apply_evidence_floor(hits)

        hit_pages = {h.chunk.page_number for h in hits}
        return RetrievalResult(
            query=query,
            hits=hits,
            blind_spots=self._match_blind_regions(terms, hit_pages),
            total_indexed_chunks=self._n,
            unreadable_page_count=len(self._unreadable_pages),
        )

    def _apply_evidence_floor(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        """Drop everything when the best match is too weak to count as evidence.

        BM25 always returns *something*. Asked "who currently owns this parcel?", this
        corpus happily returns §2.123 defining the word "site" — a real passage, correctly
        retrieved, that does not address the question at all. Presenting it as evidence
        manufactures coverage the document does not have, which is the failure this product
        exists to prevent, committed by the product itself.

        The floor asks the same question used for blind spots: does the top passage share
        at least two terms with the query, one of them distinctive? Measured across the
        evaluation set, that accepts 20/20 genuine questions and rejects 2 of 3 questions
        the document does not address.

        The third — "current market price per square foot" — still slips through on
        ``market`` and ``square``, which do occur here. That is recorded as a known
        limitation in ``docs/11-ai-evaluation.md`` rather than fixed by lowering the bar
        until the case passes: tuning a threshold against a specific test until it goes
        green produces a number that describes the threshold, not the system.
        """
        if not hits:
            return hits
        top = hits[0]
        distinctive = [t for t in top.matched_terms if self._idf(t) >= DISTINCTIVE_IDF]
        if len(set(top.matched_terms)) >= 2 and distinctive:
            return hits
        return []
