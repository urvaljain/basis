# 09 — Agent Architecture

## Why four and not nine

The original brief specified nine agents. I cut it to four.

An "agent" that wraps a single API call and reformats the response is a function. Calling it
an agent does not add intelligence; it adds a layer of indirection and a slide in a deck. The
test I applied to each proposed agent:

> Does this module make a **judgement** that could be wrong in an interesting way, and that
> another module could catch?

`MOBILITY AGENT` fails that test — computing distance to the nearest station is deterministic
arithmetic over OSM. It belongs in a provider, not an agent. `CLIMATE AGENT` likewise: ERA5
returns numbers.

Four modules pass it. Each one can be wrong, and the ones downstream are built to catch it.

```
                        ┌──────────────────────────────┐
     question  ────────▶│   ORCHESTRATOR (deterministic)│
   + site + corpus      └──────────────┬───────────────┘
                                       │ fan-out, parallel
                   ┌───────────────────┴───────────────────┐
                   ▼                                       ▼
        ┌─────────────────────┐              ┌──────────────────────────┐
        │  1. SITE AGENT      │              │  2. REGULATION AGENT     │
        │  measured geography │              │  grounded retrieval      │
        │                     │              │                          │
        │  providers:         │              │  corpus: RMP 2031 +      │
        │   geocode, OSM,     │              │   user uploads           │
        │   ERA5, SRTM        │              │  emits: Claim + Passage  │
        │  emits: Observation │              │   + Coverage gap         │
        └──────────┬──────────┘              └────────────┬─────────────┘
                   │  Observations (facts)                │  Claims (grounded)
                   └───────────────┬──────────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  3. CONFLICT AGENT           │
                    │  holds both against each     │
                    │  other; finds tension and    │
                    │  unresolvable gaps           │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  4. CRITIC AGENT             │
                    │  adversarial. can DEMOTE or  │
                    │  REJECT anything above.      │
                    │  runs on a separate prompt   │
                    │  with no memory of authoring │
                    └──────────────┬───────────────┘
                                   ▼
                          Finding  (persisted, linkable)
```

---

## The shape every answer takes

Borrowed in spirit from Planso's own declared trace, extended with the two steps I think are
missing from theirs (`UNREADABLE` and `WHAT WOULD CHANGE THIS`):

```
QUESTION      Can I build to 2.5 FAR on this plot?
CONTEXT       measured site facts that bear on the question
EVIDENCE      grounded claims, each with page + passage + exact span
CONFLICT      where evidence disagrees with context, or with itself
UNREADABLE    what the system could not parse, shown as rendered page images
ANSWER        the finding, with epistemic status per statement
CHANGE-MY-MIND what evidence would overturn this
VERIFY        prioritised human verification tasks
```

---

## The epistemic type system

This is the core data model, not a UI concern. Every statement in the system carries exactly
one of four types, and the type determines both rendering and what the Critic is allowed to do
to it.

| Type | Definition | Must have | Example |
|---|---|---|---|
| **FACT** | Directly measured or directly quoted. Reproducible. | A source with a timestamp; for documents, a page + character span | "881 m elevation (SRTM 30 m, 2026-09-27)" |
| **INFERENCE** | Derived from facts by a stated transformation | The facts it derives from, and the transformation named | "Local relief 1 m over 490 m → effectively flat" |
| **ASSUMPTION** | Required for the reasoning to hold, not itself established | Explicit statement + what would falsify it | "Assuming the plot is not in a valley zone" |
| **RECOMMENDATION** | A suggested human action | The uncertainty it is responding to | "Obtain the RMP valley-zone sheet for this survey number" |

**Rules enforced in code, not prose:**

1. A FACT with no source is rejected at construction. This is a type-level invariant.
2. An INFERENCE must name at least one FACT it derives from, or it is demoted to ASSUMPTION.
3. Confidence may only be attached to INFERENCE. A FACT is not 80% true — it either has a
   source or it is not a FACT. A RECOMMENDATION is not probabilistic.
4. Any statement the Critic cannot trace to evidence is demoted one level, not deleted —
   demotion is visible, deletion is not.

That third rule is the one most AI products break, and breaking it is why confidence badges
have become meaningless.

---

## Agent 1 — Site Agent

**Judgement it makes:** which measured properties of this location are *relevant to this
question*, and what each one is a proxy for.

Providers underneath it (deterministic, not agents): Nominatim geocoding, Overpass/OSM
features, Open-Meteo ERA5 archive, OpenTopoData SRTM.

