# 10 — Data Sources

Every source below was called directly before being written into this document. The probes
are reproducible: `python data/probes/probe_sources.py` regenerates
`data/probes/results-<date>.json`. Current run: **5/5 pass**.

Nothing here is listed as available because a vendor's marketing page said so.

---

## Principle

> If a source cannot be reliably accessed, the product says "data unavailable" and explains
> what it checked. It does not substitute a plausible value.

This is the reason the site workspace has an empty Constraints panel rather than a populated
one. See `08-non-goals.md` §8.

---

## Available — verified working

### Nominatim (geocoding)

| | |
|---|---|
| **Provides** | Place name / address → coordinates, administrative hierarchy, bounding box |
| **Endpoint** | `https://nominatim.openstreetmap.org/search` |
| **Coverage** | Global; good in urban India for suburb and locality level |
| **Freshness** | Continuous (OSM) |
| **Licence** | ODbL — attribution required |
| **Limits** | **1 request/second**, User-Agent mandatory |
| **Verified** | `Bellandur, Bengaluru` → 12.9320495, 77.6842915, with full admin chain and bbox |

**Limitations surfaced in the product:** geocoding a suburb returns a *centroid*, not a plot.
Where a query is ambiguous the product shows the candidates rather than silently picking the
top result — an address resolved to the wrong plot invalidates every downstream measurement,
and that failure is invisible to the user unless the interface makes it visible.

### Overpass / OpenStreetMap (spatial features)

| | |
|---|---|
| **Provides** | Transit stations, bus stops, road classification, water bodies, amenities |
| **Endpoint** | `https://overpass-api.de/api/interpreter` + mirrors |
| **Coverage** | Global, but **completeness varies by area and contributor activity** |
| **Freshness** | Minutes — probe returned `timestamp_osm_base: 2026-09-27T09:37:51Z` |
| **Licence** | ODbL |
| **Limits** | Rejects requests with no User-Agent (**HTTP 406**); public instances throttle |
| **Verified** | 59 features within the query radii at the reference site (11 nodes, 48 ways) |

**Reliability finding:** the first scripted run returned **HTTP 504 Gateway Timeout**. This
is normal for public Overpass instances under load. The client therefore implements mirror
fallback (`overpass-api.de` → `kumi.systems` → `private.coffee`) with backoff, and the probe
models the same behaviour rather than pretending one endpoint is dependable.

**Limitations surfaced in the product:** OSM is crowd-sourced. A feature count is *what was
found*, never *what exists*. The product states this wherever counts are displayed, because
"0 hospitals nearby" and "no hospital data contributed nearby" mean very different things to
someone making a decision.

### Open-Meteo Archive (ERA5 reanalysis)

| | |
|---|---|
| **Provides** | Daily historical climate — precipitation, temperature, wind |
| **Endpoint** | `https://archive-api.open-meteo.com/v1/archive` |
| **Coverage** | Global, 1940→present |
| **Freshness** | ~5-day lag |
| **Licence** | Free for non-commercial use; ERA5 is Copernicus |
| **Limits** | No key required; fair-use rate limits |
| **Verified** | 366 days of 2024 precipitation at the reference site → **1,009.9 mm** annual |

**The limitation that must never be hidden:** ERA5 is a ~9 km reanalysis grid. It does not
return data *for your point* — it returns data for its nearest grid cell. At the reference
site the returned centroid (12.8998, 77.6567) is **4.71 km** from the requested point, with a
model elevation of 875 m against a measured 881 m.

For a city where flooding is intensely local, a 4.71 km offset can mean the difference
between a catchment and a ridge. The product displays the grid point alongside the site
point, always. Reporting a 9 km-resolution number as a site measurement would be a
fabrication in everything but intent.

### OpenTopoData / SRTM (elevation)

| | |
|---|---|
| **Provides** | Ground elevation from SRTM 30 m |
| **Endpoint** | `https://api.opentopodata.org/v1/srtm30m` |
| **Coverage** | 60°N–56°S |
| **Freshness** | Static (SRTM, 2000 mission) |
| **Licence** | Public domain (NASA/USGS) |
| **Limits** | 1,000 calls/day, 100 locations/call |
| **Verified** | 881 m and 880 m at two points ~490 m apart |

**Limitations surfaced in the product:** 30 m postings cannot resolve plot-level grade, and
SRTM measures a surface that includes vegetation and buildings in places. Useful for
catchment context; useless for a cut-and-fill estimate, and the product does not imply
otherwise.

---

