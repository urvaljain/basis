# Phase 0 — Research

Compiled 2026-09-27. Every claim here is either sourced to a URL, or to a probe I ran
myself. Where I could not verify something, it is marked **[unverified]**. Nothing in this
file is inferred and then presented as fact.

---

## 1. What Planso actually says it is

Source: <https://planso.co> — homepage, Technology, Careers (single-page app; content
captured 2026-09-27).

Positioning, verbatim:

- "Planso is building the decision intelligence layer for the built environment."
- "Spatial context, project knowledge and domain expertise, in one model."
- "AI agents that extend human judgement."
- "The layer between information and decisions."

Their problem narrative is a **three-step decay of evidence**, which is unusually specific
for a startup homepage:

| Step | Their framing | Duration they claim |
|---|---|---|
| 01 Assemble | "Someone gathers site conditions, climate, regulations, models, drawings and reports from eleven places." | Weeks 1–3 |
| 02 Interpret | "Specialists translate each source into something the project team can act on. Most of it never meets the rest." | Weeks 3–6 |
| 03 Decide | "The decision is made from whatever made it into the room, and whoever happened to be there." | One meeting |

And the loss they name: *"The relationships between everything gathered."*

This is the sharpest thing on their site. Their thesis is **not** "we have more data." It is
**"the data already exists and never gets connected at the moment of decision."**

### Their six declared intelligence layers

Spatial · Context · Domain · Knowledge · Organisational · Agentic — each phrased as a
question:

- Where is this project? (spatial)
- What is happening around it? (context)
- What constraints shape it? (domain)
- What have we done before? (knowledge)
- Who understands this problem? (organisational)
- What should we consider next? (agentic)

### Their agent taxonomy

Four families, not nine: **Site agents** (climate, terrain, mobility, ecology, risk,
regulation, context) · **Domain agents** (climate, sustainability, zoning, carbon,
resilience, cost) · **Persona agents** (architect, engineer, planner, sustainability
specialist, project leader, BD) · **Knowledge agents** (projects, expertise, precedents,
research, standards, deliverables).

### Their declared reasoning trace — the most important find on the site

Planso shows a worked example with a fixed five-step shape:

```
QUESTION   Can we add two storeys?
CONTEXT    Zoning envelope · height limit 48m
EVIDENCE   4 precedents from 2019–2024
CONFLICT   Daylight to north neighbour
ANSWER     Two storeys, 6m setback above L12
```

Two observations:

1. **Their unit of work is a question about a live project, not a report about a site.**
   Nothing on their site is "generate a site analysis." It is "answer the question that is
   blocking this decision."
2. **`CONFLICT` is a first-class step.** Most AI products go context → evidence → answer.
   Planso explicitly surfaces the thing that argues against the answer *before* answering.
   Their own line: *"An answer is only useful if you can see how it was reached."*

Their sixth technology pillar is literally **"Traceable intelligence — connect conclusions
to evidence, assumptions and sources."**

> This matters for us: verification-first is **not** a differentiator against Planso. It is
> their stated architecture. Building it well is how we speak their language; it is not how
> we surprise them. The surprise has to come from somewhere else. See §6.

---

## 2. The founder, and what his background predicts he will judge

