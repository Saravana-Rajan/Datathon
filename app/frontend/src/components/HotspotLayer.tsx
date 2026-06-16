"use client";

/**
 * HotspotLayer — renders DBSCAN/H3 clusters as filled circular polygons on
 * top of Google Maps. Density (0..1) maps to a green→red colour ramp; opacity
 * grows with density so the most-active cells punch through.
 *
 * Each cluster is rendered as a `google.maps.Circle` because:
 *   1. The store ships a centroid + bounding box only — we don't have the H3
 *      hex vertices yet. Circles approximate the cluster footprint cheaply.
 *   2. Native Circle objects respond to map zoom without the React-side
 *      re-projection that polygons would need.
 *
 * Lifecycle: on every change of `hotspots` we tear down the previous Circle
 * instances and create fresh ones. This is O(n) in cluster count and fine for
 * the hundreds-of-clusters scale we expect from KSP queries.
 */

import * as React from "react";
import { useMap } from "@vis.gl/react-google-maps";
import type { Hotspot } from "@/types/map";

interface HotspotLayerProps {
  hotspots: Hotspot[];
  /** Toggle visibility without destroying the layer. */
  visible: boolean;
  /** Fires when a hotspot is clicked — caller decides what to show. */
  onHotspotClick?: (h: Hotspot) => void;
}

/**
 * Green (low density) → yellow (mid) → red (high) ramp. Density is clamped
 * to [0, 1] to guard against malformed backend payloads.
 */
function densityColor(density: number): string {
  const d = Math.max(0, Math.min(1, density));
  // Interpolate hue 120° (green) → 0° (red).
  const hue = 120 * (1 - d);
  return `hsl(${hue.toFixed(0)}, 75%, 45%)`;
}

/**
 * Pick a radius (metres) from the bounding box diagonal. Falls back to a
 * sensible 500 m if bounds are missing/degenerate so a cluster never renders
 * as an invisible zero-radius circle.
 */
function radiusMetres(h: Hotspot): number {
  const [[swLat, swLng], [neLat, neLng]] = h.bounds;
  if (
    !Number.isFinite(swLat) ||
    !Number.isFinite(swLng) ||
    !Number.isFinite(neLat) ||
    !Number.isFinite(neLng)
  ) {
    return 500;
  }
  // Rough metres-per-degree at Bengaluru latitude (~13°N).
  const latM = (neLat - swLat) * 111_000;
  const lngM = (neLng - swLng) * 108_000;
  const diag = Math.sqrt(latM * latM + lngM * lngM);
  // Halve the diagonal so the circle inscribes the bounding box.
  return Math.max(150, diag / 2);
}

export function HotspotLayer({
  hotspots,
  visible,
  onHotspotClick,
}: HotspotLayerProps): React.ReactElement | null {
  const map = useMap();
  const circlesRef = React.useRef<google.maps.Circle[]>([]);
  const listenersRef = React.useRef<google.maps.MapsEventListener[]>([]);

  React.useEffect(() => {
    if (!map) return;

    // Tear down previous circles + listeners before drawing the new set.
    for (const l of listenersRef.current) l.remove();
    listenersRef.current = [];
    for (const c of circlesRef.current) c.setMap(null);
    circlesRef.current = [];

    if (!visible || hotspots.length === 0) return;

    for (const h of hotspots) {
      const color = densityColor(h.density);
      const circle = new google.maps.Circle({
        map,
        center: { lat: h.center[0], lng: h.center[1] },
        radius: radiusMetres(h),
        fillColor: color,
        fillOpacity: 0.15 + 0.45 * Math.max(0, Math.min(1, h.density)),
        strokeColor: color,
        strokeOpacity: 0.9,
        strokeWeight: 1.5,
        clickable: Boolean(onHotspotClick),
        zIndex: 5,
      });
      circlesRef.current.push(circle);

      if (onHotspotClick) {
        const l = circle.addListener("click", () => onHotspotClick(h));
        listenersRef.current.push(l);
      }
    }

    return () => {
      for (const l of listenersRef.current) l.remove();
      listenersRef.current = [];
      for (const c of circlesRef.current) c.setMap(null);
      circlesRef.current = [];
    };
  }, [map, hotspots, visible, onHotspotClick]);

  return null; // imperative overlay — no DOM output
}

export default HotspotLayer;
