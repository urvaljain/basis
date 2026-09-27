"""Site Agent — turns provider measurements into typed, sourced facts.

The judgement this agent makes is not "what is measurable here" but **"which measurements
bear on the question, and what is each one actually a proxy for."**

That second half is the whole job. *Distance to the nearest railway station is 2,579 m* is a
fact. *The site is well connected* is not — it is an interpretation, and a contestable one,
since 2.5 km of straight-line distance says nothing about whether a pedestrian can cross the
Outer Ring Road. The agent therefore emits the measurement as a :class:`Fact` with
``proxy_for`` naming the leap, and any interpretation separately as an :class:`Inference`
that has to declare what it derives from and why its confidence band is what it is.

Interfaces blur this constantly: a dashboard tile reading "Accessibility: High" over a
distance figure has quietly promoted a measurement into a judgement without anyone deciding
to. Keeping them as separate objects makes that promotion impossible to do by accident.

No LLM is involved. This agent is arithmetic and typing — deterministic, reproducible, and
identical in extractive and generative mode.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.domain.epistemics import (
    AnyStatement,
    Assumption,
    Confidence,
    DatasetLocator,
    Fact,
    Inference,
    Source,
    SourceKind,
)
from app.providers.base import ProviderResult
from app.providers.climate import ClimateSummary, fetch_climate
from app.providers.elevation import TerrainContext, fetch_terrain
from app.providers.geocode import GeocodeCandidate, GeocodeResult, geocode
from app.providers.osm import OSMContext, fetch_osm_context

AGENT = "site"


@dataclass
class SiteReading:
    """Everything the site layer established, plus what it could not."""

    query: str
    latitude: float | None
    longitude: float | None
    resolved_name: str | None

    facts: list[Fact] = field(default_factory=list)
    inferences: list[Inference] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)

    unavailable: list[str] = field(default_factory=list)
    """Human-readable notes for every source that failed or does not exist."""

    geocode_candidates: list[GeocodeCandidate] = field(default_factory=list)
    osm: OSMContext | None = None
    climate: ClimateSummary | None = None
    terrain: TerrainContext | None = None

    @property
    def statements(self) -> list[AnyStatement]:
        return [*self.facts, *self.inferences, *self.assumptions]

    @property
    def resolved(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def needs_disambiguation(self) -> bool:
        return len(self.geocode_candidates) > 1


def _dataset_source(result: ProviderResult, endpoint_note: str | None = None) -> Source:
    """Build an epistemic Source that carries the provider's limitation forward.

    This is the join between the provider layer and the epistemic layer, and the single
    place where a caveat could be dropped. It is not dropped: ``limitation`` is copied onto
    the locator, and the UI renders it beside the value.
    """
    return Source(
        kind=SourceKind.DATASET,
        dataset=DatasetLocator(
            provider=result.provider,
            endpoint=endpoint_note or result.endpoint,
            retrieved_at=result.retrieved_at,
            query=result.query,
            licence=result.licence,
            limitation=result.limitation,
        ),
    )


class SiteAgent:
    """Measured geography, typed honestly."""

    async def run(
        self,
        location_query: str,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        use_cache: bool = True,
    ) -> SiteReading:
        reading = SiteReading(
            query=location_query, latitude=latitude, longitude=longitude, resolved_name=None
        )

        # --- resolve location -------------------------------------------------------
        if latitude is None or longitude is None:
            geo = await geocode(location_query, use_cache=use_cache)
            if not geo.ok or geo.data is None:
                reading.unavailable.append(geo.unavailable_message())
                return reading
            self._record_location(reading, geo)
        else:
            reading.resolved_name = location_query

        assert reading.latitude is not None and reading.longitude is not None
        lat, lon = reading.latitude, reading.longitude

        # --- gather context in parallel --------------------------------------------
        osm_result, climate_result, terrain_result = await asyncio.gather(
            fetch_osm_context(lat, lon, use_cache=use_cache),
            fetch_climate(lat, lon, start_date="2020-01-01", use_cache=use_cache),
            fetch_terrain(lat, lon, use_cache=use_cache),
        )

        self._record_osm(reading, osm_result)
        self._record_climate(reading, climate_result)
        self._record_terrain(reading, terrain_result)
        self._record_structural_absences(reading)

        return reading

    # ------------------------------------------------------------------ location

    def _record_location(self, reading: SiteReading, result: ProviderResult[GeocodeResult]) -> None:
        data = result.data
        assert data is not None
        best = data.best

        reading.latitude = best.latitude
        reading.longitude = best.longitude
        reading.resolved_name = best.display_name
        reading.geocode_candidates = data.candidates if data.is_ambiguous else [best]

        source = _dataset_source(result)
        reading.facts.append(
            Fact(
                text=(
                    f"“{reading.query}” resolves to {best.latitude:.6f}, {best.longitude:.6f} "
                    f"— {best.display_name}."
                ),
                source=source,
                agent=AGENT,
                proxy_for="the location of the site under consideration" if best.is_area_centroid else None,
            )
        )

        # An area centroid is an assumption about the user's intent, not a measurement.
        # Everything downstream inherits it, so it is stated once, explicitly, up front.
        if best.is_area_centroid:
            extent = best.approximate_extent_km
            reading.assumptions.append(
                Assumption(
                    text=(
                        f"All measurements below describe the centroid of {best.place_type} "
                        f"“{best.display_name.split(',')[0]}”"
                        + (f", an area spanning roughly {extent} km" if extent else "")
                        + ", not a specific plot."
                    ),
                    falsified_by=(
                        "Supplying the plot's own coordinates, survey number or boundary. "
                        "Any measurement here may differ materially across the area."
                    ),
                    why_needed="No plot-level geometry was provided and none is available as open data.",
                    agent=AGENT,
                )
            )

        if data.is_ambiguous:
            names = "; ".join(c.display_name.split(",")[0] for c in data.candidates[:4])
            reading.assumptions.append(
                Assumption(
                    text=(
                        f"“{reading.query}” matched {len(data.candidates)} distinct locations "
                        f"({names}). The highest-ranked was used."
                    ),
                    falsified_by="Selecting the intended location explicitly.",
                    why_needed="Geocoding was ambiguous and the system did not guess silently.",
                    agent=AGENT,
                )
            )

    # ----------------------------------------------------------------------- OSM

    def _record_osm(self, reading: SiteReading, result: ProviderResult[OSMContext]) -> None:
        if not result.ok or result.data is None:
            reading.unavailable.append(result.unavailable_message())
            return

        osm = result.data
        reading.osm = osm
        source = _dataset_source(result)

        # Each nearest-feature distance is a measurement. The thing it is usually taken to
        # mean is named in proxy_for rather than asserted.
        proxies = {
            "rail_station": "public transport accessibility",
            "major_road": "road connectivity",
            "hospital": "access to emergency healthcare",
            "school": "neighbourhood amenity",
            "water": "proximity to a regulated water body",
            "stream": "proximity to a regulated watercourse",
            "park": "access to open space",
        }

        for category, proxy in proxies.items():
            nearest = osm.nearest(category)
            if nearest is None:
                # Absence in a crowd-sourced dataset is not absence on the ground.
                reading.assumptions.append(
                    Assumption(
                        text=(
                            f"No {category.replace('_', ' ')} is mapped within the search "
                            f"radius. This is not evidence that none exists."
                        ),
                        falsified_by=(
                            "A site visit, a local authority dataset, or an OpenStreetMap "
                            "contribution covering this area."
                        ),
                        why_needed="OpenStreetMap coverage varies by area and contributor activity.",
                        agent=AGENT,
                    )
                )
                continue

            reading.facts.append(
                Fact(
                    text=(
                        f"Nearest mapped {category.replace('_', ' ')}: {nearest.label} at "
                        f"{nearest.distance_m:.0f} m (straight-line)."
                    ),
                    source=source,
                    agent=AGENT,
                    proxy_for=proxy,
                )
            )

        counts = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in osm.category_summary.items())
        reading.facts.append(
            Fact(
                text=f"{len(osm.features)} features mapped near this point: {counts}.",
                source=source,
                agent=AGENT,
                proxy_for="density and maturity of surrounding development",
            )
        )

    # ------------------------------------------------------------------- climate

    def _record_climate(self, reading: SiteReading, result: ProviderResult[ClimateSummary]) -> None:
        if not result.ok or result.data is None:
            reading.unavailable.append(result.unavailable_message())
            return

        climate = result.data
        reading.climate = climate
        source = _dataset_source(result)

        reading.facts.append(
            Fact(
                text=(
                    f"Mean annual precipitation {climate.mean_annual_precipitation_mm} mm "
                    f"across {climate.years_covered} years "
                    f"({climate.start_date} to {climate.end_date})."
                ),
                source=source,
                agent=AGENT,
                proxy_for="rainfall exposure at the site",
            )
        )
        reading.facts.append(
            Fact(
                text=(
                    f"Peak recorded daily rainfall {climate.max_daily_precipitation_mm} mm"
                    + (f" on {climate.max_daily_date}" if climate.max_daily_date else "")
                    + f"; {climate.days_over_50mm} day(s) above 50 mm in the period."
                ),
                source=source,
                agent=AGENT,
                proxy_for="intensity of extreme rainfall events",
            )
        )

        # The grid drift is material enough to be its own statement, not a footnote.
        reading.assumptions.append(
            Assumption(
                text=(
                    f"Climate values describe an ERA5 grid cell {climate.grid_drift_km} km "
                    f"from the site, not the site itself."
                ),
                falsified_by=(
                    "A local rain gauge record, or any station observation within ~1 km."
                ),
                why_needed="ERA5 reanalysis resolves to roughly 9 km; no finer open source was found.",
                agent=AGENT,
            )
        )

    # ------------------------------------------------------------------- terrain

    def _record_terrain(self, reading: SiteReading, result: ProviderResult[TerrainContext]) -> None:
        if not result.ok or result.data is None:
            reading.unavailable.append(result.unavailable_message())
            return

        terrain = result.data
        reading.terrain = terrain
        source = _dataset_source(result)

        reading.facts.append(
            Fact(
                text=(
                    f"Site elevation {terrain.site_elevation_m} m; local relief "
                    f"{terrain.local_relief_m} m across sampled points within "
                    f"{terrain.radius_m} m."
                ),
                source=source,
                agent=AGENT,
                proxy_for="position within the local catchment",
            )
        )

        # Report the relative position either way. A product that only speaks up when the
        # signal supports a concern is not measuring — it is arguing.
        reading.inferences.append(
            Inference(
                text=terrain.position_description,
                derived_from=[reading.facts[-1].id],
                transformation=(
                    "Site elevation compared against the mean of eight SRTM samples at "
                    f"{terrain.radius_m} m on the compass points."
                ),
                confidence=Confidence.LOW,
                confidence_basis=(
                    "SRTM vertical error is several metres and 30 m postings cannot resolve "
                    "plot-level grade. Indicative of catchment position only."
                ),
                agent=AGENT,
            )
        )

    # -------------------------------------------------- what does not exist at all

    def _record_structural_absences(self, reading: SiteReading) -> None:
        """Record the sources that do not exist, as distinct from sources that failed.

        This is the site layer's most important output and the reason the product has a
        document layer at all. A failed request might succeed on retry; an absent dataset
        will not, and the user needs to know which kind of gap they are looking at.
        """
        reading.unavailable.extend(
            [
                "Zoning / land-use class: no machine-readable source for this jurisdiction. "
                "Published as maps and prose in the master plan — see the document layer.",
                "FAR, setbacks and ground coverage: published as dimensional matrices inside "
                "the master plan PDF, not as an API.",
                "Valley-zone and eco-sensitive overlay: marked on master-plan drawings, which "
                "are not machine-readable.",
                "Official flood hazard layer: none found as open data for this jurisdiction.",
                "Parcel geometry and ownership: not open data; held in revenue records.",
            ]
        )
