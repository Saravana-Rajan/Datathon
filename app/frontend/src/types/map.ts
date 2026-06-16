/**
 * Map domain types for KSP Saathi.
 *
 * These types describe the markers, hotspots, and stations that the MapPanel
 * renders on top of Google Maps. They are produced by the backend (Catalyst
 * Functions) in response to chat queries and pushed into the Zustand store.
 */

export type CrimeMarker = {
  fir_no: string;
  lat: number;
  lng: number;
  crime_type: string;
  /** ISO 8601 date string (e.g. "2026-04-12") */
  date: string;
  summary: string;
  summary_kn: string;
};

export type Hotspot = {
  /** [lat, lng] cluster centroid */
  center: [number, number];
  /** Normalized density 0..1 (1 = highest) */
  density: number;
  /** Raw incident count inside the cluster */
  count: number;
  /** SW / NE corners of the cluster bounding box: [[swLat, swLng], [neLat, neLng]] */
  bounds: [[number, number], [number, number]];
};

export type Station = {
  name: string;
  lat: number;
  lng: number;
  jurisdiction: string;
};

/** Visual layer flags driven by the layer toggle UI. */
export type MapLayerKey = "incidents" | "hotspots" | "stations" | "heatmap";

export type MapLayers = Record<MapLayerKey, boolean>;

/**
 * Aggregated payload the backend pushes to the Zustand store after a query.
 * MapPanel reads from this shape via `useKspStore((s) => s.mapMarkers)`.
 */
export type MapPayload = {
  incidents: CrimeMarker[];
  hotspots: Hotspot[];
  stations: Station[];
  /** Optional ISO date window [start, end] hinted by the query */
  dateRange?: [string, string];
};
