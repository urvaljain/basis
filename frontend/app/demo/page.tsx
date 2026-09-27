"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ConflictCard } from "@/components/ConflictCard";
import { Section } from "@/components/FindingView";
import { StatementCard } from "@/components/StatementCard";
import { UnreadableSurface } from "@/components/UnreadableSurface";
import { api } from "@/lib/api";
import type { Finding } from "@/lib/types";

/**
 * The guided walkthrough.
 *
 * This is not an animation. Each step runs a **real analysis** against the real corpus, and
 * every figure on screen comes from that run. What the demo controls is only the order and
 * the narration — because the argument needs to arrive in a particular sequence to land,
 * and because a founder watching will reasonably assume a scripted demo is fabricated.
 *
 * Provider responses are served from recordings captured on a known date (see
 * `data/fixtures/`), so the walkthrough survives Overpass being down — which, during
 * development, it repeatedly was. The recordings are verbatim; nothing was edited to make
 * the demo look better.
 *
 * The sequence is deliberate. It opens on a question the system answers well, so the
 * evidence layer is understood before it is stressed. It then asks a question whose
 * governing instrument is 23 scanned pages — where a normal pipeline answers fluently and
 * wrongly. It ends on the conflict, because that is where the product stops being a search
 * tool and starts being a decision aid.
 */

const SITE = "Bellandur, Bengaluru";

interface Step {
  key: string;
  kicker: string;
  title: string;
  narration: string;
  question: string;
  focus: "evidence" | "unreadable" | "conflict";
  punchline: string;
}

const STEPS: Step[] = [
  {
    key: "buffer",
    kicker: "01 — A question with a good answer",
    title: "What buffer applies around a lake?",
    narration:
      "Start with something the document answers cleanly, so the evidence layer is legible before it gets stressed. Every claim below is a verbatim passage with a page and a character span. Click a reference and you land on the highlighted sentence.",
    question: "What buffer applies around a lake?",
    focus: "evidence",
    punchline:
      "Note the label under the quote: this passage was reconstructed. The source PDF encodes digits as unrelated characters — “75 m” extracts as “7ϱ ŵ”. Before repair, searching this document for “75 m buffer” returns nothing at all, though the clause is right there on page 80.",
  },
  {
    key: "tdr",
    kicker: "02 — A question it cannot answer",
    title: "What are the TDR rules?",
    narration:
      "Transferable Development Rights directly increase buildable area, so this is a question a developer actually asks. The governing instrument is in this document — as 23 scanned pages that carry no machine-readable text.",
    question: "What are the TDR rules for transferable development rights?",
    focus: "unreadable",
    punchline:
      "A retrieval pipeline over this corpus will answer that question fluently from the prose that happens to surround the gap. It has no way to know the governing rules are invisible to it, and neither does the reader. Basis reports the gap, names the instrument from the text that introduces it, and hands over the pages.",
  },
  {
    key: "conflict",
    kicker: "03 — Where the decision actually lives",
    title: "Is this site affected by a water body or valley buffer?",
    narration:
      "Now both layers at once. The site measures well: Outer Ring Road 216 m, a hospital at 108 m, 131 mapped features. The regulation imposes a 75 m no-development buffer around water bodies and 50/35/25 m on watercourses. Both statements are true.",
    question:
      "Is this site affected by a water body or valley buffer, and what does that restrict?",
    focus: "conflict",
    punchline:
      "The obvious inference — the nearest watercourse is 153 m away, the widest buffer is 75 m, therefore clear — is invalid, and Basis says exactly why. The applicable buffer depends on a watercourse classification OpenStreetMap does not record; the lake boundary is defined by revenue records that are not open data; the overlay is on drawings that cannot be read. So the honest output is not “you are clear”. It is: here is what you must obtain, and who holds it.",
  },
];

