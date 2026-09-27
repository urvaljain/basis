"use client";

import type { Conflict } from "@/lib/types";

/**
 * A conflict, shown as two columns that do not resolve into one.
 *
 * The layout is the argument. Most tools present measured context and regulatory text on
 * separate screens, where each reads as reassuring or alarming on its own. Here they sit
 * side by side under a heading that says plainly they cannot be compared — because the
 * decision lives in the tension, not in either column.
 *
 * `unresolvable_with_open_data` is given the strongest treatment on the card. That is the
 * honest and common outcome in this domain, and a product that quietly resolved it would be
 * inventing the resolution.
 */

const KIND_LABEL: Record<string, string> = {
  context_vs_regulation: "Measurement vs regulation",
  source_vs_source: "Evidence quality",
  evidence_vs_absence: "Evidence vs absence",
};

export function ConflictCard({ conflict }: { conflict: Conflict }) {
  const unresolvable = conflict.resolvability === "unresolvable_with_open_data";

  return (
    <article
      className="panel overflow-hidden"
      style={{
        borderColor: conflict.severity === 1 ? "var(--conflict)" : "var(--border)",
      }}
    >
      <header className="panel-header flex-wrap">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="tag tag-conflict">{KIND_LABEL[conflict.kind] ?? conflict.kind}</span>
            {unresolvable ? (
              <span className="tag tag-assumption">cannot be resolved with open data</span>
            ) : (
              <span className="tag tag-recommendation">resolvable</span>
            )}
            <span className="mono text-[10px] text-ink-4">severity {conflict.severity}</span>
          </div>
          <h3 className="m-0 text-[15px] font-semibold leading-snug text-ink">
            {conflict.title}
          </h3>
        </div>
      </header>

      <div className="grid gap-px bg-line sm:grid-cols-2">
        <div className="bg-panel p-4">
          <p className="label mb-1.5">What was measured</p>
          <p className="m-0 text-[13px] leading-relaxed text-ink-2">{conflict.measured_side}</p>
        </div>
        <div className="bg-panel p-4">
          <p className="label mb-1.5">What the regulation says</p>
          <p className="m-0 text-[13px] leading-relaxed text-ink-2">
            {conflict.regulatory_side}
          </p>
        </div>
      </div>

      <div className="border-t border-line bg-raised p-4">
        <p className="label mb-1.5">Why it matters</p>
        <p className="m-0 text-[13px] leading-relaxed text-ink">{conflict.why_it_matters}</p>
      </div>

      {conflict.blocking_reasons.length > 0 && (
        <div className="border-t border-line p-4">
          <p className="label mb-2">
            Why these two cannot simply be compared
          </p>
          <ul className="m-0 list-none space-y-2 p-0">
            {conflict.blocking_reasons.map((reason, i) => (
              <li key={i} className="flex gap-2.5 text-[12.5px] leading-relaxed text-ink-2">
                <span className="mono shrink-0 pt-px text-[10px] text-conflict">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {conflict.what_would_resolve_it.length > 0 && (
        <div className="border-t border-line bg-raised p-4">
          <p className="label mb-2">What would settle it</p>
          <ul className="m-0 list-none space-y-1.5 p-0">
            {conflict.what_would_resolve_it.map((item, i) => (
              <li key={i} className="flex gap-2.5 text-[12.5px] leading-relaxed text-ink-2">
                <span aria-hidden className="shrink-0 text-recommendation">
                  →
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
