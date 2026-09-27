# 08 — Non-Goals

Things Basis deliberately does not do. Each has a reason, and several were removed *after*
being attempted (see `14-decision-log.md`).

---

## 1. No site score

**Not doing:** `Site A = 92, Site B = 84`.

A single number requires weighting incommensurable things — accessibility against flood
exposure against regulatory risk — and the weights encode a development thesis the user has
not told us. Two developers evaluating the same plot for a warehouse and a hospital should
get different answers, and neither should be 92.

Worse: a score destroys the audit trail it sits on. Once a number exists, nobody opens the
evidence. The score becomes the product and the reasoning becomes decoration.

**Attempted and removed.** See `14-decision-log.md` D-004.

**Instead:** a comparison matrix where every cell is evidence, and differences are traceable
to their source.

---

## 2. No organisational or knowledge intelligence

**Not doing:** "4 precedents from your firm's past projects," expertise location, "who in
your organisation understands this."

This is two of Planso's six declared layers, and it is genuinely valuable — but it requires a
firm's decades of private project history. **I have none.** Any version I built would be
populated with invented precedents, which breaks the one principle this product exists to
demonstrate.

Fabricating a precedent to demo a precedent engine would be the single most damaging thing I
could ship to an audience that cares about evidence integrity.

**Instead:** the document layer is genuinely user-supplied. Upload a real report, get real
passage-level extraction. The mechanism that would power knowledge intelligence is built and
demonstrated on real documents — just not on a fake corporate memory.

---

## 3. No simulation

**Not doing:** solar studies, wind, daylight, thermal, carbon modelling.

Autodesk Forma owns this and does it properly with validated physics. A prototype-grade
simulation would be both worse and unverifiable, and physics I cannot validate is exactly the
kind of confident-and-wrong output this product argues against.

**Instead:** measured climate observations from ERA5 (real, cited, with the 4.71 km grid drift
disclosed) — description, not prediction.

---

## 4. No generative massing or "what fits here"

**Not doing:** building envelopes, unit yield, floorplate optimisation.

TestFit and Hypar own this. It also requires the dimensional matrices that live on the
image-only pages I cannot read — so building it would require either fabricating the inputs
or silently guessing them.

**Instead:** report honestly that the governing matrix is unreadable, and show the user the
page.

---

## 5. No compliance certification

**Not doing:** "this proposal complies with RMP 2031."

The corpus is a **draft** master plan. Interpretation of development control regulations is
a licensed professional activity with statutory consequences, and local authority discretion
routinely overrides the written rule.

**Instead:** "here is what the document says, here is the passage, here is what a licensed
professional must confirm." Every export carries this. See `docs/28-responsible-ai` content
folded into `12-risk-register.md`.

---

## 6. No nine-agent architecture

**Not doing:** the nine specialised agents in the original brief.

Agents that each wrap a single API call are functions wearing a costume. Planso themselves
use four families. Nine modules over data sources that mostly do not exist is architecture
theatre, and a founder who has shipped AI products will read it as such immediately.

**Instead:** four agents, each of which genuinely reasons rather than fetches. See
`09-agent-architecture.md`.

---

## 7. No chat as the primary surface

**Not doing:** a message thread as the main interaction.

Planso's own job posting says it explicitly: *"not just as generic chat interfaces."* A chat
log also makes provenance fragile — claims scroll away, and there is no stable object to
attach evidence to.

**Instead:** a question produces a persistent, structured, linkable **finding** with a fixed
anatomy. Findings accumulate into a workspace. Chat, if present at all, is an input method,
not the artefact.

---

## 8. No fabricated metrics anywhere

**Not doing:** displaying any number that no measurement produced.

This includes confidence percentages that are actually the model's self-report dressed as
measurement, "91% evidence coverage" without an evaluation run behind it, and progress bars
for work that is not happening.

**Instead:** every number in the UI traces to `11-ai-evaluation.md`. Where confidence is
model-reported rather than measured, it is **labelled as self-reported**, because those are
different epistemic objects and conflating them is the exact dishonesty this product opposes.

---

## 9. No multi-jurisdiction breadth in the MVP

**Not doing:** Dubai, Mumbai, Delhi, generic "any city."

One jurisdiction done to the depth where the failure modes are visible beats five done
shallowly. The data layer is abstracted so a second jurisdiction is an implementation, not a
rewrite — but breadth without depth would hide precisely the problems worth showing.

---

## 10. No authentication or multi-tenancy in the MVP

**Not doing:** accounts, orgs, roles, sharing permissions.

This is a demonstration of product and AI judgement, not a SaaS. Auth adds surface area and
demonstrates nothing about the thesis. Uploaded documents are scoped to a session and are
deletable.

**Revisit if** the product is ever put in front of real users with real project documents —
at which point document confidentiality becomes the first requirement, not the last.
