"use client";

import { useCallback, useEffect, useState } from "react";
import { FindingView } from "@/components/FindingView";
import { SiteMap } from "@/components/SiteMap";
import { api } from "@/lib/api";
import type { Finding, Health } from "@/lib/types";

/**
 * The workspace.
 *
 * The unit of work is a **question about a site**, not a report about a location. That
 * follows from watching how these decisions actually stall: nobody is blocked for want of a
 * site summary, they are blocked on one specific thing they cannot establish.
 *
 * So the entry point asks for both, and the starter questions are real ones with real
 * answers in this corpus — including one whose answer the system cannot read at all.
 */

const SITES = [
  { label: "Bellandur, Bengaluru", note: "lake catchment on a dense tech corridor" },
  { label: "Whitefield, Bengaluru", note: "comparator" },
  { label: "Jayanagar, Bengaluru", note: "comparator" },
];

const QUESTIONS = [
  {
    q: "Is this site affected by a water body or valley buffer, and what does that restrict?",
    note: "measurement meets a provision it cannot be compared with",
  },
  {
    q: "What FAR and ground coverage apply to plots up to 20000 sqm in Planning Zone A?",
    note: "the governing table's columns were destroyed by extraction",
  },
  {
    q: "What are the TDR rules for transferable development rights?",
    note: "the governing instrument is 23 scanned pages",
  },
  {
    q: "What buffer applies around a lake?",
    note: "only findable because the encoding was repaired",
  },
];

