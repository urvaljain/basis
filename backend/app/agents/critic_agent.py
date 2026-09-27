"""Critic Agent — adversarial review that can weaken anything upstream.

## Why it is deliberately ignorant

The critic receives the statements and the retrieved evidence, but **not** the reasoning that
produced them. That is intentional. A critic shown the original chain of thought tends to be
persuaded by it — the justification that convinced the author convinces the reviewer, which
is how self-critique becomes self-congratulation.

So it checks claims against evidence, not against arguments.

## Why most of it needs no model

A large share of the critic's checklist is mechanically decidable, and the mechanical
versions are stricter than a language model would be:

* *Is every fact sourced?* — guaranteed at construction by the type system.
* *Does the quote actually contain the claim?* — lexical containment, exactly checkable.
* *Is confidence higher than the evidence supports?* — a rule over page quality, table risk
  and blind spots.
* *Is a proxy being presented as the thing itself?* — ``proxy_for`` is either declared or
  it is not.
* *Is the answer confident while relevant pages went unread?* — a boolean.

Running these deterministically means the critic has identical teeth with or without an API
key, and its behaviour is reproducible in tests. When a model *is* available it adds one
thing the rules cannot do: judging whether phrasing misleads a reader who does not open the
evidence. That is a genuine addition, not the foundation.

## Demotion, never deletion

Every action is recorded on the statement and rendered in the interface. A claim that was
weakened shows as weakened, with the reason. A critic whose work is invisible cannot be
audited, which would make it indistinguishable from no critic at all — and this product has
no business shipping a trust feature that cannot itself be checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.epistemics import (
    AnyStatement,
    Confidence,
    CriticAction,
    CriticNote,
    Fact,
    Inference,
    SourceKind,
    demote,
)
from app.providers.llm import LLMProvider, get_llm

AGENT = "critic"

_STOPWORDS = frozenset(
    """a an the of for to in on at by and or as be is are was were shall may can with which
    that this these those such any all not no if then than from into within under over per
    it its their there here have has had been being do does did""".split()
)

# A generated sentence must share this fraction of its content words with the evidence.
# Set from observation rather than taste: below ~0.5, sentences that merely reuse the
# question's vocabulary start passing, which defeats the check.
MIN_LEXICAL_SUPPORT = 0.55

# Phrasing that asserts more certainty than this product is ever entitled to.
_OVERCLAIM = re.compile(
    r"\b(complies?|compliant|is permitted|is allowed|you can build|guarantee[sd]?|"
    r"certainly|definitely|will be approved|no restrictions?|fully satisfies)\b",
    re.IGNORECASE,
)


@dataclass
class CriticFinding:
    """One intervention, recorded for display."""

    statement_id: str
    action: CriticAction
    reason: str
    check: str
    """Which check fired — so a reader can see the critic's coverage, not just its verdicts."""


@dataclass
class CriticReading:
    findings: list[CriticFinding] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    statements_reviewed: int = 0
    model_used: str | None = None

    @property
    def interventions(self) -> int:
        return len(self.findings)

    @property
    def clean(self) -> bool:
        return not self.findings

    def by_action(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.action.value] = out.get(f.action.value, 0) + 1
        return out


def _content_words(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9.]+", text.lower()) if w not in _STOPWORDS and len(w) > 2
    }


CRITIC_SYSTEM = """You review claims made by a planning-regulation assistant.

You see the claims and the evidence, not the reasoning that produced them. Judge only \
whether the claims are supported by, and fairly represent, the evidence.

Report ONLY genuine problems, as JSON: {"findings": [{"index": <int>, "problem": "<one \
sentence>", "severity": "high"|"medium"|"low"}]}

Look for: statements the evidence does not support; a restriction softened or omitted; a \
correlation presented as a cause; a measurement presented as a determination; phrasing that \
would mislead someone who does not open the evidence.

An empty findings list is a valid and common answer. Do not invent problems to appear \
diligent."""


