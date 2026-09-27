"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PageDetail } from "@/lib/types";

/**
 * Opens a source page with the cited span highlighted.
 *
 * This is the interaction that makes a citation worth making. A reference the reader cannot
 * follow in a couple of seconds is decoration; one that lands on the highlighted sentence,
 * in context, on the right page, is the thing that lets them decide whether to believe the
 * claim.
 *
 * Where the page was mis-encoded, both versions are available — repaired and raw. Showing
 * only the repaired text would ask the reader to take the repair on trust, which is the
 * posture this product exists to argue against.
 */
export function PageViewer({
  pageNumber,
  highlightStart,
  highlightEnd,
  onClose,
}: {
  pageNumber: number;
  highlightStart?: number;
  highlightEnd?: number;
  onClose: () => void;
}) {
  const [page, setPage] = useState<PageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    let live = true;
    setPage(null);
    setError(null);
    api.page(pageNumber).then((result) => {
      if (!live) return;
      if (result.ok) setPage(result.data);
      else setError(result.message);
    });
    return () => {
      live = false;
    };
  }, [pageNumber]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Source page ${pageNumber}`}
    >
      <div
        className="panel my-auto w-full max-w-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="panel-header sticky top-0 z-10 bg-panel">
          <div>
            <p className="label mb-0.5">Source document</p>
            <h2 className="m-0 text-[14px] font-semibold text-ink">Page {pageNumber}</h2>
          </div>
          <div className="flex items-center gap-2">
            {page?.substitutions ? (
              <button
                type="button"
                onClick={() => setShowRaw((v) => !v)}
                className="btn text-[11px]"
              >
                {showRaw ? "repaired text" : "raw extraction"}
              </button>
            ) : null}
            <button type="button" onClick={onClose} className="btn text-[12px]" autoFocus>
              Close <span className="mono text-[10px] text-ink-3">esc</span>
            </button>
          </div>
        </header>

        <div className="p-4">
          {error && (
            <p className="m-0 text-[13px] text-conflict">
              Could not load this page: {error}
            </p>
          )}

          {!page && !error && (
            <div className="space-y-2">
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-5/6" />
            </div>
          )}

          {page && (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className={`tag ${page.is_readable ? "tag-fact" : "tag-unreadable"}`}>
                  {page.quality.replace(/_/g, " ")}
                </span>
                {page.substitutions > 0 && (
                  <span className="mono text-[11px] text-assumption">
                    {page.substitutions} characters repaired
                  </span>
                )}
                <a
                  href={page.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mono ml-auto text-[11px] text-inference no-underline hover:underline"
                >
                  source document ↗
                </a>
              </div>

              {page.caveat && (
                <div className="caveat mb-3">
                  <span aria-hidden className="shrink-0 font-bold">
                    !
                  </span>
                  <span>{page.caveat}</span>
                </div>
              )}

              {page.is_readable ? (
                <div className="paper max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                  {showRaw && page.raw_text ? (
                    <span className="mono text-[12px] leading-relaxed">{page.raw_text}</span>
                  ) : (
                    <Highlighted
                      text={page.text}
                      start={highlightStart}
                      end={highlightEnd}
                    />
                  )}
                </div>
              ) : (
                <div>
                  <p className="m-0 mb-2 text-[12.5px] text-ink-2">
                    This page contains no machine-readable text. It is rendered below as an
                    image — it has to be read by a person.
                  </p>
                  {page.image_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={page.image_url}
                      alt={`Page ${pageNumber}, rendered as an image`}
                      className="w-full rounded border border-line-strong bg-paper"
                    />
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Highlights the cited character span.
 *
 * The span is valid against both the repaired and raw text because repair is a pure
 * character translation — it never reflows or re-wraps, so offsets are preserved exactly.
 * That property is what makes a character-level citation possible at all here.
 */
function Highlighted({
  text,
  start,
  end,
}: {
  text: string;
  start?: number;
  end?: number;
}) {
  if (start == null || end == null || end <= start || start >= text.length) {
    return <>{text}</>;
  }

  const clampedEnd = Math.min(end, text.length);
  return (
    <>
      {text.slice(0, start)}
      <mark id="cited-span">{text.slice(start, clampedEnd)}</mark>
      {text.slice(clampedEnd)}
    </>
  );
}
