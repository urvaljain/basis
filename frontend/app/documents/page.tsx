"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Upload a document and find out what cannot be read in it.
 *
 * The order here is the product argument in miniature: the **ingestion report comes before
 * the question box**. A user who learns that 40% of the report they just uploaded is a scan
 * has learned something valuable about their own document, whether or not they ever ask it
 * anything.
 *
 * Every other tool in this space accepts a PDF and moves straight to a chat box, which
 * quietly asserts that the file was read. Often it was not.
 */

interface Report {
  id: string;
  filename: string;
  page_count: number;
  readable_page_count: number;
  unreadable_page_count: number;
  text_coverage: number;
  total_substitutions: number;
  pages_needing_repair: number;
  chunk_count: number;
  unreadable_ranges: number[][];
  risky_tables: { page: number; caption: string; risk: string }[];
  findings: string[];
}

interface Evidence {
  page_number: number;
  quote: string;
  citation_label: string;
  text_was_repaired: boolean;
  is_safe_verbatim: boolean;
  table_risk: string | null;
  caveats: string[];
  why_matched: string;
  score: number;
}

interface Answer {
  question: string;
  coverage_note: string | null;
  evidence: Evidence[];
  blind_spots: { page_start: number; page_end: number; page_count: number; matched_terms: string[] }[];
  no_evidence_reason: string | null;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Report[]>([]);
  const [active, setActive] = useState<Report | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const response = await fetch("/api/documents");
    if (response.ok) {
      const data = (await response.json()) as { documents: Report[] };
      setDocuments(data.documents);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upload = async (file: File) => {
    setUploading(true);
    setError(null);
    setAnswer(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch("/api/documents", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? `Upload failed (${response.status})`);
      setActive(data as Report);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
    setUploading(false);
  };

  const ask = async () => {
    if (!active || !question.trim()) return;
    setAsking(true);
    setAnswer(null);
    try {
      const response = await fetch(`/api/documents/${active.id}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), location: "n/a" }),
      });
      if (response.ok) setAnswer((await response.json()) as Answer);
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <header className="max-w-2xl">
        <p className="label mb-2">Your documents</p>
        <h1 className="m-0 text-[24px] font-semibold leading-tight tracking-tight text-ink">
          Find out what your PDF does not say
        </h1>
        <p className="m-0 mt-3 text-[13.5px] leading-relaxed text-ink-2">
          The same pipeline as the bundled corpus: page-quality classification, encoding
          repair with the raw text kept, table-damage detection and passage-level citation.
          The report comes back <em>before</em> the question box, because the most useful
          thing a system can tell you about a document it has just met is which parts of it
          it cannot read.
        </p>
      </header>

      <div className="caveat mt-5">
        <span aria-hidden className="shrink-0 font-bold">
          !
        </span>
        <span>
          This prototype has no authentication. Uploads are held in memory for the life of
          the server process and are deletable, but confidentiality is explicitly not solved
          here — do not upload anything genuinely sensitive.
        </span>
      </div>

      <section className="panel mt-5 p-4">
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
          }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Reading the document…" : "Choose a PDF"}
          </button>
          <span className="text-[12px] text-ink-3">PDF, up to 25 MB</span>
        </div>

        {error && <p className="m-0 mt-3 text-[12.5px] text-conflict">{error}</p>}

        {documents.length > 0 && (
          <div className="mt-4">
            <p className="label mb-1.5">Loaded</p>
            <div className="flex flex-wrap gap-1.5">
              {documents.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => {
                    setActive(d);
                    setAnswer(null);
                  }}
                  className={`rounded border px-2.5 py-1.5 text-[12px] transition-colors ${
                    active?.id === d.id
                      ? "border-inference text-inference"
                      : "border-line text-ink-3 hover:border-line-strong hover:text-ink-2"
                  }`}
                >
                  {d.filename.slice(0, 34)}
                  <span className="mono ml-2 text-[10px] text-ink-4">{d.page_count}p</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      {uploading && (
        <div className="mt-4 space-y-2">
          <div className="skeleton h-4 w-56" />
          <div className="skeleton h-28 w-full" />
        </div>
      )}

      {active && !uploading && (
        <>
          <section className="panel mt-5">
            <div className="panel-header">
              <h2 className="m-0 text-[13px] font-semibold text-ink">
                What could and could not be read
              </h2>
              <span className="mono text-[11px] text-ink-4">{active.filename}</span>
            </div>

            <dl className="m-0 grid grid-cols-2 gap-px bg-line sm:grid-cols-4">
              {[
                ["pages", String(active.page_count)],
                ["text coverage", `${(active.text_coverage * 100).toFixed(1)}%`],
                ["unreadable", String(active.unreadable_page_count)],
                ["chars repaired", String(active.total_substitutions)],
              ].map(([label, value]) => (
                <div key={label} className="bg-panel px-3 py-2.5">
                  <dt className="label">{label}</dt>
                  <dd className="mono m-0 text-[17px] font-medium text-ink">{value}</dd>
                </div>
              ))}
            </dl>

            <ul className="m-0 list-none space-y-2 border-t border-line p-4">
              {active.findings.map((finding, i) => (
                <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-2">
                  <span aria-hidden className="mono shrink-0 pt-px text-[10px] text-assumption">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>{finding}</span>
                </li>
              ))}
            </ul>

            {active.unreadable_ranges.length > 0 && (
              <div className="border-t border-line px-4 py-3">
                <p className="label mb-1.5">Unreadable ranges</p>
                <div className="flex flex-wrap gap-1.5">
                  {active.unreadable_ranges.map((r) => {
                    const [start, end] = [r[0]!, r[1]!];
                    return (
                      <span
                        key={`${start}-${end}`}
                        className="mono rounded border border-line px-2 py-1 text-[11px] text-unreadable"
                      >
                        {start === end ? `p. ${start}` : `pp. ${start}–${end}`}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </section>

          <section className="panel mt-4 p-4">
            <label htmlFor="doc-q" className="label mb-1.5 block">
              Ask this document
            </label>
            <div className="flex gap-2">
              <input
                id="doc-q"
                className="input"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && void ask()}
                placeholder="What does it say about setbacks?"
              />
              <button
                type="button"
                className="btn btn-primary shrink-0"
                onClick={ask}
                disabled={asking || !question.trim()}
              >
                {asking ? "…" : "Ask"}
              </button>
            </div>
          </section>

          {answer && (
            <section className="mt-4 space-y-3">
              {answer.coverage_note && (
                <div className="caveat">
                  <span aria-hidden className="shrink-0 font-bold">
                    !
                  </span>
                  <span>{answer.coverage_note}</span>
                </div>
              )}

              {answer.blind_spots.map((spot) => (
                <div
                  key={`${spot.page_start}-${spot.page_end}`}
                  className="panel border-l-[3px] p-3.5"
                  style={{ borderLeftColor: "var(--unreadable)" }}
                >
                  <p className="m-0 text-[12.5px] leading-relaxed text-ink-2">
                    <span className="mono text-unreadable">
                      pp. {spot.page_start}–{spot.page_end}
                    </span>{" "}
                    match your question on{" "}
                    <span className="mono text-unreadable">
                      {spot.matched_terms.join(", ")}
                    </span>{" "}
                    but carry no machine-readable text. Nothing below was read from them.
                  </p>
                </div>
              ))}

              {answer.no_evidence_reason ? (
                <div
                  className="panel border-l-[3px] p-4"
                  style={{ borderLeftColor: "var(--assumption)" }}
                >
                  <p className="m-0 text-[13px] leading-relaxed text-ink-2">
                    {answer.no_evidence_reason}
                  </p>
                </div>
              ) : (
                answer.evidence.map((e, i) => (
                  <article key={i} className="stmt stmt-fact">
                    <header className="mb-1.5 flex flex-wrap items-center gap-2">
                      <span className="mono text-[11px] text-ink-3">{e.citation_label}</span>
                      {e.text_was_repaired && (
                        <span className="tag tag-assumption">reconstructed</span>
                      )}
                      {e.table_risk && e.table_risk !== "none" && e.table_risk !== "low" && (
                        <span className="tag tag-conflict">table structure lost</span>
                      )}
                      <span className="mono ml-auto text-[10px] text-ink-4">
                        {e.why_matched}
                      </span>
                    </header>
                    <div className="paper">{e.quote}</div>
                    {e.caveats.map((caveat, j) => (
                      <div key={j} className="caveat mt-2">
                        <span aria-hidden className="shrink-0 font-bold">
                          !
                        </span>
                        <span>{caveat}</span>
                      </div>
                    ))}
                  </article>
                ))
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
