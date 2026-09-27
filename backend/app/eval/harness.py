"""Evaluation harness — runs the dataset and reports only what it measured.

    python -m app.eval.harness
    python -m app.eval.harness --json data/eval/results.json

## Ground truth is validated before anything is scored

The first thing this does is check every case against the corpus: does the expected phrase
actually appear on the expected page, are the pages claimed as blind spots genuinely
unreadable. If any case fails that check the run **aborts**.

That is deliberate. An evaluation against wrong ground truth produces numbers that look
exactly like real ones, and a passing score from a broken case is worse than no score — it
is a fabricated metric wearing the costume of a measurement, which is precisely what this
product argues against.

## Why these numbers are trustworthy without a model

Retrieval, blind-spot detection, caveat propagation and repair are deterministic. Ground
truth is a page and a phrase in a real 206-page government document. So a case can only pass
by finding the right text on the right page — there is no judge to persuade.

Metrics that genuinely require generation are reported as ``NOT_MEASURED`` with the reason.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.orchestrator import Finding, Orchestrator
from app.eval.dataset import DATASET, CaseKind, EvalCase, validate_dataset
from app.eval.metrics import EvalReport, Metric
from app.ingest.chunker import chunk_document
from app.ingest.pdf_extract import DocumentExtraction, extract_document
from app.ingest.retriever import RegulationIndex
from app.providers.llm import get_llm

CORPUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "corpus"
    / "bengaluru-rmp-2031-vol6-zoning-regulations.pdf"
)

# The site is fixed across the set so regulation behaviour is what varies. Bellandur has
# captured fixtures, so evaluation runs are reproducible and do not hammer public APIs.
EVAL_SITE = "Bellandur, Bengaluru"


class Harness:
    def __init__(self, doc: DocumentExtraction, index: RegulationIndex) -> None:
        self.doc = doc
        self.index = index
        self.llm = get_llm()

    # ------------------------------------------------------------------ per case

    async def run_case(self, case: EvalCase, orchestrator: Orchestrator) -> dict[str, Any]:
        started = time.monotonic()
        finding = await orchestrator.run(question=case.question, location_query=EVAL_SITE)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        evidence_pages = [
            c.source.document.page_number for c in finding.evidence if c.source.document
        ]
        evidence_text = " ".join(
            c.source.document.quote for c in finding.evidence if c.source.document
        ).lower()
        blind = [(u["page_start"], u["page_end"]) for u in finding.unreadable]

        checks: dict[str, bool | None] = {}

        # --- retrieval ---
        if case.expected_pages:
            checks["page_recall"] = any(p in evidence_pages for p in case.expected_pages)
            checks["page_precision_at_1"] = (
                bool(evidence_pages) and evidence_pages[0] in case.expected_pages
            )
        if case.expected_phrase:
            checks["phrase_found"] = case.expected_phrase.lower() in evidence_text

        # --- blind spots ---
        if case.expected_blind_spot_pages:
            want = case.expected_blind_spot_pages
            checks["blind_spot_reported"] = any(
                b[0] <= want[0] and b[1] >= want[1] for b in blind
            )
        if case.expect_no_blind_spot:
            checks["no_false_blind_spot"] = not blind

        # --- caveat propagation ---
        if case.expect_repair_caveat:
            checks["repair_caveat_present"] = any(
                c.source.document is not None and c.source.document.text_was_repaired
                for c in finding.evidence
            )
        if case.expect_table_risk:
            reg = finding.regulation
            checks["table_risk_flagged"] = bool(reg and reg.has_table_risk)

        # --- absence handling ---
        if case.expect_no_evidence:
            # Passing means either no evidence was found, or a gap was declared. Silently
            # returning loosely-related passages as if they answered the question is the
            # failure being tested for.
            reg = finding.regulation
            checks["absence_handled"] = bool(
                not finding.evidence or (reg and reg.gaps)
            )

        # --- adversarial ---
        if case.forbidden_phrases:
            surface = " ".join(
                [finding.answer or "", *(s.text for s in finding.statements)]
            ).lower()
            offenders = [p for p in case.forbidden_phrases if p.lower() in surface]
            checks["no_overclaim"] = not offenders
        else:
            offenders = []

        return {
            "id": case.id,
            "kind": case.kind.value,
            "question": case.question,
            "checks": checks,
            "passed": all(v for v in checks.values() if v is not None),
            "latency_ms": elapsed_ms,
            "evidence_pages": evidence_pages[:6],
            "blind_spots": blind,
            "offending_phrases": offenders,
            "note": case.note,
        }

    # ------------------------------------------------------------------ aggregate

    def build_report(self, results: list[dict[str, Any]]) -> EvalReport:
        def tally(check: str) -> tuple[int, int, list[dict[str, Any]]]:
            hits = misses = 0
            failures = []
            for r in results:
                value = r["checks"].get(check)
                if value is None:
                    continue
                if value:
                    hits += 1
                else:
                    misses += 1
                    failures.append(
                        {"case": r["id"], "question": r["question"][:70], "check": check}
                    )
            return hits, hits + misses, failures

        metrics: list[Metric] = []

        recall_hits, recall_total, recall_fail = tally("page_recall")
        metrics.append(
            Metric.measured(
                "citation_page_recall",
                "Retrieved evidence includes the page that actually contains the governing text.",
                recall_hits, recall_total, failures=recall_fail,
            )
        )

        p1_hits, p1_total, p1_fail = tally("page_precision_at_1")
        metrics.append(
            Metric.measured(
                "citation_precision_at_1",
                "The single highest-ranked passage is on a correct page.",
                p1_hits, p1_total, failures=p1_fail,
            )
        )

        ph_hits, ph_total, ph_fail = tally("phrase_found")
        metrics.append(
            Metric.measured(
                "governing_phrase_retrieved",
                "The exact governing phrase appears in the cited evidence.",
                ph_hits, ph_total, failures=ph_fail,
            )
        )

        bs_hits, bs_total, bs_fail = tally("blind_spot_reported")
        metrics.append(
            Metric.measured(
                "blind_spot_recall",
                "Questions whose answer lies on unreadable pages are reported as such.",
                bs_hits, bs_total, failures=bs_fail,
            )
        )

        nbs_hits, nbs_total, nbs_fail = tally("no_false_blind_spot")
        metrics.append(
            Metric.measured(
                "blind_spot_precision",
                "Questions with complete evidence do NOT raise a false blind-spot warning.",
                nbs_hits, nbs_total, failures=nbs_fail,
            )
        )

        rc_hits, rc_total, rc_fail = tally("repair_caveat_present")
        metrics.append(
            Metric.measured(
                "repair_caveat_propagation",
                "Evidence from mis-encoded pages is labelled as reconstructed, not verbatim.",
                rc_hits, rc_total, failures=rc_fail,
            )
        )

        tr_hits, tr_total, tr_fail = tally("table_risk_flagged")
        metrics.append(
            Metric.measured(
                "table_damage_detection",
                "Figures from structurally damaged tables carry a column-binding warning.",
                tr_hits, tr_total, failures=tr_fail,
            )
        )

        ab_hits, ab_total, ab_fail = tally("absence_handled")
        metrics.append(
            Metric.measured(
                "absence_handling",
                "Questions the document does not address do not produce manufactured coverage.",
                ab_hits, ab_total, failures=ab_fail,
            )
        )

        oc_hits, oc_total, oc_fail = tally("no_overclaim")
        metrics.append(
            Metric.measured(
                "overclaim_resistance",
                "Adversarial questions do not elicit compliance, permission or certainty.",
                oc_hits, oc_total, failures=oc_fail,
            )
        )

        latencies = sorted(r["latency_ms"] for r in results)
        if latencies:
            metrics.append(
                Metric.scalar(
                    "median_latency",
                    "Median end-to-end analysis time (providers served from recordings).",
                    latencies[len(latencies) // 2], "ms",
                )
            )
            metrics.append(
                Metric.scalar(
                    "p95_latency",
                    "95th-percentile end-to-end analysis time.",
                    latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))], "ms",
                )
            )

        # Honestly unmeasured without a model.
        if not self.llm.available:
            for name, description in [
                (
                    "unsupported_claim_rate",
                    "Share of generated sentences not supported by retrieved evidence.",
                ),
                (
                    "uncertainty_calibration",
                    "Whether stated confidence tracks measured correctness.",
                ),
                (
                    "answer_completeness",
                    "Whether generated answers address every part of the question.",
                ),
                ("cost_per_analysis", "Model spend per analysis."),
            ]:
                metrics.append(
                    Metric.unmeasured(
                        name,
                        description,
                        "No language model configured — this run used extractive mode, which "
                        "generates no prose. Requires ANTHROPIC_API_KEY or OPENAI_API_KEY.",
                    )
                )

        return EvalReport(
            run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            mode="extractive" if not self.llm.available else "generative",
            corpus_title=self.doc.title,
            corpus_sha256=self.doc.source_sha256,
            case_count=len(results),
            metrics=metrics,
            case_results=results,
        )


async def run(cases: list[EvalCase] | None = None) -> EvalReport:
    cases = cases or DATASET

    doc = extract_document(str(CORPUS_PATH), render_unreadable=False)
    chunks = chunk_document(doc, "rmp2031")
    index = RegulationIndex(chunks)

    # Validate ground truth BEFORE scoring anything.
    pages = [p.text if p.is_readable else "" for p in doc.pages]
    unreadable = set(doc.unreadable_pages)
    problems = validate_dataset(pages, unreadable)
    if problems:
        print(f"GROUND TRUTH INVALID — {len(problems)} problem(s). Refusing to score.\n")
        for p in problems:
            print(f"  ✗ {p}")
        raise SystemExit(2)
    print(f"Ground truth validated: {len(cases)} cases against {doc.page_count} pages.\n")

    harness = Harness(doc, index)
    orchestrator = Orchestrator(index, harness.llm)

    results = []
    for case in cases:
        result = await harness.run_case(case, orchestrator)
        results.append(result)
        mark = "✓" if result["passed"] else "✗"
        failed = [k for k, v in result["checks"].items() if v is False]
        detail = f"  [{', '.join(failed)}]" if failed else ""
        print(f"  {mark} {case.id} {case.kind.value:18s} {result['latency_ms']:5d}ms{detail}")

    return harness.build_report(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write the full report to this path")
    parser.add_argument("--kind", help="run only one case kind")
    args = parser.parse_args()

    cases = DATASET
    if args.kind:
        cases = [c for c in DATASET if c.kind.value == args.kind]
        if not cases:
            print(f"no cases of kind {args.kind!r}")
            return 1

    report = asyncio.run(run(cases))
    print()
    print(report.render())

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
        print(f"\nwrote {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
