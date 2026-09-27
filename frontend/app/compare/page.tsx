"use client";

import { useCallback, useState } from "react";

/**
 * Site comparison, as an evidence matrix.
 *
 * There is no score and no ranking anywhere on this page — see `backend/app/api/compare.py`
 * for the full reasoning, and `docs/14-decision-log.md` D-004 for the version that was
 * built, looked convincing, and was removed.
 *
 * The most useful thing this view produces is usually not a difference. It is the line at
 * the top saying the sites are *indistinguishable* on the constraint that actually decides —
 * because that tells a reader to stop comparing and go and get a document.
 */

const SITE_OPTIONS = [
  "Bellandur, Bengaluru",
  "Whitefield, Bengaluru",
  "Jayanagar, Bengaluru",
];

const QUESTIONS = [
  "Is this site affected by a water body or valley buffer?",
  "What FAR and ground coverage apply to plots up to 20000 sqm in Planning Zone A?",
  "What buffer applies around a lake?",
];

interface Cell {
  site: string;
  value: string | null;
  established: boolean;
  epistemic_type: string | null;
  source: string | null;
  limitation: string | null;
  proxy_for: string | null;
}

interface Row {
  key: string;
  label: string;
  differentiating: boolean;
  all_established: boolean;
  cells: Cell[];
}

interface Comparison {
  question: string;
  sites: string[];
  rows: Row[];
  coverage: Record<string, Record<string, number>>;
  differentiating: string[];
  undifferentiating: string[];
  critical_question: string;
  conflicts_by_site: Record<
    string,
    { title: string; resolvability: string; severity: number }[]
  >;
  no_score_reason: string;
}

