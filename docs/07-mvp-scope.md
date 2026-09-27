# 07 — MVP Scope

Direction selected: **regulatory evidence engine as the core, plus the site workspace and
multi-site comparison.** Jurisdiction: Bengaluru. Decision recorded in `14-decision-log.md`
D-001 / D-002.

The scope is wider than I initially recommended. That was Urval's call, and it is defensible —
the workspace makes the evidence engine legible in context rather than presenting it as a bare
QA box. My obligation is to sequence it so the core lands at full depth and the workspace is
genuinely data-backed rather than padded with plausible-looking panels.

**Sequencing rule: nothing in the workspace renders unless a real provider or a real document
populated it.** An empty state that says "no data source covers this" ships. A panel filled
with illustrative content does not.

---

## The vertical slice

```
  1  Landing              the thesis in one screen, not a feature list
  2  Enter a site         address · coordinates · map click
  3  Geocode              Nominatim, real, with the ambiguity case handled
  4  Site workspace       measured context from four verified providers
  5  Corpus               Bengaluru RMP 2031 pre-indexed + user PDF upload
  6  Ask a question       the blocking question, not a chat prompt
  7  Run the four agents  streamed, with real per-agent progress
  8  Finding              the eight-part anatomy, epistemic types visible
  9  Evidence inspector   click any claim → page, passage, exact span
 10  Unreadable surface   rendered image pages the system could not parse
 11  Conflict             site vs regulation, held together
 12  Change my mind       what evidence would overturn this
 13  Verify next          prioritised, with what to ask and whom
 14  Compare sites        evidence matrix, no scores
 15  Decision brief       export with full provenance + limitations
 16  Eval view            measured AI quality, nothing fabricated
 17  /demo                guided, cached, clearly labelled
```

---

## In scope — and what "done" means for each

### Core: the evidence engine

| Item | Done means |
|---|---|
| Corpus ingestion | 206-page PDF chunked, embedded, per-page text-extractability recorded, image pages rendered to PNG |
| Grounded retrieval | Every claim carries page + character span + verbatim quote that provably contains the claim's substance |
| Coverage gaps | Retrieval adjacent to image-only pages emits a gap *before* answering |
| Unreadable surface | Rendered page image shown inline, with the naive baseline's real output beside it |
| Conflict detection | Three conflict classes implemented; unresolvable conflicts stated as such |
| Critic pass | Runs blind to authoring reasoning; every demotion visible in the UI |
| Epistemic types | Enforced as code invariants — unsourced FACT is unconstructable |
| Trace persistence | Every agent I/O stored; UI inspector and eval harness read the same trace |

### Site workspace

Four providers, all verified in Phase 0: Nominatim, Overpass/OSM, Open-Meteo ERA5,
OpenTopoData SRTM.

| Panel | Backed by | Honest limit shown |
|---|---|---|
| Location & administrative context | Nominatim | geocoding ambiguity surfaced, not auto-resolved |
| Mobility & surrounding features | Overpass/OSM | crowd-sourced; completeness varies; feature count is what was found, not what exists |
| Climate observations | ERA5 archive | ~9 km grid; **4.71 km drift** at the reference site, displayed |
| Terrain | SRTM 30 m | cannot resolve plot-level grade |
| Constraints | **nothing** | explicit: "no open structured source covers zoning, FAR, flood or parcel geometry for this jurisdiction" → routes to the document layer |

That last row is the most important panel in the workspace. It is where the product's argument
becomes visible in the interface.

### Map

MapLibre. Site marker, search radius rings, OSM features as inspectable layers,
click-to-inspect returning *what is this · why it matters · source · how it was measured*.
Map and list selection synchronised.

Not decorative: every rendered feature is a real OSM element with an ID that resolves.

### Comparison

Bellandur + two comparator sites. Matrix of evidence cells, not scores. Each cell opens its
provenance. A `data confidence` row that reports **coverage** — how many cells are FACT vs
INFERENCE vs unavailable — because that is measurable, unlike a quality score.

### Evaluation

25–30 question test set with hand-built ground truth from the actual PDF. Dimensions measured:
citation correctness, evidence coverage, unsupported-claim rate, calibration, latency, cost.
A held-out subset whose answers live *only* on image-only pages, to test blind-spot reporting.
Results surfaced in an eval view. See `11-ai-evaluation.md`.

### Demo mode

`/demo` — guided, from cached real responses so it survives API failure, clearly labelled as
cached with the capture timestamp. Every value traces to a real call that actually happened.

---

## Explicitly out — with the reason

| Cut | Why |
|---|---|
| Site scores | Attempted, failed. `14-decision-log.md` D-004 |
| Knowledge / organisational intelligence | Requires a firm's private history I do not have; would require fabrication |
| Simulation (solar, wind, carbon) | Forma owns it with validated physics; mine would be unverifiable |
| Generative massing | Needs the dimensional matrices I cannot read |
| Compliance certification | Draft document, licensed activity, authority discretion |
| Nine agents | Four that reason beat nine that fetch |
| Chat as primary surface | Their posting: "not just as generic chat interfaces" |
| Auth / multi-tenancy | Demonstrates nothing about the thesis |
| Second jurisdiction | Depth over breadth; abstraction layer makes it an implementation, not a rewrite |
| PostGIS | Every operation is point-buffer/distance; Shapely handles it in-process |

---

## Risk register for the scope itself

| Risk | Mitigation |
|---|---|
| Breadth dilutes the core | Core ships and is polished before workspace panels get visual attention |
| Workspace panels look like filler | Hard rule: no panel renders without a real provider behind it |
| The valley-zone conflict is not in the primary document | **Blocking check before building the conflict feature.** If absent, find the real conflict the document does contain — do not stage one |
| Public API flakiness during a live demo | Cache layer + `/demo` from captured real responses; Overpass mirrors already implemented |
| Image-page rendering is heavy | Pre-render at ingest, not request time |
| Eval ground truth is subjective | Ground truth is verbatim page+span from the PDF, not my opinion of a good answer |

---

## The one thing that must land

If everything else is mediocre and this works, the project succeeded:

> A user asks about setbacks. The system shows them the exact page containing the governing
> table, tells them it cannot read it, shows what a naive pipeline confidently answered
> instead, and explains why that answer is not trustworthy.

Real document. Real limitation. Real baseline output. Nothing staged.
