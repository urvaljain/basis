"""Site comparison as an evidence matrix, not a ranking.

## Why there is no score

The obvious output here is `A = 92, B = 84, C = 72`. It was built, looked convincing, and was
removed. Three reasons, in order of how badly each one bites:

1. **A single number requires weights nobody stated.** Ranking accessibility against flood
   exposure against regulatory risk encodes a development thesis — and two developers
   evaluating the same plot for a warehouse and a hospital should reach different answers.
   Neither of them should be 92.
2. **A score destroys the audit trail it sits on.** Once a number exists, nobody opens the
   evidence. The score becomes the product and the reasoning becomes decoration — which is
   precisely the failure mode this whole system is built to avoid.
3. **Most cells here are genuinely unresolved.** Averaging over unknowns produces a number
   that looks more confident than any of its inputs.

See `docs/08-non-goals.md` §1 and the decision log entry D-004.

## What replaces it

A matrix where every cell is **evidence with its provenance**, and differences between sites
are traceable to their source. The one row that does carry a number is *coverage* — how many
cells are facts, how many are assumptions, how many could not be established — because that
is measurable, unlike site quality.

The honest finding, and the point of the feature: on a regulatory question the sites are
often **indistinguishable from open data**. The comparison's real output is usually "these
three sites differ in ways this data cannot see, and here is what you would need to tell
them apart."
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.agents.orchestrator import Finding, Orchestrator
from app.domain.epistemics import EpistemicType

# Dimensions compared. Each names the measurement and how it is matched from the site facts,
# so a cell can always be traced back to the statement that produced it.
DIMENSIONS: list[tuple[str, str, tuple[str, ...]]] = [
    ("water", "Nearest water body", ("nearest mapped water",)),
    ("stream", "Nearest watercourse", ("nearest mapped stream",)),
    ("major_road", "Nearest major road", ("nearest mapped major road",)),
    ("rail", "Nearest rail station", ("nearest mapped rail station",)),
    ("hospital", "Nearest hospital", ("nearest mapped hospital",)),
    ("rainfall", "Mean annual rainfall", ("mean annual precipitation",)),
    ("extreme_rain", "Extreme rainfall days", ("peak recorded daily rainfall",)),
    ("terrain", "Elevation & local relief", ("site elevation",)),
    ("density", "Mapped feature density", ("features mapped near this point",)),
]


@dataclass
class Cell:
    """One site's value on one dimension, with its provenance attached."""

    site: str
    dimension: str
    value: str | None
    epistemic_type: str | None = None
    source: str | None = None
    limitation: str | None = None
    proxy_for: str | None = None
    statement_id: str | None = None

    @property
    def established(self) -> bool:
        return self.value is not None


@dataclass
class ComparisonRow:
    key: str
    label: str
    cells: list[Cell] = field(default_factory=list)

    @property
    def all_established(self) -> bool:
        return all(c.established for c in self.cells)

    @property
    def differentiating(self) -> bool:
        """True when the sites actually differ on this dimension.

        Surfaced because a row where every site reads the same is not a comparison — it is
        a dimension that cannot tell them apart, and saying so is more useful than showing
        three identical cells and letting the reader infer equivalence.
        """
        values = {c.value for c in self.cells if c.established}
        return len(values) > 1