Naveen Baskaran N — Founder & CEO, Planso.
Sources: [LinkedIn](https://in.linkedin.com/in/naveen-baskaran),
[The Org — HyperVerge leadership](https://theorg.com/org/hyperverge/teams/leadership-team),
[ZoomInfo](https://www.zoominfo.com/p/Naveen-Baskaran/5312937822).

- Dual B.Tech, IIT Madras.
- Rolls-Royce — digital manufacturing / new product introduction; deployed visual defect
  collection software with process owners on the shop floor.
- HyperVerge — **Global Head of Account Management & Customer Success**; progressed through
  Head of Key Account Management (India) → Global Head.
- Now founder/CEO, Planso Intelligence Private Limited (Bangalore; team 1–10 per Wellfound).

**The inference I draw, flagged as inference:** he is not primarily an ML researcher. He
spent years as the customer-facing owner at HyperVerge, an AI identity-verification company
selling into banks and regulated finance. In that business the hardest part of the sale is
never model accuracy — it is *whether a compliance function will accept a decision an AI
made*. He will have sat in rooms where a good model lost because it could not show its work.

Consequence for us: **he has seen trust theatre and he will recognise it.** A confidence
badge whose number no measurement produced will read to him as a lie, not a feature. A
"sources" panel that names a document without pinpointing the passage will read as
unfinished. This raises the bar on the evidence layer specifically — it is the part of the
product he is most qualified to audit and most likely to poke at.

His public activity skews to industry events (`#fibac2025`, `#gff`, `#regtech`) —
customer-facing, not thought-leadership essays. I found **no long-form public product
writing by him [unverified — may exist behind LinkedIn's login wall]**, so I will not
pretend to have read his philosophy. The website *is* the philosophy document, and it is
unusually well written, which suggests he wrote or closely edited it.

---

## 3. The hiring signal — and a correction to the brief

Planso's public careers page lists **four** roles, all Bangalore / on-site:
AI Engineer · Design Engineer · Full-Stack Engineer · **AEC Product Intern**.

I could not find a posting titled "0→1 product" **[unverified]**. The posting whose text
matches the brief I was given — full ownership, talk to customers, find the real problem,
handle failed attempts, hands-on, responsible AI, "build something world class" — is the
**AEC Product Intern** role. If that is the target, it is worth knowing the field is
early-career: an MBA Business Analytics grad arriving with a working, evaluated product is
not competing at the same altitude as the rest of that pool.

### The part that changes everything

The application asks candidates to answer a **product-learning exercise, verbatim**:

> "Imagine our tool can answer questions from a team's project documents and show the source
> documents behind each answer. You have five working days, no engineering support, and
> access to five potential users. **How would you test whether people would trust and use
> this capability?**"

Read that again. Planso told us, in public:

1. **What they are actually building right now** — question answering over a team's project
   documents, with source attribution. Not site scoring. Not maps. Documents.
2. **What they do not yet know** — whether users will *trust* it. That is the open question
   they are spending their own hiring process on.
3. **How they evaluate thinking** — "Specificity and real-world observation," "Ability to
   identify a problem before jumping to a solution," "Good judgment under uncertainty."

They also say: "You may use AI for research, brainstorming, or editing. If you do, tell us
how you used it… we also want to see how you work with AI." So an AI-assisted build is an
asset to disclose, not a liability to hide.

Other role text worth noting: "Learn how AI products are built for real, high-trust
workflows — **not just as generic chat interfaces**." And from The Planso Way: *"Build the
best in the world, fast. World-class is not a department. It is a standard."*

**Conclusion: the brief aims at site evaluation. Planso's live product question is
document-grounded answering and whether it earns trust. Those are not the same product.**
See §6.

---

## 4. Competitive landscape — site analysis is already crowded

Sources: [AEC Magazine — 11 AI start-ups to watch](https://aecmag.com/news/ai-eleven-start-ups-to-watch-in-aec/),
[Energent comparison](https://www.energent.ai/use-cases/en/compare/ai-tools-for-site-analysis),
[Nomic comparison](https://www.nomic.ai/compare/best-ai-for-site-analysis),
[Tracxn — Deepblocks](https://tracxn.com/d/companies/deepblocks/__ESEgKBlv9q1nTQBLWgrm_sNWh80jyNRmZKza9wRSf9k).

| Tool | Owns | Implication for us |
|---|---|---|
| **Autodesk Forma** | Solar, wind, microclimate at massing stage | Simulation is a solved, funded problem. Do not enter. |
| **TestFit** | Yield / feasibility / building configuration, real-time generative massing | "What fits on this site" is taken. |
| **Deepblocks** | Parcel screening + underwriting at city scale (US) | Site *funnelling* is taken, and rests on US parcel/zoning databases. |
| **Hypar** | Configurable zoning logic as code | Zoning-as-computation is taken — for jurisdictions with digital codes. |
| **Giraffe** | Urban-scale planning | Taken. |

Both comparison write-ups conclude that no tool does all of it and teams combine two or three.

**Every one of these is strongest where zoning and parcel data are already digital — chiefly
the US. Their moat is a data moat.** A prototype competing on "evaluate this site from public
data" enters the most crowded, best-funded lane with the worst data. That is the lane the
brief points at, and I think it is the wrong lane.

What is *not* crowded: jurisdictions where the rules exist only as prose in a 200-page
government PDF, and the question is not "what fits" but **"what does the regulation actually
say, and can I trust the answer enough to put it in front of a client."**

---

## 5. Data reality — what I verified by calling it

I took none of this on trust. Probes run 2026-09-27.

### Works — verified live, free, no key

| Source | Probe result | Licence / limits |
|---|---|---|
| **Nominatim** geocoding | ✅ `Bellandur, Bengaluru` → 12.9320495, 77.6842915, with admin hierarchy + bbox | ODbL. 1 req/s, UA required. |
| **Overpass / OSM** | ✅ 59 features around the geocoded centroid (11 nodes, 48 ways) — stations, bus stops, primary roads, hospitals, water bodies. `timestamp_osm_base: 2026-09-27T09:37:51Z` | ODbL. **Rejects requests with no User-Agent (HTTP 406)**, and **returned a 504 Gateway Timeout on the first scripted run.** Mirrors + retries are mandatory. |
| **Open-Meteo Archive** (ERA5) | ✅ 366 days of `precipitation_sum` for 2024 → **1,009.9 mm** annual total; returns its own grid centroid (12.8998, 77.6567) + model elevation 875 m | Free for non-commercial. **Snaps to a ~9 km grid — the point returned is 4.71 km from the point requested.** Must be disclosed, not hidden. |
| **OpenTopoData** SRTM 30 m | ✅ 881 m and 880 m at two points ~490 m apart (1 m relief) | 1,000 calls/day, 100 locations/call. 30 m postings cannot resolve plot-level grade. |

All four are re-verifiable: `python data/probes/probe_sources.py` regenerates
`data/probes/results-<date>.json`. Current run: **5/5 probes pass.** Two corrections landed
this way — my first hand-run used a slightly different centre point (69 features, not 59),
and I had eyeballed the ERA5 drift at ~3 km when it is 4.71 km. Both numbers above now come
from the script, not from memory.

### Does not work — the finding that reframes the product

| What a real decision needs | Status in India |
|---|---|
| Zoning / land-use class for a parcel | ❌ **No machine-readable API.** RMP 2031 land use is maps + prose. |
| FAR, setbacks, coverage for a plot | ❌ Published as **dimensional matrices inside PDFs**. |
| Valley-zone / eco-sensitive overlay | ❌ Mapped in RMP 2031 drawings; no queryable layer found. |
| Official flood hazard layer, Bengaluru | ❌ None found open. |
| Parcel geometry / ownership | ❌ Not open. |

`data.gov.in` responds 200 and `bhuvan-app1.nrsc.gov.in` 302, so the portals exist — but
neither exposes a parcel-level zoning endpoint I could call. **[Unverified: whether any paid
or partner API closes this gap. I found none in open research.]**

> **This is the central research finding.** In the geography Planso is registered in, the
> data that actually decides a project — what you may build, how big, how far from the
> drain — does not exist as an API. **It exists as a document.** Any product here that
> pretends otherwise is fabricating. Any product that ignores the document layer is
> answering the easy half of the question.

### The corpus I secured, and its built-in failure mode

Downloaded and inspected: **Revised Master Plan for Bengaluru 2031 (Draft), Volume 6 —
Zoning Regulations**, Bangalore Development Authority, via the OpenCity CKAN portal.
Now at `data/corpus/bengaluru-rmp-2031-vol6-zoning-regulations.pdf` (7.5 MB).
Source: [OpenCity](https://data.opencity.in/dataset/bda-revised-master-plan-2031) ·
[direct PDF](https://data-opencity.sgp1.cdn.digitaloceanspaces.com/Documents/Recent/Bengaluru-BDA-RMP-2031-Volume_6_Zoning_Regulations.pdf)

Measured by the ingestion pipeline (`backend/app/ingest/`), not assumed:

- **206 pages**, **336,452 characters** after repair
- **54 pages carry no usable text** (26.2%). 49 extract literally zero characters; a further
  5 fall under the 120-character usability threshold. **Text coverage: 73.8%.**
- **542 character substitutions across 37 pages** from an encoding fault (below).

### Correction — three claims I got wrong before checking

I originally wrote that "the dimensional matrices for setbacks and FAR sit on image-only
pages." **That is false.** I inferred it from term-frequency and nearly shipped it as a
finding. Verifying it meant opening the rendered pages, which is exactly what the product
asks its users to be able to do.

What is actually true is more interesting. There are **three distinct failure modes** in this
one document, and they differ in the only way that matters: whether the system can tell.

**Failure 1 — pages that cannot be read at all (detectable).**
54 pages, in contiguous blocks. The two large ones:

| Pages | What it is |
|---|---|
| **106–128** (23 pp) | **Annexure-1: Government Notification UDD 283 BEMRUPRA 2015 dated 04 March 2017 — Karnataka Town and Country Planning (Benefit of Development Rights) Rules, 2016.** An entire statutory instrument governing TDR, scanned. Invisible to extraction. |
| **173–190** (18 pp) | Annexure-5, list of heritage buildings outside heritage zones. |

So the system cannot see the rules governing Transferable Development Rights — a live,
high-value question for any Bengaluru developer, because TDR directly increases buildable
area. It *can* detect that it cannot see them, which makes this the honest failure.

**Failure 2 — text that extracts but is mis-encoded (detectable, and repaired).**
A custom font encoding without a correct `ToUnicode` CMap. `buffers` extracts as `ďuffeƌs`.
Critically, **the corruption reaches inside the numbers**: `75 m` extracts as `7ϱ ŵ`, because
digits map sequentially from U+03EC.

Consequence before repair: a search for `75 m buffer` over this document returns **nothing**,
although the clause is right there on page 80. And any pipeline that did surface it would
quote `7ϱ ŵ ďuffeƌ` to the user as verbatim evidence.

The mapping was derived from corpus evidence (`“`→`S` from `“ultaŶ͛s`→`Sultan's`; `‘`→`R`
from `FA‘`→`FAR`) and is covered by 17 passing tests. After repair, zero suspect characters
remain and `75 m buffer`, `no development zone` and `50, 35 and 25 m` all become findable.

**Failure 3 — tables that extract "successfully" while losing their structure (NOT
detectable by any coverage metric).** This is the dangerous one.

Page 57 holds *Table 6: FAR and Ground Coverage for Plots/Sites up to 20000 sqm, Planning
Zone A*. The page classifies as **readable and clean**. Every coverage metric reports success.
The extracted text reads:

```
Sl.No. Plot/Site Size (sqm)  Maximum Ground Coverage  FAR Road Width (m)
   Base   Allowable against TDR/ any other Rules   Total Maximum allowable
1 Up to 60          Up to 75 %  1.50       1.50  Below 6
5 Above 360 & up to 750  Up to 65 %  1.80  0.45  2.25  15.5 and below 18.5
```

Rows 5–8 carry three FAR figures (base, TDR uplift, total). Rows 1–4 carry **two**, because
the TDR cell is blank — a blank a human sees instantly in the PDF and which vanishes entirely
in flattened text. Nothing in the extraction says which column the missing value belongs to.

So for a 100 sqm plot the correct reading is *total FAR 1.50, no TDR uplift available*. A
model reading the flat text can equally well read *base 1.50 plus TDR 1.50 = 3.00*. **That is
a 2× error on the single number that determines what can be built** — produced with complete
fluency, from a page every quality check calls clean.

> This is the finding that shaped the product. Failure modes 1 and 2 are survivable because
> the system knows. Failure 3 is the one that destroys trust, because **the system does not
> know, and neither does the reader.** Detecting structural damage in tables — inconsistent
> numeric arity across rows of the same table — becomes a first-class requirement rather
> than a nicety.

For the record, the FAR and ground-coverage tables that *are* readable: Tables 6 and 7
(pp. 57–58), Table 8 (p. 65), Table 24 (p. 91), Table 26 (p. 96).

### The constraint the demo is built around — and the secondary source that was wrong

I flagged this in §7 as assumption **A5, blocking**: secondary sources describe plots in an
RMP-2031 **valley zone** facing **FAR reductions of 25–50%**
([Studio Matrx](https://www.studiomatrx.org/india/bengaluru/setbacks),
[Liza Homes](https://lizahomes.in/blog/revised-setback-rules-bengaluru-2026/)).

**I checked it against the primary document. The 25–50% FAR reduction is not in there.**

What RMP 2031 §6.5.3 (p. 80, *Regulations for Eco-sensitive Zones and Water Bodies including
Valley/Streams*) actually says, quoted from the repaired extraction:

- *"In case of water bodies a 75 m buffer of 'no development zone' is to be maintained
  around the lake (as per revenue records)"* — governed by the **NGT Order**.
- Streams are categorised Primary / Secondary / Tertiary per the NGT Order, with buffers of
  **50, 35 and 25 m** respectively, **on either side**, measured from the edge of the stream.
- Within demarcated valley-system buffers, the **only** permitted uses are sewage and water
  treatment plants, and roads, pathways, drains, culverts and bridges that do not obstruct
  the watercourse.
- Buffer land may count toward park and open-space reservation.
- Permissions granted before the notification date remain valid.

This is **categorically different from, and far more severe than, the figure in circulation**.
A 25–50% FAR cut is a haircut. A 75 m no-development zone means you cannot build there at all.

> **This is the strongest argument for the product, and I found it by accident.** I nearly
> built the demo's central conflict on a number from a real-estate blog. The primary document
> says something different and stricter. A professional who Googles this question gets the
> wrong answer confidently; the only defence is reading the actual clause. That is precisely
> what passage-level provenance is for — and I was the user it would have saved.
>
> Recorded as a genuine failed assumption in `14-decision-log.md` and `17-product-case-study.md`.

**The conflict the demo now uses is real and verified.** Bellandur is a lake catchment. The
site measures *excellently* on accessibility (59 live OSM features — Outer Ring Road, tech
corridor). The governing regulation imposes a *75 m no-development buffer* around water
bodies and 50/35/25 m on streams. Both statements are true and they point opposite ways.

And the honest system **cannot resolve it**: the buffers are "marked on the proposed land use
plans" — which are the drawings on the unreadable pages, and the lake extent is defined "as
per revenue records", which are not open data. So the correct output is not an answer. It is:
*here is the clause, here is why it may be decisive, here is exactly what you must obtain to
find out, and here is why the figure you may have read elsewhere is unsupported.*

That is a genuine `CONFLICT` with a genuine unresolvable gap — not a staged one.

---

## 6. Patterns, gaps, and what not to copy

### Patterns across everything above

1. **The bottleneck is synthesis, not acquisition.** Planso's own framing; the competitor
   landscape confirms it (teams run two or three tools and join the results by hand).
2. **Trust is the live constraint, not capability.** Planso is spending its own hiring
   process asking how to test trust. That is where the product risk sits.
3. **Where rules are prose, computation stops.** Every funded competitor is strong exactly
   where codes are digital. The prose jurisdictions are unserved.
4. **The valuable answer is the one that argues with itself.** Planso puts `CONFLICT` before
   `ANSWER`. Nobody in the comparison tables does.

### Gaps I think are real

- **Passage-level provenance, not document-level.** "Source: RMP 2031" is not evidence.
  "§4.16, page 41, this sentence" is. Their exercise says *"show the source documents"* —
  showing the **passage** is a stronger answer to their own question.
- **Nobody models what the system could not read.** A 206-page PDF with 49 unreadable pages
  is normal, not exceptional. A product that reports its own blind spots — "the setback
  matrix on p.108 is an image I cannot parse; here it is, read it yourself" — is more
  trustworthy than one that silently answers anyway.
- **Geometry and regulation are never held together.** Measured distance is a fact.
  Regulatory consequence is prose. The decision needs both in one frame.
- **Confidence is decorative everywhere.** If a number is shown, something must have
  measured it. Otherwise it is a lie with a progress bar.

### What NOT to copy from Planso

- **Do not rebuild their six-layer stack.** Spatial + context + domain + knowledge +
  organisational + agentic is a company roadmap. Reproducing it as a prototype produces a
  shallow imitation of all six and mastery of none — and reads as a pitch deck, not a
  product.
- **Do not build Knowledge or Organisational intelligence.** Both require a firm's decades of
  private project history. I have none. Any version of it would be fabricated, which violates
  the one principle that matters most here.
- **Do not copy the nine-agent list from the brief.** Planso themselves use four families.
  Nine specialised agents over data sources that do not exist is architecture cosplay —
  agents that each wrap one API call are just functions in a costume.
- **Do not copy their visual language.** Their site is a specific, confident aesthetic. A
  near-copy invites comparison on their terms and looks derivative.
- **Do not adopt their vocabulary wholesale.** Repeating "decision intelligence layer" back
  at the founder demonstrates reading comprehension, not thinking.

---

## 7. Assumptions carried into Phase 1

Stated so they can be falsified later; tracked in `14-decision-log.md`.

| # | Assumption | Risk if wrong | How to test it |
|---|---|---|---|
| A1 | The AEC Product Intern posting is the target role | Deliverable is mis-calibrated | Ask Urval directly |
| A2 | Passage-level citation moves trust more than answer quality | Core product bet is wrong | Show 5 users answer-only vs answer+passage; watch which they act on |
| A3 | Users want the conflict surfaced, not resolved | The `CONFLICT` step is friction, not value | Offer both; see which gets forwarded to a colleague |
| A4 | "I cannot read this page" increases trust rather than reducing confidence | Honest degradation backfires | A/B the unreadable-page disclosure |
| A5 | The valley-zone FAR rule is genuinely in the RMP document | The demo's central conflict is unsupported | Verify against the primary PDF in Phase 2 — **blocking** |
| A6 | An Indian jurisdiction is the right demo geography | Wrong market signal to a founder whose own site shows Dubai | planso.co's spatial example is **Dubai · 25.20°N**, not India. Worth revisiting. |

---

## 8. Sources

- <https://planso.co> — homepage, Technology, Careers, AEC Product Intern role (captured 2026-09-27)
- [Naveen Baskaran N — LinkedIn](https://in.linkedin.com/in/naveen-baskaran)
- [HyperVerge leadership — The Org](https://theorg.com/org/hyperverge/teams/leadership-team)
- [Planso — Junior Backend Developer, Wellfound](https://wellfound.com/jobs/4717817-junior-backend-developer)
- [Planso Intelligence Private Limited — Tracxn](https://tracxn.com/d/legal-entities/india/planso-intelligence-private-limited/__bBP4Cz9mgOin2sY0dPBexrYtzkqGW_9DkRGB75DLrTY)
- [AEC Magazine — AI: eleven start-ups to watch in AEC](https://aecmag.com/news/ai-eleven-start-ups-to-watch-in-aec/)
- [Energent — AI tools for site analysis](https://www.energent.ai/use-cases/en/compare/ai-tools-for-site-analysis)
- [Nomic — best AI for site analysis](https://www.nomic.ai/compare/best-ai-for-site-analysis)
- [Tracxn — Deepblocks](https://tracxn.com/d/companies/deepblocks/__ESEgKBlv9q1nTQBLWgrm_sNWh80jyNRmZKza9wRSf9k)
- [OpenCity — BDA Revised Master Plan 2031](https://data.opencity.in/dataset/bda-revised-master-plan-2031)
- [Studio Matrx — BBMP setbacks reference](https://www.studiomatrx.org/india/bengaluru/setbacks)
- [Liza Homes — revised setback rules Bengaluru 2026](https://lizahomes.in/blog/revised-setback-rules-bengaluru-2026/)
- APIs probed directly: Nominatim, Overpass, Open-Meteo Archive, OpenTopoData
