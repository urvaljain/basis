# 17 — Product Case Study

**Basis — evidence-first site and regulation intelligence**
Urval Jain · September 2026

---

## The problem

A built-environment decision fails rarely because evidence was missing. It fails because the
evidence that mattered never met the evidence that contradicted it — and because nobody could
tell, at the moment of deciding, which parts were measured, which were inferred, and which
were guessed.

I started from a brief to build *site decision intelligence*: evaluate a location from public
geospatial data, surface opportunities and risks. Phase 0 research killed the pure form of
that idea, for a reason I could measure rather than argue.

**The data that decides a project in this jurisdiction does not exist as an API.**

I probed the sources rather than assuming. Geocoding, OpenStreetMap, ERA5 climate and SRTM
elevation all work — real, free, verified. Zoning class, FAR, setbacks, valley-zone overlay,
flood hazard and parcel geometry are **not machine-queryable in India**. They are published as
prose and drawings inside a 206-page government PDF.

So a public-data site evaluator is confident about the distance to a bus stop and silent about
whether you may build at all. It answers the easy half loudly.

The constraint layer is a document. And reading a document honestly turned out to be the
actual problem.

---

## Why existing workflows break

Three things, from the research:

**The bottleneck is synthesis, not acquisition.** Comparison write-ups of the tooling
landscape converge on the same observation — no single tool does all of it, so teams run two
or three and join the results by hand. Planso's own homepage frames it as a three-step decay:
assemble over weeks, interpret in silos where "most of it never meets the rest", then decide
in one meeting from whatever made it into the room.

**Where rules are prose, computation stops.** Every well-funded tool in this space — TestFit,
Deepblocks, Autodesk Forma, Hypar, Giraffe — is strongest exactly where planning codes are
already digital, chiefly the US. Their moat is a data moat. The jurisdictions where the rules
live only in a PDF are unserved.

**Trust is the live constraint, not capability.** This is the part I could not have guessed.
Planso's own hiring process asks candidates how they would test whether users would *trust*
question answering over project documents with source attribution. They published their open
question.

---

## The hypothesis

> The valuable output of an AI system in a high-stakes workflow is not the answer. It is the
> answer plus everything that could make the answer wrong.

Three claims underneath it:

1. **Provenance must be passage-level.** "Source: RMP 2031" is unfalsifiable in practice —
   nobody reads 206 pages to check you. "§6.5.3(ii), p. 80, characters 1603–1975" is checkable
   in four seconds. A citation the reader *can* check is trust infrastructure; one they will
   not is decoration.
2. **A system must report what it could not read.** Blind spots as results, not omissions.
3. **Conflict is more valuable than conclusion.** The decision lives in the tension between
   two things that are each true.

---

## What I built

A question about a site goes in. What comes back has a fixed anatomy:

```
QUESTION → CONTEXT → EVIDENCE → CONFLICT → UNREADABLE
         → ANSWER → CHANGE-MY-MIND → VERIFY
```

Four agents — Site, Regulation, Conflict, Critic — over a real 206-page government document
and four verified live data providers. Every claim carries its page and character span. Every
measurement carries its provider's limitation. The critic can demote anything, and every
demotion is shown.

Plus: multi-site comparison as an evidence matrix with no score, document upload through the
identical pipeline, a corpus view that publishes its own ingestion quality, and an evaluation
view that displays four metrics as **"not measured"** with the reason.

---

## The decisions, and what they cost

### Four agents, not nine

The brief specified nine. I applied one test: *does this module make a judgement that could be
wrong in an interesting way, and that another module could catch?*

`MOBILITY AGENT` fails it — distance to a station is deterministic arithmetic, and belongs in
a provider, not an agent. Nine modules wrapping single API calls are functions in a costume,
and a founder who has shipped AI products reads that immediately.

### No score — built, then removed

I implemented a 0–100 composite. It demoed well. I removed it because:

- the weights encode a development thesis nobody stated (a warehouse and a hospital on the
  same plot should not get the same number);
- **once a score exists, nobody opens the evidence** — the score becomes the product and the
  reasoning becomes decoration;
- most cells are genuinely unresolved, and averaging over unknowns produces a number more
  confident than any of its inputs.

