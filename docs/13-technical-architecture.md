# 13 — Technical Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND — Next.js 15 · React 19 · TypeScript strict · Tailwind · MapLibre │
│                                                                             │
│  landing · workspace · compare · documents · demo · corpus · evaluation     │
│  StatementCard · CitationBlock · ConflictCard · UnreadableSurface           │
│  PageViewer · SiteMap                                                       │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ JSON over HTTP
┌────────────────────────────────┴────────────────────────────────────────────┐
│  API — FastAPI                                                              │
│  /analyse  /compare  /documents  /corpus  /corpus/page/{n}[/image]          │
│  /geocode  /eval  /sources  /health                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  AGENTS — fixed DAG, plain asyncio                                          │
│    ┌──────────┐   ┌────────────┐                                            │
│    │   Site   │   │ Regulation │   parallel                                 │
│    └────┬─────┘   └─────┬──────┘                                            │
│         └───────┬───────┘                                                   │
│            ┌────┴─────┐   ┌────────┐                                        │
│            │ Conflict │──▶│ Critic │   sequential                           │
│            └──────────┘   └────────┘                                        │
├────────────────────────────┬────────────────────────────────────────────────┤
│  DOMAIN — epistemics       │  INGEST                                        │
│  Fact · Inference          │  text_repair → pdf_extract → table_risk        │
│  Assumption · Recommendation│  → chunker → retriever (BM25)                 │
│  invariants enforced at    │  1,088 chunks · per-page quality               │
│  construction              │                                                │
├────────────────────────────┴────────────────────────────────────────────────┤
│  PROVIDERS — retry · mirror fallback · per-provider throttle · disk cache    │
│  Nominatim · Overpass · Open-Meteo ERA5 · OpenTopoData SRTM · LLM (optional) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The constraint that shapes everything

**A value cannot move through this system without what is wrong with it.**

`ProviderResult.limitation` is a required field. It is copied onto `DatasetLocator.limitation`
in the epistemic layer, serialised onto the statement object itself — never into a sibling
`notes` array — and rendered beside the value in the interface.

That is deliberate at every layer. The moment a caveat becomes a sibling of the value rather
than a property of it, some future screen shows the number without it, and the product's whole
argument fails quietly.

---

## Stack decisions

| Layer | Chose | Over | Why |
|---|---|---|---|
| Retrieval | BM25, hand-implemented (~30 lines) | embeddings / vector DB | Questions are lexical; gradeable with no model; can surface *which terms matched* |
| Index | In-memory, built at startup (6.5 s) | Postgres + pgvector | 7.5 MB corpus, 1,088 chunks, 49 MB RSS, ~1.5 ms queries. One fewer deployment dependency |
| Geometry | Hand-written haversine (~8 lines) | PostGIS / Shapely | Every operation is point-to-point distance. Shapely was declared early and never imported — it has been removed |
| Orchestration | Plain `asyncio.gather` | LangChain / LangGraph | Static DAG, ~40 lines |
| Cache | In-process TTL + verbatim disk fixtures | Redis | A cache tier is a service that can fail during the demo it was meant to protect |
| LLM | Provider abstraction + `NullLLM` | Direct SDK | Extractive mode is a supported mode, not a broken state |
| Frontend | Next.js App Router, client components | SSR data fetching | Analysis is interactive and user-initiated; SSR buys nothing |
| Basemap | Esri Dark Gray Canvas | CARTO / demotiles / Mapbox | No key to expire; real detail at city zoom (see D-014) |

**Each of these has a revisit threshold**, recorded so the decision can be re-opened on
evidence rather than taste:

- **Postgres + pgvector** when there are multiple corpora, multiple tenants, or startup
  ingestion becomes noticeable.
- **PostGIS** when a real polygon operation appears — a plot boundary against a buffer
  polygon, rather than a point against a radius.
- **An agent framework** when the DAG becomes dynamic (an agent choosing at runtime which
  others to call). It is not, today.
- **Embeddings** after the lexical baseline is measured, for paraphrase-heavy questions.

