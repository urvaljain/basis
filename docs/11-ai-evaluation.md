# 11 — AI Evaluation

Run it yourself:

```bash
cd backend
python -m app.eval.harness --json ../data/eval/results.json
```

---

## The rule

> Every number this product displays traces to a measurement performed by the harness. A
> metric that was not measured is reported as **NOT MEASURED**, with the reason, and rendered
> as such in the interface.

This is not fastidiousness. The product's whole argument is that an AI system should be
checkable. A fabricated quality metric would be dishonesty *about its honesty* — the one
failure it could not survive.

---

## Why these numbers are trustworthy

**Ground truth is a place in a document, not an opinion.** Each case names a page and a phrase
that physically exists in the real 206-page corpus. Nothing encodes a view about what a good
answer sounds like, so a case can only pass by finding the right text in the right place.
There is no judge to persuade.

**Ground truth is validated before anything is scored.** `validate_dataset()` checks every
case against the corpus: does the expected phrase actually appear on the expected page, are
the pages claimed as blind spots genuinely unreadable. **If any case fails, the run aborts.**
An evaluation against wrong ground truth produces numbers that look exactly like real ones,
and a passing score from a broken case is worse than no score at all.

**Most of it needs no language model.** Retrieval, blind-spot detection, caveat propagation
and encoding repair are deterministic — which is why this project has measurements rather than
an unrun script.

---

## The dataset — 23 cases, five kinds

| Kind | n | What it tests |
|---|---|---|
| `answerable` | 10 | The governing text is readable. The system should cite it. |
| `blind_spot` | 3 | The governing text is on unreadable pages. The system should say so rather than answer from surrounding prose. |
| `unreliable_source` | 3 | The answer is in a damaged table or repaired text. The system should answer *and* carry the caveat. |
| `absent` | 3 | The document does not address this. The system should not manufacture coverage. |
| `adversarial` | 4 | Phrased to invite an overclaim — compliance, permission, certainty. |

The `blind_spot` cases are the most important in the set. **B01** asks about Transferable
Development Rights, whose governing instrument is Annexure-1 — 23 scanned pages. A naive
pipeline answers it fluently from the prose that happens to surround the gap.

---

## Results

Run 2026-09-27 · extractive mode · corpus sha256 `d00fcc58…` · **16/23 cases fully passed**

### Measured

| Metric | Result | What it means |
|---|---|---|
| **blind_spot_recall** | **100%** (3/3) | Questions whose answer lies on unreadable pages are reported as such |
| **blind_spot_precision** | **100%** (2/2) | Questions with complete evidence raise no false warning |
| **repair_caveat_propagation** | **100%** (3/3) | Evidence from mis-encoded pages is labelled reconstructed, not verbatim |
| **table_damage_detection** | **100%** (3/3) | Figures from structurally damaged tables carry a column-binding warning |
| **overclaim_resistance** | **100%** (4/4) | Adversarial questions elicit no compliance, permission or certainty |
| **governing_phrase_retrieved** | 92.3% (12/13) | The exact governing phrase appears in the cited evidence |
| **citation_page_recall** | 84.6% (11/13) | Retrieved evidence includes the page that actually contains the governing text |
| **absence_handling** | 66.7% (2/3) | Questions the document does not address produce no manufactured coverage |
| **citation_precision@1** | 61.5% (8/13) | The single highest-ranked passage is on a correct page |
| **median latency** | 31 ms | End to end, providers served from recordings |
| **p95 latency** | 46 ms | |

### Not measured

Reported as such rather than estimated. All four require generated prose, and extractive mode
produces none.

| Metric | Why not |
|---|---|
| `unsupported_claim_rate` | No generated sentences to check against evidence |
| `uncertainty_calibration` | No stated confidence on generated answers |
| `answer_completeness` | No generated answers |
| `cost_per_analysis` | No model calls, therefore no cost |

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` and re-run to populate them.

---

## What the evaluation caught

The first run found four real bugs that would otherwise have shipped. This is the argument for
building the harness before polishing the interface.

**1 · Absence handling was 0%.** Asked *"who currently owns this parcel?"*, the system
confidently returned §2.123 defining "site" — a real passage, correctly retrieved, that does
not address the question. BM25 always returns *something*, and presenting it as evidence
manufactures coverage the document does not have. That is the product's own cardinal sin,
committed by the product.

*Fixed* with an evidence floor: the top passage must share ≥2 distinct terms with the query,
one of them distinctive (idf ≥ 3.0). Measured across the set — 20/20 genuine questions
accepted, 2/3 absent rejected.

**2 · No stemming.** A question about a "drain" could not reach §2.41 defining *Drains/
Halla*. The governing definition was present, indexed and unreachable, because `drain` never
matched `Drains`.

**3 · Table captions fused into 1,400-character chunks.** BM25 length normalisation then
buried Table 8 entirely — a question naming every word in its caption could not find it.
*Fixed* by making a table caption its own chunk boundary.

**4 · Table risk keyed to extracted numbers.** When retrieval surfaced a table's *caption* —
which ranks highest, since it names the subject — the column-damage warning was absent,
because the caption contains no digits. *Fixed* by propagating risk at chunk level.

**Movement:** page recall 61.5 → 84.6% · phrase retrieval 76.9 → 92.3% · absence handling
0 → 66.7% · table damage detection 66.7 → 100%.

---

## Known failures, and why they were not fixed

Two results are below where they could be. Both are reported rather than tuned away.

**`citation_precision@1` = 61.5%.** Recall is 84.6%, so the right page *is* retrieved — it is
not always ranked first. Top-1 exactness is a strict metric and the evidence panel shows six
passages, so a correct page at rank 2 costs a reader very little.

**N01 still passes the absence filter.** *"What is the current market price per square foot?"*
matches on *market* and *square*, which genuinely occur in this corpus. Lowering the bar until
this case goes green would weaken the filter for every other question.

> **Tuning a threshold until a specific test passes produces a number that describes the
> threshold, not the system.** The point of an evaluation is to be informed by it, not to
> reach a target. Both failures are in the dataset, visible in the interface, and recorded
> here.

---

## Blind-spot relevance: three rules, measured

A blind spot must fire when the question bears on it and stay quiet otherwise — a warning that
fires on coincidence teaches users to dismiss warnings.

| Rule | TDR (want yes) | heritage | water (want no) | FAR-a (no) | FAR-b (no) | Separates? |
|---|---|---|---|---|---|---|
| ≥ 2 matched terms | yes | yes | yes | yes | yes | **no** |
| sum(idf) ≥ threshold | 11.20 | 3.59 | 4.10 | 4.96 | 3.74 | **no** — unwanted cases outscore a wanted one |
| **max(idf) ≥ 3.0** | **5.21** | 2.00 | 2.15 | 2.78 | 2.15 | **yes** |

Summing rewards accumulating generic words, which is the coincidence being guarded against.
The accepted cost is one known false negative, recorded as a test so it cannot regress
silently.

---

## What this evaluation cannot tell you

The honest limit, stated plainly.

**It does not measure whether anyone trusts the output.** That is the question Planso poses in
its own hiring exercise, and it cannot be answered without users. Everything here measures
whether the system is *correct and honest about its limits* — a necessary condition for trust,
and not the same thing.

Testing the actual question needs five practitioners and five working days:

1. Show three the answer with passage-level citations; three the same answer without.
2. Measure who opens the evidence, who forwards the finding to a colleague, and who acts.
3. Watch specifically what happens at the blind-spot case — does reporting the gap increase
   confidence in everything else, or reduce it?

A4 in `research.md` §7 records the assumption that honest degradation *increases* trust. It is
untested. It might be wrong.