export default function ComparePage() {
  const [sites, setSites] = useState<string[]>(SITE_OPTIONS.slice(0, 3));
  const [question, setQuestion] = useState(QUESTIONS[0]!);
  const [result, setResult] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openCell, setOpenCell] = useState<Cell | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, sites }),
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      setResult((await response.json()) as Comparison);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed");
      setResult(null);
    }
    setLoading(false);
  }, [question, sites]);

  const toggleSite = (site: string) => {
    setSites((current) =>
      current.includes(site)
        ? current.length > 2
          ? current.filter((s) => s !== site)
          : current
        : current.length < 3
          ? [...current, site]
          : current,
    );
  };

  return (
    <div className="mx-auto max-w-content px-4 py-8 sm:px-6">
      <header className="max-w-3xl">
        <p className="label mb-2">Comparison</p>
        <h1 className="m-0 text-[24px] font-semibold leading-tight tracking-tight text-ink">
          Every cell is evidence. There is no score.
        </h1>
        <p className="m-0 mt-3 text-[13.5px] leading-relaxed text-ink-2">
          Ranking sites with a single number requires weights that encode a development
          thesis nobody stated — and once a score exists, nobody opens the evidence beneath
          it. This compares the same question across sites and shows where they genuinely
          differ, where they do not, and where the data cannot tell.
        </p>
      </header>

      <section className="panel mt-6 p-4">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
          <div className="space-y-3">
            <div>
              <p className="label mb-1.5">Sites (2–3)</p>
              <div className="flex flex-wrap gap-1.5">
                {SITE_OPTIONS.map((site) => {
                  const active = sites.includes(site);
                  return (
                    <button
                      key={site}
                      type="button"
                      onClick={() => toggleSite(site)}
                      className={`rounded border px-2.5 py-1.5 text-[12px] transition-colors ${
                        active
                          ? "border-inference bg-[var(--inference-dim)] text-inference"
                          : "border-line text-ink-3 hover:border-line-strong hover:text-ink-2"
                      }`}
                    >
                      {site.split(",")[0]}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label htmlFor="cmp-q" className="label mb-1.5 block">
                Question
              </label>
              <select
                id="cmp-q"
                className="input"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              >
                {QUESTIONS.map((q) => (
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-end">
            <button
              type="button"
              onClick={run}
              disabled={loading || sites.length < 2}
              className="btn btn-primary h-10 px-6"
            >
              {loading ? "Comparing…" : `Compare ${sites.length} sites`}
            </button>
          </div>
        </div>
      </section>

      {error && (
        <div className="panel mt-4 border-l-[3px] p-4" style={{ borderLeftColor: "var(--conflict)" }}>
          <p className="m-0 text-[13px] text-ink">{error}</p>
        </div>
      )}

      {loading && (
        <div className="mt-5 space-y-2">
          <div className="skeleton h-12 w-full" />
          <div className="skeleton h-64 w-full" />
        </div>
      )}

      {result && !loading && (
        <>
          {/* The headline is the constraint, not a winner. */}
          <div
            className="panel mt-5 border-l-[3px] p-4"
            style={{ borderLeftColor: "var(--conflict)" }}
          >
            <p className="label mb-1.5">The question that decides this</p>
            <p className="m-0 text-[14px] leading-relaxed text-ink">
              {result.critical_question}
            </p>
          </div>

          <div className="panel mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr>
                  <th className="label sticky left-0 z-10 bg-panel px-3 py-2.5 text-left font-medium">
                    dimension
                  </th>
                  {result.sites.map((site) => (
                    <th
                      key={site}
                      className="border-l border-line px-3 py-2.5 text-left text-[13px] font-semibold text-ink"
                    >
                      {site.split(",")[0]}
                      <span className="mono ml-2 text-[10px] font-normal text-ink-4">
                        {result.coverage[site]?.cells_established ?? 0}/
                        {result.coverage[site]?.cells_total ?? 0}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.key} className="border-t border-line align-top">
                    <th className="sticky left-0 z-10 bg-panel px-3 py-2.5 text-left font-normal">
                      <span className="text-ink-2">{row.label}</span>
                      {!row.differentiating && row.all_established && (
                        <span
                          className="mono ml-2 text-[10px] text-ink-4"
                          title="All sites read the same on this dimension"
                        >
                          same
                        </span>
                      )}
                    </th>
                    {row.cells.map((cell) => (
                      <td key={cell.site} className="border-l border-line p-0">
                        {cell.established ? (
                          <button
                            type="button"
                            onClick={() => setOpenCell(cell)}
                            className="block h-full w-full cursor-pointer border-0 bg-transparent px-3 py-2.5 text-left text-ink-2 transition-colors hover:bg-hover"
                          >
                            {cell.value}
                            {cell.proxy_for && (
                              <span className="mt-1 block text-[11px] text-ink-4">
                                proxy for {cell.proxy_for}
                              </span>
                            )}
                          </button>
                        ) : (
                          <div className="px-3 py-2.5 text-[12px] text-ink-4">
                            not established
                          </div>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}

                {/* Coverage is measurable. Site quality is not. */}
                <tr className="border-t-2 border-line-strong bg-raised align-top">
                  <th className="sticky left-0 z-10 bg-raised px-3 py-2.5 text-left">
                    <span className="label">evidence coverage</span>
                  </th>
                  {result.sites.map((site) => {
                    const c = result.coverage[site];
                    return (
                      <td key={site} className="border-l border-line px-3 py-2.5">
                        <span className="mono text-[12px] text-ink">
                          {c?.fact ?? 0} facts
                        </span>
                        <span className="mt-0.5 block text-[11px] text-ink-3">
                          {c?.assumption ?? 0} assumptions · {c?.evidence_passages ?? 0}{" "}
                          passages · {c?.unreadable_pages ?? 0} unreadable pages
                        </span>
                      </td>
                    );
                  })}
                </tr>

                <tr className="border-t border-line align-top">
                  <th className="sticky left-0 z-10 bg-panel px-3 py-2.5 text-left">
                    <span className="label">unresolved constraints</span>
                  </th>
                  {result.sites.map((site) => {
                    const conflicts = result.conflicts_by_site[site] ?? [];
                    const unresolved = conflicts.filter(
                      (c) => c.resolvability === "unresolvable_with_open_data",
                    );
                    return (
                      <td key={site} className="border-l border-line px-3 py-2.5">
                        {unresolved.length === 0 ? (
                          <span className="text-[12px] text-ink-4">none detected</span>
                        ) : (
                          <ul className="m-0 list-none space-y-1 p-0">
                            {unresolved.map((c, i) => (
                              <li key={i} className="text-[11.5px] leading-snug text-conflict">
                                {c.title}
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="panel p-3.5">
              <p className="label mb-1.5">Where they genuinely differ</p>
              {result.differentiating.length ? (
                <ul className="m-0 list-none space-y-0.5 p-0">
                  {result.differentiating.map((d) => (
                    <li key={d} className="text-[12.5px] text-ink-2">
                      — {d}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="m-0 text-[12.5px] text-ink-3">
                  No dimension separated these sites.
                </p>
              )}
            </div>
            <div className="panel p-3.5">
              <p className="label mb-1.5">Where the data cannot tell them apart</p>
              {result.undifferentiating.length ? (
                <ul className="m-0 list-none space-y-0.5 p-0">
                  {result.undifferentiating.map((d) => (
                    <li key={d} className="text-[12.5px] text-ink-2">
                      — {d}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="m-0 text-[12.5px] text-ink-3">
                  Every established dimension showed a difference. Note that differing on a
                  measurement is not the same as differing on what the regulation turns on.
                </p>
              )}
            </div>
          </div>

          <p className="m-0 mt-4 max-w-2xl text-[11.5px] leading-relaxed text-ink-4">
            {result.no_score_reason}
          </p>
        </>
      )}

      {openCell && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={() => setOpenCell(null)}
          role="dialog"
          aria-modal="true"
        >
          <div className="panel max-w-lg p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="label">{openCell.site.split(",")[0]}</span>
              <button
                type="button"
                onClick={() => setOpenCell(null)}
                className="btn text-[11px]"
              >
                Close
              </button>
            </div>
            <p className="m-0 text-[13.5px] leading-relaxed text-ink">{openCell.value}</p>
            {openCell.proxy_for && (
              <p className="m-0 mt-2 text-[12px] text-ink-3">
                Used as a proxy for{" "}
                <span className="text-inference">{openCell.proxy_for}</span> — which this
                does not itself establish.
              </p>
            )}
            {openCell.limitation && (
              <p className="m-0 mt-2.5 border-l-2 border-line-strong pl-2.5 text-[11.5px] leading-relaxed text-ink-3">
                <span className="mono text-[10px] uppercase tracking-wider text-ink-4">
                  {openCell.source}
                </span>{" "}
                — {openCell.limitation}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
