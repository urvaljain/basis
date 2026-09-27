"""Capture real provider responses for Demo Mode and offline evaluation.

Run when the upstream services are healthy::

    python -m app.eval.capture_fixtures

Every fixture is a **verbatim recording** of a live response, written only by this script,
with the capture timestamp stored alongside it. Nothing here authors or edits a payload. That
constraint is what lets Demo Mode claim, truthfully, that every value on screen came from a
real call to a real service — it is simply being replayed rather than re-made.

The need is not theoretical. During development all three public Overpass mirrors returned
504 or timed out simultaneously, for an extended period. A demo that depends on them being up
at the moment someone is watching is a demo that will fail.

``--verify`` re-parses every stored fixture through its provider's own parser, which catches
a recording that has drifted out of shape before an audience does.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

from app.providers import disk_cache
from app.providers.climate import OpenMeteoArchive, fetch_climate
from app.providers.elevation import OpenTopoDataProvider, fetch_terrain
from app.providers.geocode import NominatimGeocoder, geocode
from app.providers.osm import OverpassProvider, fetch_osm_context


@dataclass
class DemoSite:
    """A location the demo and the evaluation set rely on."""

    label: str
    query: str
    latitude: float
    longitude: float


# Bellandur is the primary demo site: a lake catchment on a dense tech corridor, where
# excellent measured accessibility sits beside a regulation that may prohibit building
# outright. The comparators exist so the comparison view has real, contrasting data.
DEMO_SITES = [
    DemoSite("Bellandur", "Bellandur, Bengaluru", 12.9320495, 77.6842915),
    DemoSite("Whitefield", "Whitefield, Bengaluru", 12.9698, 77.7500),
    DemoSite("Jayanagar", "Jayanagar, Bengaluru", 12.9250, 77.5938),
]


async def capture_all(sites: list[DemoSite]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {"ok": [], "failed": []}

    for site in sites:
        print(f"\n--- {site.label} ---")

        geo = await geocode(site.query, use_cache=False)
        _record(results, f"geocode:{site.label}", geo.ok, geo)

        lat = geo.data.best.latitude if geo.ok and geo.data else site.latitude
        lon = geo.data.best.longitude if geo.ok and geo.data else site.longitude

        terrain, climate, osm = await asyncio.gather(
            fetch_terrain(lat, lon, use_cache=False),
            fetch_climate(lat, lon, start_date="2020-01-01", use_cache=False),
            fetch_osm_context(lat, lon, use_cache=False),
        )
        _record(results, f"terrain:{site.label}", terrain.ok, terrain)
        _record(results, f"climate:{site.label}", climate.ok, climate)
        _record(results, f"osm:{site.label}", osm.ok, osm)

    return results


def _record(results: dict[str, list[str]], label: str, ok: bool, result) -> None:
    if ok:
        note = " (served from an existing recording)" if result.cached else ""
        print(f"  ✓ {label}{note}")
        results["ok"].append(label)
    else:
        print(f"  ✗ {label}: {result.error}")
        results["failed"].append(label)


def verify() -> int:
    """Re-parse every stored fixture through its provider's parser."""
    parsers = {
        "nominatim": NominatimGeocoder().parse,
        "overpass": OverpassProvider().parse,
        "open-meteo-era5": OpenMeteoArchive().parse,
        "opentopodata-srtm30m": OpenTopoDataProvider().parse,
    }
    problems = disk_cache.verify_fixtures(parsers)
    info = disk_cache.summary()

    print(f"{info['count']} fixture(s) from {len(info['providers'])} provider(s)")
    for provider in info["providers"]:
        print(f"  - {provider}")
    if info["count"]:
        print(f"  oldest: {info['oldest_days']} days | newest: {info['newest_days']} days")
        if info["any_stale"]:
            print("  ⚠ some fixtures are stale — re-capture before demonstrating")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  ✗ {p}")
        return 1

    print("\nAll fixtures parse correctly.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="check stored fixtures only")
    parser.add_argument("--site", help="capture a single site by label")
    args = parser.parse_args()

    if args.verify:
        return verify()

    sites = DEMO_SITES
    if args.site:
        sites = [s for s in DEMO_SITES if s.label.lower() == args.site.lower()]
        if not sites:
            print(f"unknown site {args.site!r}")
            return 1

    results = asyncio.run(capture_all(sites))
    print(f"\ncaptured {len(results['ok'])} | failed {len(results['failed'])}")
    if results["failed"]:
        print("failed:", ", ".join(results["failed"]))
        print("Re-run when the upstream services recover; existing fixtures are unaffected.")
    print(f"\nfixtures on disk: {disk_cache.summary()['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
