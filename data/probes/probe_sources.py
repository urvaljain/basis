"""Reproduce the Phase 0 data-source probes.

Every feasibility claim in docs/research.md section 5 comes from this script.
Run it to re-verify; sources change and the research doc should be falsifiable.

    python data/probes/probe_sources.py

Writes results to data/probes/results-<date>.json and prints a summary table.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Callable

# Nominatim and Overpass both require a real User-Agent. Overpass returns HTTP 406
# without one, which cost me twenty minutes of confusion in Phase 0.
UA = "basis-research/0.1 (+https://github.com/urvaljain; urvaljain@gmail.com)"

# Bellandur, Bengaluru — the Phase 0 reference site.
LAT, LON = 12.9320495, 77.6842915


def _get(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _post(url: str, data: dict[str, str], timeout: int = 90) -> str:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def probe_nominatim() -> dict[str, Any]:
    q = urllib.parse.urlencode(
        {"q": "Bellandur, Bengaluru", "format": "json", "limit": 1, "addressdetails": 1}
    )
    hits = json.loads(_get(f"https://nominatim.openstreetmap.org/search?{q}"))
    if not hits:
        return {"ok": False, "note": "no geocoding result"}
    h = hits[0]
    return {
        "ok": True,
        "lat": float(h["lat"]),
        "lon": float(h["lon"]),
        "display_name": h["display_name"],
        "bbox": h.get("boundingbox"),
        "licence": h.get("licence"),
        "note": "ODbL. 1 req/s. User-Agent required.",
    }


# The public Overpass instances routinely return 504 under load — the first run of this
# script hit one. Any production client needs mirrors and retries, so the probe models
# that rather than pretending a single endpoint is reliable.
OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)


def probe_overpass() -> dict[str, Any]:
    # Counts only — the real client fetches geometry. Keep the probe cheap.
    query = f"""[out:json][timeout:60];
    (
      node["railway"="station"](around:2000,{LAT},{LON});
      node["public_transport"="station"](around:2000,{LAT},{LON});
      node["highway"="bus_stop"](around:800,{LAT},{LON});
      way["highway"~"^(motorway|trunk|primary)$"](around:1000,{LAT},{LON});
      node["amenity"="hospital"](around:2000,{LAT},{LON});
      way["natural"="water"](around:2000,{LAT},{LON});
    );
    out count;"""

    attempts: list[str] = []
    for mirror in OVERPASS_MIRRORS:
        for attempt in range(2):
            try:
                raw = json.loads(_post(mirror, {"data": query}))
                tags = raw["elements"][0]["tags"]
                return {
                    "ok": True,
                    "mirror_used": mirror,
                    "attempts": attempts + [f"{mirror} -> OK"],
                    "total_features": int(tags["total"]),
                    "nodes": int(tags["nodes"]),
                    "ways": int(tags["ways"]),
                    "osm_base_timestamp": raw["osm3s"]["timestamp_osm_base"],
                    "note": "ODbL. Crowd-sourced: completeness varies by area and must be "
                    "disclosed. Public instances return 504 under load — mirrors and "
                    "retries are mandatory, not defensive.",
                }
            except Exception as e:  # noqa: BLE001 - try the next mirror
                attempts.append(f"{mirror} -> {type(e).__name__}: {e}")
                time.sleep(2 + 3 * attempt)

    return {"ok": False, "attempts": attempts, "note": "all Overpass mirrors failed"}


def probe_open_meteo() -> dict[str, Any]:
    q = urllib.parse.urlencode(
        {
            "latitude": LAT,
            "longitude": LON,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "daily": "precipitation_sum",
            "timezone": "Asia/Kolkata",
        }
    )
    d = json.loads(_get(f"https://archive-api.open-meteo.com/v1/archive?{q}"))
    series = [v for v in d["daily"]["precipitation_sum"] if v is not None]
    # ERA5 snaps to its own ~9km grid. The offset is a real limitation, so measure it.
    drift_km = (
        ((d["latitude"] - LAT) ** 2 + (d["longitude"] - LON) ** 2) ** 0.5
    ) * 111.0
    return {
        "ok": True,
        "requested": [LAT, LON],
        "grid_centroid": [d["latitude"], d["longitude"]],
        "grid_drift_km": round(drift_km, 2),
        "model_elevation_m": d.get("elevation"),
        "days_returned": len(series),
        "annual_precip_mm_2024": round(sum(series), 1),
        "note": "ERA5 reanalysis on a ~9km grid. Free for non-commercial use. "
        "The drift above is why the UI must show the grid point, not the site point.",
    }


def probe_elevation() -> dict[str, Any]:
    locs = f"{LAT},{LON}|{LAT + 0.004},{LON + 0.002}"
    d = json.loads(_get(f"https://api.opentopodata.org/v1/srtm30m?locations={locs}"))
    elevations = [r["elevation"] for r in d["results"]]
    return {
        "ok": True,
        "elevations_m": elevations,
        "local_relief_m": round(max(elevations) - min(elevations), 1),
        "note": "SRTM 30m. 1000 calls/day, 100 locations/call. "
        "30m postings cannot resolve plot-level grade.",
    }


def probe_missing_sources() -> dict[str, Any]:
    """Confirm the negative findings still hold.

    These are the sources a real decision needs and that I could not find as an API.
    Recording them as a probe keeps the claim honest: if one of these ever gains an
    endpoint, this list is what should be revisited.
    """
    checked = {}
    for name, url in {
        "data.gov.in": "https://www.data.gov.in/",
        "bhuvan (ISRO)": "https://bhuvan-app1.nrsc.gov.in/",
    }.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
            with urllib.request.urlopen(req, timeout=25) as r:
                checked[name] = f"HTTP {r.status} — portal reachable"
        except urllib.error.HTTPError as e:
            checked[name] = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001 - probe should never abort the run
            checked[name] = f"unreachable: {type(e).__name__}"

    return {
        "ok": True,
        "portals_reachable": checked,
        "no_parcel_level_api_found_for": [
            "zoning / land-use class per parcel",
            "FAR, setbacks, coverage per plot",
            "valley-zone / eco-sensitive overlay",
            "official flood hazard layer (Bengaluru)",
            "parcel geometry / ownership",
        ],
        "note": "Portals exist; neither exposes a parcel-level zoning endpoint. "
        "This is the finding that pushes the product toward the document layer.",
    }


PROBES: dict[str, Callable[[], dict[str, Any]]] = {
    "nominatim_geocoding": probe_nominatim,
    "overpass_osm": probe_overpass,
    "open_meteo_archive": probe_open_meteo,
    "opentopodata_srtm": probe_elevation,
    "absent_structured_sources": probe_missing_sources,
}


def main() -> int:
    results: dict[str, Any] = {"probed_at": date.today().isoformat(), "site": [LAT, LON]}
    failures = 0

    for name, fn in PROBES.items():
        try:
            results[name] = fn()
            status = "OK" if results[name].get("ok") else "SOFT-FAIL"
        except Exception as e:  # noqa: BLE001 - one dead source must not kill the run
            results[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            status = "FAIL"
            failures += 1
        print(f"  [{status:9s}] {name}")
        time.sleep(1.1)  # Nominatim's rate limit is the strictest; respect it globally.

    out = Path(__file__).parent / f"results-{results['probed_at']}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    print(f"{len(PROBES) - failures}/{len(PROBES)} probes succeeded.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