export default function WorkspacePage() {
  const [location, setLocation] = useState(SITES[0]!.label);
  const [question, setQuestion] = useState(QUESTIONS[0]!.q);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api.health().then((r) => r.ok && setHealth(r.data));
  }, []);

  const run = useCallback(async () => {
    if (!question.trim() || !location.trim()) return;
    setLoading(true);
    setError(null);
    const result = await api.analyse(question.trim(), location.trim());
    if (result.ok) {
      setFinding(result.data);
    } else {
      setError(result.message);
      setFinding(null);
    }
    setLoading(false);
  }, [question, location]);

  return (
    <div className="mx-auto max-w-content px-4 py-6 sm:px-6">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="order-2 space-y-5 lg:order-1">
          {!finding && !loading && !error && <Intro onPick={setQuestion} />}
          {loading && <LoadingState question={question} />}
          {error && (
            <div className="panel border-l-[3px] p-4" style={{ borderLeftColor: "var(--conflict)" }}>
              <p className="m-0 text-[13px] font-medium text-ink">Analysis could not run</p>
              <p className="m-0 mt-1.5 text-[12.5px] leading-relaxed text-ink-2">{error}</p>
              <p className="m-0 mt-2 text-[12px] text-ink-3">
                The API needs to be running on port 8000. Start it with{" "}
                <code className="mono text-ink-2">
                  python -m uvicorn app.main:app --port 8000
                </code>{" "}
                from <code className="mono text-ink-2">backend/</code>.
              </p>
            </div>
          )}
          {finding && !loading && <FindingView finding={finding} />}
        </div>

        {/* The whole column sticks as one unit. Making only the inner panel sticky put the
            map in a sibling stacking context that painted over it — MapLibre's canvas wins
            against an opaque background once both are positioned. One sticky container
            keeps a single stacking context and reads better anyway: the question and the
            map stay together while the finding scrolls beside them. */}
        <aside className="order-1 space-y-4 lg:order-2 lg:sticky lg:top-[68px] lg:self-start">
          <div className="panel relative z-10">
            <div className="panel-header">
              <h2 className="m-0 text-[13px] font-semibold text-ink">Ask about a site</h2>
              {health && (
                <span className={`tag ${health.mode === "extractive" ? "tag-fact" : "tag-inference"}`}>
                  {health.mode}
                </span>
              )}
            </div>

            <div className="space-y-3 p-3.5">
              <div>
                <label htmlFor="site" className="label mb-1 block">
                  Site
                </label>
                <input
                  id="site"
                  className="input"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Address, locality or coordinates"
                />
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {SITES.map((s) => (
                    <button
                      key={s.label}
                      type="button"
                      onClick={() => setLocation(s.label)}
                      title={s.note}
                      className={`rounded border px-2 py-1 text-[11px] transition-colors ${
                        location === s.label
                          ? "border-inference text-inference"
                          : "border-line text-ink-3 hover:border-line-strong hover:text-ink-2"
                      }`}
                    >
                      {s.label.split(",")[0]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label htmlFor="question" className="label mb-1 block">
                  The question blocking your decision
                </label>
                <textarea
                  id="question"
                  className="input resize-y"
                  rows={3}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="e.g. Can I build to 2.5 FAR on this plot?"
                />
              </div>

              <button
                type="button"
                className="btn btn-primary w-full"
                onClick={run}
                disabled={loading || !question.trim()}
              >
                {loading ? "Analysing…" : "Run analysis"}
              </button>

              <div>
                <p className="label mb-1.5">Questions with real answers in this corpus</p>
                <ul className="m-0 list-none space-y-1.5 p-0">
                  {QUESTIONS.map((item) => (
                    <li key={item.q}>
                      <button
                        type="button"
                        onClick={() => setQuestion(item.q)}
                        className={`w-full rounded border p-2 text-left transition-colors ${
                          question === item.q
                            ? "border-inference bg-[var(--inference-dim)]"
                            : "border-line hover:border-line-strong hover:bg-hover"
                        }`}
                      >
                        <span className="block text-[12px] leading-snug text-ink-2">
                          {item.q}
                        </span>
                        <span className="mt-1 block text-[11px] leading-snug text-ink-4">
                          {item.note}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {finding && (
            <SiteMap
              latitude={finding.latitude}
              longitude={finding.longitude}
              features={finding.map_features}
              label={finding.resolved_name}
            />
          )}
        </aside>
      </div>
    </div>
  );
}

function Intro({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="panel p-6">
      <h1 className="m-0 text-[20px] font-semibold tracking-tight text-ink">
        Ask the question that is blocking the decision.
      </h1>
      <p className="m-0 mt-2.5 max-w-2xl text-[13.5px] leading-relaxed text-ink-2">
        Basis answers from the governing regulation and the site&apos;s measured context, and
        shows you the exact passage behind every claim — plus where the two disagree, what it
        could not read, and what would change the answer.
      </p>

      <dl className="m-0 mt-5 grid gap-4 sm:grid-cols-3">
        {[
          [
            "Passage, not document",
            "Every claim carries a page and a character span. Click it and land on the highlighted sentence.",
          ],
          [
            "Blind spots are results",
            "54 of this document's 206 pages carry no machine-readable text. When your question lands near one, it says so and shows you the page.",
          ],
          [
            "Nothing resolves that cannot be",
            "Most conflicts here cannot be settled from open data. Basis names what is missing and who holds it, instead of guessing.",
          ],
        ].map(([title, body]) => (
          <div key={title}>
            <dt className="text-[12.5px] font-semibold text-ink">{title}</dt>
            <dd className="m-0 mt-1 text-[12px] leading-relaxed text-ink-3">{body}</dd>
          </div>
        ))}
      </dl>

      <p className="m-0 mt-5 text-[12px] text-ink-4">
        Pick a question on the right, or{" "}
        <button
          type="button"
          onClick={() => onPick(QUESTIONS[2]!.q)}
          className="cursor-pointer border-0 bg-transparent p-0 text-[12px] text-inference underline decoration-dotted underline-offset-2 hover:decoration-solid"
        >
          try the one whose answer the system cannot read
        </button>
        .
      </p>
    </div>
  );
}

function LoadingState({ question }: { question: string }) {
  const steps = [
    ["site", "measuring location, mobility, water, climate and terrain"],
    ["regulation", "retrieving governing passages and checking coverage"],
    ["conflict", "holding measurement against regulation"],
    ["critic", "challenging every claim against its evidence"],
  ];

  return (
    <div className="panel p-5">
      <p className="label mb-1">Analysing</p>
      <p className="m-0 mb-4 text-[14px] text-ink">{question}</p>
      <ul className="m-0 list-none space-y-2.5 p-0">
        {steps.map(([agent, doing]) => (
          <li key={agent} className="flex items-baseline gap-3">
            <span className="mono w-20 shrink-0 text-[12px] text-ink-2">{agent}</span>
            <span className="skeleton h-3 flex-1" />
            <span className="hidden text-[11.5px] text-ink-4 sm:block">{doing}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
