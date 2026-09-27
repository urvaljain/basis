"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { MapFeature } from "@/lib/types";

/**
 * The map, as an evidence surface rather than a decoration.
 *
 * Every marker is a real OpenStreetMap element with a resolvable id, and clicking one
 * answers four questions: what is this, how far, why it matters here, and where it came
 * from — with a link out to the element on openstreetmap.org so the reader can see who
 * contributed it and when.
 *
 * Water and watercourses are given their own emphasis because they are the features the
 * governing regulation turns on. Distances shown are straight-line to a feature's
 * representative point, which is stated on the card rather than implied, because it is not
 * the measurement the regulation uses.
 *
 * MapLibre is loaded lazily and the component degrades to a readable list if tiles cannot
 * be fetched. A map that fails should cost the reader the picture, not the evidence.
 */

/**
 * A raster basemap that needs no API key and no account.
 *
 * Two earlier choices failed, and both failed quietly enough to be worth recording:
 *
 * - **MapLibre demotiles** carry only low-zoom country outlines, so at the city zoom this
 *   product works at, the map rendered as a flat block of colour.
 * - **CARTO dark** returns HTTP 200 for every tile request — and at this zoom the body is a
 *   2.5 KB "API KEY REQUIRED" watermark. A status-code check would have called it healthy;
 *   only comparing response sizes against a known-good provider showed it was not.
 *
 * Esri's Dark Gray Canvas is detailed at street level, free for non-commercial use with
 * attribution, needs no key, and its palette already suits this interface — markers stay
 * legible without fighting the tiles.
 *
 * Key-free is a demo-reliability decision as much as a cost one: an expired or rate-limited
 * token is one more thing that can fail in front of an audience.
 */
