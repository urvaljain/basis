# Basis

**Evidence-first site and regulation intelligence.**

Basis answers a blocking question about a site from the governing regulation and the site's
measured context — and shows the exact passage behind every claim, where the two disagree,
what it could not read at all, and what would change the answer.

Built as a 0→1 product experiment in the built-environment decision space. The thesis, the
tradeoffs and the things that failed are in [`docs/`](docs/).

---

## The problem, in one document

The bundled corpus is the **Revised Master Plan for Bengaluru 2031 (Draft), Volume 6 — Zoning
Regulations**: 206 pages, published by the Bangalore Development Authority.

In this jurisdiction the rules that actually decide a project — zoning class, FAR, setbacks,
valley-zone overlay, flood hazard, parcel geometry — **do not exist as an API**. They are
prose and drawings inside that PDF. So the constraint layer is a document, and reading it
honestly is much harder than it looks.

Measured by the ingestion pipeline, that one document defeats a retrieval system in three
different ways:

| | Extent | Can the system tell? |
|---|---|---|
| **Unreadable pages** | 54 of 206 — 73.8% text coverage — including the entire 23-page statutory instrument governing Transferable Development Rights | ✅ yes |
| **Encoding corruption** | 542 characters across 37 pages, **including digits**: `75 m` extracts as `7ϱ ŵ`, so searching for the clause returns nothing | ✅ yes, and repairable |
| **Flattened tables** | 6 FAR tables extract cleanly and lose their columns. A base figure reads as a total — a **2× error on the number that decides what gets built** | ⚠️ **only heuristically** |

The third is the one that matters. Those pages classify as *readable and clean*; every
coverage metric reports success; and the structure that made the numbers meaningful is gone.
Neither the system nor the reader can tell.

---

## Quick start

```bash
# backend — ingests the corpus at startup (~15s)
cd backend
python -m venv venv && venv/Scripts/activate      # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000 --reload
```

```bash
# frontend
cd frontend
npm install
npm run dev          # http://localhost:3000
```

No API key is required. Basis runs in **extractive mode** by default — see below.

```bash
# optional: enable generated prose
export ANTHROPIC_API_KEY=...       # or OPENAI_API_KEY
```

```bash
# evaluation — validates ground truth, then scores
cd backend && python -m app.eval.harness --json ../data/eval/results.json
```

```bash
# re-capture provider fixtures when the upstream services are healthy
cd backend && python -m app.eval.capture_fixtures
python -m app.eval.capture_fixtures --verify
```

---

## Two modes, and where the guarantees live

**Extractive (no model).** Every claim is a verbatim passage with its page and character span.
The system selects, orders and qualifies evidence but writes nothing of its own about what the
regulation says. It cannot hallucinate a provision, because it never composes one.

**Generative (model configured).** Same retrieval, same epistemic types, same critic. The
model adds synthesis, and every sentence is checked against retrieved text.

The ordering is the architecture, not a fallback:

> **Passage-level provenance, blind-spot reporting, table-damage detection, epistemic typing
> and critic demotion all work with no model at all.** Remove the model and the prose gets
> worse. Nothing else changes.

That inverts the usual arrangement, where a model produces the answer and retrieval is bolted
on afterwards to justify it.

---

## How it works

```
                 ┌──────────────────────────────┐
  question  ────▶│  ORCHESTRATOR (fixed DAG)    │
  + site         └───────────────┬──────────────┘
                     ┌───────────┴───────────┐
                     ▼                       ▼
          ┌────────────────────┐  ┌──────────────────────┐
          │ 1. SITE AGENT      │  │ 2. REGULATION AGENT  │
          │ measured geography │  │ grounded retrieval   │
          │ Nominatim · OSM    │  │ BM25 over 1,088      │
          │ ERA5 · SRTM        │  │ clause-level chunks  │
          └─────────┬──────────┘  └───────────┬──────────┘
                    └────────────┬────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ 3. CONFLICT AGENT            │
                  │ holds both against each      │
                  │ other; names what cannot     │
                  │ be resolved                  │
                  └──────────────┬───────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ 4. CRITIC AGENT              │
                  │ blind to authoring reasoning │
                  │ can DEMOTE · REJECT · FLAG   │
                  └──────────────┬───────────────┘
                                 ▼
                          FINDING (persisted)
```

Four agents, not nine. The test applied to each: *does this module make a judgement that could
be wrong in an interesting way, and that another could catch?* Computing distance to a station
fails it — that is arithmetic, and it belongs in a provider.

No agent framework. The DAG is static, so orchestration is ~40 lines of `asyncio`. See
[`docs/14-decision-log.md`](docs/14-decision-log.md) D-007.

### Every answer has the same anatomy

```
QUESTION → CONTEXT → EVIDENCE → CONFLICT → UNREADABLE
         → ANSWER → CHANGE-MY-MIND → VERIFY
```

Conflicts and blind spots come **before** the answer. A reader who has already accepted a
conclusion reads its caveats as pedantry.

### Four kinds of statement, enforced in code

