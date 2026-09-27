# 14 — Decision Log

Decisions that shaped the product, with what was actually tried. Reverse chronological within
each phase. Entries marked **REVERSED** record things that were built and then removed —
those are the most useful ones.

---

## D-001 · Direction: regulatory evidence engine, not site scoring

**Date:** 2026-09-27 · **Status:** decided

The brief specified "SiteSignal" — site decision intelligence from public geospatial data.
Phase 0 research argued against the pure form of it for a reason I could measure rather than
assert: **the data that decides a project in this jurisdiction does not exist as an API.**

Zoning class, FAR, setbacks, valley-zone overlay, flood hazard and parcel geometry are all
unavailable as machine-readable sources (verified by probing; see `research.md` §5). What
*is* available — geocoding, OSM, ERA5, SRTM — describes context, not constraint.

Three further arguments:

1. **The lane is crowded and data-moated.** TestFit owns feasibility, Deepblocks parcel
   screening, Forma microclimate, Hypar zoning-as-code. All are strongest where codes are
   already digital — chiefly the US.
2. **Proximity is a weak insight.** "Within X of transit, therefore accessible, confidence
   medium" is something a professional knows by looking.
3. **Planso published its own live question.** Their AEC Product Intern application asks how
   you would test whether users *trust* question answering over project documents with
   source attribution. That is document-grounded answering, not site scoring.

**Decision:** build the regulatory evidence engine. Urval extended scope to include the site
workspace and comparison (see D-002).

**Would reverse if:** a reliable parcel-level zoning API appeared for this jurisdiction, which
would make the structured path viable and change the product's centre of gravity.

---

## D-002 · Scope: keep the site workspace and comparison

**Date:** 2026-09-27 · **Status:** decided by Urval

My recommendation was the narrow slice. Urval chose the broader version — evidence engine
plus workspace plus comparison. Defensible: the workspace makes the evidence layer legible in
context instead of presenting it as a bare QA box, and the empty constraints panel is where
the product's argument becomes *visible* rather than explained.

**Guard rail adopted:** no panel renders unless a real provider populated it. An empty state
that says "no open source covers this" ships; a panel filled with illustrative content does
not.

---

## D-003 · Four agents, not nine

**Date:** 2026-09-27 · **Status:** decided

The brief specified nine. Test applied to each: *does this module make a judgement that could
be wrong in an interesting way, and that another module could catch?*

`MOBILITY AGENT` fails — distance to a station is deterministic arithmetic over OSM, and
belongs in a provider. `CLIMATE AGENT` likewise. Four passed: Site, Regulation, Conflict,
Critic. Planso themselves use four families.

Nine modules over data sources that mostly do not exist is architecture theatre, and a
founder who has shipped AI products reads it as such immediately.

---

## D-004 · Site scoring — **REVERSED**

**Date:** 2026-09-27 · **Status:** built, then removed

A 0–100 composite per site was implemented. It demoed well. It was removed for three reasons,
in order of severity:

1. **The weights encode a thesis nobody stated.** Ranking accessibility against flood exposure
   against regulatory risk presumes a development intent. Two developers evaluating the same
   plot for a warehouse and a hospital should get different answers; neither should be 92.
2. **A score destroys the audit trail it sits on.** Once the number exists, nobody opens the
   evidence. The score becomes the product and the reasoning becomes decoration — which is
   exactly the failure this system exists to prevent.
3. **Most cells are genuinely unresolved.** Averaging over unknowns produces a number that
   looks more confident than any of its inputs.

**Replaced by:** an evidence matrix where each cell is traceable, plus a *coverage* row —
how many cells are facts, how many assumptions, how many unestablished. Coverage is
measurable; site quality is not.

**Unexpected benefit:** the comparison's most useful output turned out to be the line saying
the sites are **indistinguishable** on the constraint that decides. A score would have
manufactured a difference between them.

---

## D-005 · The valley-zone FAR figure — **ASSUMPTION FALSIFIED**

**Date:** 2026-09-27 · **Status:** corrected before it shipped

Assumption A5 in `research.md` §7: secondary sources state that plots in an RMP-2031 valley
zone face a **25–50% FAR reduction**. Two independent sources agreed. I flagged it as blocking
and checked it against the primary document.

**It is not in there.** RMP 2031 §6.5.3 (p. 80) says something categorically stricter: a
**75 m "no development zone"** around water bodies per the NGT Order, and **50/35/25 m**
buffers on primary/secondary/tertiary streams, within which the only permitted uses are
treatment plants and non-obstructing infrastructure.

