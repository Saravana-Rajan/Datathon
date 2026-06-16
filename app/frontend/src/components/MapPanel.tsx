"use client";

/**
 * MapPanel — KSP Saathi's Google Maps surface.
 *
 * Responsibilities:
 *   • Render incidents, hotspot clusters, police stations on Google Maps.
 *   • React to chat-driven store updates: when the backend pushes new
 *     `crimeMarkers` / `hotspots` / `stations`, the camera animates to the
 *     bounding box of the new data set.
 *   • Let the user click a marker to inspect a FIR summary and pin it as
 *     additional chat context.
 *   • Toggle layers (incidents / hotspots / stations / heatmap).
 *   • Scrub through time with the DateRangeSlider — affects marker visibility.
 *
 * Tech choices:
 *   • `@vis.gl/react-google-maps` for the declarative wrapper. We load the
 *     `visualization` library too so HeatmapLayer works.
 *   • Imperative side-effect components (HotspotLayer, HeatmapLayer) hang
 *     off the map context — they own their own Google Maps objects and clean
 *     up on unmount.
 *
 * Auth: reads `NEXT_PUBLIC_GOOGLE_MAPS_KEY`. When the env var is missing we
 * render a clear instructional placeholder rather than silently breaking.
 */

import * as React from "react";
import {
  APIProvider,
  Map,
  AdvancedMarker,
  InfoWindow,
  useMap,
} from "@vis.gl/react-google-maps";
import { Loader2, Layers, MapPin, Shield, Flame, Activity } from "lucide-react";

import { useKspStore } from "@/lib/store";
import type { CrimeMarker, MapLayerKey } from "@/types/map";
import {
  BENGALURU_CENTER,
  DEFAULT_ZOOM,
  boundsFromMarkers,
  colorForCrimeType,
  isWithinRange,
  naturalDateRange,
} from "@/lib/map-utils";

import HotspotLayer from "./HotspotLayer";
import HeatmapLayer from "./HeatmapLayer";
import DateRangeSlider from "./DateRangeSlider";

/* ────────────────────────────────────────────────────────────────────────── */
/*  Camera animator — listens for marker payload changes and flies to bounds  */
/* ────────────────────────────────────────────────────────────────────────── */

interface CameraAnimatorProps {
  bbox: { south: number; west: number; north: number; east: number } | null;
}

/**
 * Smooth `panTo` then `fitBounds`. `fitBounds` alone is instantaneous; chaining
 * after a brief `panTo` gives the eye-pleasing "fly" feel without animation
 * libraries. Idle-listener defers the fit so it doesn't fight a user gesture.
 */