## Unavailable — checked, and absent

This table is the most important one in the document, because it is why the product exists
in the shape it does.

| What a decision needs | Status | What was checked |
|---|---|---|
| Zoning / land-use class per parcel | ❌ No API | `data.gov.in` (HTTP 200), Bhuvan/NRSC (HTTP 302); RMP 2031 land use is maps + prose |
| FAR / setbacks / coverage per plot | ❌ No API | Published as dimensional matrices inside PDFs |
| Valley-zone & eco-sensitive overlay | ❌ No API | "Marked on the proposed land use plans" — i.e. drawings |
| Official flood hazard layer (Bengaluru) | ❌ None found open | — |
| Parcel geometry / ownership | ❌ Not open | Requires revenue records |
| Lake extent (for buffer measurement) | ❌ Not open | RMP 2031 defines it "as per revenue records" |

**[Unverified: whether a paid or partner API closes any of these gaps. None found in open
research.]**

The last row deserves emphasis. RMP 2031 §6.5.3 makes the 75 m no-development buffer
measurable *from the lake boundary as per revenue records*. Those records are not open data.
So even with the clause correctly retrieved and quoted, **the system cannot tell a user
whether their plot is inside the buffer.** The honest output is the clause, the measurement
rule, and a verification task naming who holds the answer — not a determination.

---

## The document layer — where the constraints actually live

Because the structured sources above stop exactly where the decision starts, the governing
constraint layer is a document.

### Primary corpus

**Revised Master Plan for Bengaluru 2031 (Draft), Volume 6 — Zoning Regulations**
Bangalore Development Authority.
Source: [OpenCity CKAN](https://data.opencity.in/dataset/bda-revised-master-plan-2031) ·
[direct PDF](https://data-opencity.sgp1.cdn.digitaloceanspaces.com/Documents/Recent/Bengaluru-BDA-RMP-2031-Volume_6_Zoning_Regulations.pdf)
SHA-256 `d00fcc58faccb15075ed448e9290ffe32a908dd74e8ef41a10129756563f9ae8`

Measured by the ingestion pipeline, not estimated:

| Property | Value |
|---|---|
| Pages | 206 |
| Readable pages | 152 (**73.8% text coverage**) |
| Unreadable pages | 54 |
| Characters after repair | 336,452 |
| Character substitutions | 542 across 37 pages |
| Quality breakdown | 115 clean · 16 repaired · 21 heavily repaired · 54 unreadable · 0 residual |
| Citable chunks | 1,004 |
| Structurally damaged tables | 6 (all FAR / Ground Coverage) |

**Status: draft.** It is a draft master plan, and the product says so at every export.

### Three failure modes, and whether the system can tell

| Mode | Extent | Detectable? | Product behaviour |
|---|---|---|---|
| **Unreadable pages** | 54 pages, incl. pp. 106–128 (TDR Rules 2016, 23 pp) and pp. 173–190 (heritage annexure, 18 pp) | ✅ Yes | Indexed as searchable blind regions; rendered as page images |
| **Encoding corruption** | 542 substitutions, incl. digits (`75 m` → `7ϱ ŵ`) | ✅ Yes | Repaired; raw retained; quotes labelled reconstructed |
| **Flattened tables** | 6 FAR tables | ⚠️ **Only heuristically** | Column-binding ambiguity flagged on every citation from them |

The third is the dangerous one: those pages classify as *readable and clean*, and every
coverage metric reports success while the column structure that made the numbers meaningful
is gone. See `research.md` §5 and `backend/app/ingest/table_risk.py`.

### User uploads

Any PDF, processed by the identical pipeline — same repair, same page-quality classification,
same table-risk detection, same passage-level citation. A user's own planning report gets the
same honesty treatment as the corpus, because the failure modes are properties of PDFs, not
of this one document.

Uploads are session-scoped and deletable. No authentication in the MVP (`08-non-goals.md`
§10), so confidentiality is explicitly *not* yet solved — stated plainly rather than implied.

---

## Abstraction

Providers sit behind a single interface (`backend/app/providers/base.py`) supplying retries,
mirror fallback, caching and a uniform `limitation` field that travels with every value into
the epistemic layer as `DatasetLocator.limitation`.

The point of the abstraction is not swappability for its own sake. It is that **a provider
cannot return a value without also returning what is wrong with it**, and nothing downstream
is able to strip that away before it reaches the user.

Adding a jurisdiction means implementing providers and ingesting a corpus. It does not mean
touching the agents, the epistemic model or the interface.