A 25% FAR cut is a haircut. A 75 m no-development buffer means you cannot build there at all.

**Why this matters more than the correction:** I was about to build the demo's central conflict
on a real-estate blog's number. The only defence was reading the clause — which is precisely
what passage-level provenance is for. The product's argument, encountered first-hand, with me
as the user it would have saved.

---

## D-006 · BM25 over embeddings

**Date:** 2026-09-27 · **Status:** decided

Three reasons, all tied to what the product must prove:

1. **The questions are lexical.** Defined terms in a regulation are terms of art — *Floor Area
   Ratio*, *raja kaluve*, *no development zone*, *§6.5.3*. Matching them literally is a
   feature.
2. **It is gradeable with no model.** Retrieval quality is measurable against page-and-phrase
   ground truth with no API key, which is why this project's evaluation numbers are
   measurements rather than an unrun script.
3. **It is inspectable.** BM25 can show *which terms matched*. A cosine distance cannot be
   offered to a sceptical professional as justification.

Embeddings would genuinely help paraphrase-heavy questions and are scoped in
`15-future-roadmap.md`. Adding them before measuring the lexical baseline would be optimising
blind.

---

## D-007 · No agent framework

**Date:** 2026-09-27 · **Status:** decided

The DAG is static: fan out to two agents, join, then two sequential passes — about forty lines
of `asyncio`. LangChain or LangGraph would add a dependency tree, a new vocabulary, opaque
prompt construction and version churn, to solve a problem that does not exist here.

**Revisit if** the DAG becomes dynamic — an agent deciding at runtime which others to call.

---

## D-008 · Extractive mode as a first-class mode

**Date:** 2026-09-27 · **Status:** decided

No LLM key was available in the build environment. Rather than stub the agents, the product
was designed so **the guarantees live in the deterministic layer**: passage-level provenance,
blind-spot reporting, table-damage detection, epistemic typing and critic demotion all work
with no model at all.

This started as a constraint and became the better architecture. It inverts the usual
arrangement, where a model produces the answer and retrieval is bolted on to justify it
afterwards. Here the question "which parts stop working without the model?" has a precise
answer: the prose gets worse, and nothing else changes.

---

## D-009 · Three failure modes, and the one that matters

**Date:** 2026-09-27 · **Status:** foundational

Measured on the real corpus:

| Mode | Extent | Detectable? |
|---|---|---|
| Unreadable pages | 54 of 206 (73.8% coverage), incl. the 23-page TDR Rules 2016 | ✅ |
| Encoding corruption | 542 substitutions on 37 pages, **including digits** (`75 m` → `7ϱ ŵ`) | ✅ |
| Flattened tables | 6 FAR tables | ⚠️ **only heuristically** |

The third reframed the product. Page 57 classifies as readable and clean; every coverage
metric reports success; and the column structure that made its numbers meaningful is gone.
Rows 1–4 of Table 6 carry two FAR figures where rows 5–8 carry three, because the TDR cell is
blank — obvious in the PDF, invisible in flattened text. A 100 sqm plot reads as *total FAR
1.50* or *1.50 + 1.50 = 3.00* depending on how the columns bind. **A 2× error on the number
that decides what gets built.**

Modes 1 and 2 are survivable because the system knows. Mode 3 is the dangerous one, because
neither the system nor the reader does.

---

## D-010 · Claims I got wrong and corrected

**Date:** 2026-09-27 · **Status:** corrected

Recorded because the discipline matters more than the individual errors.

| Claim | Reality | How it was caught |
|---|---|---|
| "The FAR matrices are on image-only pages" | False. They are readable (pp. 57, 58, 65, 91, 96). pp. 106–128 are the scanned **TDR Rules**. | Opened the rendered pages instead of inferring from term frequency |
| "49 pages yield zero text" | 49 yield *zero*; 54 fall under the usability threshold | Ingestion pipeline measured it |
| "ERA5 drift is ~3 km" | 4.71 km at the reference site | The reproducible probe script |
| Valley zone → 25–50% FAR cut | Not in the document; the real rule is a 75 m no-development buffer | Checked the primary source (D-005) |

---

## D-011 · Blind-spot relevance: three rules tried, two rejected

**Date:** 2026-09-27 · **Status:** decided by measurement

A blind spot must be reported when the question bears on it, and stay quiet otherwise. A
warning that fires on coincidence teaches users to dismiss warnings, which costs more than the
missed blind spot it was trying to catch.