@dataclass
class ComparisonResult:
    question: str
    sites: list[str]
    rows: list[ComparisonRow] = field(default_factory=list)
    findings: dict[str, Finding] = field(default_factory=dict)

    @property
    def coverage(self) -> dict[str, dict[str, int]]:
        """Per-site counts of what was actually established. Measured, not scored."""
        out: dict[str, dict[str, int]] = {}
        for site, finding in self.findings.items():
            counts = {t.value: 0 for t in EpistemicType}
            for statement in finding.statements:
                if not statement.rejected:
                    counts[statement.type.value] += 1
            out[site] = {
                **counts,
                "evidence_passages": len(finding.evidence),
                "conflicts": len(finding.conflict_list),
                "unreadable_pages": sum(u["page_count"] for u in finding.unreadable),
                "cells_established": sum(
                    1 for row in self.rows for c in row.cells if c.site == site and c.established
                ),
                "cells_total": len(self.rows),
            }
        return out

    @property
    def differentiating_rows(self) -> list[str]:
        return [r.label for r in self.rows if r.differentiating]

    @property
    def undifferentiating_rows(self) -> list[str]:
        return [r.label for r in self.rows if not r.differentiating and r.all_established]

    def critical_question(self) -> str:
        """The single thing that would most change a choice between these sites.

        Derived from the conflicts the analyses actually produced, not composed. If every
        site carries the same unresolvable conflict, that *is* the answer: open data cannot
        separate them, and the reader needs to go and get something else.
        """
        unresolvable = [
            c
            for finding in self.findings.values()
            for c in finding.conflict_list
            if c.resolvability.value == "unresolvable_with_open_data"
        ]
        if unresolvable and len(unresolvable) >= len(self.findings):
            first = unresolvable[0]
            return (
                f"Every site carries the same unresolved constraint — {first.title.lower()}. "
                f"Open data cannot separate them on it. "
                f"{first.what_would_resolve_it[0] if first.what_would_resolve_it else ''}"
            )
        if unresolvable:
            return (
                f"{len(unresolvable)} of these sites carry an unresolved regulatory "
                f"constraint that the others do not. That difference is the decision."
            )
        return (
            "No unresolvable regulatory conflict was detected for any of these sites on this "
            "question. That is not the same as none existing — it means none was found in "
            "the readable portion of the document."
        )


def _match_fact(finding: Finding, keywords: tuple[str, ...]) -> Any | None:
    for statement in finding.context:
        text = statement.text.lower()
        if any(k in text for k in keywords):
            return statement
    return None


async def compare_sites(
    orchestrator: Orchestrator, question: str, sites: list[str]
) -> ComparisonResult:
    """Run the same question against several sites and assemble the matrix."""
    findings = await asyncio.gather(
        *(orchestrator.run(question=question, location_query=site) for site in sites)
    )
    by_site = dict(zip(sites, findings))

    result = ComparisonResult(question=question, sites=sites, findings=by_site)

    for key, label, keywords in DIMENSIONS:
        row = ComparisonRow(key=key, label=label)
        for site in sites:
            finding = by_site[site]
            fact = _match_fact(finding, keywords)
            if fact is None:
                row.cells.append(
                    Cell(site=site, dimension=key, value=None, epistemic_type=None)
                )
                continue

            dataset = fact.source.dataset
            row.cells.append(
                Cell(
                    site=site,
                    dimension=key,
                    value=fact.text,
                    epistemic_type=fact.type.value,
                    source=dataset.provider if dataset else None,
                    limitation=dataset.limitation if dataset else None,
                    proxy_for=fact.proxy_for,
                    statement_id=fact.id,
                )
            )
        result.rows.append(row)

    return result


def serialise_comparison(result: ComparisonResult) -> dict[str, Any]:
    return {
        "question": result.question,
        "sites": result.sites,
        "rows": [
            {
                "key": row.key,
                "label": row.label,
                "differentiating": row.differentiating,
                "all_established": row.all_established,
                "cells": [
                    {
                        "site": c.site,
                        "value": c.value,
                        "established": c.established,
                        "epistemic_type": c.epistemic_type,
                        "source": c.source,
                        "limitation": c.limitation,
                        "proxy_for": c.proxy_for,
                    }
                    for c in row.cells
                ],
            }
            for row in result.rows
        ],
        "coverage": result.coverage,
        "differentiating": result.differentiating_rows,
        "undifferentiating": result.undifferentiating_rows,
        "critical_question": result.critical_question(),
        "conflicts_by_site": {
            site: [
                {
                    "title": c.title,
                    "resolvability": c.resolvability.value,
                    "severity": c.severity,
                }
                for c in finding.conflict_list
            ]
            for site, finding in result.findings.items()
        },
        # Deliberately absent: any overall score or ranking. See the module docstring.
        "no_score_reason": (
            "Basis does not score or rank sites. A single number requires weights that "
            "encode a development thesis nobody stated, and once a score exists nobody "
            "opens the evidence beneath it. Every cell below is evidence with its source."
        ),
    }
