# 18 — Founder Outreach

**Status: draft for Urval to edit and send. Do not send as-is without reading §Notes.**

The product link is the centrepiece. Everything else is scaffolding around it.

---

## The message

> **Subject:** I built something on the Bengaluru master plan — would value your read
>
> Naveen,
>
> Your site describes evidence decaying on its way to a decision — assembled over weeks,
> interpreted in silos, then decided from whatever made it into the room. I wanted to see how
> much of that I could actually reproduce, so I spent a week on one real document: the RMP
> 2031 zoning regulations.
>
> The document defeated me three different ways, and only two of them were detectable.
>
> 54 of its 206 pages carry no machine-readable text — including the entire 23-page Karnataka
> TCP Benefit of Development Rights Rules. Ask about TDR and a normal pipeline answers
> fluently from the prose surrounding the gap; it has no way to know the governing rules are
> invisible to it.
>
> 542 characters are mis-encoded, and the corruption reaches inside the numbers: "75 m"
> extracts as "7ϱ ŵ". Searching that document for "75 m buffer" returns nothing, though the
> clause is on page 80.
>
> The third one is the one I did not expect. Six tables — the FAR tables — extract perfectly
> cleanly and lose their column structure. Rows 1–4 of Table 6 carry two FAR figures where
> rows 5–8 carry three, because a cell is blank. Obvious in the PDF, invisible in flattened
> text. A base figure reads as a total: a 2× error on the number that decides what gets built,
> from a page every coverage metric calls fine.
>
> So I built Basis around that: answers with the passage and character span attached, blind
> spots reported as results with the pages rendered, and conflicts held open rather than
> resolved. Most conflicts here are unresolvable from open data, and saying so precisely
> turned out to be more useful than answering.
>
> **[link]**
>
> Two things I got wrong, since they are probably more informative than what works. I nearly
> built the demo's central conflict on the "valley zone cuts FAR 25–50%" figure that every
> secondary source repeats — it is not in the primary document, which says something
> categorically stricter. And my own evaluation harness caught the system manufacturing
> coverage for questions the document does not address: asked who owns a parcel, it
> confidently returned the clause defining "site". Exactly the failure the product exists to
> prevent, committed by the product.
>
> The thing I could not test is the one that matters: whether any of this actually makes
> someone trust the output. That needs practitioners, not a harness.
>
> If you have ten minutes, I would value your read — particularly on whether the blind-spot
> reporting reads as rigour or as hedging to someone who does this work.
>
> Urval
> [portfolio / LinkedIn]

---

## Why it is shaped this way

**It opens on their own framing, then moves immediately to something they do not know.** The
three failure modes in that specific document are novel, concrete and verifiable in thirty
seconds. That is the only real currency in a cold message.

**It leads with the hardest finding, not the product.** The flattened-table failure is the most
interesting thing in the whole build and it is genuinely non-obvious. A founder who has looked
at AEC documents will recognise it immediately — and will know it is not something you can
find without actually doing the work.

**It volunteers two failures.** Including one where the product committed its own cardinal
sin. This is the single strongest signal available: anyone can show a working demo, almost
nobody shows the evaluation that caught them.

**The ask is feedback on a specific question**, not a job. And the question is the one he is
actually spending his hiring process on — whether users trust document answering with source
attribution. It invites a reply he has an opinion about.

**No "passionate about AI". No "huge fan of Planso".** No claim to have solved anything.

---

## Notes before sending

1. **Confirm the role.** The public careers page lists AI Engineer, Design Engineer,
   Full-Stack Engineer and AEC Product Intern — no posting titled "0→1 product". If you are
   responding to a specific posting seen elsewhere, paste its text and this should be
   re-aimed. As written it works as cold outreach with a feedback ask, which is the safer
   framing.

2. **The AEC Product Intern application asks you to answer its questions in your own words and
   to disclose AI use.** If you apply to that, do not send this message instead — answer their
   questions, and use the link as evidence inside that answer. Their product-learning exercise
   ("how would you test whether people trust it?") is precisely what
   `docs/11-ai-evaluation.md` §"What this evaluation cannot tell you" sets out. That section
   is your answer.

3. **Disclose how you worked.** They explicitly say they want to see how candidates work with
   AI. This was built with Claude as a pair — research, implementation and review — with the
   product decisions, the corrections and the calls on what to cut being yours. Say that
   plainly; hiding it would be both dishonest and a missed signal, given they asked.

4. **Check the link works before sending**, from a device that is not yours, and confirm
   `/demo` runs when the API is cold.

5. **Trim if it is too long for your taste.** The two paragraphs that must survive are the
   flattened-tables one and the two-things-I-got-wrong one.

---

## One-line version, if you need it

> I spent a week on the RMP 2031 zoning regulations and found three ways it defeats a
> retrieval pipeline — one of which no coverage metric detects. Built a thing around it:
> [link]. Would value your read.
