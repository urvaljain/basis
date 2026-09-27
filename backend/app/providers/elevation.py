"""Terrain from SRTM 30 m via OpenTopoData.

SRTM is a 30 m posting from a radar mission. Two consequences shape how it is used here.

**It cannot resolve a plot.** Two points 490 m apart at the reference site returned 881 m and
880 m. That is genuine information about catchment position and it is useless for cut-and-fill
or for a plot's own grade.

**It is a surface model in places, not a ground model.** SRTM radar returns from tree canopy
and buildings, so in dense urban fabric the value can sit above true ground.

What it is legitimately good for is *relative* position: whether a site sits low in its
surroundings. That matters here, because the product's central regulatory constraint concerns
proximity to water bodies and valley systems, and a local depression is a weak corroborating
signal for catchment position.

Weak, and labelled weak. Sitting low is not a valley zone. The regulation defines valley
systems on the master plan drawings, which are the unreadable pages of the corpus. This
provider produces a hint that prompts verification — never a determination.
"""

from __future__ import annotations

import math
import statistics
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from app.providers.base import Provider, ProviderError


@dataclass
class TerrainSample:
    latitude: float
    longitude: float
    elevation_m: float
    bearing: str


@dataclass
class TerrainContext:
    """Site elevation and its immediate neighbourhood."""

    latitude: float
    longitude: float
    site_elevation_m: float
    samples: list[TerrainSample]
    radius_m: int

    @property
    def neighbourhood_elevations(self) -> list[float]:
        return [s.elevation_m for s in self.samples if s.bearing != "site"]

    @property
    def local_relief_m(self) -> float:
        all_values = [self.site_elevation_m, *self.neighbourhood_elevations]
        return round(max(all_values) - min(all_values), 1)

    @property
    def mean_neighbourhood_m(self) -> float:
        values = self.neighbourhood_elevations
        return round(statistics.mean(values), 1) if values else self.site_elevation_m

    @property
    def relative_position_m(self) -> float:
        """Negative when the site sits below its surroundings."""
        return round(self.site_elevation_m - self.mean_neighbourhood_m, 1)

    @property
    def sits_low(self) -> bool:
        """Whether the site is meaningfully below its neighbours.

        The 2 m threshold is set against SRTM's own vertical error, which is on the order of
        several metres. Anything smaller is noise, and reporting noise as a finding is how a
        system loses the right to be believed about the findings that matter.
        """
        return self.relative_position_m <= -2.0

    @property
    def position_description(self) -> str:
        if self.sits_low:
            return (
                f"The site sits {abs(self.relative_position_m)} m below the mean of sampled "
                f"points within {self.radius_m} m."
            )
        if self.relative_position_m >= 2.0:
            return (
                f"The site sits {self.relative_position_m} m above the mean of sampled "
                f"points within {self.radius_m} m."
            )
        return (
            f"The site is within 2 m of the mean of sampled points within "
            f"{self.radius_m} m — effectively level at this resolution."
        )


# Eight compass points plus the site. Enough to characterise local relief in one API call,
# which matters against a 1,000 calls/day budget.
_BEARINGS: tuple[tuple[str, float, float], ...] = (
    ("N", 1.0, 0.0),
    ("NE", 0.7, 0.7),
    ("E", 0.0, 1.0),
    ("SE", -0.7, 0.7),
    ("S", -1.0, 0.0),
    ("SW", -0.7, -0.7),
    ("W", 0.0, -1.0),
    ("NW", 0.7, -0.7),
)


class OpenTopoDataProvider(Provider[TerrainContext]):
    name = "opentopodata-srtm30m"
    licence = "Public domain — NASA/USGS SRTM"
    attribution = "SRTM 30m via OpenTopoData"
    endpoints = ("https://api.opentopodata.org/v1/srtm30m",)
    timeout_seconds = 30.0
    cache_ttl_seconds = 604_800  # terrain does not change

    def build_request(self, endpoint: str, **kwargs: Any) -> httpx.Request:
        lat, lon = kwargs["latitude"], kwargs["longitude"]
        radius_m = kwargs.get("radius_m", 400)
        d_lat = radius_m / 111_000
        d_lon = radius_m / (109_000 * max(0.1, abs(math.cos(math.radians(lat)))))

        points = [f"{lat},{lon}"]
        points += [
            f"{lat + ny * d_lat:.6f},{lon + ex * d_lon:.6f}" for _, ny, ex in _BEARINGS
        ]
        params = urllib.parse.urlencode({"locations": "|".join(points)})
        return httpx.Request("GET", f"{endpoint}?{params}")

    def parse(self, payload: Any, **kwargs: Any) -> TerrainContext:
        if not isinstance(payload, dict) or payload.get("status") != "OK":
            raise ProviderError(f"OpenTopoData returned status {payload!r:.80}")

        results = payload.get("results") or []
        if not results:
            raise ProviderError("no elevation data returned for this location")

        elevations = [r.get("elevation") for r in results]
        if elevations[0] is None:
            raise ProviderError("no elevation value at the site coordinate")

        labels = ["site", *(b[0] for b in _BEARINGS)]
        samples = [
            TerrainSample(
                latitude=r["location"]["lat"],
                longitude=r["location"]["lng"],
                elevation_m=float(r["elevation"]),
                bearing=label,
            )
            for r, label in zip(results, labels)
            if r.get("elevation") is not None
        ]

        return TerrainContext(
            latitude=kwargs["latitude"],
            longitude=kwargs["longitude"],
            site_elevation_m=float(elevations[0]),
            samples=samples,
            radius_m=kwargs.get("radius_m", 400),
        )

    def limitation_for(self, data: TerrainContext, **kwargs: Any) -> str:
        return (
            "SRTM 30 m postings with vertical error on the order of several metres. This "
            "cannot resolve plot-level grade and, in built-up areas, may reflect canopy or "
            "rooftops rather than ground. Useful only as relative catchment context: sitting "
            "low is not a valley zone, which RMP 2031 defines on master-plan drawings that "
            "are not machine-readable."
        )


async def fetch_terrain(
    latitude: float, longitude: float, *, radius_m: int = 400, use_cache: bool = True
):
    return await OpenTopoDataProvider().fetch(
        latitude=latitude, longitude=longitude, radius_m=radius_m, use_cache=use_cache
    )
