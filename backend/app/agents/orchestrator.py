"""Orchestrator — a fixed DAG, deliberately without a framework.

The control flow is static: fan out to the Site and Regulation agents in parallel, join,
then run Conflict and Critic in sequence. That is roughly forty lines of ``asyncio``.

LangChain or LangGraph would add a dependency tree, a new abstraction vocabulary, opaque
prompt construction and version churn, in exchange for solving a problem this system does
not have. The value here is in the epistemic model and the evidence handling, not in the
graph engine. If the DAG ever becomes dynamic — an agent deciding at runtime which other
agents to call — that judgement should be revisited. It is not dynamic today.

What *is* built, because these are real needs: full trace capture (the evidence inspector and
the evaluation harness read the same trace), per-agent timing, and a result that degrades to
something useful when any single agent fails.

## The output shape

A :class:`Finding` has a fixed anatomy, extending the trace Planso publishes with the two
steps this product argues are missing from it — what could not be read, and what would change
the conclusion::

    QUESTION → CONTEXT → EVIDENCE → CONFLICT → UNREADABLE
             → ANSWER → CHANGE-MY-MIND → VERIFY
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.agents.conflict_agent import Conflict, ConflictAgent, ConflictReading
from app.agents.critic_agent import CriticAgent, CriticReading, apply_demotions
from app.agents.regulation_agent import RegulationAgent, RegulationReading
from app.agents.site_agent import SiteAgent, SiteReading
from app.domain.epistemics import (
    AnyStatement,
    Assumption,
    EpistemicType,
    Fact,
    Inference,
    Recommendation,
    summarise,
)
from app.ingest.retriever import RegulationIndex
from app.providers.llm import LLMMode, LLMProvider, get_llm

logger = logging.getLogger(__name__)


@dataclass
class AgentTrace:
    """One agent's execution record. Persisted so the UI and the evaluator agree."""

    agent: str
    started_at: datetime
    duration_ms: int
    ok: bool
    statements_produced: int = 0
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    """The persistent, linkable unit of work.

    Not a chat message: a chat log makes provenance fragile, because claims scroll away and
    there is no stable object to attach evidence to. A Finding has an id, a fixed anatomy,
    and evidence bound to each part of it.
    """

    id: str
    question: str
    location_query: str
    created_at: datetime
    mode: LLMMode

    site: SiteReading | None = None
    regulation: RegulationReading | None = None
    conflicts: ConflictReading | None = None
    critic: CriticReading | None = None

    statements: list[AnyStatement] = field(default_factory=list)
    traces: list[AgentTrace] = field(default_factory=list)
    total_duration_ms: int = 0

    # --- the eight-part anatomy ------------------------------------------------

    @property
    def context(self) -> list[Fact]:
        """What was measured about this place."""
        return [s for s in self.statements if isinstance(s, Fact) and s.agent == "site"]

    @property
    def evidence(self) -> list[Fact]:
        """What the governing document says, with spans."""
        return [s for s in self.statements if isinstance(s, Fact) and s.agent == "regulation"]

    @property
    def conflict_list(self) -> list[Conflict]:
        return self.conflicts.conflicts if self.conflicts else []

    @property
    def unreadable(self) -> list[dict[str, Any]]:
        """Regions of the document bearing on this question that could not be parsed."""
        if not self.regulation:
            return []
        return [
            {
                "page_start": s.page_start,
                "page_end": s.page_end,
                "page_count": s.page_count,
                "descriptor": s.descriptor,
                "matched_terms": s.matched_terms,
            }
            for s in self.regulation.blind_spots
        ]

    @property
    def answer(self) -> str | None:
        """Generated prose, or None in extractive mode.

        None is a real answer state, not a missing one. In extractive mode the evidence
        list *is* the output, and inventing a narrative stand-in would defeat the point.
        """
        return self.regulation.synthesis if self.regulation else None

    @property
    def assumptions(self) -> list[Assumption]:
        return [s for s in self.statements if isinstance(s, Assumption) and not s.rejected]

    @property
    def change_my_mind(self) -> list[dict[str, str]]:
        """What evidence would overturn each part of this.

        Assembled from the falsification conditions already attached to assumptions and
        conflicts — not generated. Every entry is something a specific person could go and
        obtain, which is what separates this from a disclaimer.
        """
        out: list[dict[str, str]] = []
        for a in self.assumptions:
            out.append(
                {
                    "current_position": a.text,
                    "would_change_if": a.falsified_by,
                    "type": "assumption",
                }
            )
        for c in self.conflict_list:
            for resolver in c.what_would_resolve_it:
                out.append(
                    {
                        "current_position": f"{c.title}: {c.why_it_matters}",
                        "would_change_if": resolver,
                        "type": "conflict",
                    }
                )
        return out

    @property
    def verify_next(self) -> list[Recommendation]:
        """Verification tasks, highest priority first."""
        recs = [s for s in self.statements if isinstance(s, Recommendation) and not s.rejected]
        return sorted(recs, key=lambda r: r.priority)

    # --- honest summary numbers ------------------------------------------------

    @property
    def coverage(self) -> dict[str, Any]:
        """Counts of real objects. Not a quality score — see docs/08-non-goals.md."""
        counts = summarise(self.statements)
        return {
            **counts,
            "unreadable_regions": len(self.unreadable),
            "unreadable_pages": sum(u["page_count"] for u in self.unreadable),
            "conflicts": len(self.conflict_list),
            "unresolvable_conflicts": len(self.conflicts.unresolvable) if self.conflicts else 0,
            "critic_interventions": self.critic.interventions if self.critic else 0,
            "evidence_complete": bool(self.regulation and self.regulation.evidence_is_complete),
            "mode": self.mode.value,
        }

    @property
    def failed_agents(self) -> list[str]:
        return [t.agent for t in self.traces if not t.ok]