function CameraAnimator({ bbox }: CameraAnimatorProps): null {
  const map = useMap();
  const lastSignature = React.useRef<string>("");

  React.useEffect(() => {
    if (!map || !bbox) return;
    const sig = `${bbox.south.toFixed(4)},${bbox.west.toFixed(4)},${bbox.north.toFixed(4)},${bbox.east.toFixed(4)}`;
    if (sig === lastSignature.current) return;
    lastSignature.current = sig;

    const center = {
      lat: (bbox.south + bbox.north) / 2,
      lng: (bbox.west + bbox.east) / 2,
    };
    map.panTo(center);

    // Defer fitBounds a tick so the pan animation registers first.
    const t = window.setTimeout(() => {
      const bounds = new google.maps.LatLngBounds(
        { lat: bbox.south, lng: bbox.west },
        { lat: bbox.north, lng: bbox.east }
      );
      map.fitBounds(bounds, 64);
    }, 200);
    return () => window.clearTimeout(t);
  }, [map, bbox]);

  return null;
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  Layer toggle UI                                                            */
/* ────────────────────────────────────────────────────────────────────────── */

interface LayerToggleProps {
  layers: Record<MapLayerKey, boolean>;
  onToggle: (key: MapLayerKey) => void;
}

const LAYER_META: Record<
  MapLayerKey,
  { label: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  incidents: { label: "Incidents", Icon: MapPin },
  hotspots: { label: "Hotspots", Icon: Flame },
  stations: { label: "Stations", Icon: Shield },
  heatmap: { label: "Heatmap", Icon: Activity },
};

function LayerToggle({ layers, onToggle }: LayerToggleProps): React.ReactElement {
  return (
    <div
      className="pointer-events-auto flex flex-wrap items-center gap-1 rounded-md border bg-background/95 p-1 shadow-sm backdrop-blur"
      role="group"
      aria-label="Map layers"
    >
      <Layers
        className="ml-1 h-3.5 w-3.5 text-muted-foreground"
        aria-hidden="true"
      />
      {(Object.keys(LAYER_META) as MapLayerKey[]).map((key) => {
        const { label, Icon } = LAYER_META[key];
        const active = layers[key];
        return (
          <button
            key={key}
            type="button"
            onClick={() => onToggle(key)}
            aria-pressed={active}
            className={
              "inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors " +
              (active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground")
            }
          >
            <Icon className="h-3 w-3" aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  MapPanel                                                                   */
/* ────────────────────────────────────────────────────────────────────────── */

const VISUALIZATION_LIB: ("visualization" | "places" | "geometry" | "drawing" | "marker")[] = [
  "visualization",
  "marker",
];

export function MapPanel(): React.ReactElement {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY;

  // Subscribe to the slices we actually use — Zustand bails out on equality.
  const crimeMarkers = useKspStore((s) => s.crimeMarkers);
  const hotspots = useKspStore((s) => s.hotspots);
  const stations = useKspStore((s) => s.stations);
  const layers = useKspStore((s) => s.mapLayers);
  const setMapLayers = useKspStore((s) => s.setMapLayers);
  const dateRange = useKspStore((s) => s.mapDateRange);
  const setDateRange = useKspStore((s) => s.setMapDateRange);
  const loading = useKspStore((s) => s.mapLoading);
  const language = useKspStore((s) => s.language);
  const addContext = useKspStore((s) => s.addMapContextSelection);

  // Selected marker for InfoWindow — local UI state, doesn't belong in store.
  const [selected, setSelected] = React.useState<CrimeMarker | null>(null);

  // Natural date window from the data (used when backend doesn't supply one).
  const natural = React.useMemo(
    () => naturalDateRange(crimeMarkers),
    [crimeMarkers]
  );

  // Apply the active date filter to incident visibility.
  const activeRange = React.useMemo(() => {
    if (dateRange) return { start: dateRange[0], end: dateRange[1] };
    if (natural) return natural;
    return undefined;
  }, [dateRange, natural]);

  const visibleIncidents = React.useMemo(
    () => crimeMarkers.filter((m) => isWithinRange(m.date, activeRange)),
    [crimeMarkers, activeRange]
  );

  // Compute bounding box from the *visible* incident set + hotspots + stations
  // so the camera animates as the user scrubs time too.
  const bbox = React.useMemo(
    () =>
      boundsFromMarkers({
        incidents: visibleIncidents,
        hotspots: layers.hotspots ? hotspots : [],
        stations: layers.stations ? stations : [],
      }),
    [visibleIncidents, hotspots, stations, layers.hotspots, layers.stations]
  );

  const toggleLayer = React.useCallback(
    (key: MapLayerKey) => setMapLayers({ [key]: !layers[key] }),
    [layers, setMapLayers]
  );

  /* ── Missing API key — clear, actionable fallback ────────────────────── */
  if (!apiKey) {
    return (
      <div
        className="flex h-full w-full flex-col items-center justify-center gap-2 rounded-md border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground"
        role="status"
      >
        <MapPin className="h-5 w-5" aria-hidden="true" />
        <p className="font-medium text-foreground">
          Google Maps key missing
        </p>
        <p className="max-w-sm text-xs">
          Set <code className="rounded bg-muted px-1 py-0.5 font-mono">NEXT_PUBLIC_GOOGLE_MAPS_KEY</code>{" "}
          in your environment to enable the hotspot map.
        </p>
      </div>
    );
  }

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden rounded-md border">
      <APIProvider apiKey={apiKey} libraries={VISUALIZATION_LIB}>
        <div className="relative flex-1">
          <Map
            mapId="ksp-saathi-map"
            defaultCenter={BENGALURU_CENTER}
            defaultZoom={DEFAULT_ZOOM}
            gestureHandling="greedy"
            disableDefaultUI={false}
            clickableIcons={false}
            className="absolute inset-0"
            aria-label="Crime hotspot map for Karnataka"
          >
            {/* Incident markers — each FIR is a small dot, click → InfoWindow */}
            {layers.incidents &&
              visibleIncidents.map((m) => (
                <AdvancedMarker
                  key={m.fir_no}
                  position={{ lat: m.lat, lng: m.lng }}
                  onClick={() => setSelected(m)}
                  title={m.crime_type}
                >
                  <span
                    aria-label={`${m.crime_type} incident ${m.fir_no}`}
                    style={{
                      display: "inline-block",
                      width: 12,
                      height: 12,
                      borderRadius: 9999,
                      backgroundColor: colorForCrimeType(m.crime_type),
                      boxShadow: "0 0 0 2px white",
                    }}
                  />
                </AdvancedMarker>
              ))}

            {/* Station markers — blue shield icons */}
            {layers.stations &&
              stations.map((s) => (
                <AdvancedMarker
                  key={`${s.name}-${s.lat},${s.lng}`}
                  position={{ lat: s.lat, lng: s.lng }}
                  title={`${s.name} • ${s.jurisdiction}`}
                >
                  <span
                    aria-label={`Police station ${s.name}`}
                    className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-white bg-blue-700 text-white shadow"
                  >
                    <Shield className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                </AdvancedMarker>
              ))}

            {/* InfoWindow for the active incident */}
            {selected && (
              <InfoWindow
                position={{ lat: selected.lat, lng: selected.lng }}
                onCloseClick={() => setSelected(null)}
                pixelOffset={[0, -10]}
              >
                <div className="max-w-[280px] space-y-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium text-white"
                      style={{
                        backgroundColor: colorForCrimeType(selected.crime_type),
                      }}
                    >
                      {selected.crime_type}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {selected.date}
                    </span>
                  </div>
                  <div className="font-mono text-[10px] text-muted-foreground">
                    FIR {selected.fir_no}
                  </div>
                  <p className="leading-snug text-foreground">
                    {language === "kn" && selected.summary_kn
                      ? selected.summary_kn
                      : selected.summary}
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      addContext(selected);
                      setSelected(null);
                    }}
                    className="inline-flex w-full items-center justify-center rounded border border-primary px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary hover:text-primary-foreground"
                  >
                    Add to chat context
                  </button>
                </div>
              </InfoWindow>
            )}

            {/* Imperative side-effect overlays */}
            <HotspotLayer hotspots={hotspots} visible={layers.hotspots} />
            <HeatmapLayer
              incidents={visibleIncidents}
              visible={layers.heatmap}
            />
            <CameraAnimator bbox={bbox} />
          </Map>

          {/* Top-left layer toggle */}
          <div className="pointer-events-none absolute left-3 top-3 z-10">
            <LayerToggle layers={layers} onToggle={toggleLayer} />
          </div>

          {/* Loading veil */}
          {loading && (
            <div
              className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-background/40 backdrop-blur-[1px]"
              role="status"
              aria-live="polite"
            >
              <div className="flex items-center gap-2 rounded-md border bg-background px-3 py-1.5 text-xs shadow">
                <Loader2
                  className="h-3.5 w-3.5 animate-spin text-primary"
                  aria-hidden="true"
                />
                Loading map data…
              </div>
            </div>
          )}

          {/* Empty state — only when not loading and we truly have nothing */}
          {!loading &&
            crimeMarkers.length === 0 &&
            hotspots.length === 0 &&
            stations.length === 0 && (
              <div className="pointer-events-none absolute inset-x-3 bottom-20 z-10 rounded-md border bg-background/95 p-2 text-center text-[11px] text-muted-foreground shadow-sm">
                Ask a question in chat to populate hotspots — e.g. {""}
                <span className="font-mono">
                  &ldquo;chain snatching near Indiranagar last 30 days&rdquo;
                </span>
                .
              </div>
            )}
        </div>

        {/* Time scrubber */}
        {natural && (
          <div className="border-t bg-background px-3 py-2">
            <DateRangeSlider
              min={natural.start}
              max={natural.end}
              value={activeRange ? [activeRange.start, activeRange.end] : [natural.start, natural.end]}
              onChange={(next) => setDateRange(next)}
            />
          </div>
        )}
      </APIProvider>
    </div>
  );
}

export default MapPanel;
