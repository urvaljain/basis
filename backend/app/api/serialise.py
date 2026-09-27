"""Convert domain objects into the wire format.

Kept separate from the agents so the domain model owes nothing to HTTP, and separate from
the schemas so the mapping rules live in one readable place.

The rule enforced throughout: a caveat is serialised *onto* the object it qualifies. There
is no path by which a value reaches the client without the reason it might be wrong.
"""

from __future__ import annotations

from typing import Any

from app.agents.orchestrator import Finding
from app.api.schemas import (
    AgentTraceOut,
    BlindSpotOut,
    ChangeMyMindOut,
    CitationOut,
    ConflictOut,
    CriticFindingOut,
    FindingOut,
    SitePanelOut,
    StatementOut,
)
from app.domain.epistemics import (
    AnyStatement,
    Assumption,
    Fact,
    Inference,
    Recommendation,
)

# Site panels, in the order they are shown. The last entry is the important one: a panel
# that exists precisely to say that nothing fills it.
PANEL_SPEC: list[tuple[str, str, tuple[str, ...]]] = [
    ("location", "Location & administrative context", ("resolves to",)),
    (
        "mobility",
        "Mobility & surrounding features",
        ("rail station", "bus stop", "major road", "features mapped"),
    ),
    ("water", "Water & watercourses", ("water", "stream")),
    ("amenities", "Amenities", ("hospital", "school", "park")),
    ("climate", "Climate observations", ("precipitation", "rainfall")),
    ("terrain", "Terrain", ("elevation", "relief")),
]


def citation_out(fact: Fact) -> CitationOut | None:
    doc = fact.source.document
    if doc is None:
        return None
    return CitationOut(
        document_id=doc.document_id,
        document_title=doc.document_title,
        page_number=doc.page_number,
        char_start=doc.char_start,
        char_end=doc.char_end,
        quote=doc.quote,
        is_verbatim=doc.is_verbatim,
        text_was_repaired=doc.text_was_repaired,
        raw_quote=doc.raw_quote,
        page_quality=doc.page_quality,
        caveat=doc.caveat,
        reference=doc.display_reference(),
    )


def statement_out(statement: AnyStatement) -> StatementOut:
    out = StatementOut(
        id=statement.id,
        type=statement.type.value,
        text=statement.text,
        agent=statement.agent,
        was_weakened=statement.was_weakened,
        rejected=statement.rejected,
        critic_notes=[
            {
                "action": n.action.value,
                "reason": n.reason,
                "from": n.from_value,
                "to": n.to_value,
            }
            for n in statement.critic_notes
        ],
    )

    if isinstance(statement, Fact):
        out.citation = citation_out(statement)
        out.proxy_for = statement.proxy_for
        if dataset := statement.source.dataset:
            out.dataset_provider = dataset.provider
            out.dataset_retrieved_at = dataset.retrieved_at.isoformat()
            # The limitation rides on the fact itself. It cannot be separated from the
            # number it qualifies by any client-side choice.
            out.dataset_limitation = dataset.limitation

    elif isinstance(statement, Inference):
        out.derived_from = statement.derived_from
        out.transformation = statement.transformation
        out.confidence = statement.confidence.value
        out.confidence_basis = statement.confidence_basis

    elif isinstance(statement, Assumption):
        out.falsified_by = statement.falsified_by
        out.why_needed = statement.why_needed
        out.demoted_from = statement.demoted_from.value if statement.demoted_from else None

    elif isinstance(statement, Recommendation):
        out.responds_to = statement.responds_to
        out.priority = statement.priority
        out.who = statement.who

    return out


def _panels(finding: Finding) -> list[SitePanelOut]:
    """Group measured facts into panels, with honest empty states."""
    facts = finding.context
    used: set[str] = set()
    panels: list[SitePanelOut] = []

    for key, title, keywords in PANEL_SPEC:
        matched = [
            f
            for f in facts
            if f.id not in used and any(k in f.text.lower() for k in keywords)
        ]
        used.update(f.id for f in matched)
        limitation = next(
            (f.source.dataset.limitation for f in matched if f.source.dataset), None
        )
        panels.append(
            SitePanelOut(
                key=key,
                title=title,
                available=bool(matched),
                facts=[statement_out(f) for f in matched],
                limitation=limitation,
                unavailable_reason=(
                    None
                    if matched
                    else "No source returned data for this at this location."
                ),
            )
        )

    # The constraints panel is always present and always empty. It is the most important
    # thing on the screen: it shows where the structured world stops and the document layer
    # has to begin, which is the argument the whole product rests on.
    panels.append(
        SitePanelOut(
            key="constraints",
            title="Zoning, FAR & statutory constraints",
            available=False,
            facts=[],
            unavailable_reason=(
                "No open, machine-readable source exists for zoning class, FAR, setbacks, "
                "valley-zone overlay, flood hazard or parcel geometry in this jurisdiction. "
                "These constraints are published as prose and drawings in the master plan — "
                "which is why they are answered from the document layer below, with the "
                "passage shown, rather than asserted here."
            ),
        )
    )
    return panels


