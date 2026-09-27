"use client";

import { useState } from "react";
import type { Statement } from "@/lib/types";
import { CitationBlock } from "./CitationBlock";

/**
 * Renders one typed statement.
 *
 * The visual grammar is the epistemic model, not a decoration of it:
 *
 *   FACT            solid rule, no colour   — measured; certainty needs no emphasis
 *   INFERENCE       dashed rule, blue       — derived, and the derivation is shown
 *   ASSUMPTION      dotted rule, amber      — unestablished, and what would settle it is shown
 *   RECOMMENDATION  solid rule, teal        — an action, with an addressee
 *
 * Border *style* carries the meaning as well as colour, so the distinction survives
 * colour-blindness and print.
 *
 * Two things are deliberately not collapsible: a citation's caveat, and an assumption's
 * falsification condition. Everything else can be folded away. A caveat behind a disclosure
 * triangle is a caveat most readers will never see, which makes showing it a formality
 * rather than a disclosure.
 */

const TYPE_LABEL: Record<Statement["type"], string> = {
  fact: "Fact",
  inference: "Inference",
  assumption: "Assumption",
  recommendation: "Action",
};

const TYPE_MEANING: Record<Statement["type"], string> = {
  fact: "Measured or directly quoted. Reproducible from the source.",
  inference: "Derived from facts by a stated transformation. Can be wrong if the transformation is.",
  assumption: "Required for the reasoning to hold, but not itself established.",
  recommendation: "A suggested human action, responding to a specific uncertainty.",
};

export function StatementCard({
  statement,
  onOpenPage,
  compact = false,
}: {
  statement: Statement;
  onOpenPage?: (pageNumber: number, charStart?: number, charEnd?: number) => void;
  compact?: boolean;
}) {
  const [showDerivation, setShowDerivation] = useState(false);
  const { type } = statement;

  const normalise = (s: string) => s.replace(/\s+/g, " ").trim();
  const quoteIsStatement =
    statement.citation != null &&
    normalise(statement.citation.quote) === normalise(statement.text);

  return (
    <article className={`stmt stmt-${type} ${statement.rejected ? "opacity-55" : ""}`}>
      <header className="mb-1.5 flex flex-wrap items-center gap-2">
        <span className={`tag tag-${type}`} title={TYPE_MEANING[type]}>
          {TYPE_LABEL[type]}
        </span>

        {statement.confidence && (
          <span className="text-[11px] text-ink-3">
            confidence{" "}
            <span
              className={
                statement.confidence === "low"
                  ? "text-assumption"
                  : statement.confidence === "medium"
                    ? "text-ink-2"
                    : "text-ink"
              }
            >
              {statement.confidence}
            </span>
          </span>
        )}

        {statement.priority != null && (
          <span className="mono text-[11px] text-ink-3">P{statement.priority}</span>
        )}

        {statement.was_weakened && (
          <span className="tag tag-conflict" title="The critic weakened this claim">
            critic
          </span>
        )}

        {statement.rejected && <span className="tag tag-conflict">rejected</span>}

        {statement.agent && !compact && (
          <span className="mono ml-auto text-[10px] text-ink-4">{statement.agent}</span>
        )}
      </header>

      {/* In extractive mode a regulation claim IS its quoted passage, so rendering both the
          statement text and the citation would print the same sentence twice. The citation
          is the better of the two — it carries the page, the span and the caveat — so the
          plain text is dropped when they are the same. */}
      {!quoteIsStatement && (
        <p className="text-[13.5px] leading-relaxed text-ink">{statement.text}</p>
      )}

      {/* A proxy must name what it stands in for. "Distance to a station" is a fact;
          "accessibility" is an interpretation, and the gap between them is where an
          interface quietly turns a measurement into a judgement. */}
      {statement.proxy_for && (
        <p className="mt-1.5 text-[12px] text-ink-3">
          Used as a proxy for{" "}
          <span className="text-inference">{statement.proxy_for}</span> — which this does not
          itself establish.
        </p>
      )}

      {statement.citation && (
        <div className="mt-2.5">
          <CitationBlock citation={statement.citation} onOpenPage={onOpenPage} />
        </div>
      )}

      {/* A dataset's limitation is a property of the value, never a footnote to it. */}
      {statement.dataset_limitation && (
        <p className="mt-2 border-l-2 border-line-strong pl-2.5 text-[11.5px] leading-relaxed text-ink-3">
          <span className="mono text-[10px] uppercase tracking-wider text-ink-4">
            {statement.dataset_provider}
          </span>{" "}
          — {statement.dataset_limitation}
        </p>
      )}

      {statement.type === "inference" && statement.transformation && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setShowDerivation((v) => !v)}
            className="mono text-[10.5px] uppercase tracking-wider text-ink-3 hover:text-inference"
          >
            {showDerivation ? "− hide" : "+ show"} derivation
          </button>
          {showDerivation && (
            <dl className="mt-1.5 space-y-1.5 rounded border border-line bg-bg px-3 py-2 text-[12px]">
              <div>
                <dt className="label">Transformation</dt>
                <dd className="text-ink-2">{statement.transformation}</dd>
              </div>
              {statement.confidence_basis && (
                <div>
                  <dt className="label">Why this confidence</dt>
                  <dd className="text-ink-2">{statement.confidence_basis}</dd>
                </div>
              )}
              {statement.derived_from.length > 0 && (
                <div>
                  <dt className="label">Derived from</dt>
                  <dd className="mono text-[10.5px] text-ink-3">
                    {statement.derived_from.join(", ")}
                  </dd>
                </div>
              )}
            </dl>
          )}
        </div>
      )}

      {/* Never collapsible: an assumption without its falsifier is just a hedge. */}
      {statement.falsified_by && (
        <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
          <span className="label">Would be settled by</span>{" "}
          <span className="text-assumption">{statement.falsified_by}</span>
        </p>
      )}

      {statement.who && (
        <p className="mt-1.5 text-[12px] text-ink-3">
          <span className="label">Who</span> {statement.who}
        </p>
      )}

      {/* Critic interventions are shown, always. An invisible critic cannot be audited,
          which makes it indistinguishable from no critic at all. */}
      {statement.critic_notes.length > 0 && (
        <ul className="mt-2 space-y-1">
          {statement.critic_notes.map((note, i) => (
            <li key={i} className="flex gap-2 text-[11.5px] leading-relaxed text-conflict">
              <span className="mono shrink-0 text-[10px] uppercase tracking-wider">
                {note.action.replace(/_/g, " ")}
              </span>
              <span className="text-ink-2">
                {note.reason}
                {note.from && note.to && (
                  <span className="mono text-ink-3">
                    {" "}
                    ({note.from} → {note.to})
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
