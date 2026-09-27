import Link from "next/link";

/**
 * How it works, and what it will not claim.
 *
 * This doubles as the responsible-AI surface. Rather than a paragraph of reassurance, it
 * states the specific mechanisms, the specific limits, and the specific things a reader must
 * not conclude — because a limitation that is not concrete is not a limitation, it is a
 * liability notice.
 */
export default function MethodPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <header className="max-w-2xl">
        <p className="label mb-2">Method</p>
        <h1 className="m-0 text-[26px] font-semibold leading-tight tracking-tight text-ink">
          How Basis reaches an answer, and where it stops
        </h1>
      </header>

      <Block title="Four agents, not nine">
        <p>
          An &ldquo;agent&rdquo; that wraps one API call and reformats the response is a
          function. The test applied to each proposed module was whether it makes a{" "}
          <em>judgement</em> that could be wrong in an interesting way, and that another
          module could catch. Computing distance to a station fails that test — it is
          arithmetic, and it belongs in a provider.
        </p>
        <Agents />
        <p className="mt-3">
          Orchestration is forty lines of <code className="mono">asyncio</code>: fan out to
          Site and Regulation in parallel, join, then Conflict and Critic in sequence. No
          agent framework, because the graph is static and the value is in the epistemic
          model rather than the graph engine.
        </p>
      </Block>

      <Block title="Four kinds of statement, enforced in code">
        <p>
          Most systems emit one undifferentiated kind of output and decorate it with a
          confidence number. That flattens four genuinely different things, and a reader who
          cannot tell them apart cannot calibrate their trust.
        </p>
        <dl className="m-0 mt-3 grid gap-px overflow-hidden rounded border border-line bg-line sm:grid-cols-2">
          {[
            ["Fact", "fact", "Measured or directly quoted. Cannot be constructed without a source — that is a type-level invariant, not a lint rule."],
            ["Inference", "inference", "Derived from facts by a named transformation. Must state what it rests on and why its confidence band is what it is."],
            ["Assumption", "assumption", "Required for the reasoning to hold, not itself established. Must state what would falsify it."],
            ["Action", "recommendation", "A suggested human step, responding to a specific uncertainty, addressed to someone who can actually take it."],
          ].map(([label, cls, body]) => (
            <div key={label} className="bg-panel p-3.5">
              <dt>
                <span className={`tag tag-${cls}`}>{label}</span>
              </dt>
              <dd className="m-0 mt-2 text-[12.5px] leading-relaxed text-ink-2">{body}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3">
          Confidence may attach only to an inference. A fact is not 80% true — it either has
          a source or it is not a fact. A recommendation is not probabilistic. Conflating
          these is how confidence badges became meaningless.
        </p>
      </Block>

      <Block title="The critic can weaken anything, and shows its work">
        <p>
          The critic receives the claims and the evidence but <em>not</em> the reasoning that
          produced them, so it cannot be persuaded by the argument that convinced the author.
          Most of its checklist is mechanically decidable, which means it has identical teeth
          with or without a language model:
        </p>
        <ul className="m-0 mt-2.5 list-none space-y-1.5 p-0">
          {[
            "Is every fact actually sourced?",
            "Does the cited passage contain what the claim asserts?",
            "Is a proxy being presented as the thing it stands for?",
            "Is confidence higher than the evidence supports?",
            "Does any statement assert compliance, permission or certainty?",
            "Is generated prose lexically anchored in the retrieved text?",
          ].map((check) => (
            <li key={check} className="flex gap-2.5 text-[13px] text-ink-2">
              <span aria-hidden className="mono shrink-0 text-recommendation">
                ✓
              </span>
              {check}
            </li>
          ))}
        </ul>
        <p className="mt-3">
          It demotes rather than deletes, and every intervention is rendered in the interface.
          A critic whose work is invisible cannot be audited, which makes it indistinguishable
          from no critic at all.
        </p>
      </Block>

      <Block title="Two modes, and the guarantees live in the deterministic one">
        <p>
          With no language model configured, Basis runs <strong>extractive</strong>: every
          claim is a verbatim passage with its page and span. It cannot hallucinate a
          provision, because it never composes one.
        </p>
        <p className="mt-2.5">
          With a model, the same retrieval, the same epistemic types and the same critic
          apply, and the model adds synthesis. The ordering is deliberate:{" "}
          <strong>
            passage-level provenance, blind-spot reporting, table-damage warnings, epistemic
            typing and critic demotion all work with no model at all.
          </strong>{" "}
          Remove the model and the prose gets worse. Nothing else changes.
        </p>
      </Block>

      <Block title="What Basis will not claim">
        <ul className="m-0 list-none space-y-2.5 p-0">
          {[
            ["It does not certify compliance.", "The source is a draft master plan, and interpretation of development control regulations is a licensed professional activity. Local authority discretion routinely overrides the written rule."],
            ["It does not score a site.", "A single number requires weighting incommensurable things against a development thesis nobody stated — and once a score exists, nobody opens the evidence beneath it."],
            ["It does not determine whether a rule applies to your plot.", "The regulation's requirements turn on plot attributes — land-use zone, overlay status, dimensions — that do not exist as open data here. Basis can state the rule; it cannot tell you which rule is yours."],
            ["It does not display a metric it did not measure.", "Four evaluation dimensions currently read “not measured”, with the reason. They are not estimated."],
            ["It does not present repaired text as verbatim.", "Where the source PDF was mis-encoded, the quote is reconstructed and says so, with the raw extraction one click away."],
          ].map(([title, body]) => (
            <li key={title}>
              <p className="m-0 text-[13px] font-medium text-ink">{title}</p>
              <p className="m-0 mt-0.5 text-[12.5px] leading-relaxed text-ink-3">{body}</p>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Where the numbers come from">
        <p>
          Everything quantified in this product is measured by code you can run.{" "}
          <Link href="/corpus" className="text-inference no-underline hover:underline">
            Corpus coverage
          </Link>{" "}
          comes from the ingestion pipeline;{" "}
          <Link href="/evaluation" className="text-inference no-underline hover:underline">
            evaluation results
          </Link>{" "}
          come from a run against ground truth anchored to pages and phrases in the real
          document, which is validated before anything is scored — if a case&apos;s expected
          phrase is not where it claims to be, the run aborts rather than reporting a number
          that means nothing.
        </p>
      </Block>
    </div>
  );
}

function Agents() {
  const agents = [
    ["Site", "Which measured properties bear on this question, and what each one is a proxy for.", "Nominatim · Overpass · ERA5 · SRTM"],
    ["Regulation", "What the document says — and whether it can see the part that governs.", "BM25 over 1,088 clause-level chunks"],
    ["Conflict", "Do measurement and regulation point the same way, and can they even be compared?", "rule-based over typed statements"],
    ["Critic", "Should any of the above survive?", "deterministic checks, plus a model pass when available"],
  ];
  return (
    <ol className="m-0 mt-3 list-none space-y-2 p-0">
      {agents.map(([name, job, how], i) => (
        <li key={name} className="flex gap-3 rounded border border-line bg-raised p-3">
          <span className="mono shrink-0 pt-0.5 text-[11px] text-ink-4">
            {String(i + 1).padStart(2, "0")}
          </span>
          <div className="min-w-0">
            <p className="m-0 text-[13px] font-medium text-ink">{name}</p>
            <p className="m-0 mt-0.5 text-[12.5px] leading-relaxed text-ink-2">{job}</p>
            <p className="mono m-0 mt-1 text-[11px] text-ink-4">{how}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-9 border-t border-line pt-7">
      <h2 className="m-0 mb-2.5 text-[16px] font-semibold tracking-tight text-ink">{title}</h2>
      <div className="max-w-2xl space-y-0 text-[13.5px] leading-relaxed text-ink-2 [&_p]:m-0">
        {children}
      </div>
    </section>
  );
}
