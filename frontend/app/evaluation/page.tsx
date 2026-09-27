"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EvalReport } from "@/lib/types";

/**
 * The evaluation view.
 *
 * Two rules govern this page, and the second is the one that matters.
 *
 * Every number shown was produced by a run of `app.eval.harness` against ground truth
 * anchored to a page and a phrase in the real document — so a case can only pass by finding
 * the right text in the right place, and there is no judge to persuade.
 *
 * And metrics that were **not** measured are displayed as not measured, with the reason.
 * They are not hidden, not greyed into invisibility, and never filled with a plausible
 * figure. A product arguing that AI claims should be checkable cannot fabricate its own
 * quality metrics — that would be dishonesty about its honesty, which is the one failure it
 * could not survive.
 */
export default function EvaluationPage() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCases, setShowCases] = useState(false);

  useEffect(() => {
    api.evaluation().then((r) => (r.ok ? setReport(r.data) : setError(r.message)));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-content px-4 py-10 sm:px-6">
        <div className="panel border-l-[3px] p-4" style={{ borderLeftColor: "var(--assumption)" }}>
          <p className="m-0 text-[13px] font-medium text-ink">No evaluation results</p>
          <p className="m-0 mt-1.5 text-[12.5px] leading-relaxed text-ink-2">{error}</p>
          <p className="m-0 mt-2 text-[12px] leading-relaxed text-ink-3">
            This page shows results from an actual run. It does not display placeholder
            figures when none exist.
          </p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-content space-y-3 px-4 py-10 sm:px-6">
        <div className="skeleton h-8 w-1/3" />
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }

  const measured = report.metrics.filter((m) => m.status === "measured");
  const unmeasured = report.metrics.filter((m) => m.status === "not_measured");
  const passed = report.cases.filter((c) => c.passed).length;

  return (
    <div className="mx-auto max-w-content px-4 py-8 sm:px-6">
      <header className="max-w-3xl">
        <p className="label mb-2">Evaluation</p>
        <h1 className="m-0 text-[24px] font-semibold leading-tight tracking-tight text-ink">
          Measured, not asserted
        </h1>
        <p className="m-0 mt-3 text-[13.5px] leading-relaxed text-ink-2">
          {report.case_count} cases, each anchored to a page and a phrase in the real
          document. Ground truth is validated against the corpus before anything is scored —
          if a case&apos;s expected phrase is not where it claims to be, the run aborts
          rather than reporting a number that means nothing.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-[11.5px] text-ink-4">
          <span className="mono">run {report.run_at}</span>
          <span className={`tag ${report.mode === "extractive" ? "tag-fact" : "tag-inference"}`}>
            {report.mode}
          </span>
          <span className="mono">
            {passed}/{report.case_count} cases fully passed
          </span>
        </div>
      </header>

      <section className="mt-7">
        <h2 className="m-0 mb-3 text-[14px] font-semibold text-ink">Measured</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {measured.map((metric) => {
            const pct = metric.unit === "%" ? metric.value : null;
            const good = pct == null ? null : pct >= 90;
            const weak = pct != null && pct < 70;
            return (
              <div key={metric.name} className="panel p-3.5">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="mono m-0 text-[12px] font-medium text-ink-2">
                    {metric.name.replace(/_/g, " ")}
                  </h3>
                  <span
                    className={`mono text-[17px] font-medium ${
                      good ? "text-recommendation" : weak ? "text-assumption" : "text-ink"
                    }`}
                  >
                    {metric.display}
                  </span>
                </div>

                {pct != null && (
                  <div className="mt-2 h-1 overflow-hidden rounded bg-raised">
                    <div
                      className="h-full rounded"
                      style={{
                        width: `${pct}%`,
                        background: good
                          ? "var(--recommendation)"
                          : weak
                            ? "var(--assumption)"
                            : "var(--inference)",
                      }}
                    />
                  </div>
                )}

                <p className="m-0 mt-2 text-[12px] leading-relaxed text-ink-3">
                  {metric.description}
                </p>

                {metric.failures.length > 0 && (
                  <ul className="m-0 mt-2 list-none space-y-0.5 p-0">
                    {metric.failures.map((f, i) => (
                      <li key={i} className="mono text-[10.5px] text-conflict">
                        ✗ {String((f as { case?: string }).case ?? "")}{" "}
                        <span className="text-ink-4">
                          {String((f as { question?: string }).question ?? "").slice(0, 52)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {unmeasured.length > 0 && (
        <section className="mt-7">
          <h2 className="m-0 mb-1 text-[14px] font-semibold text-ink">Not measured</h2>
          <p className="m-0 mb-3 max-w-2xl text-[12.5px] leading-relaxed text-ink-3">
            These require a language model to produce generated prose to evaluate. This run
            used extractive mode, so there is nothing to measure. They are shown here rather
            than omitted, because a metrics page that quietly drops what it could not measure
            reads exactly like one that measured everything.
          </p>
          <div className="panel divide-y divide-line">
            {unmeasured.map((metric) => (
              <div key={metric.name} className="flex flex-wrap gap-x-4 gap-y-1 p-3">
                <span className="mono w-52 shrink-0 text-[12px] text-ink-2">
                  {metric.name.replace(/_/g, " ")}
                </span>
                <span className="mono text-[12px] text-assumption">not measured</span>
                <span className="w-full text-[11.5px] leading-relaxed text-ink-4">
                  {metric.description} — {metric.reason_not_measured}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mt-7">
        <button
          type="button"
          onClick={() => setShowCases((v) => !v)}
          className="btn text-[12px]"
          aria-expanded={showCases}
        >
          {showCases ? "Hide" : "Show"} all {report.case_count} cases
        </button>

        {showCases && (
          <div className="panel mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-line text-left">
                  {["", "id", "kind", "question", "checks", "ms"].map((h) => (
                    <th key={h} className="label px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {report.cases.map((c) => {
                  const failed = Object.entries(c.checks).filter(([, v]) => v === false);
                  return (
                    <tr key={c.id} className="border-b border-line align-top last:border-0">
                      <td className="px-3 py-2">
                        <span className={c.passed ? "text-recommendation" : "text-conflict"}>
                          {c.passed ? "✓" : "✗"}
                        </span>
                      </td>
                      <td className="mono px-3 py-2 text-ink-2">{c.id}</td>
                      <td className="px-3 py-2 text-ink-3">{c.kind.replace(/_/g, " ")}</td>
                      <td className="max-w-md px-3 py-2 text-ink-2">
                        {c.question}
                        {c.note && (
                          <span className="mt-0.5 block text-[11px] text-ink-4">{c.note}</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {failed.length === 0 ? (
                          <span className="text-ink-4">—</span>
                        ) : (
                          <span className="mono text-[10.5px] text-conflict">
                            {failed.map(([k]) => k).join(", ")}
                          </span>
                        )}
                      </td>
                      <td className="mono px-3 py-2 text-ink-4">{c.latency_ms}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