class Orchestrator:
    """Runs the fixed agent DAG and assembles a Finding."""

    def __init__(self, index: RegulationIndex, llm: LLMProvider | None = None) -> None:
        self.index = index
        self.llm = llm or get_llm()

    async def run(
        self,
        question: str,
        location_query: str,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        use_cache: bool = True,
    ) -> Finding:
        started = time.monotonic()
        finding = Finding(
            id=f"fnd_{uuid.uuid4().hex[:12]}",
            question=question,
            location_query=location_query,
            created_at=datetime.now(timezone.utc),
            mode=LLMMode.GENERATIVE if self.llm.available else LLMMode.EXTRACTIVE,
        )

        # --- fan out -----------------------------------------------------------
        site_task = self._timed(
            "site",
            SiteAgent().run(
                location_query, latitude=latitude, longitude=longitude, use_cache=use_cache
            ),
        )
        regulation_task = self._timed(
            "regulation", RegulationAgent(self.index, self.llm).run(question)
        )
        (site, site_trace), (regulation, regulation_trace) = await asyncio.gather(
            site_task, regulation_task
        )

        finding.site = site
        finding.regulation = regulation
        finding.traces.extend([site_trace, regulation_trace])

        if site is not None:
            finding.statements.extend(site.statements)
            site_trace.statements_produced = len(site.statements)
            site_trace.detail = {
                "resolved": site.resolved,
                "unavailable_sources": len(site.unavailable),
                "needs_disambiguation": site.needs_disambiguation,
            }
        if regulation is not None:
            finding.statements.extend(regulation.statements)
            regulation_trace.statements_produced = len(regulation.statements)
            regulation_trace.detail = {
                "claims": len(regulation.claims),
                "blind_spots": len(regulation.blind_spots),
                "numeric_provisions": len(regulation.numeric_provisions),
                "mode": regulation.mode.value,
            }
            finding.mode = regulation.mode  # may have fallen back mid-run

        # --- join: conflict ----------------------------------------------------
        if site is not None and regulation is not None:
            conflicts, trace = await self._timed_sync(
                "conflict", lambda: ConflictAgent().run(site, regulation)
            )
            finding.conflicts = conflicts
            finding.traces.append(trace)
            if conflicts is not None:
                finding.statements.extend(conflicts.statements)
                trace.statements_produced = len(conflicts.statements)
                trace.detail = {
                    "conflicts": len(conflicts.conflicts),
                    "unresolvable": len(conflicts.unresolvable),
                }

        # --- critic ------------------------------------------------------------
        evidence_texts = [
            c.source.document.quote
            for c in (regulation.claims if regulation else [])
            if c.source.document
        ]
        critic, critic_trace = await self._timed(
            "critic",
            CriticAgent(self.llm).run(
                finding.statements,
                evidence_texts=evidence_texts,
                has_blind_spots=bool(regulation and regulation.blind_spots),
                has_risky_tables=bool(regulation and regulation.has_table_risk),
                generated_text=regulation.synthesis if regulation else None,
            ),
        )
        finding.critic = critic
        finding.traces.append(critic_trace)
        if critic is not None:
            critic_trace.detail = {
                "interventions": critic.interventions,
                "checks_run": len(critic.checks_run),
                "by_action": critic.by_action(),
            }
            finding.statements = apply_demotions(finding.statements)

        finding.total_duration_ms = int((time.monotonic() - started) * 1000)
        return finding

    # ------------------------------------------------------------------- helpers

    async def _timed(self, name: str, coro) -> tuple[Any, AgentTrace]:
        """Run an agent, capturing timing and containing its failure.

        One agent failing must not abort the analysis. A Finding with a site reading and no
        regulation reading is degraded but still useful, and the trace says which part is
        missing — which beats a 500 that tells the user nothing.
        """
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        try:
            result = await coro
            return result, AgentTrace(
                agent=name,
                started_at=started_at,
                duration_ms=int((time.monotonic() - t0) * 1000),
                ok=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("agent %s failed", name)
            return None, AgentTrace(
                agent=name,
                started_at=started_at,
                duration_ms=int((time.monotonic() - t0) * 1000),
                ok=False,
                error=f"{type(e).__name__}: {str(e)[:200]}",
            )

    async def _timed_sync(self, name: str, fn) -> tuple[Any, AgentTrace]:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        try:
            result = fn()
            return result, AgentTrace(
                agent=name,
                started_at=started_at,
                duration_ms=int((time.monotonic() - t0) * 1000),
                ok=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("agent %s failed", name)
            return None, AgentTrace(
                agent=name,
                started_at=started_at,
                duration_ms=int((time.monotonic() - t0) * 1000),
                ok=False,
                error=f"{type(e).__name__}: {str(e)[:200]}",
            )