The replacement turned out better than the thing it replaced. Comparing Bellandur, Whitefield
and Jayanagar, all three differ on every measurement — and the system's headline is that they
are **indistinguishable on the constraint that actually decides**. A score would have
manufactured a difference.

### Extractive mode as a first-class mode

No LLM key was available in my build environment. Rather than stub the agents, I put the
guarantees in the deterministic layer. Passage-level provenance, blind-spot reporting,
table-damage detection, epistemic typing and critic demotion all work with no model at all.

This began as a constraint and became the better architecture. It inverts the usual
arrangement — model produces answer, retrieval bolted on to justify it — and it means the
question "what stops working without the model?" has a precise answer: *the prose gets worse,
and nothing else changes.*

---

## How the AI system works

**Retrieval is BM25, not embeddings.** Three reasons: the questions are lexical (defined terms
in a regulation are terms of art); it is gradeable with no model, which is why this project has
measurements rather than an unrun script; and it can show *which terms matched*, where a cosine
distance cannot be offered to a sceptical professional as justification.

**Chunking follows the document's structure.** Fixed-size chunks cut between a clause and its
measurement, producing a citation that points at a span the claim cannot be read out of.
Section headings, enumerated clauses and table captions are boundaries. 1,088 citable units.

**Four statement types are enforced in code.** A `Fact` cannot be constructed without a source
— a type-level failure, not a lint rule. Confidence attaches only to inferences, because a fact
is not 80% true.

**The critic is blind to authorship.** It receives claims and evidence, not the reasoning that
produced them, so it cannot be persuaded by the argument that convinced the author. Most of its
checklist is mechanically decidable, so it has identical teeth with or without a model. Every
intervention is rendered — an invisible critic cannot be audited, which makes it
indistinguishable from no critic.

---

## What failed

Five real failures, in the order they hurt.

### 1 · I nearly built the demo on a number that does not exist

Every secondary source says a Bengaluru valley zone cuts FAR by **25–50%**. Two independent
sources agreed. I flagged it as a blocking assumption and checked it against the primary
document.

**It is not in there.** RMP 2031 §6.5.3 says something categorically stricter: a **75 m "no
development zone"** around water bodies per the NGT Order, and **50/35/25 m** buffers on
primary/secondary/tertiary streams, inside which the only permitted uses are treatment plants
and non-obstructing infrastructure.

A 25% FAR cut is a haircut. A 75 m no-development buffer means you cannot build there at all.

I was the user my own product would have saved. That is the argument, encountered first-hand,
and it is why the product exists in the shape it does.

### 2 · I asserted where the FAR tables were without looking

I wrote that the dimensional matrices sat on image-only pages, inferring it from term
frequency. Opening the rendered pages showed page 108 is scanned *TDR statutory prose*, and
the FAR tables are on readable pages.

The correction led somewhere better — see the next failure.

### 3 · The dangerous failure mode is the one nothing detects

Chasing that correction, I found three distinct ways this one document defeats a retrieval
pipeline, and they differ in the only way that matters:

| | Extent | Can the system tell? |
|---|---|---|
| Unreadable pages | 54 of 206, incl. the 23-page TDR Rules 2016 | yes |
| Encoding corruption | 542 chars on 37 pages — **including digits**: `75 m` → `7ϱ ŵ` | yes, repairable |
| **Flattened tables** | 6 FAR tables | **no** |

Page 57 holds *Table 6: FAR and Ground Coverage*. It classifies as readable and clean. Rows
5–8 carry three FAR figures; rows 1–4 carry two, because the TDR cell is blank — obvious in
the PDF, invisible in flattened text. A 100 sqm plot reads as *total FAR 1.50*, or as
*1.50 + 1.50 = 3.00*, depending on how a model binds the columns.

**A 2× error on the number that decides what gets built**, delivered fluently, from a page
every quality check calls fine.

That reframed the product. Detecting structural damage became a first-class requirement, and
the detector now flags exactly six tables — every one a FAR or ground-coverage table — with
no false positives on prose.

### 4 · My own product committed its cardinal sin

The first evaluation run scored **absence handling at 0%**. Asked *"who currently owns this
parcel?"*, Basis confidently returned §2.123 defining "site" — a real passage, correctly
retrieved, that does not address the question.

