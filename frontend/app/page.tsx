import Link from "next/link";

/**
 * Landing page.
 *
 * It argues one thing and shows one artefact. A feature grid would be easy and would say
 * nothing — the claim that matters is specific and checkable, so the page makes it
 * specifically: here is a real clause in a real document that a real pipeline cannot read,
 * and here is what this product does about that.
 */
export default function Home() {
  return (
    <div className="mx-auto max-w-content px-4 py-12 sm:px-6 sm:py-16">
      <section className="max-w-3xl">
        <p className="label mb-3">Site &amp; regulation intelligence</p>
        <h1 className="m-0 text-[32px] font-semibold leading-[1.15] tracking-tight text-ink sm:text-[42px]">
          The answer is easy.
          <br />
          <span className="text-ink-3">Knowing whether to believe it is the work.</span>
        </h1>
        <p className="m-0 mt-5 text-[15px] leading-relaxed text-ink-2">
          Basis answers a blocking question about a site from the governing regulation and
          the site&apos;s measured context — and shows you the exact passage behind every
          claim, where the evidence disagrees with itself, and what it could not read at all.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <Link href="/demo" className="btn btn-primary no-underline">
            See the three-minute walkthrough
          </Link>
          <Link href="/workspace" className="btn no-underline">
            Open the workspace
          </Link>
        </div>
      </section>

      <section className="mt-16 border-t border-line pt-10">
        <p className="label mb-4">Why this exists</p>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <h2 className="m-0 text-[17px] font-semibold leading-snug text-ink">
              In this jurisdiction, the rules that decide a project are not an API.
            </h2>
            <p className="m-0 mt-3 text-[13.5px] leading-relaxed text-ink-2">
              Zoning class, FAR, setbacks, valley-zone overlay, flood hazard, parcel
              geometry — none are machine-queryable here. Every one of them is published as
              prose and drawings inside a 206-page government PDF.
            </p>
            <p className="m-0 mt-3 text-[13.5px] leading-relaxed text-ink-2">
              So a product that only reads APIs is confident about the distance to a bus stop
              and silent on whether you may build at all. The constraint layer is a document,
              and reading it honestly is harder than it looks.
            </p>
          </div>

          <div>
            <h2 className="m-0 text-[17px] font-semibold leading-snug text-ink">
              That document defeats a retrieval pipeline in three different ways.
            </h2>
            <ol className="m-0 mt-3 list-none space-y-3 p-0">
              {[
                [
                  "54 of 206 pages have no text at all",
                  "including the entire 23-page statutory instrument governing Transferable Development Rights. Detectable — so Basis reports it and renders the pages.",
                ],
                [
                  "542 characters are mis-encoded",
                  "and the corruption reaches inside the numbers: 75 m extracts as 7ϱ ŵ. A search for the clause finds nothing. Detectable — so Basis repairs it and labels every repaired quote.",
                ],
                [
                  "Six tables extract cleanly and lose their columns",
                  "The FAR tables. Blank cells vanish, so a base figure can be read as a total — a 2× error on the number that decides what gets built. Not detectable by any coverage metric, which is what makes it the dangerous one.",
                ],
              ].map(([title, body], i) => (
                <li key={title} className="flex gap-3">
                  <span className="mono shrink-0 pt-0.5 text-[11px] text-ink-4">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>
                    <span className="block text-[13px] font-medium text-ink">{title}</span>
                    <span className="mt-0.5 block text-[12.5px] leading-relaxed text-ink-3">
                      {body}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="mt-14 border-t border-line pt-10">
        <p className="label mb-4">The clause that shaped the product</p>
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <p className="m-0 text-[13.5px] leading-relaxed text-ink-2">
              Search for what a Bengaluru valley zone does to your buildable area and you
              will find, repeatedly, that it cuts FAR by 25–50%.
            </p>
            <p className="m-0 mt-3 text-[13.5px] leading-relaxed text-ink">
              That figure is not in the governing document. What the document actually says
              is stricter by an order of magnitude — and the only way to know that is to read
              the clause.
            </p>
            <p className="m-0 mt-3 text-[12.5px] leading-relaxed text-ink-3">
              This was found while building Basis, by checking a secondary source against the
              primary one. It is the product&apos;s argument, encountered first-hand.
            </p>
          </div>

          <figure className="m-0">
            <div className="paper">
              <span className="mono text-[10px] uppercase tracking-wider text-paper-muted">
                RMP 2031 (Draft) Vol. 6 · §6.5.3(ii) · p. 80
              </span>
              <blockquote className="m-0 mt-2">
                The buffer for Water bodies such as Lakes/Streams/ Drains shall be governed as
                per the NGT Order. In case of water bodies a{" "}
                <mark>75 m buffer of &lsquo;no development zone&rsquo;</mark> is to be
                maintained around the lake (as per revenue records)…
              </blockquote>
            </div>
            <figcaption className="mono mt-1.5 text-[10.5px] uppercase tracking-wider text-assumption">
              reconstructed — this page was mis-encoded; raw extraction reads “7ϱ ŵ ďuffeƌ”
            </figcaption>
          </figure>
        </div>
      </section>

      <section className="mt-14 border-t border-line pt-10">
        <p className="label mb-4">What it will not do</p>
        <ul className="m-0 grid list-none gap-x-8 gap-y-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Give a site a score", "It would collapse incommensurable things — and nobody opens the evidence underneath a number."],
            ["Certify compliance", "The source is a draft plan, and interpretation is a licensed activity."],
            ["Hide what it could not read", "Blind spots are reported as results, with the pages rendered."],
            ["Show a metric it did not measure", "Four evaluation dimensions read “not measured”, with the reason."],
            ["Resolve what open data cannot", "It names what is missing and who holds it."],
            ["Quote repaired text as verbatim", "Reconstructed quotes say so, with the raw extraction one click away."],
          ].map(([title, body]) => (
            <li key={title}>
              <span className="block text-[13px] font-medium text-ink">{title}</span>
              <span className="mt-0.5 block text-[12px] leading-relaxed text-ink-3">
                {body}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
