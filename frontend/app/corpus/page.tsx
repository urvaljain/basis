"use client";

import { useEffect, useState } from "react";
import { PageViewer } from "@/components/PageViewer";
import { api } from "@/lib/api";
import type { Corpus } from "@/lib/types";

/**
 * The corpus page: what the system can and cannot read, stated up front.
 *
 * Most products hide their ingestion quality, because "73.8% text coverage" sounds like a
 * failure. It is not — it is the true state of a real government PDF, and a reader who
 * knows it can calibrate everything else. A product claiming to have read a document it has
 * only partly read is making a much larger claim than it can support.
 */
export default function CorpusPage() {
  const [corpus, setCorpus] = useState<Corpus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openPage, setOpenPage] = useState<number | null>(null);

  useEffect(() => {
    api.corpus().then((r) => (r.ok ? setCorpus(r.data) : setError(r.message)));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-content px-4 py-10 sm:px-6">
        <p className="text-[13px] text-conflict">Could not load the corpus: {error}</p>
      </div>
    );
  }

  if (!corpus) {
    return (
      <div className="mx-auto max-w-content space-y-3 px-4 py-10 sm:px-6">
        <div className="skeleton h-8 w-1/3" />
        <div className="skeleton h-40 w-full" />
      </div>
    );
  }

  const coveragePct = (corpus.text_coverage * 100).toFixed(1);

  return (
    <div className="mx-auto max-w-content px-4 py-8 sm:px-6">
      <header className="max-w-3xl">
        <p className="label mb-2">Source document</p>
        <h1 className="m-0 text-[24px] font-semibold leading-tight tracking-tight text-ink">
          {corpus.title}
        </h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {corpus.is_draft && <span className="tag tag-assumption">draft document</span>}
          <span className="mono text-[11px] text-ink-4">
            sha256 {corpus.sha256.slice(0, 24)}…
          </span>
        </div>
        <p className="m-0 mt-3 text-[13.5px] leading-relaxed text-ink-2">
          Everything below is measured by the ingestion pipeline, not estimated. The numbers
          are what a real government PDF actually yields.
        </p>
      </header>

      <dl className="m-0 mt-6 grid grid-cols-2 gap-px overflow-hidden rounded border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
        {[
          ["pages", String(corpus.page_count)],
          ["text coverage", `${coveragePct}%`],
          ["unreadable pages", String(corpus.unreadable_page_count)],
          ["characters", corpus.total_chars.toLocaleString()],
          ["chars repaired", String(corpus.total_substitutions)],
          ["citable chunks", corpus.chunk_count.toLocaleString()],
        ].map(([label, value]) => (
          <div key={label} className="bg-panel px-3 py-3">
            <dt className="label">{label}</dt>
            <dd className="mono m-0 mt-0.5 text-[20px] font-medium text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-8 grid gap-5 lg:grid-cols-2">
        <section className="panel">
          <div className="panel-header">
            <h2 className="m-0 text-[13px] font-semibold text-ink">
              Pages with no machine-readable text
            </h2>
            <span className="tag tag-unreadable">{corpus.unreadable_page_count} pages</span>
          </div>
          <div className="p-3.5">
            <p className="m-0 mb-3 text-[12.5px] leading-relaxed text-ink-2">
              Scans and drawings. Nothing in these pages is searchable, and a provision in
              them can contradict anything retrieved elsewhere. Click a range to read it.
            </p>
            <ul className="m-0 list-none space-y-1.5 p-0">
              {corpus.unreadable_ranges.map((range) => {
                const [start, end] = [range[0]!, range[1]!];
                const count = end - start + 1;
                return (
                  <li key={`${start}-${end}`}>
                    <button
                      type="button"
                      onClick={() => setOpenPage(start)}
                      className="flex w-full items-baseline gap-3 rounded border border-line px-2.5 py-2 text-left transition-colors hover:border-line-strong hover:bg-hover"
                    >
                      <span className="mono text-[12px] text-unreadable">
                        {start === end ? `p. ${start}` : `pp. ${start}–${end}`}
                      </span>
                      <span className="text-[11.5px] text-ink-3">
                        {count} page{count === 1 ? "" : "s"}
                      </span>
                      {count >= 15 && (
                        <span className="ml-auto text-[11px] text-assumption">
                          large gap
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2 className="m-0 text-[13px] font-semibold text-ink">
              Tables whose structure was lost
            </h2>
            <span className="tag tag-conflict">{corpus.risky_tables.length} tables</span>
          </div>
          <div className="p-3.5">
            <p className="m-0 mb-3 text-[12.5px] leading-relaxed text-ink-2">
              These pages extract cleanly — every coverage metric calls them fine. But a PDF
              table is a visual grid, and flattening it to text discards which column a value
              sits under. Every one flagged here is a FAR or ground coverage table: the
              numbers that decide what can be built.
            </p>
            <ul className="m-0 list-none space-y-2 p-0">
              {corpus.risky_tables.map((table, i) => (
                <li key={i} className="rounded border border-line p-2.5">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <button
                      type="button"
                      onClick={() => setOpenPage(table.page)}
                      className="mono cursor-pointer border-0 bg-transparent p-0 text-[12px] text-inference underline decoration-dotted underline-offset-2 hover:decoration-solid"
                    >
                      p. {table.page}
                    </button>
                    <span
                      className={`tag ${table.risk === "severe" ? "tag-conflict" : "tag-assumption"}`}
                    >
                      {table.risk.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="m-0 mt-1 text-[12px] leading-snug text-ink-2">
                    {table.caption}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="panel mt-5">
        <div className="panel-header">
          <h2 className="m-0 text-[13px] font-semibold text-ink">Page quality breakdown</h2>
          <span className="mono text-[11px] text-ink-4">
            {corpus.pages_needing_repair} pages needed repair
          </span>
        </div>
        <div className="p-3.5">
          <div className="mb-3 flex h-3 overflow-hidden rounded">
            {(
              [
                ["clean", "var(--fact-dim)"],
                ["repaired", "var(--inference)"],
                ["heavily_repaired", "var(--assumption)"],
                ["unreadable", "var(--unreadable)"],
                ["residual_corruption", "var(--conflict)"],
              ] as const
            ).map(([key, colour]) => {
              const count = corpus.quality_breakdown[key] ?? 0;
              if (!count) return null;
              return (
                <div
                  key={key}
                  title={`${key.replace(/_/g, " ")}: ${count} pages`}
                  style={{
                    width: `${(count / corpus.page_count) * 100}%`,
                    background: colour,
                  }}
                />
              );
            })}
          </div>
          <dl className="m-0 grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-5">
            {Object.entries(corpus.quality_breakdown).map(([key, count]) => (
              <div key={key} className="flex items-baseline gap-2">
                <dt className="text-[12px] text-ink-3">{key.replace(/_/g, " ")}</dt>
                <dd className="mono m-0 text-[13px] text-ink">{count}</dd>
              </div>
            ))}
          </dl>
          <p className="m-0 mt-3 text-[11.5px] leading-relaxed text-ink-4">
            <strong className="font-medium text-ink-3">residual corruption: 0</strong> means
            the repair map fully covers this document. A non-zero value would mean an
            encoding pattern the pipeline does not yet recognise — which is a signal to
            extend the map from evidence, never to suppress the warning.
          </p>
        </div>
      </section>

      {openPage !== null && (
        <PageViewer pageNumber={openPage} onClose={() => setOpenPage(null)} />
      )}
    </div>
  );
}