const BASEMAP_STYLE = {
  version: 8 as const,
  sources: {
    basemap: {
      type: "raster" as const,
      tiles: [
        "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 16,
      attribution: "Esri, HERE, Garmin, © OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "background", type: "background" as const, paint: { "background-color": "#0a0c0f" } },
    { id: "basemap", type: "raster" as const, source: "basemap" },
  ],
};

const CATEGORY_STYLE: Record<string, { colour: string; label: string; why: string }> = {
  water: {
    colour: "#4aa3e8",
    label: "Water body",
    why: "RMP 2031 §6.5.3 imposes a 75 m no-development buffer around water bodies.",
  },
  stream: {
    colour: "#5bc8d8",
    label: "Watercourse",
    why: "Primary/secondary/tertiary drains carry 50/35/25 m buffers under the NGT Order.",
  },
  rail_station: {
    colour: "#a78bfa",
    label: "Rail station",
    why: "Proximity is a proxy for transit access; it does not establish connectivity.",
  },
  major_road: {
    colour: "#e8ebef",
    label: "Major road",
    why: "Road width determines permissible FAR bands in the zoning tables.",
  },
  hospital: { colour: "#e8734a", label: "Hospital", why: "Emergency access context." },
  school: { colour: "#e0a63c", label: "School", why: "Neighbourhood amenity context." },
  park: { colour: "#4fc1a6", label: "Park", why: "Open space context." },
  bus_stop: { colour: "#9aa4b2", label: "Bus stop", why: "Local transit context." },
};

export function SiteMap({
  latitude,
  longitude,
  features,
  label,
}: {
  latitude: number | null;
  longitude: number | null;
  features: MapFeature[];
  label: string | null;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<MapFeature | null>(null);
  const [mapFailed, setMapFailed] = useState(false);
  const [ready, setReady] = useState(false);

  const categories = useMemo(() => {
    const seen = new Map<string, number>();
    for (const f of features) seen.set(f.category, (seen.get(f.category) ?? 0) + 1);
    return [...seen.entries()].sort((a, b) => b[1] - a[1]);
  }, [features]);

  useEffect(() => {
    if (!container.current || latitude == null || longitude == null) return;

    let map: import("maplibre-gl").Map | null = null;
    let cancelled = false;

    (async () => {
      try {
        const maplibre = await import("maplibre-gl");
        if (cancelled || !container.current) return;

        map = new maplibre.Map({
          container: container.current,
          style: BASEMAP_STYLE,
          center: [longitude, latitude],
          zoom: 13.5,
          attributionControl: false,
        });

        map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
        map.addControl(
          new maplibre.AttributionControl({
            compact: true,
            customAttribution: "© OpenStreetMap contributors",
          }),
        );

        map.on("load", () => {
          if (cancelled || !map) return;
          setReady(true);

          const siteMarker = document.createElement("div");
          siteMarker.style.cssText =
            "width:14px;height:14px;border-radius:50%;background:#6aa6ff;border:3px solid #0a0c0f;box-shadow:0 0 0 2px #6aa6ff";
          new maplibre.Marker({ element: siteMarker })
            .setLngLat([longitude, latitude])
            .addTo(map);

          for (const feature of features) {
            const style = CATEGORY_STYLE[feature.category];
            if (!style) continue;
            const el = document.createElement("button");
            el.setAttribute("aria-label", feature.label);
            el.style.cssText = `width:9px;height:9px;border-radius:50%;background:${style.colour};border:1.5px solid rgba(10,12,15,.85);cursor:pointer;padding:0`;
            el.addEventListener("click", (e) => {
              e.stopPropagation();
              setSelected(feature);
            });
            new maplibre.Marker({ element: el })
              .setLngLat([feature.longitude, feature.latitude])
              .addTo(map!);
          }
        });

        map.on("error", () => setMapFailed(true));
      } catch {
        setMapFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [latitude, longitude, features]);

  if (latitude == null || longitude == null) return null;

  return (
    <div className="panel overflow-hidden">
      <div className="panel-header">
        <h2 className="m-0 text-[13px] font-semibold text-ink">Site context</h2>
        <span className="mono text-[10.5px] text-ink-4">
          {latitude.toFixed(5)}, {longitude.toFixed(5)}
        </span>
      </div>

      {!mapFailed ? (
        <div className="relative isolate overflow-hidden">
          <div ref={container} className="h-[260px] w-full bg-raised" />
          {!ready && (
            <div className="absolute inset-0 flex items-center justify-center bg-raised">
              <span className="mono text-[11px] text-ink-4">loading basemap…</span>
            </div>
          )}
        </div>
      ) : (
        <div className="border-b border-line bg-raised px-3 py-2.5">
          <p className="m-0 text-[12px] leading-relaxed text-ink-3">
            The basemap could not be loaded. The mapped features are listed below — the
            evidence does not depend on the picture.
          </p>
        </div>
      )}

      {selected ? (
        <div className="border-t border-line p-3.5">
          <div className="mb-1.5 flex items-center gap-2">
            <span
              aria-hidden
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: CATEGORY_STYLE[selected.category]?.colour ?? "#9aa4b2" }}
            />
            <span className="label">
              {CATEGORY_STYLE[selected.category]?.label ?? selected.category}
            </span>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="mono ml-auto text-[11px] text-ink-4 hover:text-ink-2"
            >
              close
            </button>
          </div>

          <p className="m-0 text-[13px] font-medium text-ink">{selected.label}</p>
          <p className="m-0 mt-0.5 text-[12px] text-ink-3">
            <span className="mono">{selected.distance_m.toFixed(0)} m</span> straight-line
            from the site point — not travel distance, and not the distance from a plot
            boundary to a feature edge.
          </p>

          <p className="m-0 mt-2 text-[12px] leading-relaxed text-ink-2">
            <span className="label">Why it matters</span>{" "}
            {CATEGORY_STYLE[selected.category]?.why}
          </p>

          <a
            href={selected.osm_url}
            target="_blank"
            rel="noreferrer"
            className="mono mt-2 inline-block text-[11px] text-inference no-underline hover:underline"
          >
            {selected.osm_type}/{selected.osm_id} on OpenStreetMap ↗
          </a>
        </div>
      ) : (
        <div className="border-t border-line p-3">
          <p className="label mb-2">
            {features.length} mapped features — click any marker
          </p>
          <ul className="m-0 flex list-none flex-wrap gap-x-3 gap-y-1 p-0">
            {categories.map(([category, count]) => (
              <li key={category} className="flex items-center gap-1.5 text-[11.5px] text-ink-3">
                <span
                  aria-hidden
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: CATEGORY_STYLE[category]?.colour ?? "#9aa4b2" }}
                />
                {CATEGORY_STYLE[category]?.label ?? category}
                <span className="mono text-ink-4">{count}</span>
              </li>
            ))}
          </ul>
          <p className="m-0 mt-2.5 text-[11px] leading-relaxed text-ink-4">
            OpenStreetMap is crowd-sourced. These are the features that have been{" "}
            <em>mapped</em> near this point, not everything that exists.
          </p>
        </div>
      )}
    </div>
  );
}