| Rule | TDR (want yes) | heritage | water (want no) | FAR-a (no) | FAR-b (no) | Separates? |
|---|---|---|---|---|---|---|
| ≥ 2 matched terms | yes | yes | yes | yes | yes | **no** |
| sum(idf) ≥ threshold | 11.20 | 3.59 | 4.10 | 4.96 | 3.74 | **no** — unwanted cases outscore a wanted one |
| **max(idf) ≥ 3.0** | **5.21** | 2.00 | 2.15 | 2.78 | 2.15 | **yes, cleanly** |

Summing rewards accumulating generic words, which is the coincidence being guarded against.
Requiring one *distinctive* term asks the right question.

**Accepted cost:** a heritage question no longer flags pp. 173–190 — the intended direction of
error, and the case was weak anyway (Annexure-5 starts at p. 191, so those pages are not the
heritage list they appeared to be). Recorded as a test so it cannot regress silently.

---

## D-012 · Evaluation-driven fixes, and where I stopped

**Date:** 2026-09-27 · **Status:** decided

The first evaluation run found four real bugs:

- **absence handling 0%** — asked "who owns this parcel?", the system returned §2.123 defining
  "site". BM25 always returns *something*, and presenting it as evidence manufactures coverage
  the document does not have. Fixed with an evidence floor (≥2 distinct matched terms, one
  distinctive): 20/20 genuine questions accepted, 2/3 absent rejected.
- **no stemming** — a question about a "drain" could not reach the clause defining "Drains/
  Halla". Present, indexed, unreachable.
- **table captions fused into 1,400-char chunks** — BM25 length normalisation buried Table 8
  entirely, though its caption names every word in the question.
- **table risk keyed to extracted numbers** — so when retrieval surfaced a table's *caption*
  (which ranks highest), the column-damage warning was absent.

Results moved: page recall 61.5 → 84.6%, phrase retrieval 76.9 → 92.3%, absence handling
0 → 66.7%, table damage detection 66.7 → 100%.

**Where I stopped, deliberately.** `citation_precision@1` sits at 61.5% against recall of
84.6% — the right page is retrieved, not always ranked first. And N01 ("market price per
square foot") still passes the absence filter on *market* and *square*, which genuinely occur
here. Both are reported rather than fixed: **tuning a threshold until a specific case goes
green produces a number that describes the threshold, not the system.**

---

## D-013 · Recorded provider responses, and why Demo Mode is not an animation

**Date:** 2026-09-27 · **Status:** decided under duress

All three public Overpass mirrors returned 504 or timed out simultaneously, repeatedly. A
cold analysis took **191 seconds** and came back without spatial context at all.

Diagnosis, eventually: not an outage. **Self-inflicted rate limiting** — Overpass allocates a
small number of concurrent slots per IP, and repeated full-pipeline runs exhausted them. Worse,
it signals this with an HTTP **200** carrying an HTML body, which surfaced several layers away
as a `JSONDecodeError` and looked like a parsing bug.

Fixes: per-provider throttling (3 s for Overpass), explicit detection of non-JSON bodies, and a
disk cache of verbatim responses. Cold analysis went from **191 s to 0.05 s**.

**Consequence for Demo Mode:** it replays real recorded responses with their capture timestamp
shown, rather than being a scripted animation. Fixtures are written only by the capture script
— never hand-authored — so "every value came from a real call on a real date" is a claim the
code enforces.

---

## D-014 · Basemap: two providers rejected

**Date:** 2026-09-27 · **Status:** decided

- **MapLibre demotiles** — only low-zoom country outlines. At city zoom the map rendered as a
  flat block of colour.
- **CARTO dark** — returns HTTP **200** for every tile, and at this zoom the body is a 2.5 KB
  "API KEY REQUIRED" watermark. A status-code health check calls that healthy; only comparing
  response *sizes* against a known-good provider exposed it.
- **Esri Dark Gray Canvas** — adopted. Street-level detail, no key, free for non-commercial
  use with attribution.

Key-free is a demo-reliability decision as much as a cost one.

---

## D-015 · In-memory corpus, no Postgres or PostGIS

**Date:** 2026-09-27 · **Status:** decided

The corpus is 7.5 MB, yields ~1,088 chunks, and serves in ~30 ms from a single process.
Postgres + pgvector would add a deployment dependency, a migration story and a network hop for
capability this scope does not use. PostGIS likewise: every geometry operation here is
point-buffer and distance, which Shapely does in-process.

**Revisit at:** multiple corpora, multiple tenants, or a corpus large enough that startup
ingestion becomes noticeable.