def _map_features(finding: Finding) -> list[dict[str, Any]]:
    """Real OSM elements with resolvable ids.

    Every marker links back to openstreetmap.org. A feature nobody can look up is an
    assertion; one with a resolvable id is evidence, and the map is only worth having if it
    is the latter.
    """
    if not finding.site or not finding.site.osm:
        return []
    return [
        {
            "osm_type": f.osm_type,
            "osm_id": f.osm_id,
            "category": f.category,
            "label": f.label,
            "latitude": f.latitude,
            "longitude": f.longitude,
            "distance_m": f.distance_m,
            "osm_url": f.osm_url,
            "tags": {k: v for k, v in list(f.tags.items())[:8]},
        }
        for f in finding.site.osm.features
    ]


def finding_out(finding: Finding, *, page_image_base: str = "/api/corpus/page") -> FindingOut:
    site = finding.site
    regulation = finding.regulation

    unreadable = []
    for spot in regulation.blind_spots if regulation else []:
        unreadable.append(
            BlindSpotOut(
                page_start=spot.page_start,
                page_end=spot.page_end,
                page_count=spot.page_count,
                descriptor=spot.descriptor,
                following_context=spot.following_context,
                matched_terms=spot.matched_terms,
                page_image_urls=[
                    f"{page_image_base}/{p}/image"
                    for p in range(spot.page_start, min(spot.page_end, spot.page_start + 24) + 1)
                ],
            )
        )

    return FindingOut(
        id=finding.id,
        question=finding.question,
        location_query=finding.location_query,
        created_at=finding.created_at.isoformat(),
        mode=finding.mode.value,
        total_duration_ms=finding.total_duration_ms,
        resolved_name=site.resolved_name if site else None,
        latitude=site.latitude if site else None,
        longitude=site.longitude if site else None,
        needs_disambiguation=bool(site and site.needs_disambiguation),
        geocode_candidates=[
            {
                "display_name": c.display_name,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "place_type": c.place_type,
                "is_area_centroid": c.is_area_centroid,
                "extent_km": c.approximate_extent_km,
                "precision_note": c.precision_note,
            }
            for c in (site.geocode_candidates if site else [])
        ],
        context=[statement_out(s) for s in finding.context],
        evidence=[statement_out(s) for s in finding.evidence],
        conflicts=[
            ConflictOut(
                kind=c.kind.value,
                title=c.title,
                measured_side=c.measured_side,
                regulatory_side=c.regulatory_side,
                why_it_matters=c.why_it_matters,
                resolvability=c.resolvability.value,
                blocking_reasons=c.blocking_reasons,
                what_would_resolve_it=c.what_would_resolve_it,
                severity=c.severity,
                is_decisive=c.is_decisive,
            )
            for c in finding.conflict_list
        ],
        unreadable=unreadable,
        answer=finding.answer,
        change_my_mind=[ChangeMyMindOut(**c) for c in finding.change_my_mind],
        verify_next=[statement_out(s) for s in finding.verify_next],
        assumptions=[statement_out(s) for s in finding.assumptions],
        site_panels=_panels(finding),
        unavailable_sources=site.unavailable if site else [],
        traces=[
            AgentTraceOut(
                agent=t.agent,
                duration_ms=t.duration_ms,
                ok=t.ok,
                statements_produced=t.statements_produced,
                error=t.error,
                detail=t.detail,
            )
            for t in finding.traces
        ],
        critic_findings=[
            CriticFindingOut(
                statement_id=f.statement_id,
                action=f.action.value,
                reason=f.reason,
                check=f.check,
            )
            for f in (finding.critic.findings if finding.critic else [])
        ],
        critic_checks_run=finding.critic.checks_run if finding.critic else [],
        coverage=finding.coverage,
        map_features=_map_features(finding),
    )
