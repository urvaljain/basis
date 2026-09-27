"use client";

import { useState } from "react";
import { pageImageUrl } from "@/lib/api";
import type { BlindSpot } from "@/lib/types";

/**
 * The unreadable surface — what the system could not read, handed to the reader.
 *
 * This is the component the product is built around.
 *
 * A retrieval system over a 206-page government PDF, 54 pages of which carry no
 * machine-readable text, has two options when a question lands near the gap. It can answer
 * from the surrounding prose — fluent, confident, and quietly answering a different
 * question. Or it can say precisely what it could not read, and show the reader the actual
 * page so they can do what the machine could not.
 *
 * The second is harder to build and much harder to look impressive with, which is roughly
 * why nothing does it. It is also the only version that survives contact with a
 * professional who will be held responsible for the decision.
 *
 * The worked case: ask this corpus about Transferable Development Rights and the governing
 * instrument — the Karnataka TCP (Benefit of Development Rights) Rules 2016, 23 scanned
 * pages — is invisible to every form of text search. The system reports the gap, names the
 * instrument from the text that introduces it, and renders the pages.
 */
export function UnreadableSurface({ spots }: { spots: BlindSpot[] }) {
  if (spots.length === 0) return null;

  const totalPages = spots.reduce((sum, s) => sum + s.page_count, 0);

  return (
    <section className="panel border-l-[3px]" style={{ borderLeftColor: "var(--unreadable)" }}>
      <header className="panel-header flex-wrap">
        <div>
          <span className="tag tag-unreadable">could not be read</span>
          <h2 className="mb-0 mt-2 text-[15px] font-semibold leading-snug text-ink">
            {totalPages} page{totalPages === 1 ? "" : "s"} bearing on this question carry no
            machine-readable text
          </h2>
        </div>
      </header>

      <div className="border-b border-line bg-raised px-4 py-3">
        <p className="m-0 text-[12.5px] leading-relaxed text-ink-2">
          These pages are scans or drawings. Nothing below was read from them, and a
          provision in them could contradict or supersede the evidence shown elsewhere —
          the system cannot tell which, and neither can a reader who has not opened them.
          They are rendered here so you can.
        </p>
      </div>

      <div className="divide-y divide-line">
        {spots.map((spot) => (
          <SpotDetail key={`${spot.page_start}-${spot.page_end}`} spot={spot} />
        ))}
      </div>
    </section>
  );
}

/**
 * Which page to open on.
 *
 * The first page of a scanned annexure is very often a cover or a blank separator — page 106
 * of this corpus, the first page of the 23-page TDR instrument, is entirely blank. Opening
 * there shows the reader a white rectangle and undersells the point entirely.
 *
 * The middle of a run is reliably substantive content. For a one or two page gap there is
 * nothing to choose, so it starts at the beginning.
 */
function defaultPage(spot: BlindSpot): number {
  if (spot.page_count <= 2) return spot.page_start;
  return spot.page_start + Math.floor(spot.page_count / 2);
}

function SpotDetail({ spot }: { spot: BlindSpot }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(() => defaultPage(spot));

  const pages = Array.from(
    { length: spot.page_end - spot.page_start + 1 },
    (_, i) => spot.page_start + i,
  );

  return (
    <div className="p-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="mono text-[13px] font-medium text-unreadable">
          {spot.page_start === spot.page_end
            ? `page ${spot.page_start}`
            : `pages ${spot.page_start}–${spot.page_end}`}
        </span>
        <span className="text-[12px] text-ink-3">
          {spot.page_count} page{spot.page_count === 1 ? "" : "s"}
        </span>
        {spot.matched_terms.length > 0 && (
          <span className="text-[11.5px] text-ink-3">
            matched your question on{" "}
            <span className="mono text-unreadable">{spot.matched_terms.join(", ")}</span>
          </span>
        )}
      </div>

      {/* The descriptor is the text that *leads into* the gap — an honest proxy for what is
          missing. It is never presented as a description of the contents, because nothing
          can be known about pages that cannot be read. */}
      {spot.descriptor && (
        <div className="mt-2.5">
          <p className="label mb-1">The document's last readable words before this gap</p>
          <p className="paper m-0 text-[13px]">…{spot.descriptor}</p>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="btn mt-3 text-[12px]"
        aria-expanded={open}
      >
        {open ? "Hide" : "Show me the pages"}
        <span className="mono text-[10px] text-ink-3">
          {spot.page_count} image{spot.page_count === 1 ? "" : "s"}
        </span>
      </button>

      {open && (
        <div className="mt-3">
          <div className="mb-2 flex flex-wrap items-center gap-1">
            {pages.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPage(p)}
                className={`mono rounded border px-2 py-1 text-[11px] transition-colors ${
                  p === page
                    ? "border-unreadable bg-[var(--unreadable-dim)] text-unreadable"
                    : "border-line text-ink-3 hover:border-line-strong hover:text-ink-2"
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          <figure className="m-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              key={page}
              src={pageImageUrl(page)}
              alt={`Page ${page} of the source document, rendered as an image because it contains no machine-readable text`}
              className="w-full rounded border border-line-strong bg-paper"
              loading="lazy"
            />
            <figcaption className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-4">
              <span>
                Page {page} — rendered from the source PDF at the moment you asked for it.
              </span>
              <a
                href={pageImageUrl(page)}
                target="_blank"
                rel="noreferrer"
                className="mono text-inference no-underline hover:underline"
              >
                open full size ↗
              </a>
            </figcaption>
          </figure>
        </div>
      )}
    </div>
  );
}