class CriticAgent:
    """Adversarial pass over everything the other agents produced."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or get_llm()

    async def run(
        self,
        statements: list[AnyStatement],
        *,
        evidence_texts: list[str] | None = None,
        has_blind_spots: bool = False,
        has_risky_tables: bool = False,
        generated_text: str | None = None,
    ) -> CriticReading:
        reading = CriticReading(statements_reviewed=len(statements))
        evidence_texts = evidence_texts or []

        self._check_facts_are_sourced(reading, statements)
        self._check_quotes_support_claims(reading, statements)
        self._check_proxies_are_declared(reading, statements)
        self._check_confidence_against_evidence(
            reading, statements, has_blind_spots, has_risky_tables
        )
        self._check_overclaiming(reading, statements)

        if generated_text and evidence_texts:
            self._check_generated_text_is_grounded(reading, statements, evidence_texts)

        if self.llm.available and generated_text:
            await self._model_review(reading, statements, evidence_texts, generated_text)

        return reading

    # --------------------------------------------------------------- deterministic

    def _check_facts_are_sourced(
        self, reading: CriticReading, statements: list[AnyStatement]
    ) -> None:
        """Belt and braces over the type-system invariant.

        ``Fact`` cannot be constructed unsourced, so this should never fire. It is kept
        because a guarantee nobody re-checks is a guarantee that quietly stops holding
        when someone adds a code path.
        """
        reading.checks_run.append("every fact carries a source")
        for s in statements:
            if isinstance(s, Fact) and s.source.kind is SourceKind.ABSENT:
                self._apply(
                    reading, s, CriticAction.REJECT,
                    "Asserted as fact with no source.", "every fact carries a source",
                )

    def _check_quotes_support_claims(
        self, reading: CriticReading, statements: list[AnyStatement]
    ) -> None:
        """A document-sourced fact must actually appear in its own quote.

        Guards the case where a span and a claim drift apart — the citation looks right,
        points at a real passage, and does not contain what is being asserted. That is the
        most damaging citation failure, because it survives inspection by anyone who checks
        that the link resolves rather than that the text matches.
        """
        reading.checks_run.append("claim text appears in its cited passage")
        for s in statements:
            if not isinstance(s, Fact) or s.source.document is None:
                continue
            quote_words = _content_words(s.source.document.quote)
            claim_words = _content_words(s.text)
            if not claim_words:
                continue
            overlap = len(claim_words & quote_words) / len(claim_words)
            if overlap < MIN_LEXICAL_SUPPORT:
                self._apply(
                    reading, s, CriticAction.DEMOTE,
                    f"Only {overlap:.0%} of the claim's content words appear in the cited "
                    f"passage; the citation may not support the statement.",
                    "claim text appears in its cited passage",
                )

    def _check_proxies_are_declared(
        self, reading: CriticReading, statements: list[AnyStatement]
    ) -> None:
        """A measurement used as a stand-in must say so."""
        reading.checks_run.append("proxy measurements declare what they stand for")
        interpretive = re.compile(
            r"\baccessib|\bconnectivit|\bsuitab|\bdesirab|\battractiv|\bwell[- ]served\b",
            re.IGNORECASE,
        )
        for s in statements:
            if isinstance(s, Fact) and interpretive.search(s.text) and not s.proxy_for:
                self._apply(
                    reading, s, CriticAction.DEMOTE,
                    "States an interpretation (accessibility, suitability) as a measured "
                    "fact without declaring the proxy involved.",
                    "proxy measurements declare what they stand for",
                )

    def _check_confidence_against_evidence(
        self,
        reading: CriticReading,
        statements: list[AnyStatement],
        has_blind_spots: bool,
        has_risky_tables: bool,
    ) -> None:
        """Cap confidence when the evidence base is known to be incomplete or unreliable."""
        reading.checks_run.append("confidence does not exceed evidence quality")
        if not (has_blind_spots or has_risky_tables):
            return

        reasons = []
        if has_blind_spots:
            reasons.append("relevant pages of the source could not be read")
        if has_risky_tables:
            reasons.append("governing figures came from structurally damaged tables")
        reason = "Confidence capped because " + " and ".join(reasons) + "."

        for s in statements:
            if isinstance(s, Inference) and s.confidence.rank > Confidence.LOW.rank:
                s.reduce_confidence(Confidence.LOW, reason)
                reading.findings.append(
                    CriticFinding(
                        statement_id=s.id,
                        action=CriticAction.REDUCE_CONFIDENCE,
                        reason=reason,
                        check="confidence does not exceed evidence quality",
                    )
                )

    def _check_overclaiming(
        self, reading: CriticReading, statements: list[AnyStatement]
    ) -> None:
        """No statement may assert compliance or permission."""
        reading.checks_run.append("no compliance or permission is asserted")
        for s in statements:
            if match := _OVERCLAIM.search(s.text):
                self._apply(
                    reading, s, CriticAction.FLAG_MISLEADING,
                    f"Asserts certainty this system cannot support (“{match.group(0)}”). "
                    f"The source is a draft plan and interpretation is a licensed activity.",
                    "no compliance or permission is asserted",
                )

    def _check_generated_text_is_grounded(
        self,
        reading: CriticReading,
        statements: list[AnyStatement],
        evidence_texts: list[str],
    ) -> None:
        """Every sentence of generated prose must be lexically anchored in the evidence."""
        reading.checks_run.append("generated sentences are grounded in retrieved evidence")
        evidence_words: set[str] = set()
        for t in evidence_texts:
            evidence_words |= _content_words(t)

        for s in statements:
            if not isinstance(s, Inference) or s.agent != "regulation":
                continue
            unsupported = []
            for sentence in re.split(r"(?<=[.!?])\s+", s.text):
                words = _content_words(sentence)
                if len(words) < 4:
                    continue
                if len(words & evidence_words) / len(words) < MIN_LEXICAL_SUPPORT:
                    unsupported.append(sentence.strip()[:110])
            if unsupported:
                s.reduce_confidence(
                    Confidence.LOW,
                    f"{len(unsupported)} generated sentence(s) are not lexically supported "
                    f"by the retrieved passages.",
                )
                reading.findings.append(
                    CriticFinding(
                        statement_id=s.id,
                        action=CriticAction.REQUIRE_VERIFICATION,
                        reason=(
                            f"Unsupported by retrieved text: “{unsupported[0]}…”"
                            + (f" (+{len(unsupported) - 1} more)" if len(unsupported) > 1 else "")
                        ),
                        check="generated sentences are grounded in retrieved evidence",
                    )
                )

    # --------------------------------------------------------------- model-assisted

    async def _model_review(
        self,
        reading: CriticReading,
        statements: list[AnyStatement],
        evidence_texts: list[str],
        generated_text: str,
    ) -> None:
        """The one check rules cannot do: would this mislead a reader who does not check?"""
        reading.checks_run.append("model review for misleading framing")

        numbered = "\n".join(f"[{i}] {t[:400]}" for i, t in enumerate(evidence_texts[:8], 1))
        prompt = (
            f"EVIDENCE:\n{numbered}\n\nCLAIMS UNDER REVIEW:\n{generated_text[:2500]}\n\n"
            f"Report only genuine problems, as JSON."
        )
        response = await self.llm.complete(
            prompt, system=CRITIC_SYSTEM, max_tokens=900, temperature=0.0
        )
        if not response.ok:
            reading.checks_run.append("model review unavailable — deterministic checks only")
            return

        reading.model_used = response.usage.model
        parsed = response.as_json()
        if not isinstance(parsed, dict):
            return

        target = next(
            (s for s in statements if isinstance(s, Inference) and s.agent == "regulation"), None
        )
        for finding in parsed.get("findings", []) or []:
            problem = str(finding.get("problem", "")).strip()
            if not problem:
                continue
            severity = str(finding.get("severity", "medium")).lower()
            action = (
                CriticAction.FLAG_MISLEADING
                if severity == "high"
                else CriticAction.REQUIRE_VERIFICATION
            )
            if target is not None:
                target.record_critic(CriticNote(action=action, reason=problem))
            reading.findings.append(
                CriticFinding(
                    statement_id=target.id if target else "-",
                    action=action,
                    reason=problem,
                    check="model review for misleading framing",
                )
            )

    # ---------------------------------------------------------------------- helper

    def _apply(
        self,
        reading: CriticReading,
        statement: AnyStatement,
        action: CriticAction,
        reason: str,
        check: str,
    ) -> None:
        if action is CriticAction.DEMOTE and isinstance(statement, (Fact, Inference)):
            # demote() returns a new object; the orchestrator swaps it in by id so the
            # audit trail and the statement's identity both survive.
            statement.record_critic(
                CriticNote(action=CriticAction.DEMOTE, reason=reason, from_value=statement.type.value)
            )
        else:
            statement.record_critic(CriticNote(action=action, reason=reason))

        reading.findings.append(
            CriticFinding(
                statement_id=statement.id, action=action, reason=reason, check=check
            )
        )


def apply_demotions(statements: list[AnyStatement]) -> list[AnyStatement]:
    """Materialise recorded demotions into actual type changes.

    Kept separate from the critic so review and mutation are distinct steps: the critic
    decides, this applies, and both are visible.
    """
    out: list[AnyStatement] = []
    for s in statements:
        should_demote = any(
            n.action is CriticAction.DEMOTE and n.to_value is None for n in s.critic_notes
        )
        if should_demote and isinstance(s, (Fact, Inference)):
            reason = next(
                n.reason for n in s.critic_notes if n.action is CriticAction.DEMOTE
            )
            out.append(demote(s, reason))
        else:
            out.append(s)
    return out
