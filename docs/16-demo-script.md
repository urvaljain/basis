# 16 — Demo Script

Three minutes. One real site, one real 206-page government document, three questions.

**Setup:** `/demo` runs the walkthrough with the narration built in. This script is for
driving it live, where you can talk over it. Provider responses replay from recordings
captured 2026-09-27, so nothing depends on Overpass being up.

**The one rule:** do not explain the architecture. Show three questions and let the third one
land.

---

## 0:00 — The frame (20s)

> "This is a 206-page draft master plan from the Bangalore Development Authority. In
> Bengaluru, the rules that actually decide a project — zoning, FAR, setbacks, buffers — are
> not an API. They're in this PDF.
>
> So I built something that reads it. The interesting part isn't that it answers questions.
> It's what it does when it can't."

Open `/workspace`, Bellandur selected.

---

## 0:20 — Question one: a good answer (40s)

**Ask:** *What buffer applies around a lake?*

Result in ~30 ms. Point at one evidence card.

> "Every claim is a verbatim passage. Page 80, characters 1603 to 1975."

**Click the citation.** Page opens, the cited span highlighted.

> "Four seconds to check. That's the whole design — a citation you won't check is decoration."

Now point at the amber label beneath the quote.

> "**Reconstructed — not verbatim.** This page is mis-encoded in the source PDF. The digits
> are corrupted: '75 m' extracts as '7-rho m'."

**Click "show raw extraction."**

> "Before repair, searching this document for '75 m buffer' returns nothing. The clause is
> right there on page 80 and it's unfindable. 542 characters across 37 pages are like this."

---

## 1:00 — Question two: no answer at all (50s)

**Ask:** *What are the TDR rules for transferable development rights?*

> "Transferable Development Rights directly increase how much you can build. Real question."

The violet panel appears: **23 pages bearing on this question carry no machine-readable text.**

> "The governing instrument is in this document — Annexure-1, the Karnataka TCP Benefit of
> Development Rights Rules 2016. Twenty-three scanned pages. Invisible to every form of text
> search."

**Click "Show me the pages."** The rendered page appears.

> "Here's the thing. A normal retrieval pipeline answers this question fluently, from the
> prose that happens to surround the gap. It has no way to know the rules are invisible to
> it — and neither does the reader.
>
> This says: I can't read this, here's what it is, here's the page, go and read it yourself."

**Pause here. This is the moment.**

---

## 1:50 — Question three: the decision (60s)

**Ask:** *Is this site affected by a water body or valley buffer, and what does that restrict?*

The conflict card, two columns.

> "The site measures well. Outer Ring Road 216 metres, hospital 108 metres, 131 mapped
> features. Nearest watercourse 153 metres.
>
> The regulation imposes a 75-metre no-development buffer around water bodies, and 50, 35 or
> 25 metres on watercourses.
>
> So the obvious inference is: 153 is bigger than 75, we're clear."

Point at the numbered blocking reasons.

> "It says that inference is invalid, and gives four reasons. The buffer depends on whether
> the watercourse is Primary, Secondary or Tertiary under the NGT Order — OpenStreetMap
> doesn't record that. For lakes it's measured from the boundary in the revenue records, which
> aren't open data. The valley overlay is on drawings it can't read. And straight-line
> distance to a centroid isn't the distance from your plot boundary to the water's edge.
>
> It doesn't say you're clear. It doesn't say you're affected. It says: **this comparison
> can't be made with available data, here's exactly what you need, and here's who has it.**"

Scroll to **Verify next**.

> "Named tasks, with an addressee. 'Obtain the RMP Planning District sheet for this survey
> number' — Bangalore Development Authority planning office."

---

## 2:50 — Land it (30s)

Open `/evaluation`.

> "Twenty-three test cases, ground truth anchored to pages and phrases in the real document —
> validated before anything is scored, so a broken case aborts the run rather than reporting
> a number that means nothing.
>
> Blind-spot recall 100%. Overclaim resistance 100%. Citation precision at 1 is 61.5%, which
> is the weakest number here and it's on the page."

Scroll to **Not measured**.

> "And four metrics say 'not measured', with the reason. They need a model to generate prose
> and this run was extractive. I'm not going to estimate them."

> "The thing I'd want to test next isn't in here. Whether any of this actually makes someone
> trust the output — that needs five users and a week, not a harness."

---

## If asked: "what surprised you?"

> "I nearly built the demo on a number that doesn't exist. Every source online says a
> Bengaluru valley zone cuts FAR by 25 to 50%. I flagged it as a blocking assumption and
> checked it against the primary document.
>
> It's not in there. What the document actually says is a 75-metre no-development zone — which
> is categorically stricter. A FAR cut is a haircut; a no-development zone means you can't
> build at all.
>
> I was the user my own product would have saved."

## If asked: "what's the weakest part?"

> "Citation precision at rank one. And one absence case still slips through — asking about
> market price matches on 'market' and 'square', which genuinely occur in a planning document.
> I left both. Tuning a threshold until a specific test passes gives you a number that
> describes the threshold, not the system."

## If asked: "why no score?"

> "I built one. It demoed well. I removed it because once a number exists nobody opens the
> evidence underneath it — and the evidence is the product.
>
> The comparison view replaced it, and it's better. Three sites, all different on every
> measurement, and the headline is that they're *indistinguishable* on the constraint that
> actually decides. A score would have invented a difference."

---

## Failure drill

| If | Then |
|---|---|
| API is down | `/demo` still runs — provider responses are recorded. Say so; it's the point of the feature. |
| A page image is slow | It renders on first request. Say "that's rendering now — it's not pre-baked." |
| Basemap fails | The feature list below it is the evidence. The map is not load-bearing. |
| Someone asks for a live site | Use the workspace with any Bengaluru locality — geocoding is live. |
