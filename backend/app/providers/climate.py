"""Historical climate from the Open-Meteo ERA5 archive.

ERA5 is reanalysis, not observation. It is a physically consistent model reconstruction on a
roughly 9 km grid, and it does not return data *for your point* — it returns data for the
grid cell containing it.

At the project's reference site that cell centre is **4.71 km away**, with a model elevation
of 875 m against a measured 881 m. For most purposes that is fine. For Bengaluru flooding,
which is intensely local and driven by catchment position and storm-water drains, a 4.71 km
offset can be the difference between a valley floor and a ridge.

So this provider computes the drift on every call and returns it as a first-class number. The
interface shows the grid point next to the site point. Presenting a 9 km-resolution figure as
a site measurement would be fabrication in everything but intent — the number is real, but
the thing it describes is not the thing the user asked about.
"""

from __future__ import annotations

import statistics
import urllib.parse
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.providers.base import Provider, ProviderError
from app.providers.osm import haversine_m


@dataclass
class ClimateSummary:
    """Multi-year climate context, with the model's own geometry exposed."""

    requested_latitude: float
    requested_longitude: float
    grid_latitude: float
    grid_longitude: float
    grid_drift_km: float
    model_elevation_m: float | None

    start_date: str
    end_date: str
    years_covered: int

    annual_precipitation_mm: dict[int, float]
    wettest_month_mm: float
    wettest_month_label: str | None
    max_daily_precipitation_mm: float
    max_daily_date: str | None
    days_over_50mm: int
    days_over_100mm: int

    @property
    def mean_annual_precipitation_mm(self) -> float:
        values = list(self.annual_precipitation_mm.values())
        return round(statistics.mean(values), 1) if values else 0.0

    @property
    def intensity_note(self) -> str:
        """Plain description of heavy-rain frequency.

        Deliberately descriptive, not predictive. This provider reports what the reanalysis
        recorded; it does not model flood risk, which depends on drainage, catchment and
        surface permeability that nothing here measures.
        """
        return (
            f"{self.days_over_50mm} day(s) above 50 mm and {self.days_over_100mm} above "
            f"100 mm across {self.years_covered} year(s). Peak recorded daily total: "
            f"{self.max_daily_precipitation_mm} mm"
            + (f" on {self.max_daily_date}." if self.max_daily_date else ".")
        )


class OpenMeteoArchive(Provider[ClimateSummary]):
    name = "open-meteo-era5"
    licence = "Free for non-commercial use; ERA5 © Copernicus Climate Change Service"
    attribution = "Open-Meteo / ECMWF ERA5"
    endpoints = ("https://archive-api.open-meteo.com/v1/archive",)
    timeout_seconds = 45.0
    cache_ttl_seconds = 86_400

    def build_request(self, endpoint: str, **kwargs: Any) -> httpx.Request:
        params = urllib.parse.urlencode(
            {
                "latitude": kwargs["latitude"],
                "longitude": kwargs["longitude"],
                "start_date": kwargs["start_date"],
                "end_date": kwargs["end_date"],
                "daily": "precipitation_sum",
                "timezone": "Asia/Kolkata",
            }
        )
        return httpx.Request("GET", f"{endpoint}?{params}")

    def parse(self, payload: Any, **kwargs: Any) -> ClimateSummary:
        if not isinstance(payload, dict) or "daily" not in payload:
            raise ProviderError("unexpected Open-Meteo response shape")

        daily = payload["daily"]
        dates: list[str] = daily.get("time", [])
        precip: list[float | None] = daily.get("precipitation_sum", [])
        if not dates:
            raise ProviderError("no climate data returned for this location and period")

        by_year: dict[int, float] = {}
        by_month: dict[str, float] = {}
        max_daily = 0.0
        max_daily_date: str | None = None
        over_50 = over_100 = 0

        for day, value in zip(dates, precip):
            if value is None:
                continue
            year = int(day[:4])
            month = day[:7]
            by_year[year] = round(by_year.get(year, 0.0) + value, 1)
            by_month[month] = round(by_month.get(month, 0.0) + value, 1)
            if value > max_daily:
                max_daily, max_daily_date = value, day
            if value >= 100:
                over_100 += 1
                over_50 += 1
            elif value >= 50:
                over_50 += 1

        wettest_label = max(by_month, key=lambda m: by_month[m]) if by_month else None

        lat, lon = kwargs["latitude"], kwargs["longitude"]
        grid_lat = float(payload.get("latitude", lat))
        grid_lon = float(payload.get("longitude", lon))

        return ClimateSummary(
            requested_latitude=lat,
            requested_longitude=lon,
            grid_latitude=grid_lat,
            grid_longitude=grid_lon,
            grid_drift_km=round(haversine_m(lat, lon, grid_lat, grid_lon) / 1000, 2),
            model_elevation_m=payload.get("elevation"),
            start_date=kwargs["start_date"],
            end_date=kwargs["end_date"],
            years_covered=len(by_year),
            annual_precipitation_mm=by_year,
            wettest_month_mm=by_month.get(wettest_label, 0.0) if wettest_label else 0.0,
            wettest_month_label=wettest_label,
            max_daily_precipitation_mm=round(max_daily, 1),
            max_daily_date=max_daily_date,
            days_over_50mm=over_50,
            days_over_100mm=over_100,
        )

    def limitation_for(self, data: ClimateSummary, **kwargs: Any) -> str:
        return (
            f"ERA5 reanalysis on a ~9 km grid. These values describe the grid cell centred "
            f"at {data.grid_latitude:.4f}, {data.grid_longitude:.4f} — "
            f"{data.grid_drift_km} km from the site — not the site itself. Reanalysis is a "
            f"model reconstruction, not a gauge reading. It describes rainfall only: it says "
            f"nothing about drainage, catchment position or flood risk, which this product "
            f"does not model."
        )


async def fetch_climate(
    latitude: float,
    longitude: float,
    *,
    start_date: str = "2019-01-01",
    end_date: str | None = None,
    use_cache: bool = True,
):
    end = end_date or date(date.today().year - 1, 12, 31).isoformat()
    return await OpenMeteoArchive().fetch(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end,
        use_cache=use_cache,
    )
