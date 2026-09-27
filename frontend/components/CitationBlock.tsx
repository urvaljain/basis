"use client";

import { useState } from "react";
import type { Citation } from "@/lib/types";

/**
 * A passage-level citation, rendered in the document's own voice.
 *
 * Three decisions carry the product's argument here.
 *
 * **The quote sits on paper.** A warm surface and a serif face, against the dark chrome
 * everywhere else. A reader can tell at a glance which words are the regulation's and which
 * are the machine's, without reading a label.
 *
 * **The reference is a coordinate.** Monospaced, with page and character span. "Source: RMP
 * 2031" is unfalsifiable in practice — nobody reads 206 pages to check you. "p. 80
 * [1603–1975]" is checkable in seconds, and a citation the reader *can* check is the whole
 * difference between evidence and decoration.
 *
 * **A reconstructed quote says so, prominently.** Where the source PDF was mis-encoded the
 * text was repaired, and the repaired text is what is shown — but presenting it as verbatim
 * would be exactly the silent transformation this product exists to argue against. The raw
 * extraction is one click away, so the reader can see precisely what changed.
 */
export function CitationBlock({
  citation,
  onOpenPage,
}: {
  citation: Citation;
  onOpenPage?: (pageNumber: number, charStart?: number, charEnd?: number) => void;
}) {
  const [showRaw, setShowRaw] = useState(false);

  return (
    <figure className="m-0">
      <div className="paper relative">
        <blockquote className="m-0">
          {showRaw && citation.raw_quote ? (
            <span className="mono text-[12px] leading-relaxed text-paper-muted">
              {citation.raw_quote}
            </span>
          ) : (
            citation.quote
          )}
        </blockquote>

        <figcaption className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-paper-dim pt-2">
          <button
            type="button"
            onClick={() =>
              onOpenPage?.(citation.page_number, citation.char_start, citation.char_end)
            }
            className="mono cursor-pointer border-0 bg-transparent p-0 text-[11px] text-[#2f5fa8] underline decoration-dotted underline-offset-2 hover:decoration-solid"
            title="Open this page with the passage highlighted"
          >
            {citation.document_title}, p.&nbsp;{citation.page_number}
          </button>

          <span className="mono text-[10.5px] text-paper-muted">
            [{citation.char_start}–{citation.char_end}]
          </span>

          {citation.text_was_repaired && citation.raw_quote && (
            <button
              type="button"
              onClick={() => setShowRaw((v) => !v)}
              className="mono cursor-pointer border-0 bg-transparent p-0 text-[10.5px] text-[#8a5a12] underline decoration-dotted underline-offset-2 hover:decoration-solid"
            >
              {showRaw ? "show repaired" : "show raw extraction"}
            </button>
          )}
        </figcaption>
      </div>

      {citation.text_was_repaired && (
        <p className="mono mt-1.5 text-[10.5px] uppercase tracking-wider text-assumption">
          reconstructed — not verbatim
        </p>
      )}

      {/* Never collapsible, never a tooltip. */}
      {citation.caveat && (
        <div
          className={`caveat mt-1.5 ${
            citation.caveat.includes("column structure") ? "caveat-severe" : ""
          }`}
        >
          <span aria-hidden className="shrink-0 font-bold">
            !
          </span>
          <span>{citation.caveat}</span>
        </div>
      )}
    </figure>
  );
}
