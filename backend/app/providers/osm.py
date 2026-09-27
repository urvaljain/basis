"""Spatial features from OpenStreetMap via Overpass.

## The honesty problem specific to OSM

OSM is crowd-sourced, so absence of evidence is not evidence of absence. "No hospital within
2 km" and "nobody has mapped a hospital within 2 km" are different statements with the same
query result, and only one of them is safe to act on.

Every count this provider returns is therefore phrased as *what was found*, never *what
exists*, and the limitation says so. This is not pedantry: in an Indian context OSM coverage
of formal infrastructure (metro, arterial roads, lakes) is good, while coverage of civic
amenities is patchy and varies street by street.

## Water features carry extra weight here

The product's central regulatory constraint — RMP 2031 §6.5.3's 75 m no-development buffer
around water bodies, and 50/35/25 m on streams — is triggered by proximity to water. So water
features are queried at a wider radius than everything else and distances are reported
precisely, because a measured distance to a *mapped* lake edge is the closest open data gets
to answering a question the regulation makes decisive.

It is still not an answer. The regulation measures from the lake boundary "as per revenue
records", which are not open data, and OSM's polygon is a contributor's tracing. The provider
returns the measurement and states plainly that it is not the regulatory boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.providers.base import Provider, ProviderError

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass
class OSMFeature:
    """One mapped feature, with a resolvable identity.

    ``osm_type``/``osm_id`` matter: they let the UI link to openstreetmap.org so a user can
    inspect the raw element, who contributed it and when. A feature nobody can look up is an
    assertion; one with a resolvable id is evidence.
    """

    osm_type: str
    osm_id: int
    category: str
    name: str | None
    latitude: float
    longitude: float
    distance_m: float
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def osm_url(self) -> str:
        return f"https://www.openstreetmap.org/{self.osm_type}/{self.osm_id}"

    @property
    def label(self) -> str:
        return self.name or f"unnamed {self.category.replace('_', ' ')}"


@dataclass
class OSMContext:
    """Everything found around a site, grouped by category."""

    latitude: float
    longitude: float
    features: list[OSMFeature]
    categories_queried: list[str]
    osm_base_timestamp: str | None = None

    def by_category(self, category: str) -> list[OSMFeature]:
        return sorted(
            (f for f in self.features if f.category == category),
            key=lambda f: f.distance_m,
        )

    def nearest(self, category: str) -> OSMFeature | None:
        found = self.by_category(category)
        return found[0] if found else None

    def count(self, category: str) -> int:
        return sum(1 for f in self.features if f.category == category)

    @property
    def nearest_water(self) -> OSMFeature | None:
        return self.nearest("water")

    @property
    def category_summary(self) -> dict[str, int]:
        return {c: self.count(c) for c in self.categories_queried}


# category -> (Overpass element filters, search radius in metres)
# Radii are chosen per category from what the decision needs, not one global number:
# a bus stop 2 km away is irrelevant, a lake 2 km away may still be decisive.
QUERY_PLAN: dict[str, tuple[tuple[str, ...], int]] = {
    "rail_station": (
        ('node["railway"="station"]', 'node["railway"="halt"]', 'node["station"="subway"]'),
        3000,
    ),
    "bus_stop": (('node["highway"="bus_stop"]',), 1000),
    # Exact-match clauses rather than one regex. Overpass optimises `["highway"="primary"]`
    # far better than a regex evaluated against every way in the radius, and the regex form
    # was a likely contributor to the repeated 504s seen on this dense urban area.
    "major_road": (
        (
            'way["highway"="motorway"]',
            'way["highway"="trunk"]',
            'way["highway"="primary"]',
        ),
        1000,
    ),
    # 1200 m is ample: the widest regulatory buffer in the corpus is 75 m, so a water body
    # beyond this cannot bear on buffer applicability and only costs query time.
    "water": (('way["natural"="water"]', 'relation["natural"="water"]'), 1200),
    "stream": (
        (
            'way["waterway"="stream"]',
            'way["waterway"="drain"]',
            'way["waterway"="river"]',
        ),
        1200,
    ),
    "hospital": (('node["amenity"="hospital"]', 'way["amenity"="hospital"]'), 3000),
    "school": (('node["amenity"="school"]', 'way["amenity"="school"]'), 2000),
    "park": (('way["leisure"="park"]', 'node["leisure"="park"]'), 1500),
}


class OverpassProvider(Provider[OSMContext]):
    name = "overpass"
    licence = "ODbL 1.0 — © OpenStreetMap contributors"
    attribution = "© OpenStreetMap contributors"

    # Public instances return 504 under load; observed during Phase 0 probing.
    endpoints = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )
    # Fail fast. Three mirrors at 90s each meant a total outage cost up to 270s before the
    # product could degrade; at 25s it degrades in under a minute and the user sees a
    # designed empty state (or a labelled recording) instead of a hang.
    timeout_seconds = 25.0
    cache_ttl_seconds = 3600

    # Overpass allocates a small number of concurrent slots per client IP. Repeated
    # full-pipeline runs during development exhausted them, and the service then answers
    # with an HTML "too many requests" page rather than an error status — which looked like
    # an outage and was actually self-inflicted. Throttling is politeness *and* correctness.
    min_request_interval_seconds = 3.0
    retry_backoff_seconds = 4.0
    max_attempts_per_endpoint = 2

    def build_request(self, endpoint: str, **kwargs: Any) -> httpx.Request:
        lat, lon = kwargs["latitude"], kwargs["longitude"]
        categories = kwargs.get("categories") or list(QUERY_PLAN)

        clauses = []
        for category in categories:
            filters, radius = QUERY_PLAN[category]
            for f in filters:
                clauses.append(f"{f}(around:{radius},{lat},{lon});")

        # `out center` gives ways and relations a representative point without downloading
        # full geometry — enough to measure distance, far cheaper on a public instance.
        query = f"[out:json][timeout:20];({''.join(clauses)});out center tags;"
        return httpx.Request("POST", endpoint, data={"data": query})

    def parse(self, payload: Any, **kwargs: Any) -> OSMContext:
        if not isinstance(payload, dict) or "elements" not in payload:
            raise ProviderError("unexpected Overpass response shape")

        lat, lon = kwargs["latitude"], kwargs["longitude"]
        categories = kwargs.get("categories") or list(QUERY_PLAN)
        features: list[OSMFeature] = []

        for element in payload["elements"]:
            tags = element.get("tags", {}) or {}
            centre = element.get("center") or {}
            e_lat = element.get("lat", centre.get("lat"))
            e_lon = element.get("lon", centre.get("lon"))
            if e_lat is None or e_lon is None:
                continue

            category = self._categorise(tags)
            if category is None or category not in categories:
                continue

            features.append(
                OSMFeature(
                    osm_type=element.get("type", "node"),
                    osm_id=int(element.get("id", 0)),
                    category=category,
                    name=tags.get("name"),
                    latitude=float(e_lat),
                    longitude=float(e_lon),
                    distance_m=round(haversine_m(lat, lon, float(e_lat), float(e_lon)), 1),
                    tags=tags,
                )
            )

        return OSMContext(
            latitude=lat,
            longitude=lon,
            features=sorted(features, key=lambda f: f.distance_m),
            categories_queried=list(categories),
            osm_base_timestamp=(payload.get("osm3s") or {}).get("timestamp_osm_base"),
        )

    @staticmethod
    def _categorise(tags: dict[str, str]) -> str | None:
        if tags.get("railway") in {"station", "halt"} or tags.get("station") == "subway":
            return "rail_station"
        if tags.get("highway") == "bus_stop":
            return "bus_stop"
        if tags.get("highway") in {"motorway", "trunk", "primary", "secondary"}:
            return "major_road"
        if tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
            return "water"
        if tags.get("waterway") in {"stream", "drain", "river", "canal"}:
            return "stream"
        if tags.get("amenity") == "hospital":
            return "hospital"
        if tags.get("amenity") == "school":
            return "school"
        if tags.get("leisure") == "park":
            return "park"
        return None

    def limitation_for(self, data: OSMContext, **kwargs: Any) -> str:
        return (
            "OpenStreetMap is crowd-sourced. These counts are what has been *mapped* near "
            "this point, not what exists — absence here is not evidence of absence, and "
            "coverage varies street by street. Distances are straight-line from the site "
            "coordinate to a feature's representative point, not travel distance or the "
            "nearest edge. Where a water body is involved, this is a contributor's tracing "
            "and is not the regulatory boundary, which RMP 2031 defines from revenue records."
        )


async def fetch_osm_context(
    latitude: float,
    longitude: float,
    *,
    categories: list[str] | None = None,
    use_cache: bool = True,
):
    return await OverpassProvider().fetch(
        latitude=latitude, longitude=longitude, categories=categories, use_cache=use_cache
    )