| Type | Invariant |
|---|---|
| **Fact** | Cannot be constructed without a source. A type-level failure, not a lint rule. |
| **Inference** | Must name what it derives from, the transformation, and why its confidence band is what it is. |
| **Assumption** | Must state what would falsify it. |
| **Recommendation** | Responds to a specific uncertainty; addressed to someone who can act. |

Confidence attaches only to inferences. A fact is not 80% true — it either has a source or it
is not a fact.

---

## Measured results

From `python -m app.eval.harness`, against ground truth anchored to page-and-phrase in the
real document. **Ground truth is validated before anything is scored; if a case's expected
phrase is not where it claims to be, the run aborts.**

| | |
|---|---|
| blind-spot recall | **100%** (3/3) |
| blind-spot precision | **100%** (2/2) |
| repair caveat propagation | **100%** (3/3) |
| table damage detection | **100%** (3/3) |
| overclaim resistance | **100%** (4/4) |
| governing phrase retrieved | 92.3% (12/13) |
| citation page recall | 84.6% (11/13) |
| absence handling | 66.7% (2/3) |
| citation precision@1 | 61.5% (8/13) |
| median latency | 31 ms |

Four further metrics report **"not measured"** with the reason — they need generated prose,
and extractive mode produces none. They are not estimated.

Two results are knowingly below where they could be, and are reported rather than tuned away.
See [`docs/11-ai-evaluation.md`](docs/11-ai-evaluation.md).

---

## Data sources

Every source was called before being written down. Probes are reproducible:
`python data/probes/probe_sources.py` (currently 5/5 pass).

| Source | Provides | Limitation, always displayed |
|---|---|---|
| Nominatim | geocoding | Returns area centroids for place names; 1 req/s |
| Overpass / OSM | spatial features | Crowd-sourced — counts are what has been *mapped*, not what exists |
| Open-Meteo (ERA5) | historical climate | ~9 km grid; **4.71 km** from the site at the reference point |
| OpenTopoData SRTM 30 m | elevation | Cannot resolve plot-level grade |

**Not available, verified by probing:** zoning class per parcel · FAR/setbacks per plot ·
valley-zone overlay · official flood hazard layer · parcel geometry and ownership.

A provider cannot return a value without also returning what is wrong with it: `limitation` is
a required field that travels into the epistemic layer and is rendered beside the value.
Nothing downstream can strip it.

---

## What it will not do

- **Score a site.** Built, demoed well, removed — see D-004. A single number needs weights that
  encode a development thesis nobody stated, and once a score exists nobody opens the evidence.
- **Certify compliance.** The source is a *draft* plan; interpretation is a licensed activity.
- **Determine whether a rule applies to your plot.** The regulation turns on plot attributes
  that are not open data here. Basis states the rule; it cannot tell you which rule is yours.
- **Display a metric it did not measure.**
- **Quote repaired text as verbatim.** Reconstructed quotes say so, with the raw extraction one
  click away.

---

## Layout

```
backend/
  app/
    ingest/      text_repair · pdf_extract · table_risk · chunker · retriever
    domain/      epistemics — the four statement types and their invariants
    providers/   base (retry, mirrors, disk cache) · geocode · osm · climate · elevation · llm
    agents/      site · regulation · conflict · critic · orchestrator
    eval/        dataset · harness · metrics · capture_fixtures
    api/         main · schemas · serialise · compare · uploads
  tests/         67 tests, incl. assertions against the real corpus
frontend/
  app/           landing · workspace · compare · documents · demo · corpus · evaluation · method
  components/    StatementCard · CitationBlock · ConflictCard · UnreadableSurface · PageViewer · SiteMap
data/
  corpus/        the RMP 2031 PDF
  fixtures/      verbatim recorded provider responses (12)
  probes/        reproducible data-source probes
docs/            thesis · scope · non-goals · agent architecture · data sources · evaluation · decision log
```

---

## Documentation

| | |
|---|---|
| [`research.md`](docs/research.md) | Phase 0 — including three claims I got wrong and corrected |
| [`01-product-thesis.md`](docs/01-product-thesis.md) | The bet, and its falsifiable form |
| [`07-mvp-scope.md`](docs/07-mvp-scope.md) | What ships, and what "done" means for each part |
| [`08-non-goals.md`](docs/08-non-goals.md) | What it deliberately does not do, and why |
| [`09-agent-architecture.md`](docs/09-agent-architecture.md) | Four agents, the epistemic type system, no framework |
| [`10-data-sources.md`](docs/10-data-sources.md) | Every source, licence and limitation — and what is absent |
| [`11-ai-evaluation.md`](docs/11-ai-evaluation.md) | Results, what the harness caught, what it cannot tell you |
| [`14-decision-log.md`](docs/14-decision-log.md) | Decisions, reversals and falsified assumptions |

---

## Licence and attribution

Corpus © Bangalore Development Authority, via [OpenCity](https://data.opencity.in/dataset/bda-revised-master-plan-2031).
Spatial data © OpenStreetMap contributors (ODbL). Climate: ERA5 © Copernicus via Open-Meteo.
Elevation: SRTM, NASA/USGS. Basemap: Esri, HERE, Garmin, © OpenStreetMap contributors.

Basis reads a draft regulation and reports what it found. It does not certify compliance.