---

## Ingestion pipeline

```
PDF ──▶ pypdf extract ──▶ text_repair ──▶ classify page ──▶ table_risk ──▶ chunk ──▶ index
         per page          validated       5 quality        6 tables       1,088
                           char map        levels           flagged        units
```

**`text_repair`** — a pure character translation, so offsets are preserved one-to-one. That
property is what makes a character-level citation valid against both the repaired and the raw
text, and it is why the UI can show both.

**`pdf_extract`** — classifies each page: `clean` · `repaired` · `heavily_repaired` ·
`unreadable` · `residual_corruption`. The last is deliberately distinct: it means an encoding
pattern the map does not recognise, which is a signal to extend the map from evidence rather
than tolerate silently. Currently 0 on this corpus.

**`table_risk`** — detects tables whose rows disagree on decimal count. Reports *risk*, not
error: it cannot recover the grid, and says so rather than claiming column analysis it did not
perform.

**`chunker`** — boundaries are section headings, enumerated clauses and table captions. Fixed
-size chunks would cut between a clause and its measurement, producing citations that point at
spans the claim cannot be read out of.

**`retriever`** — BM25 with light plural stemming, domain synonym expansion (bidirectional:
`ToD` ↔ `transit oriented development`), a definition-intent boost, an evidence floor, and
**blind regions indexed as independently searchable objects**.

---

## Resilience

Every failure mode below was hit during development, not anticipated.

| Failure | Handling |
|---|---|
| Provider endpoint down | Mirror fallback, then a verbatim recorded response, labelled with its capture time |
| Rate limiting | Per-provider throttle (Overpass 3 s, Nominatim 1.1 s) |
| Non-JSON body on HTTP 200 | Detected explicitly and reported as rate limiting, not as a parse error |
| One agent raises | Contained by the orchestrator; the finding degrades and the trace says which part is missing |
| LLM unavailable | Falls back to extractive; the interface labels the mode |
| Corrupt page | Recorded as unreadable; a 206-page ingest is not aborted by one page |
| A stored recording stops parsing | Detected, logged, falls through to a live fetch |
| Basemap fails | Feature list renders instead; the evidence does not depend on the picture |

**Cold analysis: 191 s → 0.05 s** after throttling plus the disk cache.

---

## Performance

| | |
|---|---|
| Corpus ingest (startup) | 6.5 s, once |
| Analysis, providers cached | **14–46 ms** |
| Analysis, cold providers | 2–4 s |
| Three-site comparison | ~85 ms |
| Document upload, 206 pages | ~14 s |
| Retrieval over 1,088 chunks | ~1.5 ms |

---

## Testing

67 tests. The ones that matter assert against the **real corpus**, not fixtures:

- the encoding repair makes `75 m buffer` findable on page 80, where it is unfindable before;
- the table-risk detector flags exactly six tables, all FAR/coverage, with no false positives
  on prose pages;
- a TDR question reports `pp. 106–128` as a blind spot;
- ordinary questions raise **no** false blind-spot warning;
- a known false negative is asserted, so it cannot regress silently while nobody notices.

Corpus-dependent tests skip cleanly when the PDF is absent, so CI stays green without a 7.5 MB
binary in the repository.

---

## Deployment

Frontend → Vercel. Backend → Railway or Fly.io.

Requirements are modest and deliberately so: one process, no database, no Redis, no object
store. The corpus ships in the image. Measured: **49 MB RSS** loaded and indexed, **6.5 s**
ingest at startup, **~1.5 ms** per search.

Environment: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (optional — extractive mode needs
neither), `BASIS_MODEL` (optional), and `API_ORIGIN` on the frontend — a server-side
variable, so the API origin is never baked into the client bundle and the browser only ever
sees the Next.js origin.

The one deployment caveat: **page rasterisation needs PyMuPDF**. Without it the unreadable
surface degrades to a placeholder instead of the actual page — which would remove the single
most important interaction in the product, so it is a hard dependency rather than an optional
one.
