"use client";

import { useState } from "react";
import type { Finding } from "@/lib/types";
import { ConflictCard } from "./ConflictCard";
import { PageViewer } from "./PageViewer";
import { StatementCard } from "./StatementCard";
import { UnreadableSurface } from "./UnreadableSurface";

/**
 * The finding, in its fixed eight-part anatomy.
 *
 *   CONTEXT → EVIDENCE → CONFLICT → UNREADABLE → ANSWER → CHANGE-MY-MIND → VERIFY
 *
 * The order is the argument. Conflicts and blind spots come *before* the answer, because a
 * reader who has already accepted a conclusion reads its caveats as pedantry. Putting the
 * tension first makes the answer land as what it is: a position held under stated
 * conditions.
 */
export function FindingView({ finding }: { finding: Finding }) {
  const [openPage, setOpenPage] = useState<{
    page: number;
    start?: number;
    end?: number;
  } | null>(null);

  const decisive = finding.conflicts.filter((c) => c.is_decisive);
  const other = finding.conflicts.filter((c) => !c.is_decisive);

  return (
    <div className="space-y-5">
      <Summary finding={finding} />

      {finding.needs_disambiguation && <Disambiguation finding={finding} />}

      {/* Conflicts first. */}
      {decisive.length > 0 && (
        <Section
          title="What is in tension"
          caption="Each side is true. Together they change the decision."
        >
          <div className="space-y-4">
            {decisive.map((c, i) => (
              <ConflictCard key={i} conflict={c} />
            ))}
          </div>
        </Section>
      )}

      {finding.unreadable.length > 0 && <UnreadableSurface spots={finding.unreadable} />}

      <Section
        title="What the document says"
        caption={`${finding.evidence.length} passage${
          finding.evidence.length === 1 ? "" : "s"
        }, each with its page and character span. Click a reference to open the page.`}
      >
        {finding.evidence.length === 0 ? (
          <EmptyState
            title="No passage in the indexed regulation matched this question"
            body="This does not mean the regulation is silent. The governing provision may be on a page that could not be read, or phrased in terms the search did not match. Basis does not assemble an answer from loosely related passages."
          />
        ) : (
          <div className="space-y-3">
            {finding.evidence.map((s) => (
              <StatementCard
                key={s.id}
                statement={s}
                onOpenPage={(page, start, end) => setOpenPage({ page, start, end })}
              />
            ))}
          </div>
        )}
      </Section>

      {finding.answer && (
        <Section
          title="Summary"
          caption="Generated from the passages above and checked against them by the critic."
        >
          <div className="panel p-4 text-[13.5px] leading-relaxed text-ink">
            {finding.answer}
          </div>
        </Section>
      )}

      {!finding.answer && (
        <Section title="Summary" caption="Extractive mode">
          <EmptyState
            title="No narrative summary was generated"
            body="Basis is running in extractive mode: every claim above is a verbatim passage with its citation, and nothing is written about the regulation that is not quoted from it. In this mode the evidence is the answer. A generated summary appears here when a language model is configured."
            tone="neutral"
          />
        </Section>
      )}

      {other.length > 0 && (
        <Section title="Evidence quality" caption="Issues with the sources themselves.">
          <div className="space-y-4">
            {other.map((c, i) => (
              <ConflictCard key={i} conflict={c} />
            ))}
          </div>
        </Section>
      )}

      {finding.change_my_mind.length > 0 && (
        <Section
          title="What would change this"
          caption="Every position here is held under a condition. These are the conditions."
        >
          <ul className="m-0 list-none space-y-2 p-0">
            {finding.change_my_mind.map((item, i) => (
              <li key={i} className="panel p-3.5">
                <p className="m-0 text-[13px] leading-relaxed text-ink-2">
                  {item.current_position}
                </p>
                <p className="m-0 mt-2 flex gap-2 text-[12.5px] leading-relaxed">
                  <span aria-hidden className="shrink-0 text-assumption">
                    →
                  </span>
                  <span className="text-assumption">{item.would_change_if}</span>
                </p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {finding.verify_next.length > 0 && (
        <Section
          title="Verify next"
          caption="Ordered by how much each would change the picture. Each names who holds the answer."
        >
          <div className="space-y-3">
            {finding.verify_next.map((s) => (
              <StatementCard key={s.id} statement={s} />
            ))}
          </div>
        </Section>
      )}

      {finding.assumptions.length > 0 && (
        <Section
          title="Assumptions in force"
          caption="Things the reasoning requires that nothing here established."
        >
          <div className="space-y-3">
            {finding.assumptions.map((s) => (
              <StatementCard key={s.id} statement={s} />
            ))}
          </div>
        </Section>
      )}

      <Section
        title="Measured context"
        caption="What could be measured about this location, and what could not."
      >
        <div className="grid gap-3 md:grid-cols-2">
          {finding.site_panels.map((panel) => (
            <div key={panel.key} className="panel">
              <div className="panel-header">
                <h3 className="m-0 text-[13px] font-semibold text-ink">{panel.title}</h3>
                {!panel.available && <span className="tag tag-assumption">no data</span>}
              </div>
              <div className="p-3">
                {panel.available ? (
                  <div className="space-y-2.5">
                    {panel.facts.map((f) => (
                      <StatementCard key={f.id} statement={f} compact />
                    ))}
                  </div>
                ) : (
                  <p className="m-0 text-[12.5px] leading-relaxed text-ink-3">
                    {panel.unavailable_reason}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <AgentTrace finding={finding} />

      {openPage && (
        <PageViewer
          pageNumber={openPage.page}
          highlightStart={openPage.start}
          highlightEnd={openPage.end}
          onClose={() => setOpenPage(null)}
        />
      )}
    </div>
  );
}

function Summary({ finding }: { finding: Finding }) {
  const c = finding.coverage as Record<string, number | boolean | string>;
  const stats: [string, string][] = [
    ["facts", String(c.fact ?? 0)],
    ["inferences", String(c.inference ?? 0)],
    ["assumptions", String(c.assumption ?? 0)],
    ["conflicts", String(c.conflicts ?? 0)],
    ["unreadable pages", String(c.unreadable_pages ?? 0)],
    ["critic actions", String(c.critic_interventions ?? 0)],
  ];

  return (
    <div className="panel">
      <div className="panel-header flex-wrap">
        <div className="min-w-0">
          <p className="label mb-1">Question</p>
          <h1 className="m-0 text-[17px] font-semibold leading-snug text-ink">
            {finding.question}
          </h1>
          <p className="m-0 mt-1.5 text-[12.5px] text-ink-3">{finding.resolved_name}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`tag ${finding.mode === "extractive" ? "tag-fact" : "tag-inference"}`}>
            {finding.mode}
          </span>
          <span className="mono text-[11px] text-ink-4">{finding.total_duration_ms} ms</span>
        </div>
      </div>

      {/* Counts of real objects, not a score. There is deliberately no overall number:
          a score would collapse incommensurable things and, worse, stop anyone opening
          the evidence beneath it. */}
      <dl className="m-0 grid grid-cols-2 gap-px bg-line sm:grid-cols-3 lg:grid-cols-6">
        {stats.map(([label, value]) => (
          <div key={label} className="bg-panel px-3 py-2.5">
            <dt className="label">{label}</dt>
            <dd className="mono m-0 text-[18px] font-medium text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      {c.evidence_complete === false && (
        <div className="caveat m-3">
          <span aria-hidden className="shrink-0 font-bold">
            !
          </span>
          <span>
            Evidence for this question is incomplete — relevant pages of the source could not
            be read. See below.
          </span>
        </div>
      )}
    </div>
  );
}

function Disambiguation({ finding }: { finding: Finding }) {
  return (
    <div className="caveat">
      <span aria-hidden className="shrink-0 font-bold">
        !
      </span>
      <div>
        <p className="m-0 font-medium">
          This place name matched {finding.geocode_candidates.length} distinct locations.
        </p>
        <p className="m-0 mt-1 text-ink-2">
          The highest-ranked was used. Every measurement below describes that point — if it
          is the wrong one, the analysis is confidently about somewhere else.
        </p>
        <ul className="m-0 mt-2 list-none space-y-1 p-0">
          {finding.geocode_candidates.slice(0, 4).map((c, i) => (
            <li key={i} className="text-[12px] text-ink-2">
              <span className="mono text-ink-3">{i === 0 ? "used" : "    "}</span>{" "}
              {c.display_name}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function AgentTrace({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);

  return (
    <section className="panel">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="panel-header w-full cursor-pointer border-0 bg-transparent text-left"
        aria-expanded={open}
      >
        <h2 className="m-0 text-[13px] font-semibold text-ink">
          How this was produced
          <span className="ml-2 font-normal text-ink-3">
            {finding.traces.length} agents · {finding.critic_checks_run.length} critic checks
          </span>
        </h2>
        <span className="mono text-[11px] text-ink-3">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="space-y-4 p-4">
          <div>
            <p className="label mb-2">Agents</p>
            <div className="space-y-1.5">
              {finding.traces.map((t) => (
                <div
                  key={t.agent}
                  className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded border border-line bg-raised px-3 py-2"
                >
                  <span className="mono w-20 text-[12px] text-ink">{t.agent}</span>
                  <span className={`tag ${t.ok ? "tag-fact" : "tag-conflict"}`}>
                    {t.ok ? "ok" : "failed"}
                  </span>
                  <span className="mono text-[11px] text-ink-3">{t.duration_ms} ms</span>
                  <span className="text-[11.5px] text-ink-3">
                    {t.statements_produced} statements
                  </span>
                  {t.error && <span className="text-[11.5px] text-conflict">{t.error}</span>}
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="label mb-2">
              Critic checks run ({finding.critic_findings.length} intervention
              {finding.critic_findings.length === 1 ? "" : "s"})
            </p>
            <ul className="m-0 list-none space-y-1 p-0">
              {finding.critic_checks_run.map((check) => {
                const fired = finding.critic_findings.filter((f) => f.check === check);
                return (
                  <li key={check} className="flex gap-2 text-[12.5px]">
                    <span
                      aria-hidden
                      className={`mono shrink-0 ${
                        fired.length ? "text-conflict" : "text-recommendation"
                      }`}
                    >
                      {fired.length ? "!" : "✓"}
                    </span>
                    <span className="text-ink-2">
                      {check}
                      {fired.map((f, i) => (
                        <span key={i} className="block text-[12px] text-conflict">
                          {f.reason}
                        </span>
                      ))}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>

          {finding.unavailable_sources.length > 0 && (
            <div>
              <p className="label mb-2">Sources checked that returned nothing</p>
              <ul className="m-0 list-none space-y-1 p-0">
                {finding.unavailable_sources.map((s, i) => (
                  <li key={i} className="text-[12px] leading-relaxed text-ink-3">
                    — {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export function Section({
  title,
  caption,
  children,
}: {
  title: string;
  caption?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2.5">
        <h2 className="m-0 text-[14px] font-semibold tracking-tight text-ink">{title}</h2>
        {caption && <p className="m-0 mt-0.5 text-[12.5px] text-ink-3">{caption}</p>}
      </div>
      {children}
    </section>
  );
}

export function EmptyState({
  title,
  body,
  tone = "warn",
}: {
  title: string;
  body: string;
  tone?: "warn" | "neutral";
}) {
  return (
    <div
      className={`panel p-4 ${tone === "warn" ? "border-l-[3px]" : ""}`}
      style={tone === "warn" ? { borderLeftColor: "var(--assumption)" } : undefined}
    >
      <p className="m-0 text-[13px] font-medium text-ink">{title}</p>
      <p className="m-0 mt-1.5 text-[12.5px] leading-relaxed text-ink-2">{body}</p>
    </div>
  );
}
