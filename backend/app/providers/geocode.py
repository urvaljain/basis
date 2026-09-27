"""Geocoding via Nominatim.

Geocoding is the quietest failure point in the entire product. Every measurement downstream
— distance to transit, rainfall, elevation, whether a plot sits in a lake buffer — is
computed from a coordinate pair. If that pair is wrong, the whole analysis is confidently
wrong about a different place, and nothing later in the pipeline can detect it.

So this provider does two unusual things.

**It returns candidates, not an answer.** ``"Bellandur"`` in Bengaluru matches a suburb, a
lake and a ward. Silently taking the top-ranked hit is how a system ends up analysing a
neighbourhood centroid while the user believes it analysed their site. The disambiguation is
handed to the user.

**It states what kind of place it found.** A suburb centroid is not a plot. Nominatim returns
an ``addresstype``, and the product surfaces the difference, because "12.9320, 77.6843" looks
equally precise whether it denotes a 4 km² suburb or a specific building.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from app.providers.base import Provider, ProviderError

# Nominatim place types that denote an area rather than a point. A coordinate derived from
# one of these is a centroid, and any plot-level claim built on it is unsound.
_AREA_TYPES = frozenset(
    {
        "suburb",
        "neighbourhood",
        "quarter",
        "city",
        "town",
        "village",
        "state",
        "county",
        "administrative",
        "postcode",
        "residential",
        "city_district",
    }
)


@dataclass
class GeocodeCandidate:
    """One possible interpretation of a location query."""

    latitude: float
    longitude: float
    display_name: str
    place_type: str
    osm_type: str | None = None
    osm_id: int | None = None
    importance: float = 0.0
    bounding_box: tuple[float, float, float, float] | None = None
    address: dict[str, str] | None = None

    @property
    def is_area_centroid(self) -> bool:
        """True when the coordinate is the middle of an area, not a specific place."""
        return self.place_type in _AREA_TYPES

    @property
    def approximate_extent_km(self) -> float | None:
        """Rough diagonal of the bounding box — how big the 'place' actually is."""
        if not self.bounding_box:
            return None
        south, north, west, east = self.bounding_box
        return round((((north - south) * 111) ** 2 + ((east - west) * 109) ** 2) ** 0.5, 2)

    @property
    def precision_note(self) -> str:
        if self.is_area_centroid:
            extent = self.approximate_extent_km
            span = f" spanning roughly {extent} km" if extent else ""
            return (
                f"This is the centroid of a {self.place_type}{span}, not a specific plot. "
                f"Measurements are for the centroid and may not describe a site within it."
            )
        return f"Resolved to a {self.place_type}."


@dataclass
class GeocodeResult:
    query: str
    candidates: list[GeocodeCandidate]

    @property
    def best(self) -> GeocodeCandidate:
        return self.candidates[0]

    @property
    def is_ambiguous(self) -> bool:
        """True when more than one candidate is plausibly what the user meant.

        Importance alone is a weak signal, so distance is used as well: two results 30 km
        apart are genuinely different places whatever their ranking, and the user should
        choose rather than have the system guess.
        """
        if len(self.candidates) < 2:
            return False
        first, second = self.candidates[0], self.candidates[1]
        km_apart = (
            ((first.latitude - second.latitude) * 111) ** 2
            + ((first.longitude - second.longitude) * 109) ** 2
        ) ** 0.5
        return km_apart > 2.0 or abs(first.importance - second.importance) < 0.05


class NominatimGeocoder(Provider[GeocodeResult]):
    name = "nominatim"
    licence = "ODbL 1.0 — © OpenStreetMap contributors"
    attribution = "© OpenStreetMap contributors"
    endpoints = ("https://nominatim.openstreetmap.org/search",)
    timeout_seconds = 25.0
    cache_ttl_seconds = 86_400  # place names are stable
    min_request_interval_seconds = 1.1  # Nominatim usage policy: max 1 request/second

    def build_request(self, endpoint: str, **kwargs: Any) -> httpx.Request:
        params = urllib.parse.urlencode(
            {
                "q": kwargs["query"],
                "format": "json",
                "limit": kwargs.get("limit", 5),
                "addressdetails": 1,
            }
        )
        return httpx.Request("GET", f"{endpoint}?{params}")

    def parse(self, payload: Any, **kwargs: Any) -> GeocodeResult:
        if not isinstance(payload, list) or not payload:
            raise ProviderError(f"no location matched {kwargs['query']!r}")

        candidates = []
        for hit in payload:
            bbox = None
            if raw := hit.get("boundingbox"):
                try:
                    south, north, west, east = (float(v) for v in raw)
                    bbox = (south, north, west, east)
                except (ValueError, TypeError):
                    bbox = None

            candidates.append(
                GeocodeCandidate(
                    latitude=float(hit["lat"]),
                    longitude=float(hit["lon"]),
                    display_name=hit.get("display_name", ""),
                    place_type=hit.get("addresstype") or hit.get("type") or "unknown",
                    osm_type=hit.get("osm_type"),
                    osm_id=hit.get("osm_id"),
                    importance=float(hit.get("importance", 0.0)),
                    bounding_box=bbox,
                    address=hit.get("address"),
                )
            )
        return GeocodeResult(query=kwargs["query"], candidates=candidates)

    def limitation_for(self, data: GeocodeResult, **kwargs: Any) -> str:
        parts = [data.best.precision_note]
        if data.is_ambiguous:
            parts.append(
                f"{len(data.candidates)} locations matched this query and they are not "
                f"equivalent — confirm which one you mean before relying on any measurement."
            )
        parts.append("Geocoding is derived from OpenStreetMap and may be imprecise or stale.")
        return " ".join(parts)


async def geocode(query: str, *, limit: int = 5, use_cache: bool = True):
    return await NominatimGeocoder().fetch(query=query, limit=limit, use_cache=use_cache)