BM25 always returns *something*. Presenting it as evidence manufactures coverage the document
does not have, which is precisely what the product argues against — committed by the product.

Fixed with an evidence floor, measured rather than guessed: the top passage must share ≥2
distinct terms with the query, one of them distinctive. 20/20 genuine questions accepted, 2/3
absent rejected.

The evaluation also caught three more: no stemming (a question about a "drain" could not reach
the clause defining *Drains/Halla*); table captions fused into 1,400-character chunks that
BM25's length normalisation buried; and table-risk warnings keyed to extracted numbers, so the
caption chunk — the one that ranks highest — carried no warning.

**Building the harness before polishing the interface is what surfaced all four.**

### 5 · I blamed the infrastructure for something I was doing

All three public Overpass mirrors returned 504 or timed out, repeatedly. A cold analysis took
**191 seconds** and came back with no spatial context. I wrote it up as a reliability finding
about free infrastructure.

It was **self-inflicted rate limiting**. Overpass allocates a small number of concurrent slots
per IP, and my repeated full-pipeline runs exhausted them. Worse, it signals this with an HTTP
**200** carrying an HTML body, which surfaced several layers away as a `JSONDecodeError` and
looked like a parsing bug.

Throttling plus a recorded-response cache took a cold analysis from **191 s to 0.05 s**. The
same class of error bit again later: CARTO's basemap returns HTTP 200 for every tile, and the
body is a 2.5 KB "API KEY REQUIRED" watermark. A status-code health check calls that healthy.

**Lesson, twice: a 200 is not a success.** Both times the honest diagnosis required comparing
the *content* against something known-good.

---

## What I would build next

**Test the actual hypothesis.** Everything measured here shows the system is correct and
honest about its limits. That is a necessary condition for trust and not the same thing. The
real test needs five practitioners and five working days: show three the answer with
passage-level citations and three without, and measure who opens the evidence, who forwards
it, and who acts. Watch specifically what happens at the blind-spot case — does reporting a
gap increase confidence in everything else, or reduce it? I assumed it increases. It is
untested and might be wrong.

**Layout-aware extraction.** The table-damage detector reports *risk*; it cannot recover the
grid. Word bounding boxes would let it rebuild column binding rather than warn about losing
it.

**OCR the 54 unreadable pages** — starting with the 23-page TDR instrument, which is the
highest-value blind spot in the corpus.

**A second jurisdiction**, to prove the abstraction. Adding one should mean implementing
providers and ingesting a corpus, not touching the agents, the epistemic model or the
interface.

---

## Tradeoffs I accepted

| Chose | Over | Because |
|---|---|---|
| BM25 | embeddings | gradeable with no model; inspectable; the questions are lexical |
| In-memory index | Postgres + pgvector | 7.5 MB corpus, ~30 ms queries, one fewer deployment dependency |
| Shapely | PostGIS | every operation is point-buffer and distance |
| Plain `asyncio` | LangChain / LangGraph | the DAG is static — ~40 lines |
| Four agents | nine | nine over data that does not exist is architecture theatre |
| One jurisdiction deep | five shallow | breadth would hide the failure modes worth showing |
| Evidence matrix | site score | a score destroys the audit trail beneath it |

---

## Known limitations

- **No authentication.** Uploads live in memory; confidentiality is explicitly not solved.
- **`citation_precision@1` is 61.5%** against 84.6% recall — the right page is retrieved, not
  always ranked first. Reported rather than tuned away.
- **One absence case still slips the filter** (*"market price per square foot"* matches on
  *market* and *square*). Lowering the bar would weaken it for every other question.
- **One known blind-spot false negative**, accepted deliberately and locked in a test so it
  cannot regress silently.
- **Four evaluation metrics are unmeasured** without a model, and say so.
- **Trust itself is untested.** That needs users.

---

## What this was

I found an ambiguous problem, researched it, and discovered the data I was told to build on
did not exist. I formed a hypothesis about what would actually be valuable, built it, measured
it, and found my own product committing the failure it was designed to prevent. I fixed what
the measurements justified fixing, and left two failures in place rather than tune a threshold
until a test went green.

Along the way I was wrong about where the FAR tables were, wrong about a number the whole
internet agrees on, and wrong about whose fault an outage was — twice.

The product is the record of correcting those.