**Emits:** `Observation` — a FACT with source, timestamp, and a `proxy_for` field that states
the leap being made. `Distance to station` is a fact; `accessibility` is not. The Site Agent
must name that gap itself rather than letting the interface imply it.

**Honest limits it must declare, not hide:**
- OSM completeness varies by area and is crowd-sourced
- ERA5 snaps to a ~9 km grid — measured drift at the reference site is **4.71 km**
- SRTM 30 m postings cannot resolve plot-level grade

---

## Agent 2 — Regulation Agent

**Judgement it makes:** what the governing document actually says about this question, and —
critically — **whether it can see the part of the document that governs**.

**Emits:** `Claim`, each carrying `page`, `char_span`, verbatim `quote`, and a
`support_strength`. Plus a `CoverageGap` when the retrieval neighbourhood includes image-only
pages.

**The mechanism that makes this product different:** the corpus index records, per page,
whether text extraction succeeded. When retrieval surfaces a region adjacent to image-only
pages — or when a question's keywords cluster on pages with no text — the agent emits a
coverage gap *before* answering, and the answer is constrained to what the prose supports.

Measured on the real corpus: 206 pages, 336,972 chars, **49 pages with zero extractable
text**, including the setback and FAR dimensional matrices.

It renders those pages as images and hands them to the user. It does not guess their contents.

---

## Agent 3 — Conflict Agent

**Judgement it makes:** do the Site Agent's observations and the Regulation Agent's claims
point in the same direction?

This is the agent the brief did not have and Planso's diagram does. It is the difference
between a report and a decision aid.

Three conflict classes:

1. **Context vs regulation** — the site measures well on something the regulation penalises.
   *Bellandur: excellent measured accessibility, potential valley-zone FAR reduction of
   25–50%.*
2. **Source vs source** — two documents disagree, or a document contradicts itself across
   revisions.
3. **Evidence vs absence** — the decisive factor is precisely what cannot be established.
   This is the most common real outcome and the one most systems silently skip.

**Emits:** `Conflict` with both sides, their epistemic types, and whether it is resolvable
with available data. Most are not, and saying so is the point.

---

## Agent 4 — Critic Agent

**Judgement it makes:** should any of the above survive?

Deliberately adversarial and deliberately ignorant of authorship. It receives the findings and
the retrieved evidence, **not** the reasoning that produced them, so it cannot be persuaded by
the original chain of thought.

Checklist it applies, each producing a structured verdict rather than prose:

- Is every FACT actually sourced, and does the quote contain what the claim says it does?
- Does any INFERENCE depend on an unstated ASSUMPTION?
- Is correlation being presented as causation? (`proxy_for` fields are the usual offender)
- Is confidence higher than the evidence supports?
- Is a material consideration absent given the question asked?
- Could the phrasing mislead a reader who does not open the evidence?

**Powers:** `DEMOTE` (FACT → INFERENCE → ASSUMPTION), `REDUCE_CONFIDENCE`, `FLAG_MISLEADING`,
`REQUIRE_VERIFICATION`, `REJECT`.

**Every critic action is visible in the UI.** A user can see that a claim was demoted and why.
A silent critic is indistinguishable from no critic, and an invisible one cannot be audited —
which would make it exactly the trust theatre this product argues against.

---

## Orchestration: no framework

**Decision: plain Python with `asyncio.gather`. No LangChain, no LangGraph.**

The control flow is a fixed DAG: fan out to two agents in parallel, join, then two sequential
passes. It is roughly forty lines of orchestration. A framework would add a dependency tree, a
new abstraction vocabulary, opaque prompt construction, and version churn — in exchange for
solving a problem I do not have.

The brief said not to adopt them for popularity. I am not adopting them because the DAG is
static and the value is in the epistemic model, not the graph engine.

**What I do build instead**, because these are real needs:
- a provider abstraction with retries, mirror fallback and caching (Overpass returned a **504**
  on the first scripted run — this is not hypothetical)
- an LLM provider abstraction so the model is swappable and every call is logged with tokens,
  latency and cost
- structured output validated with Pydantic, with a repair pass on schema failure
- full trace persistence — every agent input and output stored, because the evaluation harness
  and the UI's evidence inspector read the same trace

**Reconsider a framework if** the DAG becomes dynamic — an agent deciding at runtime which
other agents to call. It does not, today.
