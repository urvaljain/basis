# 01 — Product Thesis

## The thesis

> A built-environment decision fails not because the evidence was missing, but because the
> evidence that mattered never met the evidence that contradicted it — and nobody could tell,
> at the moment of deciding, which parts were measured, which were inferred, and which were
> guessed.

**Basis is built on one bet: the valuable output of an AI system in a high-stakes workflow is
not the answer. It is the answer plus everything that could make the answer wrong.**

## Why this and not "site evaluation"

The original brief for this project was site decision intelligence — evaluate a location,
surface opportunities and risks from public data. Phase 0 research killed the pure form of
that idea, for a reason I could measure rather than argue:

**The data that decides a project in this jurisdiction does not exist as an API.**

Zoning class, FAR, setbacks, valley-zone overlay, flood hazard, parcel geometry — none are
machine-queryable in India (see `research.md` §5, reproducible via
`data/probes/probe_sources.py`). What *is* queryable is context: geocoding, OSM features,
ERA5 climate, SRTM elevation. All real, all verified, all working.

So a public-data site evaluator is confident about distance to a bus stop and silent about
whether you may build at all. It answers the easy half loudly.

The constraint layer exists. It is a 206-page government PDF.

## The reframe

Basis does not ask *"is this a good site?"* — a question no honest system can answer.

It asks: **"here is the question blocking your decision. Here is what the governing document
actually says. Here is the passage. Here is what the site measures. Here is where those two
disagree. Here is what I could not read. Here is what would change this answer."**

The unit of work is a **question**, not a report. This is deliberate and follows from
observing that Planso's own worked example is a question (`Can we add two storeys?`) rather
than a document.

## The three claims underneath it

### 1. Provenance must be passage-level, not document-level

"Source: RMP 2031" is a citation in the way a library is an answer. It is unfalsifiable in
practice — nobody reads 206 pages to check you.

"§4.16, page 41, *this sentence*" is verifiable in four seconds. The difference is the entire
product. A citation the user will not check is decoration; a citation they *can* check in
seconds is trust infrastructure.

### 2. A system must report what it could not read

Measured, not assumed: the corpus has **206 pages, 336,972 extractable characters, and 49
pages that yield zero text.** The setback and FAR dimensional matrices — the most
decision-critical content in the document — are on image-only pages.

A retrieval pipeline over this document will answer setback questions from the surrounding
prose with full fluency while the governing table is invisible to it. It will be confident
and wrong, and the user will have no way to tell.

**So the blind spot is a first-class output.** Basis renders the page it cannot parse and
says so. The claim is not "we read everything." It is "here is precisely the boundary of what
we read, and here is the thing you must read yourself."

This inverts the usual incentive. Most AI products minimise visible uncertainty because
uncertainty looks like weakness. In a workflow where being wrong costs a client relationship
or a regulatory approval, **legible uncertainty is the feature**.

### 3. Conflict is more valuable than conclusion

Bellandur measures excellently on accessibility — Outer Ring Road, tech corridor, 59 real OSM
features within 2 km. Bellandur also sits in a lake catchment where valley-zone status can
reduce FAR by 25–50%.

Both statements are true. Separately, each misleads. A system that returns only the first is
worse than useless — it is confidently encouraging. The value is in holding both and naming
the tension, then admitting that open data cannot resolve which applies to this plot.

## What this is not

- **Not a chatbot.** The interaction is a structured trace, not a conversation. There is no
  message thread as the primary surface.
- **Not a wrapper.** The AI layer does retrieval, grounding verification, conflict detection
  and self-critique against a graded ground-truth set. Remove the LLM and most of the
  architecture remains.
- **Not a score.** No site gets a number. See `08-non-goals.md` for why, and
  `14-decision-log.md` D-004 for the moment I tried it and it failed.
- **Not professional advice.** Basis reads a draft regulation and reports what it found. It
  does not certify compliance, and says so at every exit point.

## How it will be judged

Honestly and by measurement, not by assertion:

| Claim | How it is tested |
|---|---|
| Citations point at the right passage | Graded against hand-built ground truth from the actual PDF |
| Claims are supported by retrieved evidence | Unsupported-claim rate, per claim, auto-graded + spot-checked |
| Confidence means something | Calibration — does stated confidence track measured correctness? |
| Blind spots are reported, not hidden | Held-out set of questions whose answer lives only on image-only pages |

Anything displayed in the product as a number must trace to one of these measurements.
If a metric is not measured, it is not shown. See `11-ai-evaluation.md`.

## The falsifiable version

If the following turns out to be false, this thesis is wrong and should be abandoned:

> A professional will trust and act on an AI answer more readily when shown the exact passage
> and the system's own blind spots, than when shown a fluent answer with a high confidence
> score.

I cannot test this properly without users — five practitioners and five working days, which
is precisely the exercise Planso poses. `11-ai-evaluation.md` states what I *can* measure
solo, and `docs/17-product-case-study.md` will state plainly what remains untested.