export default function DemoPage() {
  const [step, setStep] = useState(0);
  const [findings, setFindings] = useState<Record<string, Finding>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  const current = STEPS[step]!;
  const finding = findings[current.key];

  const load = useCallback(async () => {
    if (findings[current.key]) return;
    setLoading(true);
    setError(null);
    const result = await api.analyse(current.question, SITE);
    if (result.ok) {
      setFindings((prev) => ({ ...prev, [current.key]: result.data }));
    } else {
      setError(result.message);
    }
    setLoading(false);
  }, [current, findings]);

  useEffect(() => {
    setRevealed(false);
    void load();
  }, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setStep((s) => Math.min(s + 1, STEPS.length - 1));
      if (e.key === "ArrowLeft") setStep((s) => Math.max(s - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <header className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="label m-0">Guided walkthrough · {SITE}</p>
          <span className="tag tag-fact" title="Provider responses are replayed from recordings">
            recorded responses
          </span>
        </div>
        <h1 className="m-0 mt-2 text-[22px] font-semibold leading-tight tracking-tight text-ink">
          Evaluate a site before the first meeting.
        </h1>
        <p className="m-0 mt-2 max-w-2xl text-[13px] leading-relaxed text-ink-3">
          Three questions about one real site, answered from a real 206-page government
          document. Every number below comes from an analysis run when you loaded this page —
          only the order is scripted.
        </p>
      </header>

      <nav className="mb-5 flex gap-1.5" aria-label="Walkthrough steps">
        {STEPS.map((s, i) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setStep(i)}
            aria-current={i === step}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i === step ? "bg-inference" : i < step ? "bg-line-strong" : "bg-line"
            }`}
            title={s.title}
          />
        ))}
      </nav>

      <article className="panel mb-5 p-5">
        <p className="label m-0">{current.kicker}</p>
        <h2 className="m-0 mt-1.5 text-[19px] font-semibold leading-snug text-ink">
          {current.title}
        </h2>
        <p className="m-0 mt-2.5 text-[13.5px] leading-relaxed text-ink-2">
          {current.narration}
        </p>
      </article>

      <div ref={bodyRef} className="space-y-5">
        {loading && <DemoSkeleton />}

        {error && (
          <div className="panel border-l-[3px] p-4" style={{ borderLeftColor: "var(--conflict)" }}>
            <p className="m-0 text-[13px] font-medium text-ink">Could not run this step</p>
            <p className="m-0 mt-1.5 text-[12.5px] text-ink-2">{error}</p>
          </div>
        )}

        {finding && !loading && (
          <>
            {current.focus === "evidence" && (
              <Section
                title="What the document says"
                caption={`${finding.evidence.length} passages, each with page and character span`}
              >
                <div className="space-y-3">
                  {finding.evidence.slice(0, 3).map((s) => (
                    <StatementCard key={s.id} statement={s} />
                  ))}
                </div>
              </Section>
            )}

            {current.focus === "unreadable" && (
              <>
                {finding.unreadable.length > 0 ? (
                  <UnreadableSurface spots={finding.unreadable} />
                ) : (
                  <div className="panel p-4">
                    <p className="m-0 text-[13px] text-ink-2">
                      No blind spot was reported for this phrasing on this run.
                    </p>
                  </div>
                )}
              </>
            )}

            {current.focus === "conflict" && (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="panel p-3.5">
                    <p className="label mb-2">What the site measures</p>
                    <div className="space-y-2">
                      {finding.context
                        .filter(
                          (f) =>
                            f.text.includes("major road") ||
                            f.text.includes("hospital") ||
                            f.text.includes("stream") ||
                            f.text.includes("water"),
                        )
                        .slice(0, 4)
                        .map((f) => (
                          <p key={f.id} className="m-0 text-[12.5px] leading-snug text-ink-2">
                            {f.text}
                          </p>
                        ))}
                    </div>
                  </div>
                  <div className="panel p-3.5">
                    <p className="label mb-2">What the regulation says</p>
                    <div className="space-y-2">
                      {finding.evidence.slice(0, 2).map((s) => (
                        <p key={s.id} className="m-0 text-[12.5px] leading-snug text-ink-2">
                          {s.citation?.quote.slice(0, 190)}…
                        </p>
                      ))}
                    </div>
                  </div>
                </div>

                {finding.conflicts
                  .filter((c) => c.is_decisive)
                  .map((c, i) => (
                    <ConflictCard key={i} conflict={c} />
                  ))}
              </>
            )}

            {!revealed ? (
              <button
                type="button"
                onClick={() => setRevealed(true)}
                className="btn btn-primary w-full"
              >
                So what?
              </button>
            ) : (
              <div
                className="panel border-l-[3px] p-4"
                style={{ borderLeftColor: "var(--inference)" }}
              >
                <p className="label mb-1.5">The point</p>
                <p className="m-0 text-[13.5px] leading-relaxed text-ink">
                  {current.punchline}
                </p>
              </div>
            )}
          </>
        )}
      </div>

      <nav className="mt-7 flex items-center justify-between gap-3 border-t border-line pt-4">
        <button
          type="button"
          className="btn"
          onClick={() => setStep((s) => Math.max(s - 1, 0))}
          disabled={step === 0}
        >
          ← Previous
        </button>
        <span className="mono text-[11px] text-ink-4">
          {step + 1} / {STEPS.length}
        </span>
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setStep((s) => s + 1)}
          >
            Next →
          </button>
        ) : (
          <a href="/workspace" className="btn btn-primary no-underline">
            Ask your own question →
          </a>
        )}
      </nav>
    </div>
  );
}

function DemoSkeleton() {
  return (
    <div className="space-y-3">
      <div className="skeleton h-4 w-40" />
      <div className="skeleton h-28 w-full" />
      <div className="skeleton h-28 w-full" />
    </div>
  );
}
